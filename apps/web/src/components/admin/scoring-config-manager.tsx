"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { api } from "@/lib/api";
import { Save, RefreshCw, AlertCircle, CheckCircle2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface ScoringConfig {
  id: string;
  org_id: string | null;
  audio_weight: number;
  video_weight: number;
  phish_weight: number;
  safe_threshold: number;
  dangerous_threshold: number;
}

export function ScoringConfigManager() {
  const [config, setConfig] = useState<ScoringConfig | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Local state for form
  const [audioWeight, setAudioWeight] = useState(0.5);
  const [videoWeight, setVideoWeight] = useState(0.5);
  const [phishWeight, setPhishWeight] = useState(0.5);
  const [safeThreshold, setSafeThreshold] = useState(30);
  const [dangerousThreshold, setDangerousThreshold] = useState(70);

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    setIsLoading(true);
    setMessage(null);
    try {
      const data = await api.request<ScoringConfig>("/admin/scoring-config");
      setConfig(data);
      setAudioWeight(data.audio_weight);
      setVideoWeight(data.video_weight);
      setPhishWeight(data.phish_weight);
      setSafeThreshold(data.safe_threshold);
      setDangerousThreshold(data.dangerous_threshold);
    } catch (error: any) {
      setMessage({ type: "error", text: error.message || "Failed to load configuration" });
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async () => {
    // Validation
    if (safeThreshold >= dangerousThreshold) {
      setMessage({
        type: "error",
        text: "Safe threshold must be less than dangerous threshold",
      });
      return;
    }

    setIsSaving(true);
    setMessage(null);

    try {
      const updated = await api.request<ScoringConfig>("/admin/scoring-config", {
        method: "PATCH",
        body: JSON.stringify({
          audio_weight: audioWeight,
          video_weight: videoWeight,
          phish_weight: phishWeight,
          safe_threshold: safeThreshold,
          dangerous_threshold: dangerousThreshold,
        }),
      });

      setConfig(updated);
      setMessage({ type: "success", text: "Configuration updated successfully" });

      // Clear message after 3 seconds
      setTimeout(() => setMessage(null), 3000);
    } catch (error: any) {
      setMessage({ type: "error", text: error.message || "Failed to save configuration" });
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = () => {
    if (config) {
      setAudioWeight(config.audio_weight);
      setVideoWeight(config.video_weight);
      setPhishWeight(config.phish_weight);
      setSafeThreshold(config.safe_threshold);
      setDangerousThreshold(config.dangerous_threshold);
      setMessage(null);
    }
  };

  const hasChanges =
    config &&
    (audioWeight !== config.audio_weight ||
      videoWeight !== config.video_weight ||
      phishWeight !== config.phish_weight ||
      safeThreshold !== config.safe_threshold ||
      dangerousThreshold !== config.dangerous_threshold);

  if (isLoading) {
    return (
      <Card className="border-zinc-800/60 bg-zinc-900/70">
        <CardContent className="flex items-center justify-center py-20">
          <div className="flex items-center gap-3 text-zinc-500">
            <RefreshCw className="h-5 w-5 animate-spin" />
            <span>Loading configuration...</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3 }}>
      <Card className="border-zinc-800/60 bg-zinc-900/70 backdrop-blur-sm">
        <CardHeader>
          <CardTitle>Scoring Engine Configuration</CardTitle>
          <CardDescription>
            Adjust model weights and risk thresholds for the AI threat detection engine
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Alert Messages */}
          {message && (
            <Alert
              className={cn(
                message.type === "success"
                  ? "border-green-500/50 bg-green-500/10 text-green-400"
                  : "border-red-500/50 bg-red-500/10 text-red-400"
              )}
            >
              {message.type === "success" ? (
                <CheckCircle2 className="h-4 w-4" />
              ) : (
                <AlertCircle className="h-4 w-4" />
              )}
              <AlertDescription>{message.text}</AlertDescription>
            </Alert>
          )}

          {/* Model Weights Section */}
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-semibold text-zinc-300 mb-3">Model Weights</h3>
              <p className="text-xs text-zinc-500 mb-4">
                Control the influence of each detection model in the final risk score
              </p>
            </div>

            {/* Audio Weight */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="audio-weight" className="text-sm text-zinc-400">
                  Audio Deepfake Weight
                </Label>
                <span className="font-mono text-sm font-medium text-zinc-300">
                  {audioWeight.toFixed(2)}
                </span>
              </div>
              <Slider
                id="audio-weight"
                min={0}
                max={1}
                step={0.05}
                value={[audioWeight]}
                onValueChange={(value: number[]) => setAudioWeight(value[0])}
                className="py-2"
              />
            </div>

            {/* Video Weight */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="video-weight" className="text-sm text-zinc-400">
                  Video Deepfake Weight
                </Label>
                <span className="font-mono text-sm font-medium text-zinc-300">
                  {videoWeight.toFixed(2)}
                </span>
              </div>
              <Slider
                id="video-weight"
                min={0}
                max={1}
                step={0.05}
                value={[videoWeight]}
                onValueChange={(value: number[]) => setVideoWeight(value[0])}
                className="py-2"
              />
            </div>

            {/* Phishing Weight */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="phish-weight" className="text-sm text-zinc-400">
                  Phishing Detection Weight
                </Label>
                <span className="font-mono text-sm font-medium text-zinc-300">
                  {phishWeight.toFixed(2)}
                </span>
              </div>
              <Slider
                id="phish-weight"
                min={0}
                max={1}
                step={0.05}
                value={[phishWeight]}
                onValueChange={(value: number[]) => setPhishWeight(value[0])}
                className="py-2"
              />
            </div>
          </div>

          {/* Risk Thresholds Section */}
          <div className="space-y-4 pt-4 border-t border-zinc-800">
            <div>
              <h3 className="text-sm font-semibold text-zinc-300 mb-3">Risk Thresholds</h3>
              <p className="text-xs text-zinc-500 mb-4">
                Define score ranges for safe, suspicious, and dangerous classifications
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Safe Threshold */}
              <div className="space-y-2">
                <Label htmlFor="safe-threshold" className="text-sm text-zinc-400">
                  Safe Threshold
                </Label>
                <div className="flex items-center gap-2">
                  <Input
                    id="safe-threshold"
                    type="number"
                    min={0}
                    max={100}
                    value={safeThreshold}
                    onChange={(e) => setSafeThreshold(parseInt(e.target.value) || 0)}
                    className="font-mono"
                  />
                  <span className="text-sm text-zinc-500 whitespace-nowrap">
                    ≤ {safeThreshold} = Safe
                  </span>
                </div>
              </div>

              {/* Dangerous Threshold */}
              <div className="space-y-2">
                <Label htmlFor="dangerous-threshold" className="text-sm text-zinc-400">
                  Dangerous Threshold
                </Label>
                <div className="flex items-center gap-2">
                  <Input
                    id="dangerous-threshold"
                    type="number"
                    min={0}
                    max={100}
                    value={dangerousThreshold}
                    onChange={(e) => setDangerousThreshold(parseInt(e.target.value) || 0)}
                    className="font-mono"
                  />
                  <span className="text-sm text-zinc-500 whitespace-nowrap">
                    ≥ {dangerousThreshold} = Dangerous
                  </span>
                </div>
              </div>
            </div>

            {/* Visual Range Indicator */}
            <div className="flex items-center gap-1 text-xs">
              <div className="flex-1 h-2 rounded-l-full bg-green-500/30" />
              <span className="text-zinc-500 px-1">{safeThreshold}</span>
              <div className="flex-1 h-2 bg-amber-500/30" />
              <span className="text-zinc-500 px-1">{dangerousThreshold}</span>
              <div className="flex-1 h-2 rounded-r-full bg-red-500/30" />
            </div>
            <div className="flex justify-between text-xs text-zinc-500">
              <span>Safe (0-{safeThreshold})</span>
              <span>
                Suspicious ({safeThreshold + 1}-{dangerousThreshold - 1})
              </span>
              <span>Dangerous ({dangerousThreshold}-100)</span>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-zinc-800">
            <Button
              variant="ghost"
              onClick={handleReset}
              disabled={!hasChanges || isSaving}
              className="gap-2"
            >
              <RefreshCw className="h-4 w-4" />
              Reset
            </Button>
            <Button
              onClick={handleSave}
              disabled={!hasChanges || isSaving}
              className="gap-2 bg-cs-cyan hover:bg-cs-cyan/90 text-black"
            >
              {isSaving ? (
                <>
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="h-4 w-4" />
                  Save Changes
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
