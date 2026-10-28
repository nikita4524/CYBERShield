"""
URL analysis service — fully self-contained heuristic engine.

Key design decisions:
  - UNKNOWN DOMAIN BASELINE: Any URL whose domain is not on the explicit
    whitelist starts at 0.20 ("suspicious-until-cleared"), not 0.0. This
    prevents totally clean-looking phishing URLs from scoring SAFE just
    because they happen to use HTTPS and avoid obvious keyword traps.

  - BLOCKLIST: ~400K bad domains extracted from data/url_dataset.csv are
    loaded at startup into a frozenset for O(1) lookup. A blocklisted
    domain raises the score to ≥ 0.85 (DANGEROUS threshold).

  - INVALID URL FLAGGING: Empty hostnames, bare-scheme-only strings, and
    un-parseable inputs are explicitly flagged instead of silently scoring
    0.0 or returning a catch-all 0.8.

  - QR INTEGRATION: qr_analyzer._analyze_url_content() already calls
    url_analyzer.analyze() for URL-type QR payloads — no change needed.
"""

import csv
import math
import os
import re
import socket
import time
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse, unquote

from utils.text_preprocessing import (
    INDIAN_BANKS,
    LEGITIMATE_DOMAINS as FINANCIAL_LEGITIMATE_DOMAINS,
)

logger = logging.getLogger(__name__)

# ── Threat lists ──────────────────────────────────────────────────

SUSPICIOUS_TLDS = {
    ".tk", ".ml", ".ga", ".cf", ".gq",
    ".buzz", ".top", ".xyz", ".club", ".online", ".site", ".icu",
    ".work", ".click", ".link", ".info", ".pw", ".cc",
    ".ws", ".loan", ".racing", ".win", ".download", ".stream",
    ".date", ".faith", ".review", ".party", ".science", ".trade",
    ".bid", ".accountant", ".cricket",
}

URL_SHORTENERS = {
    "bit.ly", "tinyurl.com", "goo.gl", "t.co", "ow.ly", "is.gd",
    "buff.ly", "adf.ly", "bit.do", "mcaf.ee", "su.pr", "db.tt",
    "qr.ae", "cur.lv", "ity.im", "lnkd.in", "shorte.st", "v.gd",
    "rb.gy", "cutt.ly", "shorturl.at", "rebrand.ly",
}

PHISHING_KEYWORDS = [
    "login", "signin", "sign-in", "verify", "verification",
    "secure", "security", "account", "update", "confirm",
    "banking", "password", "credential", "suspend", "alert",
    "unusual", "activity", "restore", "unlock", "validate",
    "authenticate", "wallet", "paypal", "apple", "microsoft",
    "amazon", "netflix", "facebook", "instagram", "google",
    "ebay", "chase", "wells", "citi", "hsbc",
    # India-specific phishing vocabulary
    "kyc", "netbanking", "otp", "upi", "aadhaar", "pancard",
]

# Words a scammer glues directly onto a bank code with no separator
BANK_ABUSE_SUFFIX_WORDS = [
    "bank", "secure", "verify", "login", "kyc", "netbanking",
    "online", "update", "confirm", "alert", "support",
]

# Global brand/service domains considered legitimate out of the box
LEGITIMATE_DOMAINS = {
    "google.com", "youtube.com", "facebook.com", "amazon.com",
    "apple.com", "microsoft.com", "github.com", "stackoverflow.com",
    "wikipedia.org", "twitter.com", "x.com", "linkedin.com",
    "reddit.com", "netflix.com", "paypal.com", "ebay.com",
    "instagram.com", "whatsapp.com", "zoom.us",
} | FINANCIAL_LEGITIMATE_DOMAINS


# ── Blocklist loader (runs once at module import) ─────────────────

