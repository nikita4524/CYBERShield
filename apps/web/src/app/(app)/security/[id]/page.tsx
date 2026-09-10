'use client';

import { useState, useEffect, use } from 'react';
import Link from 'next/link';
import {
  ShieldAlert,
  ShieldCheck,
  ShieldX,
  ArrowLeft,
  Bot,
  CheckCircle2,
  AlertTriangle,
  Archive,
  Lock,
  Clock,
  ExternalLink,
  FileText,
  HelpCircle,
  RefreshCw,
} from 'lucide-react';
import { PageHeader } from '@/components/shared/page-header';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { api } from '@/lib/api';
import type { SecurityIncident, ThreatExplanationResponse } from '@/lib/types';
import { cn } from '@/lib/utils';

export default function IncidentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const resolvedParams = use(params);
  const incidentId = resolvedParams.id;

  const [incident, setIncident] = useState<SecurityIncident | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUpdating, setIsUpdating] = useState(false);
  const [explanation, setExplanation] = useState<ThreatExplanationResponse | null>(null);
  const [isExplaining, setIsExplaining] = useState(false);

  useEffect(() => {
    async function loadIncident() {
      try {
        const data = await api.getIncident(incidentId);
        setIncident(data);
      } catch (err) {
        console.error('Failed to load incident:', err);
      } finally {
        setIsLoading(false);
      }
    }
    loadIncident();
  }, [incidentId]);

  const handleStatusChange = async (newStatus: "OPEN" | "REVIEWING" | "RESOLVED" | "FALSE_POSITIVE") => {
    if (!incident) return;
    setIsUpdating(true);
    try {
      const updated = await api.updateIncidentStatus(
        incident.incident_number,
        newStatus,
        `Status updated to ${newStatus} by analyst.`
      );
      setIncident(updated);
    } catch (err) {
      console.error('Failed to update incident status:', err);
    } finally {
      setIsUpdating(false);
    }
  };

  const handleRequestExplanation = async () => {
    if (!incident) return;
    setIsExplaining(true);
    try {
      const res = await api.explainThreat({
        threat_context: {
          threat_type: incident.threat_type,
          risk_score: incident.risk_score,
          action: incident.action,
          severity: incident.severity,
          reasons: incident.reasons || [],
          input_reference: incident.input_reference || '',
        },
      });
      setExplanation(res);
    } catch (err) {
      console.error('Failed to get threat explanation:', err);
    } finally {
      setIsExplaining(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-zinc-500">
        <RefreshCw className="mr-2 h-5 w-5 animate-spin" /> Loading incident details...
      </div>
    );
  }

  if (!incident) {
    return (
      <div className="space-y-4 p-8 text-center">
        <ShieldX className="mx-auto h-12 w-12 text-red-500" />
        <h2 className="text-xl font-bold text-zinc-200">Incident Not Found</h2>
        <p className="text-sm text-zinc-500">
          The requested incident ({incidentId}) could not be located in the security database.
        </p>
        <Link href="/security">
          <Button variant="outline" className="mt-4 gap-2">
            <ArrowLeft className="h-4 w-4" /> Return to Security Center
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Link href="/security">
          <Button variant="ghost" size="sm" className="gap-1.5 text-xs text-zinc-400 hover:text-zinc-200">
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to Security Center
          </Button>
        </Link>

        <div className="flex items-center gap-2">
          <span className="text-xs text-zinc-400">Incident Status:</span>
          <Select
            value={incident.status}
            onValueChange={(val) => handleStatusChange(val as any)}
            disabled={isUpdating}
          >
            <SelectTrigger className="h-8 w-[140px] border-zinc-800 bg-zinc-950 text-xs font-semibold">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="border-zinc-800 bg-zinc-950 text-xs">
              <SelectItem value="OPEN">Open</SelectItem>
              <SelectItem value="REVIEWING">Reviewing</SelectItem>
              <SelectItem value="RESOLVED">Resolved</SelectItem>
              <SelectItem value="FALSE_POSITIVE">False Positive</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Incident Header */}
      <Card className="border-zinc-800/80 bg-zinc-950/80">
        <CardContent className="p-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-3">
                <h1 className="font-mono text-2xl font-bold text-cyan-400">
                  {incident.incident_number}
                </h1>
                <Badge
                  variant="outline"
                  className={cn(
                    'font-mono uppercase text-xs px-2.5 py-0.5 font-bold',
                    incident.action === 'BLOCK' || incident.action === 'QUARANTINE'
                      ? 'border-red-500/50 bg-red-500/20 text-red-400'
                      : incident.action === 'RESTRICT'
                      ? 'border-orange-500/50 bg-orange-500/20 text-orange-400'
                      : 'border-amber-500/50 bg-amber-500/20 text-amber-400'
                  )}
                >
                  {incident.action}
                </Badge>
                <Badge variant="outline" className="text-xs border-zinc-700 bg-zinc-900 text-zinc-300">
                  {incident.severity}
                </Badge>
              </div>
              <p className="mt-1.5 text-sm text-zinc-400 capitalize">
                Category: <span className="text-zinc-200 font-medium">{incident.threat_type.replace(/_/g, ' ')}</span> • Source:{' '}
                <span className="text-zinc-200 font-medium uppercase">{incident.source}</span>
              </p>
            </div>

            <div className="flex flex-col items-end border-l border-zinc-800 pl-6">
              <span className="text-xs text-zinc-500 uppercase font-semibold">Threat Score</span>
              <span
                className={cn(
                  'font-mono text-3xl font-extrabold',
                  incident.risk_score >= 81 ? 'text-red-400' : 'text-amber-400'
                )}
              >
                {incident.risk_score}%
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Incident Details Grid */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          {/* Target & References */}
          <Card className="border-zinc-800/60 bg-zinc-900/60">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold uppercase tracking-wider text-zinc-400 flex items-center gap-2">
                <FileText className="h-4 w-4 text-cyan-400" />
                Target Payload / Reference
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-lg border border-zinc-800 bg-zinc-950/80 p-3 font-mono text-xs text-zinc-300 break-all">
                {incident.input_reference || 'N/A'}
              </div>

              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-2">
                  Prevention Engine Decision Reasons
                </h4>
                {incident.reasons && incident.reasons.length > 0 ? (
                  <ul className="space-y-2">
                    {incident.reasons.map((r, i) => (
                      <li key={i} className="flex items-start gap-2 text-xs text-zinc-300 bg-zinc-950/50 p-2.5 rounded-lg border border-zinc-800/80">
                        <span className="mt-0.5 h-2 w-2 shrink-0 rounded-full bg-red-400" />
                        <span>{r}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-zinc-500">Heuristic threat score exceeded safety threshold.</p>
                )}
              </div>
            </CardContent>
          </Card>

          {/* AI Security Advisory Panel */}
          <Card className="border-cyan-500/30 bg-cyan-950/10">
            <CardHeader className="pb-3 flex flex-row items-center justify-between">
              <CardTitle className="text-sm font-semibold uppercase tracking-wider text-cyan-400 flex items-center gap-2">
                <Bot className="h-4 w-4 text-cyan-400" />
                AI Security Advisor Explanation
              </CardTitle>
              {!explanation && (
                <Button
                  size="sm"
                  onClick={handleRequestExplanation}
                  disabled={isExplaining}
                  className="h-8 gap-1.5 text-xs bg-cyan-500/20 text-cyan-300 hover:bg-cyan-500/30 border border-cyan-500/40"
                >
                  {isExplaining ? (
                    <>
                      <RefreshCw className="h-3 w-3 animate-spin" /> Generating Advisory...
                    </>
                  ) : (
                    <>
                      <Bot className="h-3 w-3" /> Analyze with CyberShield LLM
                    </>
                  )}
                </Button>
              )}
            </CardHeader>
            <CardContent>
              {isExplaining ? (
                <div className="flex h-32 items-center justify-center text-xs text-cyan-400">
                  <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> Querying defensive security model...
                </div>
              ) : explanation ? (
                <div className="space-y-4 text-xs text-zinc-300">
                  <div className="rounded-lg border border-cyan-500/20 bg-zinc-950/80 p-4 leading-relaxed whitespace-pre-wrap">
                    {explanation.explanation}
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                    <div className="rounded-lg border border-emerald-500/30 bg-emerald-950/20 p-3 space-y-2">
                      <p className="font-semibold text-emerald-400 flex items-center gap-1.5">
                        <CheckCircle2 className="h-4 w-4" /> Immediate Recommended Actions
                      </p>
                      <ul className="space-y-1 text-zinc-300 list-disc list-inside">
                        {explanation.recommended_steps.map((s, i) => (
                          <li key={i}>{s}</li>
                        ))}
                      </ul>
                    </div>

                    <div className="rounded-lg border border-red-500/30 bg-red-950/20 p-3 space-y-2">
                      <p className="font-semibold text-red-400 flex items-center gap-1.5">
                        <ShieldX className="h-4 w-4" /> Things to Avoid
                      </p>
                      <ul className="space-y-1 text-zinc-300 list-disc list-inside">
                        {explanation.things_to_avoid.map((s, i) => (
                          <li key={i}>{s}</li>
                        ))}
                      </ul>
                    </div>
                  </div>

                  <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-3">
                    <p className="font-semibold text-zinc-400 mb-1">Official Reporting Channels</p>
                    <ul className="space-y-1 text-zinc-400">
                      {explanation.reporting_channels.map((c, i) => (
                        <li key={i}>• {c}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-zinc-400">
                  Click the button above to generate a comprehensive India-focused defensive explanation of this incident powered by Llama 3.3 70B.
                </p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Incident Metadata Sidebar */}
        <div className="space-y-6">
          <Card className="border-zinc-800/60 bg-zinc-900/60">
            <CardHeader className="pb-3">
              <CardTitle className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                Incident Timeline & Audit
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-xs">
              <div className="flex justify-between py-1.5 border-b border-zinc-800/60">
                <span className="text-zinc-500">Detected At</span>
                <span className="font-mono text-zinc-300">
                  {new Date(incident.created_at).toLocaleString()}
                </span>
              </div>

              <div className="flex justify-between py-1.5 border-b border-zinc-800/60">
                <span className="text-zinc-500">Resolution Status</span>
                <span className="font-semibold text-cyan-400">{incident.status}</span>
              </div>

              {incident.resolved_at && (
                <div className="flex justify-between py-1.5 border-b border-zinc-800/60">
                  <span className="text-zinc-500">Resolved At</span>
                  <span className="font-mono text-zinc-300">
                    {new Date(incident.resolved_at).toLocaleString()}
                  </span>
                </div>
              )}

              {incident.resolution_note && (
                <div className="space-y-1 pt-1">
                  <span className="text-zinc-500">Resolution Note</span>
                  <p className="p-2.5 rounded-lg border border-zinc-800 bg-zinc-950 text-zinc-300">
                    {incident.resolution_note}
                  </p>
                </div>
              )}

              <div className="pt-2">
                <Link
                  href={{
                    pathname: '/assistant',
                    query: {
                      threat_type: incident.threat_type,
                      risk_score: incident.risk_score,
                      action: incident.action,
                      severity: incident.severity,
                      reference: incident.input_reference || '',
                    },
                  }}
                >
                  <Button className="w-full gap-2 text-xs bg-cyan-600 hover:bg-cyan-500 text-white">
                    <Bot className="h-4 w-4" /> Open in Assistant Chat
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
