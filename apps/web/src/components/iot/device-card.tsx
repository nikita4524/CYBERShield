'use client';

import { Camera, Plug, Router, Speaker, Wifi, WifiOff } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { RISK_CONFIG } from '@/lib/constants';
import type { IoTDevice } from '@/lib/types';
import { cn } from '@/lib/utils';

const TYPE_ICONS = {
  camera: Camera,
  plug: Plug,
  router: Router,
  speaker: Speaker,
} as const;

function formatLastSeen(value?: string | null) {
  if (!value) return 'Never';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Unknown';
  return date.toLocaleString();
}

interface DeviceCardProps {
  device: IoTDevice;
  onDelete: (id: string) => void;
  deleting?: boolean;
}

export function DeviceCard({ device, onDelete, deleting }: DeviceCardProps) {
  const Icon = TYPE_ICONS[device.type] ?? Router;
  const risk = RISK_CONFIG[device.risk_label];
  const isOnline = device.status === 'online';

  return (
    <Card className="border-zinc-800/60 bg-zinc-900/70 backdrop-blur-sm">
      <CardContent className="p-5 space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-cyan-500/10">
              <Icon className="h-5 w-5 text-cyan-400" />
            </div>
            <div>
              <h3 className="font-semibold text-zinc-100">{device.name}</h3>
              <p className="text-xs text-zinc-500 capitalize">
                {device.type} · {device.location}
              </p>
            </div>
          </div>
          <Badge
            variant="outline"
            className={cn(
              'gap-1 text-[10px]',
              isOnline
                ? 'border-emerald-500/40 text-emerald-400'
                : 'border-zinc-600 text-zinc-400',
            )}
          >
            {isOnline ? (
              <Wifi className="h-3 w-3" />
            ) : (
              <WifiOff className="h-3 w-3" />
            )}
            {device.status}
          </Badge>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-zinc-500">Risk score</span>
            <span className={cn('font-semibold', risk.text)}>
              {device.risk_score}/100 · {risk.label}
            </span>
          </div>
          <Progress value={device.risk_score} className="h-2" />
        </div>

        <div className="flex items-center justify-between text-[11px] text-zinc-500">
          <span>Last seen: {formatLastSeen(device.last_seen)}</span>
          {device.open_alerts > 0 && (
            <Badge variant="outline" className="border-amber-500/40 text-amber-400">
              {device.open_alerts} alert{device.open_alerts > 1 ? 's' : ''}
            </Badge>
          )}
        </div>

        {device.mac_address && (
          <p className="text-[10px] font-mono text-zinc-600">{device.mac_address}</p>
        )}

        <Button
          variant="outline"
          size="sm"
          className="w-full border-zinc-700 text-zinc-400 hover:text-red-400 hover:border-red-500/40"
          onClick={() => onDelete(device.id)}
          disabled={deleting}
        >
          Remove device
        </Button>
      </CardContent>
    </Card>
  );
}