def _load_domain_blocklist() -> frozenset:
    """
    Load bad domains from data/url_dataset.csv.

    The CSV has rows of the form ``some.domain.com/optional/path,bad``.
    We extract just the hostname (no scheme, no path) and add it to the
    set. Rows whose URL contains a known-legitimate domain are skipped to
    avoid accidentally blocklisting CDNs or shared hosts.

    Returns a frozenset for fast O(1) membership tests.
    """
    blocklist: set = set()

    # Resolve path relative to this file (services/ → api-gateway/data/)
    data_dir = Path(__file__).resolve().parent.parent / "data"
    csv_path = data_dir / "url_dataset.csv"

    if not csv_path.exists():
        logger.warning("url_dataset.csv not found at %s — blocklist disabled", csv_path)
        return frozenset()

    # Domains that should never be blocklisted even if specific paths on
    # them appear in the bad-URL dataset (the path was malicious, not the
    # domain as a whole — e.g. bit.ly/malicious-path).
    _BLOCKLIST_EXCLUSIONS = frozenset({
        # URL shorteners — paths are what's bad, not the domain
        "bit.ly", "tinyurl.com", "goo.gl", "t.co", "ow.ly", "is.gd",
        "buff.ly", "adf.ly", "bit.do", "rb.gy", "cutt.ly", "shorturl.at",
        "rebrand.ly", "lnkd.in", "shorte.st", "v.gd", "qr.ae",
        # CDNs and shared hosting that show up as collateral
        "amazonaws.com", "cloudfront.net", "akamaihd.net",
        "googleusercontent.com", "fbcdn.net", "twimg.com",
        # Major platforms where individual pages can be malicious
        "blogspot.com", "wordpress.com", "weebly.com", "wix.com",
        "github.io", "netlify.app", "vercel.app",
    })

    try:
        with open(csv_path, newline="", encoding="utf-8", errors="replace") as fh:
            reader = csv.reader(fh)
            next(reader, None)  # skip header
            for row in reader:
                if len(row) < 2:
                    continue
                raw_url, label = row[0].strip(), row[1].strip().lower()
                if label != "bad":
                    continue
                # Ensure parseable
                if not raw_url.startswith(("http://", "https://")):
                    raw_url = "http://" + raw_url
                try:
                    hostname = urlparse(raw_url).hostname or ""
                except Exception:
                    continue
                hostname = hostname.lower().lstrip("www.")
                if hostname and len(hostname) > 3 and hostname not in _BLOCKLIST_EXCLUSIONS:
                    blocklist.add(hostname)

        logger.info("URL blocklist loaded: %d domains", len(blocklist))
    except Exception as exc:
        logger.error("Failed to load url_dataset.csv: %s", exc)

    return frozenset(blocklist)


# Module-level singleton — loaded once when the worker starts
_DOMAIN_BLOCKLIST: frozenset = _load_domain_blocklist()


# ── Result dataclass ──────────────────────────────────────────────

@dataclass
class URLAnalysisResult:
    """Result from URL analysis."""
    probability: float
    confidence: float
    flags: List[str] = field(default_factory=list)
    features: Dict[str, Any] = field(default_factory=dict)
    highlights: List[Dict] = field(default_factory=list)
    rule_score: float = 0.0
    processing_time_ms: int = 0


# ── Analyzer ──────────────────────────────────────────────────────

