'use client';

/**
 * SimulatorPanel — Simulated IoT Telemetry UI
 *
 * This component is for DEMONSTRATION and TESTING purposes only.
 * It sends synthetic telemetry events to the backend rule engine
 * to simulate security scenarios on virtual (non-physical) IoT devices.
 *
 * No real hardware is involved at any point.
 */

import { useCallback, useEffect, useState } from 'react';
import { Activity, AlertTriangle, CheckCircle2, ChevronDown, FlaskConical, Loader2, RefreshCw, ShieldAlert, ShieldCheck, Zap } from 'lucide-react';
import { toast } from 'sonner';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import { RISK_CONFIG } from '@/lib/constants';
import type {
  IoTDevice,
  IoTEventType,
  SimEventType,
  TelemetryIngestResponse,
  IoTTelemetryRecord,
} from '@/lib/types';

/* ─────────────────────────────────────────────────────────────
   Simulation scenario definitions
   Each scenario maps to a low-level event_type + data payload
   that the existing backend rule engine evaluates.
───────────────────────────────────────────────────────────── */
interface SimScenario {
  id: SimEventType;
  label: string;
  description: string;
  event_type: IoTEventType;
  buildData: (device: IoTDevice) => Record<string, unknown>;
  /** Optional override MAC for unknown-device scenario */
  mac_address?: string;
}

const SCENARIOS: SimScenario[] = [
  {
    id: 'normal_activity',
    label: 'Normal Activity',
    description: 'Routine device connection — no threats expected',
    event_type: 'connection',
    buildData: () => ({ status: 'ok', signal_strength: -55 }),
  },
  {
    id: 'brute_force',
    label: 'Brute Force Attempt',
    description: 'Multiple failed login attempts → triggers brute_force rule (+25)',
    event_type: 'connection',
    buildData: () => ({ failed_logins: 8, source_ip: '192.168.1.100' }),
  },
  {
    id: 'suspicious_dns',
    label: 'Suspicious DNS',
    description: 'Device queries a known malicious domain → triggers suspicious_dns rule (+35)',
    event_type: 'traffic',
    buildData: () => ({ dns_query: 'malware-c2.xyz', bytes_sent: 512 }),
  },
  {
    id: 'unknown_device',
    label: 'Unknown Device',
    description: 'Telemetry from an unregistered MAC → triggers unknown_device_alert rule (+40)',
    event_type: 'connection',
    buildData: () => ({ mac_address: 'DE:AD:BE:EF:00:01', status: 'new' }),
    mac_address: 'DE:AD:BE:EF:00:01',
  },
  {
    id: 'network_anomaly',
    label: 'Network Anomaly',
    description: 'High failed-login count combined with suspicious DNS traffic',
    event_type: 'traffic',
    buildData: () => ({
      dns_query: 'botnet-command.tk',
      failed_logins: 6,
      bytes_sent: 8192,
    }),
  },
  {
    id: 'device_offline',
    label: 'Device Goes Offline',
    description: 'Simulates no telemetry — the dashboard polling will raise a device_offline alert after 15 min. This sends a normal ping to demonstrate the flow.',
    event_type: 'connection',
    buildData: () => ({ status: 'ping', note: 'last_seen update only' }),
  },
];

/* ─────────────────────────────────────────────────────────────
   Helpers
───────────────────────────────────────────────────────────── */
function RiskBadge({ label }: { label: 'safe' | 'suspicious' | 'dangerous' }) {
  const cfg = RISK_CONFIG[label];
  const Icon = label === 'safe' ? ShieldCheck : label === 'suspicious' ? AlertTriangle : ShieldAlert;
  return (
    <Badge
      variant="outline"
      className={cn('gap-1 text-[10px] capitalize', cfg.text, cfg.border)}
    >
      <Icon className="h-3 w-3" />
      {cfg.label}
    </Badge>
  );
}

function EventTypeBadge({ type }: { type: string }) {
  const colours: Record<string, string> = {
    connection: 'border-blue-500/40 text-blue-400',
    motion:     'border-purple-500/40 text-purple-400',
    traffic:    'border-amber-500/40 text-amber-400',
  };
  return (
    <Badge variant="outline" className={cn('text-[10px]', colours[type] ?? 'border-zinc-600 text-zinc-400')}>
      {type}
    </Badge>
  );
}

