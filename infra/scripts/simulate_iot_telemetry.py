#!/usr/bin/env python3
"""
Simulate IoT telemetry for CyberShield AI (no hardware required).

Usage:
  export ACCESS_TOKEN=<jwt>
  export USER_ID=<uuid>
  python infra/scripts/simulate_iot_telemetry.py

Optional env:
  MQTT_HOST=localhost
  MQTT_PORT=1883
  API_URL=http://localhost:8000/api/v1
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("Install paho-mqtt: pip install paho-mqtt")
    sys.exit(1)

TOPIC = os.getenv("MQTT_TOPIC", "cybershield/telemetry")
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
API_URL = os.getenv("API_URL", "http://localhost:8000/api/v1")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN", "")
USER_ID = os.getenv("USER_ID", "")


def fetch_devices() -> list[dict]:
    if not ACCESS_TOKEN:
        return []
    req = urllib.request.Request(
        f"{API_URL}/iot/devices",
        headers={"Authorization": f"Bearer {ACCESS_TOKEN}"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
    return data.get("items", [])


def publish(client: mqtt.Client, payload: dict) -> None:
    payload["timestamp"] = datetime.now(timezone.utc).isoformat()
    if USER_ID:
        payload.setdefault("user_id", USER_ID)
    client.publish(TOPIC, json.dumps(payload), qos=1)
    print(f"→ {payload.get('event_type')} | device={payload.get('device_id', 'unknown')}")


def main() -> None:
    devices = fetch_devices()
    if not devices:
        print("No devices from API — using synthetic MAC-only events.")
        print("Tip: log in, open /dashboard/iot, click 'Load demo devices', set ACCESS_TOKEN + USER_ID.")

    router = next((d for d in devices if d.get("type") == "router"), devices[0] if devices else None)
    camera = next((d for d in devices if d.get("type") == "camera"), None)

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="cybershield-simulator",
    )
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_start()

    scenarios = []

    if router:
        scenarios.extend([
            (
                "normal traffic",
                {
                    "device_id": router["id"],
                    "mac_address": router.get("mac_address"),
                    "event_type": "traffic",
                    "data": {"bytes_out": 1200, "dns_query": "google.com"},
                },
            ),
            (
                "suspicious DNS",
                {
                    "device_id": router["id"],
                    "mac_address": router.get("mac_address"),
                    "event_type": "traffic",
                    "data": {"dns_query": "malware-c2.xyz", "bytes_out": 9000},
                },
            ),
            (
                "brute force",
                {
                    "device_id": router["id"],
                    "mac_address": router.get("mac_address"),
                    "event_type": "connection",
                    "data": {"failed_logins": 12},
                },
            ),
        ])

    if camera:
        scenarios.append(
            (
                "motion",
                {
                    "device_id": camera["id"],
                    "mac_address": camera.get("mac_address"),
                    "event_type": "motion",
                    "data": {"zone": "entrance", "confidence": 0.91},
                },
            )
        )

    scenarios.append(
        (
            "unknown device",
            {
                "device_id": None,
                "mac_address": "FF:EE:DD:CC:BB:99",
                "event_type": "connection",
                "data": {"hostname": " mystery-cam"},
            },
        )
    )

    print(f"Publishing to mqtt://{MQTT_HOST}:{MQTT_PORT}/{TOPIC}")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            for label, payload in scenarios:
                print(f"[{label}]")
                publish(client, payload)
                time.sleep(4)
            print("--- cycle complete ---\n")
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
