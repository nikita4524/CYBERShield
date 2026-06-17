'use client';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { IoTAlert } from '@/lib/types';
import { cn } from '@/lib/utils';
import { AlertTriangle } from 'lucide-react';

const SEVERITY_STYLES = {
  low: 'border-zinc-600 text-zinc-400',
  medium: 'border-amber-500/40 text-amber-400',
  high: 'border-red-500/40 text-red-400',
} as const;

interface AlertsListProps {
  alerts: IoTAlert[];
  onResolve: (alertId: string) => void;
  resolvingId?: string | null;
}

export function AlertsList({ alerts, onResolve, resolvingId }: AlertsListProps) {
  return (
    <Card className="border-zinc-800/60 bg-zinc-900/70">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base text-zinc-200">
          <AlertTriangle className="h-4 w-4 text-amber-400" />
          Security alerts
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {alerts.length === 0 ? (
          <p className="text-sm text-zinc-500">No open alerts. Devices look healthy.</p>
        ) : (
          alerts.map((alert) => (
            <div
              key={alert.id}
              className="rounded-lg border border-zinc-800/80 bg-zinc-950/50 p-3 space-y-2"
            >
              <div className="flex flex-wrap items-center gap-2">
                <Badge
                  variant="outline"
                  className={cn('text-[10px]', SEVERITY_STYLES[alert.severity])}
                >
                  {alert.severity}
                </Badge>
                <span className="text-[11px] font-mono text-zinc-500">
                  {alert.rule_triggered}
                </span>
                {alert.device_name && (
                  <span className="text-[11px] text-zinc-400">{alert.device_name}</span>
                )}
              </div>
              <p className="text-xs leading-relaxed text-zinc-300">{alert.description}</p>
              <div className="flex items-center justify-between gap-2">
                <span className="text-[10px] text-zinc-600">
                  {new Date(alert.created_at).toLocaleString()}
                </span>
                {!alert.is_resolved && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 text-[11px] border-zinc-700"
                    onClick={() => onResolve(alert.id)}
                    disabled={resolvingId === alert.id}
                  >
                    Resolve
                  </Button>
                )}
              </div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}