/* ─────────────────────────────────────────────────────────────
   SimulatorPanel
───────────────────────────────────────────────────────────── */
interface SimulatorPanelProps {
  devices: IoTDevice[];
  onSimulated: () => void; // ask parent to refresh devices + alerts
}

export function SimulatorPanel({ devices, onSimulated }: SimulatorPanelProps) {
  const [selectedDeviceId, setSelectedDeviceId] = useState<string>('');
  const [selectedScenarioId, setSelectedScenarioId] = useState<SimEventType>('normal_activity');
  const [simulating, setSimulating] = useState(false);
  const [lastResult, setLastResult] = useState<TelemetryIngestResponse | null>(null);

  // Telemetry history
  const [history, setHistory] = useState<IoTTelemetryRecord[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  // Auto-select first device when list arrives
  useEffect(() => {
    if (devices.length > 0 && !selectedDeviceId) {
      setSelectedDeviceId(devices[0].id);
    }
  }, [devices, selectedDeviceId]);

  const loadHistory = useCallback(async (deviceId: string) => {
    if (!deviceId) return;
    setHistoryLoading(true);
    try {
      const res = await api.getIoTTelemetry(deviceId, 1, 10);
      setHistory(res.items);
    } catch {
      // History panel is non-critical; silently clear on error
      setHistory([]);
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  // Reload history when device selection changes
  useEffect(() => {
    if (selectedDeviceId) {
      setHistory([]);
      loadHistory(selectedDeviceId);
    }
  }, [selectedDeviceId, loadHistory]);

  async function handleSimulate() {
    if (!selectedDeviceId) {
      toast.error('Select a device first.');
      return;
    }
    const scenario = SCENARIOS.find((s) => s.id === selectedScenarioId);
    if (!scenario) return;

    const device = devices.find((d) => d.id === selectedDeviceId);
    if (!device) return;

    setSimulating(true);
    setLastResult(null);
    try {
      const payload = {
        device_id: selectedDeviceId,
        event_type: scenario.event_type,
        data: scenario.buildData(device),
        ...(scenario.mac_address ? { mac_address: scenario.mac_address } : {}),
      };

      const result = await api.simulateTelemetry(payload);
      setLastResult(result);

      if (result.alerts_created > 0) {
        toast.warning(
          `${result.alerts_created} alert${result.alerts_created > 1 ? 's' : ''} triggered — risk score: ${result.risk_score}/100`,
          { duration: 5000 }
        );
      } else {
        toast.success(`Event simulated — no new alerts. Risk score: ${result.risk_score}/100`);
      }

      // Refresh dashboard + history
      onSimulated();
      await loadHistory(selectedDeviceId);
    } catch (err: any) {
      toast.error(err?.message ?? 'Simulation failed.');
    } finally {
      setSimulating(false);
    }
  }

  const selectedScenario = SCENARIOS.find((s) => s.id === selectedScenarioId);

  return (
    <Card className="border-zinc-800/60 bg-zinc-900/70">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base text-zinc-200">
          <FlaskConical className="h-4 w-4 text-cyan-400" />
          Telemetry Simulator
          <Badge
            variant="outline"
            className="ml-auto text-[10px] border-cyan-600/40 text-cyan-400 font-normal"
          >
            Simulation Mode — Virtual IoT Devices
          </Badge>
        </CardTitle>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* ── Device selector ── */}
        <div className="space-y-1.5">
          <label className="text-xs text-zinc-400">Virtual Device</label>
          {devices.length === 0 ? (
            <p className="text-xs text-zinc-500">
              No devices registered. Use <strong>Load demo devices</strong> or register one above.
            </p>
          ) : (
            <Select value={selectedDeviceId} onValueChange={setSelectedDeviceId}>
              <SelectTrigger className="h-9 border-zinc-700 bg-zinc-800/60 text-sm text-zinc-200">
                <SelectValue placeholder="Select a device…" />
              </SelectTrigger>
              <SelectContent className="border-zinc-700 bg-zinc-900">
                {devices.map((d) => (
                  <SelectItem key={d.id} value={d.id}>
                    <span className="capitalize">{d.name}</span>
                    <span className="ml-2 text-zinc-500 text-xs">({d.type})</span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>

        {/* ── Scenario selector ── */}
        <div className="space-y-1.5">
          <label className="text-xs text-zinc-400">Simulation Scenario</label>
          <Select
            value={selectedScenarioId}
            onValueChange={(v) => setSelectedScenarioId(v as SimEventType)}
          >
            <SelectTrigger className="h-9 border-zinc-700 bg-zinc-800/60 text-sm text-zinc-200">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="border-zinc-700 bg-zinc-900">
              {SCENARIOS.map((s) => (
                <SelectItem key={s.id} value={s.id}>
                  {s.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {selectedScenario && (
            <p className="text-[11px] text-zinc-500 leading-relaxed">
              {selectedScenario.description}
            </p>
          )}
        </div>

        {/* ── Simulate button ── */}
        <Button
          className="w-full gap-2 bg-cyan-700 hover:bg-cyan-600 text-white"
          onClick={handleSimulate}
          disabled={simulating || devices.length === 0}
        >
          {simulating ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Simulating…
            </>
          ) : (
            <>
              <Zap className="h-4 w-4" />
              Simulate Event
            </>
          )}
        </Button>

        {/* ── Last result ── */}
        {lastResult && (
          <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-3 space-y-2">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
              Last Result
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <RiskBadge label={lastResult.risk_label} />
              <span className="text-xs text-zinc-300">
                Score: <strong>{lastResult.risk_score}</strong>/100
              </span>
              <span className="text-xs text-zinc-400">
                Alerts created:{' '}
                <strong className={lastResult.alerts_created > 0 ? 'text-amber-400' : 'text-emerald-400'}>
                  {lastResult.alerts_created}
                </strong>
              </span>
            </div>
            <p className="text-[10px] font-mono text-zinc-600">
              telemetry_id: {lastResult.telemetry_id}
            </p>
          </div>
        )}

        {/* ── Telemetry history ── */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold uppercase tracking-wider text-zinc-500">
              Recent Events
            </p>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 gap-1 text-[11px] text-zinc-600 hover:text-zinc-300"
              onClick={() => selectedDeviceId && loadHistory(selectedDeviceId)}
              disabled={historyLoading || !selectedDeviceId}
            >
              <RefreshCw className={cn('h-3 w-3', historyLoading && 'animate-spin')} />
              Refresh
            </Button>
          </div>

          {historyLoading ? (
            <div className="flex items-center gap-2 py-3 text-xs text-zinc-500">
              <Loader2 className="h-3 w-3 animate-spin" />
              Loading…
            </div>
          ) : history.length === 0 ? (
            <p className="py-2 text-xs text-zinc-600">
              No telemetry recorded yet for this device.
            </p>
          ) : (
            <div className="space-y-1.5 max-h-52 overflow-y-auto pr-1">
              {history.map((row) => (
                <div
                  key={row.id}
                  className="flex items-start gap-2 rounded-md border border-zinc-800/60 bg-zinc-950/40 px-3 py-2"
                >
                  {/* alert indicator */}
                  <div className="mt-0.5 shrink-0">
                    {row.alert_triggered ? (
                      <AlertTriangle className="h-3 w-3 text-amber-400" />
                    ) : (
                      <CheckCircle2 className="h-3 w-3 text-emerald-500" />
                    )}
                  </div>

                  <div className="min-w-0 flex-1 space-y-0.5">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <EventTypeBadge type={row.event_type} />
                      <span className="text-[10px] text-zinc-600">
                        {new Date(row.created_at).toLocaleTimeString()}
                      </span>
                    </div>
                    {/* Show up to 2 key data fields, not raw dumps */}
                    <p className="truncate text-[10px] font-mono text-zinc-500">
                      {Object.entries(row.data)
                        .slice(0, 2)
                        .map(([k, v]) => `${k}: ${v}`)
                        .join(' · ')}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
