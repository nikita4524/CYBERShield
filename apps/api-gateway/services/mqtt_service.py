"""
MQTT subscriber for simulated IoT telemetry.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Dict, Optional

from config import settings
from database import SessionLocal
from services.iot_service import process_telemetry

logger = logging.getLogger(__name__)


class MQTTService:
    def __init__(self):
        self._client = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> None:
        if not settings.MQTT_ENABLED:
            logger.info("MQTT disabled — skipping subscriber startup")
            return

        if self._running:
            return

        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            logger.warning("paho-mqtt not installed — MQTT ingest disabled")
            return

        self._running = True
        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=settings.MQTT_CLIENT_ID,
        )

        def on_connect(client, userdata, flags, reason_code, properties=None):
            if reason_code == 0 or str(reason_code) == "Success":
                client.subscribe(settings.MQTT_TOPIC_TELEMETRY)
                logger.info("MQTT connected; subscribed to %s", settings.MQTT_TOPIC_TELEMETRY)
            else:
                logger.error("MQTT connection failed: %s", reason_code)

        def on_message(client, userdata, msg):
            try:
                payload = json.loads(msg.payload.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                logger.warning("Invalid MQTT payload: %s", exc)
                return

            if not isinstance(payload, dict):
                logger.warning("MQTT payload must be a JSON object")
                return

            db = SessionLocal()
            try:
                process_telemetry(db, payload)
            except Exception:
                logger.exception("Failed to process MQTT telemetry")
                db.rollback()
            finally:
                db.close()

        client.on_connect = on_connect
        client.on_message = on_message

        def _run():
            try:
                client.connect(
                    settings.MQTT_BROKER_HOST,
                    settings.MQTT_BROKER_PORT,
                    keepalive=60,
                )
                client.loop_forever()
            except Exception:
                logger.exception("MQTT subscriber stopped unexpectedly")
                self._running = False

        self._client = client
        self._thread = threading.Thread(target=_run, name="mqtt-subscriber", daemon=True)
        self._thread.start()
        logger.info(
            "MQTT subscriber starting on %s:%s",
            settings.MQTT_BROKER_HOST,
            settings.MQTT_BROKER_PORT,
        )

    def stop(self) -> None:
        if self._client:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                logger.exception("Error stopping MQTT client")
        self._running = False
        self._client = None

    def publish_test_message(self, payload: Dict[str, Any]) -> bool:
        """Publish a telemetry message (used by tests / dev helpers)."""
        if not settings.MQTT_ENABLED:
            process_telemetry(SessionLocal(), payload)
            return True

        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            db = SessionLocal()
            try:
                process_telemetry(db, payload)
            finally:
                db.close()
            return True

        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"{settings.MQTT_CLIENT_ID}-pub",
        )
        try:
            client.connect(settings.MQTT_BROKER_HOST, settings.MQTT_BROKER_PORT, keepalive=30)
            client.loop_start()
            result = client.publish(
                settings.MQTT_TOPIC_TELEMETRY,
                json.dumps(payload),
                qos=1,
            )
            result.wait_for_publish(timeout=5)
            client.loop_stop()
            client.disconnect()
            return result.rc == 0
        except Exception:
            logger.exception("Failed to publish MQTT message")
            return False


mqtt_service = MQTTService()