class URLAnalyzer:
    """Analyzes URLs for phishing and malicious indicators using heuristics."""

    # ── Scoring constants ──
    # Start here for any URL whose domain is not on the whitelist.
    # Rationale: we cannot distinguish a brand-new legitimate domain from
    # an attacker-registered one by structure alone, so "unknown" should
    # land in the suspicious band (30–69), not SAFE (< 30).
    # 0.31 puts the raw score just above the safe_threshold=30 (i.e. 31)
    # so it maps to "suspicious" with no other signals.
    _UNKNOWN_BASELINE = 0.31

    def analyze(self, url: str) -> URLAnalysisResult:
        """Analyze a single URL with comprehensive heuristic checks."""
        start_time = time.time()
        flags: List[str] = []
        features: Dict[str, Any] = {}
        highlights: List[Dict] = []

        # ── 0. Normalise ──────────────────────────────────────────
        original_url = url.strip()
        if not original_url:
            return URLAnalysisResult(
                probability=0.70,
                rule_score=0.70,
                confidence=0.90,
                flags=["empty_url"],
                features={"error": "Empty input"},
                processing_time_ms=1,
            )

        url = original_url

        # ── Dangerous schemes — bail out immediately before normalisation ──
        url_lower_raw = url.lower().lstrip()
        if url_lower_raw.startswith("javascript:") or url_lower_raw.startswith("data:"):
            scheme = url_lower_raw.split(":")[0]
            return URLAnalysisResult(
                probability=0.97,
                rule_score=0.97,
                confidence=0.99,
                flags=["dangerous_uri_scheme"],
                features={"scheme": scheme, "raw": original_url[:200]},
                highlights=[{
                    "type": "scheme",
                    "value": scheme,
                    "reason": f"'{scheme}:' URIs are never used in legitimate links and are a common XSS/injection vector",
                }],
                processing_time_ms=int((time.time() - start_time) * 1000),
            )

        if not url.startswith(("http://", "https://", "upi://")):
            url = "https://" + url

        # ── 0b. Parse ─────────────────────────────────────────────
        try:
            parsed = urlparse(url)
        except Exception:
            return URLAnalysisResult(
                probability=0.75,
                rule_score=0.75,
                confidence=0.90,
                flags=["unparseable_url"],
                features={"raw": original_url[:200]},
                processing_time_ms=int((time.time() - start_time) * 1000),
            )

        hostname = (parsed.hostname or "").lower().strip()
        path = parsed.path.lower()
        query = parsed.query.lower()
        full_url_lower = url.lower()

        # ── 0c. Validate hostname presence ───────────────────────
        if not hostname:
            return URLAnalysisResult(
                probability=0.75,
                rule_score=0.75,
                confidence=0.90,
                flags=["invalid_url_no_hostname"],
                features={"raw": original_url[:200], "scheme": parsed.scheme},
                highlights=[{
                    "type": "structure",
                    "value": original_url[:100],
                    "reason": "URL has no valid hostname — cannot be a real web address",
                }],
                processing_time_ms=int((time.time() - start_time) * 1000),
            )

        # Resolved once up front; used to guard false-positive-prone rules
        is_legitimate = self._is_legitimate_domain(hostname)

        features["scheme"] = parsed.scheme
        features["hostname"] = hostname
        features["path"] = parsed.path
        features["query"] = parsed.query
        features["url_length"] = len(url)
        features["is_known_legitimate"] = is_legitimate

        # ── Start score ───────────────────────────────────────────
        # Whitelisted domains begin at 0 so rules that fire on them
        # (e.g. long path, redirect param) don't unfairly inflate their
        # score. Unknown domains start above the safe_threshold (0.30)
        # so a structurally clean but unrecognised domain lands in
        # "suspicious" rather than "safe" — unknown ≠ safe.
        score = 0.0 if is_legitimate else self._UNKNOWN_BASELINE

        # ─────────────────────────────────────────────────────────
        # 1. Blocklist check  (highest-confidence signal)
        # ─────────────────────────────────────────────────────────
        bare_host = hostname.lstrip("www.")
        blocklisted = (bare_host in _DOMAIN_BLOCKLIST or hostname in _DOMAIN_BLOCKLIST)
        features["blocklisted"] = blocklisted
        if blocklisted and not is_legitimate:
            score = max(score, 0.85)
            flags.append("blocklisted_domain")
            highlights.append({
                "type": "hostname",
                "value": hostname,
                "reason": "Domain is on the known-malicious blocklist",
            })

        # ─────────────────────────────────────────────────────────
        # 2. HTTPS check
        # ─────────────────────────────────────────────────────────
        if parsed.scheme == "http":
            score += 0.10
            flags.append("non_https")
            highlights.append({
                "type": "scheme",
                "value": "http",
                "reason": "Connection is not encrypted (HTTP)",
            })
        features["is_https"] = parsed.scheme == "https"

        # ─────────────────────────────────────────────────────────
        # 4. IP address instead of domain
        # ─────────────────────────────────────────────────────────
        is_ip = self._is_ip_address(hostname)
        features["uses_ip_address"] = is_ip
        if is_ip:
            score += 0.30
            flags.append("ip_address_url")
            highlights.append({
                "type": "hostname",
                "value": hostname,
                "reason": "URL uses IP address instead of domain name",
            })

        # ─────────────────────────────────────────────────────────
        # 5. Suspicious TLD
        # ─────────────────────────────────────────────────────────
        tld = self._get_tld(hostname)
        features["tld"] = tld
        if tld in SUSPICIOUS_TLDS:
            score += 0.15
            flags.append("suspicious_tld")
            highlights.append({
                "type": "tld",
                "value": tld,
                "reason": f"TLD '{tld}' is commonly used in phishing",
            })

        # ─────────────────────────────────────────────────────────
        # 6. URL length
        # ─────────────────────────────────────────────────────────
        url_len = len(url)
        if url_len > 150:
            score += 0.10
            flags.append("long_url")
        if url_len > 250:
            score += 0.05
            flags.append("very_long_url")
        features["url_length_category"] = (
            "short" if url_len < 50
            else "normal" if url_len < 100
            else "long" if url_len < 200
            else "very_long"
        )

        # ─────────────────────────────────────────────────────────
        # 7. Subdomain count
        # ─────────────────────────────────────────────────────────
        subdomain_count = self._count_subdomains(hostname)
        features["subdomain_count"] = subdomain_count
        if subdomain_count >= 3:
            score += 0.10
            flags.append("excessive_subdomains")
        if subdomain_count >= 5:
            score += 0.10
            flags.append("highly_nested_subdomains")

        # ─────────────────────────────────────────────────────────
        # 8. URL shortener
        # ─────────────────────────────────────────────────────────
        if hostname in URL_SHORTENERS:
            score += 0.15
            flags.append("url_shortener")
            highlights.append({
                "type": "hostname",
                "value": hostname,
                "reason": "URL shortener hides the real destination",
            })
        features["is_shortener"] = hostname in URL_SHORTENERS

        # ─────────────────────────────────────────────────────────
        # 9. Non-standard port
        # ─────────────────────────────────────────────────────────
        port = parsed.port
        features["port"] = port
        if port and port not in (80, 443, None):
            score += 0.15
            flags.append("non_standard_port")
            highlights.append({
                "type": "port",
                "value": str(port),
                "reason": f"Non-standard port :{port}",
            })

        # ─────────────────────────────────────────────────────────
        # 10. Special characters: @, //, hyphens, encoded chars
        # ─────────────────────────────────────────────────────────
        if "@" in parsed.netloc:
            score += 0.25
            flags.append("at_symbol_in_url")
            highlights.append({
                "type": "character",
                "value": "@",
                "reason": "'@' in URL can redirect to a different domain",
            })

        dash_count = hostname.count("-")
        features["hostname_dashes"] = dash_count
        if dash_count >= 3:
            score += 0.10
            flags.append("many_hyphens_in_hostname")

        if "//" in path[1:]:
            score += 0.05
            flags.append("double_slash_in_path")

        if "%" in parsed.netloc:
            score += 0.15
            flags.append("encoded_hostname")

        # ─────────────────────────────────────────────────────────
        # 11. Phishing keywords (only on non-whitelisted domains)
        # ─────────────────────────────────────────────────────────
        keyword_hits = []
        if not is_legitimate:
            for kw in PHISHING_KEYWORDS:
                if kw in full_url_lower:
                    keyword_hits.append(kw)
        features["phishing_keywords"] = keyword_hits
        if keyword_hits:
            kw_score = min(len(keyword_hits) * 0.05, 0.20)
            score += kw_score
            flags.append(f"phishing_keywords_found ({len(keyword_hits)})")

        # ─────────────────────────────────────────────────────────
        # 12. Indian bank name abuse
        # ─────────────────────────────────────────────────────────
        bank_hit = "" if is_legitimate else self._check_bank_name_abuse(hostname)
        features["bank_name_abuse"] = bank_hit
        if bank_hit:
            score += 0.35
            flags.append(f"bank_name_abuse:{bank_hit}")
            highlights.append({
                "type": "hostname",
                "value": hostname,
                "reason": (
                    f"Bank name '{bank_hit}' found in a domain that isn't "
                    "the bank's official site — likely impersonation"
                ),
            })

        # ─────────────────────────────────────────────────────────
        # 13. Punycode / IDN homograph attack
        # ─────────────────────────────────────────────────────────
        if hostname.startswith("xn--") or any(
            part.startswith("xn--") for part in hostname.split(".")
        ):
            score += 0.25
            flags.append("punycode_domain")
            highlights.append({
                "type": "hostname",
                "value": hostname,
                "reason": "Punycode domain may be a homograph attack",
            })
        features["is_punycode"] = "xn--" in hostname

        # ─────────────────────────────────────────────────────────
        # 14. Brand impersonation in subdomain
        # ─────────────────────────────────────────────────────────
        brand_impersonation = None if is_legitimate else self._check_brand_impersonation(hostname)
        if brand_impersonation:
            score += 0.20
            flags.append(f"possible_brand_impersonation: {brand_impersonation}")
            highlights.append({
                "type": "hostname",
                "value": hostname,
                "reason": f"Possible impersonation of '{brand_impersonation}'",
            })
        features["brand_impersonation"] = brand_impersonation

        # ─────────────────────────────────────────────────────────
        # 15. Entropy of hostname (random-looking domains)
        # ─────────────────────────────────────────────────────────
        hostname_no_tld = hostname.rsplit(".", 1)[0] if "." in hostname else hostname
        entropy = self._shannon_entropy(hostname_no_tld)
        features["hostname_entropy"] = round(entropy, 3)
        if entropy > 4.0 and not is_legitimate:
            score += 0.10
            flags.append("high_entropy_hostname")

        # ─────────────────────────────────────────────────────────
        # 16. Legitimate domain bonus (reduce false positives)
        #     Applied as a downward clamp, not a simple subtraction,
        #     so a whitelisted domain that fired some rules still gets
        #     a significantly reduced score without going below 0.
        # ─────────────────────────────────────────────────────────
        features["base_domain"] = self._get_base_domain(hostname)
        if is_legitimate:
            score = max(score - 0.40, 0.0)

        # ─────────────────────────────────────────────────────────
        # 17. Query string analysis
        # ─────────────────────────────────────────────────────────
        if query:
            qs_params = parse_qs(parsed.query)
            features["query_param_count"] = len(qs_params)
            redirect_params = {"redirect", "url", "next", "return", "goto", "dest", "rurl"}
            for param in qs_params:
                if param.lower() in redirect_params:
                    score += 0.10
                    flags.append(f"redirect_param: {param}")
                    break

        # ─────────────────────────────────────────────────────────
        # 18. Multi-signal corroboration bonus
        # ─────────────────────────────────────────────────────────
        signal_count = len(flags)
        if not is_legitimate and signal_count >= 4:
            score += 0.10
            flags.append("multiple_corroborating_signals")

        # ── Clamp ─────────────────────────────────────────────────
        final_score = round(min(max(score, 0.0), 1.0), 4)

        # Confidence: zero flags on a non-whitelisted URL means we could
        # only apply the baseline — low confidence. Zero flags on a known-
        # legitimate URL is high confidence. Many flags = high confidence.
        if is_legitimate and signal_count == 0:
            confidence = 0.90
        elif signal_count == 0:
            # Only baseline fired — uncertain
            confidence = 0.45
        else:
            confidence = min(0.55 + signal_count * 0.07, 0.97)

        processing_time_ms = max(1, int((time.time() - start_time) * 1000))

        return URLAnalysisResult(
            probability=final_score,
            rule_score=final_score,
            confidence=round(confidence, 2),
            flags=flags,
            features=features,
            highlights=highlights,
            processing_time_ms=processing_time_ms,
        )

    # ── Helper methods ────────────────────────────────────────────

    @staticmethod
    def _is_legitimate_domain(hostname: str) -> bool:
        """Check hostname against the whitelist using suffix matching."""
        if not hostname:
            return False
        for legit in LEGITIMATE_DOMAINS:
            if hostname == legit or hostname.endswith("." + legit):
                return True
        return False

    @staticmethod
    def _check_bank_name_abuse(hostname: str) -> str:
        """Return abused Indian bank name if found, otherwise empty string."""
        tokens = re.split(r"[^a-z0-9]+", hostname)
        hostname_no_tld = hostname.rsplit(".", 1)[0] if "." in hostname else hostname
        for bank in INDIAN_BANKS:
            bank_key = bank.replace(" ", "")
            if bank_key in tokens:
                return bank
            if any(
                f"{bank_key}{suffix}" in hostname_no_tld
                or f"{suffix}{bank_key}" in hostname_no_tld
                for suffix in BANK_ABUSE_SUFFIX_WORDS
            ):
                return bank
        return ""

    @staticmethod
    def _is_ip_address(hostname: str) -> bool:
        """Check if hostname is an IP address."""
        h = hostname.strip("[]")
        try:
            socket.inet_pton(socket.AF_INET, h)
            return True
        except (socket.error, OSError):
            pass
        try:
            socket.inet_pton(socket.AF_INET6, h)
            return True
        except (socket.error, OSError):
            pass
        return bool(re.match(r"^\d{1,3}(\.\d{1,3}){3}$", hostname))

    @staticmethod
    def _get_tld(hostname: str) -> str:
        """Extract TLD from hostname."""
        parts = hostname.rsplit(".", 1)
        return f".{parts[-1]}" if len(parts) > 1 else ""

    @staticmethod
    def _get_base_domain(hostname: str) -> str:
        """Get base domain (last two parts)."""
        parts = hostname.split(".")
        return ".".join(parts[-2:]) if len(parts) >= 2 else hostname

    @staticmethod
    def _count_subdomains(hostname: str) -> int:
        """Count subdomains (parts before the base domain)."""
        parts = hostname.split(".")
        return max(0, len(parts) - 2)

    @staticmethod
    def _shannon_entropy(text: str) -> float:
        """Calculate Shannon entropy of a string."""
        if not text:
            return 0.0
        freq: Dict[str, int] = {}
        for ch in text:
            freq[ch] = freq.get(ch, 0) + 1
        length = len(text)
        entropy = 0.0
        for count in freq.values():
            p = count / length
            if p > 0:
                entropy -= p * math.log2(p)
        return entropy

    @staticmethod
    def _check_brand_impersonation(hostname: str) -> Optional[str]:
        """Check if a well-known brand appears in subdomain of a different domain."""
        brands = [
            "google", "facebook", "apple", "microsoft", "amazon",
            "netflix", "paypal", "instagram", "whatsapp", "twitter",
            "chase", "wellsfargo", "bankofamerica", "citibank",
            "linkedin", "dropbox", "yahoo", "outlook", "office365",
        ]
        parts = hostname.split(".")
        base = ".".join(parts[-2:]) if len(parts) >= 2 else hostname
        for brand in brands:
            if brand in hostname and brand not in base:
                return brand
        return None


# Singleton instance
url_analyzer = URLAnalyzer()
