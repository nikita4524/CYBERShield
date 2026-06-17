'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { IoTDeviceType, RegisterIoTDeviceRequest } from '@/lib/types';
import { Plus } from 'lucide-react';

interface RegisterDeviceDialogProps {
  onRegister: (payload: RegisterIoTDeviceRequest) => Promise<void>;
}

export function RegisterDeviceDialog({ onRegister }: RegisterDeviceDialogProps) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [name, setName] = useState('');
  const [location, setLocation] = useState('');
  const [macAddress, setMacAddress] = useState('');
  const [type, setType] = useState<IoTDeviceType>('camera');

  const reset = () => {
    setName('');
    setLocation('');
    setMacAddress('');
    setType('camera');
  };

  const handleSubmit = async () => {
    if (!name.trim() || !location.trim()) return;
    setLoading(true);
    try {
      await onRegister({
        name: name.trim(),
        location: location.trim(),
        type,
        mac_address: macAddress.trim() || undefined,
      });
      reset();
      setOpen(false);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button className="gap-1.5 bg-cyan-600 hover:bg-cyan-500">
          <Plus className="h-4 w-4" />
          Register device
        </Button>
      </DialogTrigger>
      <DialogContent className="border-zinc-800 bg-zinc-950">
        <DialogHeader>
          <DialogTitle>Register IoT device</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <div className="space-y-2">
            <Label htmlFor="device-name">Device name</Label>
            <Input
              id="device-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Front Door Camera"
            />
          </div>
          <div className="space-y-2">
            <Label>Device type</Label>
            <Select value={type} onValueChange={(v) => setType(v as IoTDeviceType)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="camera">Camera</SelectItem>
                <SelectItem value="plug">Smart plug</SelectItem>
                <SelectItem value="router">Router</SelectItem>
                <SelectItem value="speaker">Speaker</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="device-location">Location</Label>
            <Input
              id="device-location"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="Living Room"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="device-mac">MAC address (optional)</Label>
            <Input
              id="device-mac"
              value={macAddress}
              onChange={(e) => setMacAddress(e.target.value)}
              placeholder="AA:BB:CC:DD:EE:FF"
            />
          </div>
          <Button
            className="w-full bg-cyan-600 hover:bg-cyan-500"
            onClick={handleSubmit}
            disabled={loading || !name.trim() || !location.trim()}
          >
            {loading ? 'Registering…' : 'Register'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
