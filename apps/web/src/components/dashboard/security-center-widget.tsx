'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  ShieldAlert,
  ShieldX,
  Lock,
  Archive,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  ExternalLink,
  RefreshCw,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import type { SecurityIncident, IncidentStats } from '@/lib/types';
import { cn } from '@/lib/utils';

export function SecurityCenterWidget() {
  const [stats, setStats] = useState<IncidentStats | null>(null);
  const [incidents, setIncidents] = useState<SecurityIncident[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function loadSecurityData() {
      try {
        const [sRes, lRes] = await Promise.all([
          api.getIncidentStats().catch(() => null),
          api.getIncidents({ limit: 5 }).catch(() => ({ total: 0, items: [] })),
        ]);
        if (sRes) setStats(sRes);
        if (lRes?.items) setIncidents(lRes.items);
      } catch (err) {
        console.error('Failed to load dashboard security data:', err);
      } finally {
        setIsLoading(false);
      }
    }
    loadSecurityData();
  }, []);

  const getActionBadge = (action: string) => {
    const styles: Record<string, string> = {
      BLOCK: 'border-red-500/40 bg-red-500/20 text-red-400 font-bold',
      QUARANTINE: 'border-red-500/40 bg-red-500/20 text-red-400 font-bold',
      RESTRICT: 'border-orange-500/40 bg-orange-500/20 text-orange-400',
      WARN: 'border-amber-500/40 bg-amber-500/20 text-amber-400',
      ALLOW: 'border-emerald-500/40 bg-emerald-500/20 text-emerald-400',
      FLAG: 'border-purple-500/40 bg-purple-500/20 text-purple-400',
    };
    return (
      <Badge variant="outline" className={cn('text-[10px] uppercase font-mono', styles[action] || '')}>
        {action}
      </Badge>
    );
  };

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      OPEN: 'border-red-500/30 bg-red-500/10 text-red-400',
      REVIEWING: 'border-amber-500/30 bg-amber-500/10 text-amber-400',
      RESOLVED: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400',
      FALSE_POSITIVE: 'border-zinc-500/30 bg-zinc-500/10 text-zinc-400',
    };
    return (
      <Badge variant="outline" className={cn('text-[10px] uppercase', styles[status] || '')}>
        {status.replace('_', ' ')}
      </Badge>
    );
  };

  return (
    <Card className="border-zinc-800/80 bg-zinc-950/60 backdrop-blur-md overflow-hidden">
      <div className="h-[2px] w-full bg-gradient-to-r from-cyan-500 via-rose-500 to-purple-500" />
      <CardHeader className="p-5 pb-3 flex flex-row items-center justify-between border-b border-zinc-800/60">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-red-500/30 bg-red-500/10">
            <ShieldAlert className="h-4 w-4 text-red-400" />
          </div>
          <div>
            <CardTitle className="text-sm font-bold text-zinc-100 flex items-center gap-2">
              CyberShield Security Center
              <Badge variant="outline" className="border-red-500/30 bg-red-500/10 text-[10px] font-bold text-red-400">
                ACTIVE PREVENTION
              </Badge>
            </CardTitle>
            <p className="text-xs text-zinc-500">
              Automated threat blocking, quarantine, and security incident response
            </p>
          </div>
        </div>

        <Link href="/security">
          <Button variant="ghost" size="sm" className="h-8 gap-1 text-xs text-cyan-400 hover:text-cyan-300 hover:bg-cyan-500/10">
            View All Incidents
            <ArrowRight className="h-3.5 w-3.5" />
          </Button>
        </Link>
      </CardHeader>

      <CardContent className="p-5 space-y-5">
        {/* Metric Pills */}
        <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-6">
          <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-3">
            <div className="flex items-center justify-between text-[11px] text-zinc-400 font-medium">
              <span>Critical</span>
              <ShieldX className="h-3.5 w-3.5 text-red-400" />
            </div>
            <p className="mt-1 font-mono text-xl font-bold text-red-400">{stats?.critical ?? 0}</p>
          </div>

          <div className="rounded-lg border border-orange-500/30 bg-orange-500/5 p-3">
            <div className="flex items-center justify-between text-[11px] text-zinc-400 font-medium">
              <span>High Risk</span>
              <Lock className="h-3.5 w-3.5 text-orange-400" />
            </div>
            <p className="mt-1 font-mono text-xl font-bold text-orange-400">{stats?.high ?? 0}</p>
          </div>

          <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3">
            <div className="flex items-center justify-between text-[11px] text-zinc-400 font-medium">
              <span>Suspicious</span>
              <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
            </div>
            <p className="mt-1 font-mono text-xl font-bold text-amber-400">{stats?.medium ?? 0}</p>
          </div>

          <div className="rounded-lg border border-rose-500/30 bg-rose-500/5 p-3">
            <div className="flex items-center justify-between text-[11px] text-zinc-400 font-medium">
              <span>Blocked</span>
              <ShieldAlert className="h-3.5 w-3.5 text-rose-400" />
            </div>
            <p className="mt-1 font-mono text-xl font-bold text-rose-400">{stats?.blocked ?? 0}</p>
          </div>

          <div className="rounded-lg border border-purple-500/30 bg-purple-500/5 p-3">
            <div className="flex items-center justify-between text-[11px] text-zinc-400 font-medium">
              <span>Quarantined</span>
              <Archive className="h-3.5 w-3.5 text-purple-400" />
            </div>
            <p className="mt-1 font-mono text-xl font-bold text-purple-400">{stats?.quarantined ?? 0}</p>
          </div>

          <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3">
            <div className="flex items-center justify-between text-[11px] text-zinc-400 font-medium">
              <span>Resolved</span>
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
            </div>
            <p className="mt-1 font-mono text-xl font-bold text-emerald-400">{stats?.resolved ?? 0}</p>
          </div>
        </div>

        {/* Mini Table of Recent Incidents */}
        <div>
          <div className="flex items-center justify-between mb-2.5">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
              Recent Prevention Incidents
            </h4>
            <span className="text-[11px] text-zinc-500">auto-logged on threat detection</span>
          </div>

          {isLoading ? (
            <div className="flex h-24 items-center justify-center text-xs text-zinc-500">
              <RefreshCw className="mr-2 h-3.5 w-3.5 animate-spin" /> Loading incidents...
            </div>
          ) : incidents.length === 0 ? (
            <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4 text-center text-xs text-zinc-500">
              No recent security incidents logged. All scanned traffic has passed safety checks.
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-zinc-800 bg-zinc-900/40">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-zinc-800 bg-zinc-950/80 font-medium uppercase text-zinc-400 text-[10px]">
                  <tr>
                    <th className="px-3 py-2.5">Incident #</th>
                    <th className="px-3 py-2.5">Threat Type</th>
                    <th className="px-3 py-2.5">Risk</th>
                    <th className="px-3 py-2.5">Action</th>
                    <th className="px-3 py-2.5">Status</th>
                    <th className="px-3 py-2.5 text-right">View</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/60">
                  {incidents.slice(0, 4).map((inc) => (
                    <tr key={inc.id} className="hover:bg-zinc-800/30 transition-colors">
                      <td className="px-3 py-2 font-mono font-semibold text-cyan-400">
                        {inc.incident_number}
                      </td>
                      <td className="px-3 py-2 text-zinc-300 capitalize">
                        {inc.threat_type.replace(/_/g, ' ')}
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className={cn(
                            'font-mono font-bold',
                            inc.risk_score >= 81 ? 'text-red-400' : 'text-amber-400'
                          )}
                        >
                          {inc.risk_score}%
                        </span>
                      </td>
                      <td className="px-3 py-2">{getActionBadge(inc.action)}</td>
                      <td className="px-3 py-2">{getStatusBadge(inc.status)}</td>
                      <td className="px-3 py-2 text-right">
                        <Link href={`/security/${inc.incident_number}`}>
                          <Button size="sm" variant="ghost" className="h-6 px-2 text-[11px] text-cyan-400 hover:text-cyan-300">
                            Details
                            <ExternalLink className="ml-1 h-3 w-3" />
                          </Button>
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
