'use client';

import { useState } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ShieldCheck,
  AlertTriangle,
  ShieldX,
  Lock,
  Archive,
  Eye,
  ArrowLeft,
  ExternalLink,
  Bot,
  Info,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import type { PreventionAction, PreventionSeverity, PreventionResult } from '@/lib/types';

interface PreventionBannerProps {
  action?: PreventionAction;
  severity?: PreventionSeverity;
  riskScore: number;
  message?: string;
  reasons?: string[];
  incidentId?: string | null;
  source?: string;
  inputReference?: string;
  onContinueAnyway?: () => void;
  onAskAi?: (context: any) => void;
}

export function PreventionBanner({
  action = 'ALLOW',
  severity = 'SAFE',
  riskScore,
  message,
  reasons = [],
  incidentId,
  source = 'content',
  inputReference,
  onContinueAnyway,
  onAskAi,
}: PreventionBannerProps) {
  const [showDetails, setShowDetails] = useState(false);
  const [overrideWarning, setOverrideWarning] = useState(false);

  // Derive display config based on action
  const configs: Record<
    PreventionAction,
    {
      title: string;
      badgeText: string;
      icon: typeof ShieldCheck;
      bgClass: string;
      borderClass: string;
      textClass: string;
      badgeClass: string;
      description: string;
    }
  > = {
    ALLOW: {
      title: 'ACCESS ALLOWED',
      badgeText: 'SAFE',
      icon: ShieldCheck,
      bgClass: 'bg-emerald-500/10',
      borderClass: 'border-emerald-500/30',
      textClass: 'text-emerald-400',
      badgeClass: 'border-emerald-500/40 bg-emerald-500/20 text-emerald-400',
      description: 'CyberShield evaluated this destination as safe. No malicious payload or phishing patterns detected.',
    },
    WARN: {
      title: 'PROCEED WITH CAUTION',
      badgeText: 'SUSPICIOUS',
      icon: AlertTriangle,
      bgClass: 'bg-amber-500/10',
      borderClass: 'border-amber-500/30',
      textClass: 'text-amber-400',
      badgeClass: 'border-amber-500/40 bg-amber-500/20 text-amber-400',
      description: 'This content exhibits borderline risk indicators. Verify the sender or domain authenticity before interacting.',
    },
    RESTRICT: {
      title: 'ACCESS RESTRICTED',
      badgeText: 'HIGH RISK',
      icon: Lock,
      bgClass: 'bg-orange-500/10',
      borderClass: 'border-orange-500/30',
      textClass: 'text-orange-400',
      badgeClass: 'border-orange-500/40 bg-orange-500/20 text-orange-400',
      description: 'Access has been restricted. Strong indicators of deceptive design, unverified routing, or abnormal parameters found.',
    },
    BLOCK: {
      title: 'ACCESS BLOCKED',
      badgeText: 'CRITICAL THREAT',
      icon: ShieldX,
      bgClass: 'bg-red-500/15',
      borderClass: 'border-red-500/40',
      textClass: 'text-red-400',
      badgeClass: 'border-red-500/50 bg-red-500/25 text-red-300 font-bold',
      description: 'CyberShield AI prevented navigation to this destination to protect your credentials and payment accounts.',
    },
    QUARANTINE: {
      title: 'EMAIL QUARANTINED',
      badgeText: 'QUARANTINED',
      icon: Archive,
      bgClass: 'bg-red-500/15',
      borderClass: 'border-red-500/40',
      textClass: 'text-red-400',
      badgeClass: 'border-red-500/50 bg-red-500/25 text-red-300 font-bold',
      description: 'This message has been isolated to prevent credential harvesting, fraudulent UPI requests, or attachment execution.',
    },
    FLAG: {
      title: 'MEDIA FLAGGED FOR REVIEW',
      badgeText: 'POTENTIAL DEEPFAKE',
      icon: Eye,
      bgClass: 'bg-purple-500/15',
      borderClass: 'border-purple-500/40',
      textClass: 'text-purple-400',
      badgeClass: 'border-purple-500/50 bg-purple-500/25 text-purple-300 font-bold',
      description: 'Potential synthetic or manipulated media detected. Do not act on financial or identity requests based on this media alone.',
    },
  };

  const cfg = configs[action] || configs.ALLOW;
  const Icon = cfg.icon;

  const threatContextData = {
    threat_type: source === 'email' ? 'phishing_email' : source === 'qr' ? 'malicious_qr' : source.includes('audio') ? 'deepfake_audio' : source.includes('video') ? 'deepfake_video' : 'phishing_url',
    risk_score: riskScore,
    action,
    severity,
    reasons,
    input_reference: inputReference,
  };

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98, y: 10 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="w-full"
    >
      <Card className={cn('relative overflow-hidden border backdrop-blur-md transition-all', cfg.bgClass, cfg.borderClass)}>
        {/* Glowing top line */}
        <div
          className={cn(
            'h-1 w-full',
            action === 'ALLOW' && 'bg-emerald-500',
            action === 'WARN' && 'bg-amber-500',
            action === 'RESTRICT' && 'bg-orange-500',
            (action === 'BLOCK' || action === 'QUARANTINE') && 'bg-red-500',
            action === 'FLAG' && 'bg-purple-500'
          )}
        />

        <CardContent className="p-5 space-y-4">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            {/* Title & Icon */}
            <div className="flex items-center gap-3.5">
              <div className={cn('flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border p-2', cfg.borderClass, cfg.bgClass)}>
                <Icon className={cn('h-6 w-6', cfg.textClass)} />
              </div>

              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className={cn('text-base font-bold tracking-tight', cfg.textClass)}>
                    {cfg.title}
                  </h3>
                  <Badge variant="outline" className={cn('text-[11px] uppercase tracking-wider', cfg.badgeClass)}>
                    {cfg.badgeText}
                  </Badge>
                  {incidentId && (
                    <Badge variant="outline" className="border-zinc-700 bg-zinc-800/60 font-mono text-[10px] text-zinc-400">
                      {incidentId}
                    </Badge>
                  )}
                </div>
                <p className="mt-0.5 text-xs text-zinc-400">
                  {message || cfg.description}
                </p>
              </div>
            </div>

            {/* Risk score gauge badge */}
            <div className="flex items-center gap-2 self-end sm:self-center">
              <div className="flex flex-col items-end">
                <span className="text-[10px] uppercase font-semibold text-zinc-500">
                  Risk Assessment
                </span>
                <span className={cn('font-mono text-xl font-extrabold', cfg.textClass)}>
                  {riskScore}%
                </span>
              </div>
            </div>
          </div>

          {/* Reasons summary list */}
          {reasons && reasons.length > 0 && (
            <div className="rounded-lg border border-zinc-800/80 bg-zinc-950/60 p-3 space-y-2">
              <div className="flex items-center justify-between text-xs font-semibold text-zinc-400">
                <span className="flex items-center gap-1.5">
                  <Info className="h-3.5 w-3.5 text-zinc-500" />
                  Identified Threat Indicators ({reasons.length})
                </span>
                <button
                  type="button"
                  onClick={() => setShowDetails(!showDetails)}
                  className="flex items-center gap-1 text-[11px] text-zinc-400 hover:text-zinc-200 transition-colors"
                >
                  {showDetails ? 'Hide details' : 'Show details'}
                  {showDetails ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                </button>
              </div>

              <AnimatePresence initial={false}>
                {(showDetails || reasons.length <= 2) && (
                  <motion.ul
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 pt-1 text-xs text-zinc-300"
                  >
                    {reasons.map((reason, idx) => (
                      <li key={idx} className="flex items-start gap-2">
                        <span className={cn('mt-1 h-1.5 w-1.5 shrink-0 rounded-full', action === 'ALLOW' ? 'bg-emerald-400' : 'bg-red-400')} />
                        <span className="leading-snug">{reason}</span>
                      </li>
                    ))}
                  </motion.ul>
                )}
              </AnimatePresence>
            </div>
          )}

          {/* Action buttons */}
          <div className="flex flex-wrap items-center justify-between gap-2.5 pt-1 border-t border-zinc-800/60">
            <div className="flex flex-wrap items-center gap-2">
              {/* Back button */}
              {(action === 'BLOCK' || action === 'RESTRICT' || action === 'WARN') && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => window.history.back()}
                  className="h-8 gap-1.5 text-xs border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-200"
                >
                  <ArrowLeft className="h-3.5 w-3.5" />
                  Go Back
                </Button>
              )}

              {/* Continue anyway for WARN */}
              {action === 'WARN' && !overrideWarning && onContinueAnyway && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setOverrideWarning(true);
                    onContinueAnyway();
                  }}
                  className="h-8 text-xs text-amber-400 hover:bg-amber-500/10 hover:text-amber-300"
                >
                  Continue Anyway (Risk Acknowledged)
                </Button>
              )}

              {/* Incident report link */}
              {incidentId && (
                <Link href={`/security/${incidentId}`}>
                  <Button size="sm" variant="outline" className="h-8 gap-1.5 text-xs border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-200">
                    <ExternalLink className="h-3.5 w-3.5 text-cyan-400" />
                    View Security Incident
                  </Button>
                </Link>
              )}
            </div>

            {/* AI Assistant consultation */}
            <Link
              href={{
                pathname: '/assistant',
                query: {
                  threat_type: threatContextData.threat_type,
                  risk_score: riskScore,
                  action,
                  severity,
                  reference: inputReference || '',
                },
              }}
            >
              <Button
                size="sm"
                className="h-8 gap-1.5 text-xs bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 border border-cyan-500/30"
              >
                <Bot className="h-3.5 w-3.5" />
                Explain with AI Assistant
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
