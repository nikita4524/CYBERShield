'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import {
  ShieldAlert,
  ShieldCheck,
  ShieldX,
  AlertTriangle,
  Archive,
  RefreshCw,
  Search,
  Filter,
  ExternalLink,
  Lock,
  Eye,
  CheckCircle2,
  Clock,
} from 'lucide-react';
import { PageHeader } from '@/components/shared/page-header';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { api } from '@/lib/api';
import type { SecurityIncident, IncidentStats } from '@/lib/types';
import { cn } from '@/lib/utils';

export default function SecurityCenterPage() {
  const [incidents, setIncidents] = useState<SecurityIncident[]>([]);
  const [stats, setStats] = useState<IncidentStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [severityFilter, setSeverityFilter] = useState('ALL');
  const [actionFilter, setActionFilter] = useState('ALL');

  const loadData = useCallback(async (showSpinner = false) => {
    if (showSpinner) setIsRefreshing(true);
    try {
      const [statsRes, listRes] = await Promise.all([
        api.getIncidentStats().catch(() => null),
        api.getIncidents({ limit: 50 }).catch(() => ({ total: 0, items: [] })),
      ]);

      if (statsRes) setStats(statsRes);
      if (listRes?.items) setIncidents(listRes.items);
    } catch (err) {
      console.error('Failed to load incident data:', err);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Filtered incidents
  const filteredIncidents = incidents.filter((item) => {
    const matchesSearch =
      searchQuery === '' ||
      item.incident_number.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.threat_type.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (item.input_reference && item.input_reference.toLowerCase().includes(searchQuery.toLowerCase()));

    const matchesStatus = statusFilter === 'ALL' || item.status === statusFilter;
    const matchesSeverity = severityFilter === 'ALL' || item.severity === severityFilter;
    const matchesAction = actionFilter === 'ALL' || item.action === actionFilter;

    return matchesSearch && matchesStatus && matchesSeverity && matchesAction;
  });

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
    <div className="space-y-6">
      <PageHeader
        title="Security Center"
        description="Automated threat prevention, quarantine logs, and security incident response."
        icon={ShieldAlert}
      >
        <Button
          variant="outline"
          size="sm"
          onClick={() => loadData(true)}
          disabled={isRefreshing}
          className="h-8 gap-1.5 border-zinc-700 bg-zinc-900 text-xs text-zinc-300 hover:bg-zinc-800"
        >
          <RefreshCw className={cn('h-3.5 w-3.5', isRefreshing && 'animate-spin')} />
          Refresh
        </Button>
      </PageHeader>

      {/* ── Summary KPI Tiles ── */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Card className="border-red-500/30 bg-red-500/5">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-zinc-400">Critical</span>
              <ShieldX className="h-4 w-4 text-red-400" />
            </div>
            <p className="mt-2 font-mono text-2xl font-bold text-red-400">
              {stats?.critical ?? 0}
            </p>
            <span className="text-[10px] text-zinc-500">Immediate action required</span>
          </CardContent>
        </Card>

        <Card className="border-orange-500/30 bg-orange-500/5">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-zinc-400">High Risk</span>
              <Lock className="h-4 w-4 text-orange-400" />
            </div>
            <p className="mt-2 font-mono text-2xl font-bold text-orange-400">
              {stats?.high ?? 0}
            </p>
            <span className="text-[10px] text-zinc-500">Restricted access</span>
          </CardContent>
        </Card>

        <Card className="border-amber-500/30 bg-amber-500/5">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-zinc-400">Suspicious</span>
              <AlertTriangle className="h-4 w-4 text-amber-400" />
            </div>
            <p className="mt-2 font-mono text-2xl font-bold text-amber-400">
              {stats?.medium ?? 0}
            </p>
            <span className="text-[10px] text-zinc-500">Warning alerts</span>
          </CardContent>
        </Card>

        <Card className="border-rose-500/30 bg-rose-500/5">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-zinc-400">Blocked</span>
              <ShieldAlert className="h-4 w-4 text-rose-400" />
            </div>
            <p className="mt-2 font-mono text-2xl font-bold text-rose-400">
              {stats?.blocked ?? 0}
            </p>
            <span className="text-[10px] text-zinc-500">Prevented threats</span>
          </CardContent>
        </Card>

        <Card className="border-purple-500/30 bg-purple-500/5">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-zinc-400">Quarantined</span>
              <Archive className="h-4 w-4 text-purple-400" />
            </div>
            <p className="mt-2 font-mono text-2xl font-bold text-purple-400">
              {stats?.quarantined ?? 0}
            </p>
            <span className="text-[10px] text-zinc-500">Isolated phishing</span>
          </CardContent>
        </Card>

        <Card className="border-emerald-500/30 bg-emerald-500/5">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-zinc-400">Resolved</span>
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
            </div>
            <p className="mt-2 font-mono text-2xl font-bold text-emerald-400">
              {stats?.resolved ?? 0}
            </p>
            <span className="text-[10px] text-zinc-500">Incidents closed</span>
          </CardContent>
        </Card>
      </div>

      {/* ── Filters & Search ── */}
      <Card className="border-zinc-800/60 bg-zinc-900/60">
        <CardContent className="p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-zinc-500" />
              <Input
                placeholder="Search incident number, type, URL..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8 h-9 border-zinc-800 bg-zinc-950 text-xs text-zinc-200"
              />
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="h-9 w-[130px] border-zinc-800 bg-zinc-950 text-xs">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent className="border-zinc-800 bg-zinc-950 text-xs">
                  <SelectItem value="ALL">All Statuses</SelectItem>
                  <SelectItem value="OPEN">Open</SelectItem>
                  <SelectItem value="REVIEWING">Reviewing</SelectItem>
                  <SelectItem value="RESOLVED">Resolved</SelectItem>
                  <SelectItem value="FALSE_POSITIVE">False Positive</SelectItem>
                </SelectContent>
              </Select>

              <Select value={severityFilter} onValueChange={setSeverityFilter}>
                <SelectTrigger className="h-9 w-[130px] border-zinc-800 bg-zinc-950 text-xs">
                  <SelectValue placeholder="Severity" />
                </SelectTrigger>
                <SelectContent className="border-zinc-800 bg-zinc-950 text-xs">
                  <SelectItem value="ALL">All Severities</SelectItem>
                  <SelectItem value="CRITICAL">Critical</SelectItem>
                  <SelectItem value="HIGH">High</SelectItem>
                  <SelectItem value="MEDIUM">Medium</SelectItem>
                  <SelectItem value="SAFE">Safe</SelectItem>
                </SelectContent>
              </Select>

              <Select value={actionFilter} onValueChange={setActionFilter}>
                <SelectTrigger className="h-9 w-[130px] border-zinc-800 bg-zinc-950 text-xs">
                  <SelectValue placeholder="Action" />
                </SelectTrigger>
                <SelectContent className="border-zinc-800 bg-zinc-950 text-xs">
                  <SelectItem value="ALL">All Actions</SelectItem>
                  <SelectItem value="BLOCK">Block</SelectItem>
                  <SelectItem value="QUARANTINE">Quarantine</SelectItem>
                  <SelectItem value="RESTRICT">Restrict</SelectItem>
                  <SelectItem value="FLAG">Flag</SelectItem>
                  <SelectItem value="WARN">Warn</SelectItem>
                  <SelectItem value="ALLOW">Allow</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ── Incidents Table ── */}
      <Card className="border-zinc-800/60 bg-zinc-900/60 overflow-hidden">
        <CardHeader className="p-4 border-b border-zinc-800/80">
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-zinc-400 flex items-center justify-between">
            <span>Security Incident Log ({filteredIncidents.length})</span>
            <span className="text-[11px] font-normal lowercase text-zinc-500">
              real-time prevention stream
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="flex h-40 items-center justify-center text-sm text-zinc-500">
              <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> Loading incident stream...
            </div>
          ) : filteredIncidents.length === 0 ? (
            <div className="flex h-40 flex-col items-center justify-center text-center p-6 text-zinc-500">
              <ShieldCheck className="h-8 w-8 text-zinc-600 mb-2" />
              <p className="text-sm font-medium text-zinc-400">No security incidents found</p>
              <p className="text-xs text-zinc-600 mt-1">
                When the Prevention Engine blocks or quarantines suspicious inputs, incidents will appear here.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-zinc-800 bg-zinc-950/60 font-medium uppercase text-zinc-400 text-[10px] tracking-wider">
                  <tr>
                    <th className="px-4 py-3">Incident #</th>
                    <th className="px-4 py-3">Threat Type</th>
                    <th className="px-4 py-3">Reference / Target</th>
                    <th className="px-4 py-3">Risk</th>
                    <th className="px-4 py-3">Action</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Time</th>
                    <th className="px-4 py-3 text-right">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/60">
                  {filteredIncidents.map((incident) => (
                    <tr key={incident.id} className="hover:bg-zinc-800/30 transition-colors">
                      <td className="px-4 py-3 font-mono font-bold text-cyan-400">
                        {incident.incident_number}
                      </td>
                      <td className="px-4 py-3 text-zinc-200 capitalize">
                        {incident.threat_type.replace(/_/g, ' ')}
                      </td>
                      <td className="px-4 py-3 font-mono text-zinc-400 max-w-[200px] truncate" title={incident.input_reference || ''}>
                        {incident.input_reference || 'N/A'}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={cn(
                            'font-mono font-bold',
                            incident.risk_score >= 81 ? 'text-red-400' : incident.risk_score >= 61 ? 'text-orange-400' : incident.risk_score >= 31 ? 'text-amber-400' : 'text-emerald-400'
                          )}
                        >
                          {incident.risk_score}%
                        </span>
                      </td>
                      <td className="px-4 py-3">{getActionBadge(incident.action)}</td>
                      <td className="px-4 py-3">{getStatusBadge(incident.status)}</td>
                      <td className="px-4 py-3 text-zinc-500 font-mono text-[11px]">
                        {new Date(incident.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Link href={`/security/${incident.incident_number}`}>
                          <Button size="sm" variant="ghost" className="h-7 text-xs text-cyan-400 hover:text-cyan-300 hover:bg-cyan-500/10">
                            Inspect
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
        </CardContent>
      </Card>
    </div>
  );
}
