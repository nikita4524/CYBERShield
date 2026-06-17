'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { Cpu, RefreshCw, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import { PageHeader } from '@/components/shared/page-header';
import { DeviceCard } from '@/components/iot/device-card';
import { RegisterDeviceDialog } from '@/components/iot/register-device-dialog';
import { AlertsList } from '@/components/iot/alerts-list';
import { Button } from '@/components/ui/button';
import { LoadingSpinner } from '@/components/shared/loading-spinner';
import { api } from '@/lib/api';
import type { IoTAlert, IoTDevice, RegisterIoTDeviceRequest } from '@/lib/types';
import { cn } from '@/lib/utils';

const POLL_INTERVAL_MS = 15_000;

export default function IoTDashboardPage() {
  const [devices, setDevices] = useState<IoTDevice[]>([]);
  const [alerts, setAlerts] = useState<IoTAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [resolvingId, setResolvingId] = useState<string | null>(null);
  const [seeding, setSeeding] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadData = useCallback(async (showSpinner = false) => {
    if (showSpinner) setRefreshing(true);
    try {
      const [deviceRes, alertRes] = await Promise.all([
        api.getIoTDevices(),
        api.getIoTAlerts(1, 20, false),
      ]);
      setDevices(deviceRes.items ?? []);
      setAlerts(alertRes.items ?? []);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to load IoT data');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    pollRef.current = setInterval(() => loadData(), POLL_INTERVAL_MS);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [loadData]);

  const handleRegister = async (payload: RegisterIoTDeviceRequest) => {
    await api.registerIoTDevice(payload);
    toast.success('Device registered');
    await loadData(true);
  };

  const handleDelete = async (deviceId: string) => {
    setDeletingId(deviceId);
    try {
      await api.deleteIoTDevice(deviceId);
      toast.success('Device removed');
      await loadData(true);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete device');
    } finally {
      setDeletingId(null);
    }
  };

  const handleResolve = async (alertId: string) => {
    setResolvingId(alertId);
    try {
      await api.resolveIoTAlert(alertId);
      toast.success('Alert resolved');
      await loadData(true);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to resolve alert');
    } finally {
      setResolvingId(null);
    }
  };

  const handleSeedDemo = async () => {
    setSeeding(true);
    try {
      const res = await api.seedIoTDemoDevices();
      toast.success(res.message);
      await loadData(true);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to seed demo devices');
    } finally {
      setSeeding(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <LoadingSpinner label="Loading IoT dashboard…" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="IoT Security"
        description="Monitor simulated smart home devices, telemetry alerts, and risk scores."
        icon={Cpu}
      >
        <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              className="gap-1.5 border-zinc-700"
              onClick={() => loadData(true)}
              disabled={refreshing}
            >
              <RefreshCw className={cn('h-4 w-4', refreshing && 'animate-spin')} />
              Refresh
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="gap-1.5 border-zinc-700"
              onClick={handleSeedDemo}
              disabled={seeding}
            >
              <Sparkles className="h-4 w-4" />
              Load demo devices
            </Button>
            <RegisterDeviceDialog onRegister={handleRegister} />
        </div>
      </PageHeader>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="xl:col-span-2 space-y-4">
          {devices.length === 0 ? (
            <div className="rounded-lg border border-dashed border-zinc-800 p-8 text-center text-sm text-zinc-500">
              No devices yet. Click <strong>Load demo devices</strong> or register your own.
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {devices.map((device, i) => (
                <motion.div
                  key={device.id}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.05 }}
                >
                  <DeviceCard
                    device={device}
                    onDelete={handleDelete}
                    deleting={deletingId === device.id}
                  />
                </motion.div>
              ))}
            </div>
          )}
        </div>

        <AlertsList
          alerts={alerts}
          onResolve={handleResolve}
          resolvingId={resolvingId}
        />
      </div>
    </div>
  );
}
