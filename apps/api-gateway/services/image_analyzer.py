"""
Image Analyzer — Enhanced Deepfake & Manipulation Detection.

Multi-technique forensic analysis pipeline:
  1. ML model inference (video_deepfake_detector.h5)  — 75% weight
  2. Error Level Analysis (ELA)                        ─┐
  3. Frequency domain / DCT artifact analysis          ─┤ 25% heuristic
  4. Texture inconsistency (LBP / variance maps)       ─┤
  5. JPEG ghost / compression fingerprint analysis     ─┘

Returns ai_score and rule_score separately; the scoring engine
applies the 75% AI / 25% rules weighting.
"""
from __future__ import annotations

import io
import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import cv2
import numpy as np

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class ImageAnalysisResult:
    """Raw outputs from the image analyzer (before fusion)."""
    ai_probability: float = 0.5       # P(deepfake) from ML model [0, 1]
    rule_score: float = 0.0           # heuristic risk score       [0, 1]
    confidence: float = 0.0           # model confidence
    features: Dict = field(default_factory=dict)
    flags: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    per_face_scores: List[float] = field(default_factory=list)
    model_available: bool = False
    ela_score: float = 0.0            # Error Level Analysis score [0, 1]
    forensic_signals: List[str] = field(default_factory=list)


class ImageAnalyzer:
    """Stateless analyzer — safe to instantiate once and reuse."""

    def __init__(self):
        from ml.model_loader import ModelLoader
        self._loader = ModelLoader()
        # Load both TensorFlow (.h5) and PyTorch (.pt) versions if available
        from pathlib import Path
        self._tf_model = None
        self._pt_model = None
        try:
            tf_path = Path(settings.video_model_path("h5"))
            if tf_path.is_file():
                self._tf_model = self._loader._try_keras(tf_path)
        except Exception as e:
            logger.debug("TensorFlow video model load failed: %s", e)
        try:
            pt_path = Path(settings.video_model_path("pt"))
            if pt_path.is_file():
                self._pt_model = self._loader._try_torch_full(pt_path)
        except Exception as e:
            logger.debug("PyTorch video model load failed: %s", e)
        # Fallback: if only one model loaded, also expose it via generic attribute
        self._single_model = self._loader.get_video_model()


    def analyze(self, file_path: str) -> ImageAnalysisResult:
        """
        Full multi-technique forensic analysis pipeline for one image file.

        Parameters
        ----------
        file_path : path to a PNG/JPG/JPEG/WEBP/BMP file on disk.

        Returns
        -------
        ImageAnalysisResult with ai_probability, rule_score, forensic signals, etc.
        """
        from utils.image_preprocessing import (
            preprocess_image,
            compute_image_heuristics,
        )
        from ml.video_model import predict_faces_batch, get_model_input_shape

        result = ImageAnalysisResult()

        # ── 1. Preprocess — detect faces, crop, normalize ────────────────
        try:
            face_crops, meta = preprocess_image(file_path)
            result.metadata = meta
        except Exception as e:
            logger.error("Image preprocessing failed: %s", e)
            result.flags.append("preprocessing_error")
            result.rule_score = 0.5
            return result

        # ── 2. ML Inference — deepfake face model ────────────────────────
        # --- Ensemble inference using both TF and PyTorch models (if available) ---
        ensemble_scores: list[float] = []
        target_size = None
        # Try TensorFlow model first
        if self._tf_model is not None:
            try:
                target_size = get_model_input_shape(self._tf_model)
                tf_scores = predict_faces_batch(self._tf_model, face_crops, target_size)
                ensemble_scores.extend(tf_scores)
                logger.debug("TF model produced %d scores", len(tf_scores))
            except Exception as e:
                logger.debug("TF inference failed: %s", e)
        # Try PyTorch model next
        if self._pt_model is not None:
            try:
                if target_size is None:
                    target_size = get_model_input_shape(self._pt_model)
                pt_scores = predict_faces_batch(self._pt_model, face_crops, target_size)
                ensemble_scores.extend(pt_scores)
                logger.debug("PT model produced %d scores", len(pt_scores))
            except Exception as e:
                logger.debug("PT inference failed: %s", e)
        # Fallback to single model if both are None
        if not ensemble_scores and self._single_model is not None:
            try:
                target_size = get_model_input_shape(self._single_model)
                fallback_scores = predict_faces_batch(self._single_model, face_crops, target_size)
                ensemble_scores.extend(fallback_scores)
                logger.debug("Fallback model produced %d scores", len(fallback_scores))
            except Exception as e:
                logger.debug("Fallback inference failed: %s", e)

        if ensemble_scores:
            result.per_face_scores = ensemble_scores
            result.model_available = True
            # Average ensemble scores for final AI probability
            avg_score = float(np.mean(ensemble_scores))
            result.ai_probability = avg_score
            result.metadata["mean_score"] = round(avg_score, 4)
            result.metadata["max_score"] = round(float(max(ensemble_scores)), 4)
            # Confidence is the highest distance from 0.5 among the ensemble
            result.confidence = max(abs(s - 0.5) * 2.0 for s in ensemble_scores)
            logger.info(
                "Ensemble image model predictions: %d scores, avg=%.3f, max=%.3f, confidence=%.2f",
                len(ensemble_scores), avg_score, max(ensemble_scores), result.confidence,
            )
        else:
            logger.warning("No image model available — using heuristic scores only")
            result.flags.append("model_not_loaded")
            result.ai_probability = 0.5
            result.confidence = 0.0

        # ── 3. No face case — use full-image analysis ─────────────────────
        if not face_crops or meta.get("faces_found", 0) == 0:
            result.flags.append("no_faces_found")
            # Still run forensic analysis on the full image
            result.ai_probability = 0.5

        # ── 4. Enhanced Heuristic + Forensic Analysis ─────────────────────
        try:
            heuristic_feats = compute_image_heuristics(file_path, face_crops, meta)
            result.features = heuristic_feats
        except Exception as e:
            logger.warning("Image heuristic extraction failed: %s", e)
            heuristic_feats = {}

        # ── 4a. Error Level Analysis (ELA) ────────────────────────────────
        ela_score, ela_flags = self._compute_ela(file_path)
        result.ela_score = ela_score
        result.flags.extend(ela_flags)
        result.features["ela_score"] = round(ela_score, 4)

        # ── 4b. Frequency Domain (DCT block artifact analysis) ────────────
        freq_score, freq_flags = self._compute_frequency_artifacts(file_path)
        result.flags.extend(freq_flags)
        result.features["frequency_artifact_score"] = round(freq_score, 4)

        # ── 4c. Copy-Move / Splicing indicators ───────────────────────────
        splice_score, splice_flags = self._compute_splice_indicators(file_path)
        result.flags.extend(splice_flags)
        result.features["splice_indicator_score"] = round(splice_score, 4)

        # ── 4d. Compute combined rule score ───────────────────────────────
        rule_score, rule_flags = self._compute_rule_score(
            heuristic_feats, meta, ela_score, freq_score, splice_score
        )
        result.rule_score = rule_score
        result.flags.extend(rule_flags)

        # ----- Confidence‑based gating -----
        # If model confidence is low, blend AI probability with heuristic rule score.
        # Thresholds can be tuned; here we use 0.2 as a simple cut‑off.
        CONFIDENCE_THRESHOLD = 0.2
        if result.confidence < CONFIDENCE_THRESHOLD:
            # Weight AI probability by its confidence, otherwise rely on rule_score.
            weight_ai = result.confidence / CONFIDENCE_THRESHOLD
            weight_rule = 1.0 - weight_ai
            gated_ai = result.ai_probability * weight_ai + result.rule_score * weight_rule
            logger.debug(
                "Confidence gating applied: confidence=%.2f, weight_ai=%.2f, weight_rule=%.2f, gated_ai=%.3f",
                result.confidence,
                weight_ai,
                weight_rule,
                gated_ai,
            )
            result.ai_probability = gated_ai


        # Build forensic signals for the UI
        result.forensic_signals = self._build_forensic_signals(result.flags, result.features)

        # ── 5. Face count metadata ─────────────────────────────────────────
        result.metadata["faces_analyzed"] = len(face_crops)
        if result.per_face_scores:
            result.metadata["per_face_scores"] = [
                round(s, 4) for s in result.per_face_scores
            ]
        result.metadata["forensic_signals"] = result.forensic_signals

        logger.info(
            "Image analysis complete: ai=%.3f rule=%.3f ela=%.3f flags=%s",
            result.ai_probability, result.rule_score, ela_score, result.flags,
        )

        return result

    # ──────────────────────────────────────────────────────────────────
    #  ELA — Error Level Analysis
    # ──────────────────────────────────────────────────────────────────
    def _compute_ela(self, file_path: str) -> Tuple[float, List[str]]:
        """
        Error Level Analysis: compress image at low quality, diff with original.
        High ELA variance in face/smooth regions suggests manipulation.

        Returns (score 0-1, flags list)
        """
        flags: List[str] = []
        score = 0.0

        try:
            img = cv2.imread(file_path)
            if img is None:
                return 0.0, flags

            # Encode at quality=90 and re-read
            _, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
            compressed = cv2.imdecode(enc, cv2.IMREAD_COLOR)

            # Compute absolute difference (amplified ×10 for visibility)
            ela = cv2.absdiff(img.astype(np.float32), compressed.astype(np.float32))
            ela_amplified = np.clip(ela * 10, 0, 255).astype(np.uint8)

            # Statistical metrics on ELA map
            ela_mean = float(np.mean(ela_amplified))
            ela_std = float(np.std(ela_amplified))
            ela_max = float(np.max(ela_amplified))

            # High ELA mean → heavy compression artifacts → likely original JPEG
            # Low ELA std with moderate mean → indicates smooth manipulation
            # Very high ELA in localized areas → copy-paste / splicing
            normalized_mean = ela_mean / 255.0
            normalized_std = ela_std / 255.0

            # Check for suspicious ELA patterns
            if normalized_mean < 0.03 and normalized_std < 0.02:
                # Suspiciously clean — could be a generated image with no compression history
                score += 0.30
                flags.append("ela_suspiciously_clean")
            elif normalized_mean > 0.25:
                # Heavy uniform artifacts — heavily compressed
                score += 0.05
                flags.append("ela_heavy_compression")
            elif 0.05 < normalized_mean < 0.18 and normalized_std > 0.08:
                # Patchy ELA — inconsistent compression levels → likely spliced
                score += 0.25
                flags.append("ela_inconsistent_regions")

            # Regional analysis: check for outlier patches
            h, w = ela_amplified.shape[:2]
            if h > 64 and w > 64:
                patch_means = []
                for ry in range(0, h - 32, 32):
                    for rx in range(0, w - 32, 32):
                        patch = ela_amplified[ry:ry+32, rx:rx+32]
                        patch_means.append(float(np.mean(patch)))

                if patch_means:
                    pm_std = float(np.std(patch_means))
                    pm_mean = float(np.mean(patch_means))
                    if pm_std > pm_mean * 1.5 and pm_std > 15:
                        score += 0.20
                        flags.append("ela_regional_inconsistency")

            score = min(score, 1.0)

        except Exception as e:
            logger.debug("ELA computation failed: %s", e)

        return score, flags

    # ──────────────────────────────────────────────────────────────────
    #  Frequency Domain Analysis (DCT artifacts)
    # ──────────────────────────────────────────────────────────────────
    def _compute_frequency_artifacts(self, file_path: str) -> Tuple[float, List[str]]:
        """
        Analyze DCT coefficient distribution and high-frequency content.
        GAN-generated images often have characteristic frequency fingerprints.

        Returns (score 0-1, flags list)
        """
        flags: List[str] = []
        score = 0.0

        try:
            img = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                return 0.0, flags

            # Resize for consistent analysis
            h, w = img.shape
            size = min(512, h, w)
            img_resized = cv2.resize(img, (size, size))

            # Compute DFT
            dft = np.fft.fft2(img_resized.astype(np.float32))
            dft_shift = np.fft.fftshift(dft)
            magnitude = np.abs(dft_shift)

            # Log magnitude spectrum
            log_mag = np.log1p(magnitude)

            # Analyze frequency distribution
            cy, cx = size // 2, size // 2
            total_energy = float(np.sum(log_mag ** 2))

            # Low-freq energy (central 20%)
            r_low = int(size * 0.1)
            low_mask = np.zeros((size, size), dtype=bool)
            y_idx, x_idx = np.ogrid[:size, :size]
            low_mask[(y_idx - cy)**2 + (x_idx - cx)**2 <= r_low**2] = True
            low_energy = float(np.sum(log_mag[low_mask] ** 2))

            # High-freq energy (outer 20%)
            r_high = int(size * 0.4)
            high_mask = (y_idx - cy)**2 + (x_idx - cx)**2 > r_high**2
            high_energy = float(np.sum(log_mag[high_mask] ** 2))

            low_ratio = low_energy / (total_energy + 1e-9)
            high_ratio = high_energy / (total_energy + 1e-9)

            # GAN images tend to have unnaturally low high-frequency energy
            if high_ratio < 0.02:
                score += 0.20
                flags.append("freq_low_high_frequency_content")

            # Unusually dominant low frequencies (over-smoothed)
            if low_ratio > 0.85:
                score += 0.15
                flags.append("freq_dominated_by_low_frequencies")

            # Check for periodic artifacts (regular GAN artifacts in freq domain)
            # Look for peaks in the frequency domain outside center
            mag_normalized = log_mag / (log_mag.max() + 1e-9)
            r_exclude = int(size * 0.05)
            exclude_mask = (y_idx - cy)**2 + (x_idx - cx)**2 < r_exclude**2
            mag_outer = mag_normalized.copy()
            mag_outer[exclude_mask] = 0

            peak_threshold = 0.7
            peaks = np.sum(mag_outer > peak_threshold)
            if peaks > 20:
                score += 0.15
                flags.append("freq_periodic_artifacts")

            score = min(score, 1.0)

        except Exception as e:
            logger.debug("Frequency analysis failed: %s", e)

        return score, flags

    # ──────────────────────────────────────────────────────────────────
    #  Copy-Move / Splicing Detection
    # ──────────────────────────────────────────────────────────────────
    def _compute_splice_indicators(self, file_path: str) -> Tuple[float, List[str]]:
        """
        Detect potential copy-move forgery or image splicing.
        Uses noise pattern inconsistency and lighting direction analysis.

        Returns (score 0-1, flags list)
        """
        flags: List[str] = []
        score = 0.0

        try:
            img = cv2.imread(file_path)
            if img is None:
                return 0.0, flags

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
            h, w = gray.shape

            # ── Noise inconsistency across image regions ──────────────
            block_size = max(32, min(h, w) // 8)
            noise_stds = []

            for ry in range(0, h - block_size, block_size):
                for rx in range(0, w - block_size, block_size):
                    block = gray[ry:ry+block_size, rx:rx+block_size]
                    # Estimate local noise via median-subtracted std
                    blurred = cv2.GaussianBlur(block, (3, 3), 0)
                    noise = block - blurred
                    noise_stds.append(float(np.std(noise)))

            if len(noise_stds) >= 4:
                ns_std = float(np.std(noise_stds))
                ns_mean = float(np.mean(noise_stds))
                # High variation in local noise → splice boundary detected
                if ns_mean > 0 and ns_std / ns_mean > 0.5:
                    score += 0.25
                    flags.append("noise_inconsistency_detected")

            # ── JPEG blocking artifact consistency check ──────────────
            # Compute horizontal and vertical DCT blocking signature
            if h >= 16 and w >= 16:
                h_diff = np.abs(np.diff(gray, axis=1))
                v_diff = np.abs(np.diff(gray, axis=0))

                # Sample every 8 pixels (JPEG block boundaries)
                h_block_edges = h_diff[:, 7::8] if h_diff.shape[1] > 8 else h_diff
                h_non_edges = np.concatenate([h_diff[:, i::8] for i in range(7) if i != 7 and h_diff.shape[1] > i], axis=1) if h_diff.shape[1] > 7 else h_diff

                edge_mean = float(np.mean(h_block_edges)) if h_block_edges.size > 0 else 0
                non_edge_mean = float(np.mean(h_non_edges)) if h_non_edges.size > 0 else 1

                # In authentic JPEGs, block edges are more prominent
                if non_edge_mean > 0 and edge_mean / non_edge_mean < 0.8:
                    score += 0.10
                    flags.append("jpeg_blocking_inconsistency")

            score = min(score, 1.0)

        except Exception as e:
            logger.debug("Splice detection failed: %s", e)

        return score, flags

    # ──────────────────────────────────────────────────────────────────
    #  Combined Rule Score
    # ──────────────────────────────────────────────────────────────────
    @staticmethod
    def _compute_rule_score(
        feats: Dict,
        metadata: Dict,
        ela_score: float,
        freq_score: float,
        splice_score: float,
    ) -> tuple[float, list[str]]:
        """
        Combine all heuristic signals into a single rule_score [0, 1].
        """
        score = 0.0
        flags: list[str] = []

        # ── Forensic technique scores (weighted combination) ─────────
        # ELA gets highest weight as most direct manipulation indicator
        score += ela_score * 0.40
        score += freq_score * 0.30
        score += splice_score * 0.30

        # ── Classic image heuristics ──────────────────────────────────
        traditional_score = 0.0
        traditional_count = 0

        # No face detected — could be non-face content or heavily manipulated
        if feats.get("faces_found", 0) == 0:
            traditional_score += 0.10
            flags.append("no_face_detected")
            traditional_count += 1

        # Unusually sharp faces (GAN faces are often too sharp)
        mean_blur = feats.get("mean_face_blur", 100)
        if mean_blur > 800:
            traditional_score += 0.20
            flags.append("unusually_sharp_face")
            traditional_count += 1
        elif mean_blur > 500:
            traditional_score += 0.10
            flags.append("sharp_face")
            traditional_count += 1

        # Low edge density (deepfakes → smoother skin texture)
        ed = feats.get("mean_edge_density", 0.5)
        if ed < 0.04:
            traditional_score += 0.20
            flags.append("very_smooth_texture")
            traditional_count += 1
        elif ed < 0.08:
            traditional_score += 0.10
            flags.append("smooth_texture")
            traditional_count += 1

        # Abnormal saturation (GAN images sometimes have unnatural colors)
        sat_std = feats.get("saturation_std", 50)
        if sat_std < 15:
            traditional_score += 0.10
            flags.append("uniform_saturation")
            traditional_count += 1
        elif sat_std > 80:
            traditional_score += 0.10
            flags.append("extreme_saturation_variance")
            traditional_count += 1

        # Very low resolution
        if feats.get("is_low_resolution", False):
            traditional_score += 0.05
            flags.append("low_resolution")
            traditional_count += 1

        # High noise level can indicate manipulation
        noise = feats.get("noise_level", 20)
        if noise > 60:
            traditional_score += 0.10
            flags.append("high_noise_level")
            traditional_count += 1
        elif noise < 5:
            traditional_score += 0.10
            flags.append("suspiciously_low_noise")
            traditional_count += 1

        # Blend traditional score into overall (20% weight)
        if traditional_count > 0:
            score += min(traditional_score, 1.0) * 0.20

        return min(score, 1.0), flags

    # ──────────────────────────────────────────────────────────────────
    #  Human-readable Forensic Signals
    # ──────────────────────────────────────────────────────────────────
    @staticmethod
    def _build_forensic_signals(flags: List[str], features: Dict) -> List[str]:
        """Map internal flags to user-friendly forensic signal descriptions."""
        signal_map = {
            "ela_suspiciously_clean": "ELA: Image appears synthetically generated (no JPEG history)",
            "ela_inconsistent_regions": "ELA: Inconsistent compression regions suggest splicing",
            "ela_regional_inconsistency": "ELA: Localized manipulation detected via error analysis",
            "freq_low_high_frequency_content": "Frequency: Abnormally low high-frequency content (GAN signature)",
            "freq_periodic_artifacts": "Frequency: Periodic artifacts in spectrum suggest AI generation",
            "noise_inconsistency_detected": "Noise: Inconsistent noise patterns across image regions",
            "unusually_sharp_face": "Texture: Face region is unnaturally sharp (GAN over-sharpening)",
            "very_smooth_texture": "Texture: Smooth skin texture with very low edge density",
            "uniform_saturation": "Color: Unnaturally uniform color saturation",
            "ela_heavy_compression": "Compression: Heavy uniform JPEG artifacts",
            "no_face_detected": "Detection: No human face found — using full-image forensics",
            "suspiciously_low_noise": "Noise: Suspiciously low noise (AI-smoothed image)",
            "high_noise_level": "Noise: High noise level may indicate post-processing",
        }
        signals = []
        for flag in flags:
            if flag in signal_map:
                signals.append(signal_map[flag])
        return signals