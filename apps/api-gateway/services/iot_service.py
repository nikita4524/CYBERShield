"""
IoT device management, telemetry ingest, and alert lifecycle.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from models.iot import IoTAlert, IoTDevice, IoTTelemetry
from models.user import User
from schemas.iot import DeviceRegisterRequest, DeviceResponse
from services.iot_rules import evaluate_telemetry_rules, offline_rule_match
from services.iot_scoring_service import iot_scoring_service

logger = logging.getLogger(__name__)

OFFLINE_THRESHOLD_MINUTES = 15
DEMO_DEVICES = [
    {
        "name": "Front Door Camera",
        "type": "camera",
        "location": "Entrance",
        "mac_address": "AA:BB:CC:11:22:01",
    },
    {
        "name": "Living Room Plug",
        "type": "plug",
        "location": "Living Room",
        "mac_address": "AA:BB:CC:11:22:02",
    },
    {
        "name": "Home Router",
        "type": "router",
        "location": "Study",
        "mac_address": "AA:BB:CC:11:22:03",
    },
    {
        "name": "Kitchen Speaker",
        "type": "speaker",
        "location": "Kitchen",
        "mac_address": "AA:BB:CC:11:22:04",
    },
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_mac(mac: Optional[str]) -> Optional[str]:
    if not mac:
        return None
    return mac.strip().upper()


def _device_to_response(device: IoTDevice, open_alerts: int = 0) -> DeviceResponse:
    return DeviceResponse(
        id=str(device.id),
        name=device.name,
        type=device.type,
        location=device.location,
        status=device.status,
        mac_address=device.mac_address,
        risk_score=device.risk_score,
        risk_label=device.risk_label,
        last_seen=device.last_seen,
        open_alerts=open_alerts,
        created_at=device.created_at,
    )


def _open_alert_count(db: Session, device_id: uuid.UUID) -> int:
    return (
        db.query(IoTAlert)
        .filter(
            IoTAlert.device_id == device_id,
            IoTAlert.is_resolved.is_(False),
        )
        .count()
    )


def _has_open_alert(db: Session, device_id: Optional[uuid.UUID], user_id: uuid.UUID, rule_id: str) -> bool:
    query = db.query(IoTAlert).filter(
        IoTAlert.user_id == user_id,
        IoTAlert.rule_triggered == rule_id,
        IoTAlert.is_resolved.is_(False),
    )
    if device_id:
        query = query.filter(IoTAlert.device_id == device_id)
    else:
        query = query.filter(IoTAlert.device_id.is_(None))
    return query.first() is not None


def _create_alert(
    db: Session,
    *,
    user_id: uuid.UUID,
    device_id: Optional[uuid.UUID],
    rule_match,
) -> IoTAlert:
    alert = IoTAlert(
        id=uuid.uuid4(),
        user_id=user_id,
        device_id=device_id,
        rule_triggered=rule_match.rule_id,
        severity=rule_match.severity,
        description=rule_match.description,
        is_resolved=False,
    )
    db.add(alert)
    return alert


def _recompute_device_risk(db: Session, device: IoTDevice) -> None:
    open_rules = [
        row[0]
        for row in db.query(IoTAlert.rule_triggered)
        .filter(
            IoTAlert.device_id == device.id,
            IoTAlert.is_resolved.is_(False),
        )
        .all()
    ]
    output = iot_scoring_service.compute(open_rules)
    device.risk_score = output.risk_score
    device.risk_label = output.risk_label


def register_device(db: Session, user: User, payload: DeviceRegisterRequest) -> DeviceResponse:
    device = IoTDevice(
        id=uuid.uuid4(),
        user_id=user.id,
        name=payload.name.strip(),
        type=payload.type.value,
        location=payload.location.strip(),
        mac_address=_normalize_mac(payload.mac_address),
        status="offline",
        risk_score=0,
        risk_label="safe",
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return _device_to_response(device, 0)


def list_devices(db: Session, user: User) -> List[DeviceResponse]:
    devices = (
        db.query(IoTDevice)
        .filter(IoTDevice.user_id == user.id)
        .order_by(IoTDevice.created_at.desc())
        .all()
    )

    threshold = _utcnow() - timedelta(minutes=OFFLINE_THRESHOLD_MINUTES)
    changed = False

    for device in devices:
        if device.last_seen and device.last_seen >= threshold:
            if device.status != "online":
                device.status = "online"
                changed = True
        elif device.last_seen:
            if device.status != "offline":
                device.status = "offline"
                changed = True
            if not _has_open_alert(db, device.id, user.id, "device_offline"):
                match = offline_rule_match(device.name)
                _create_alert(
                    db,
                    user_id=user.id,
                    device_id=device.id,
                    rule_match=match,
                )
                changed = True
                _recompute_device_risk(db, device)

    if changed:
        db.commit()
        for device in devices:
            db.refresh(device)

    return [
        _device_to_response(device, _open_alert_count(db, device.id))
        for device in devices
    ]


def delete_device(db: Session, user: User, device_id: str) -> bool:
    try:
        dev_uuid = uuid.UUID(device_id)
    except ValueError:
        return False

    device = (
        db.query(IoTDevice)
        .filter(IoTDevice.id == dev_uuid, IoTDevice.user_id == user.id)
        .first()
    )
    if not device:
        return False

    db.delete(device)
    db.commit()
    return True


def seed_demo_devices(db: Session, user: User) -> List[DeviceResponse]:
    created: List[DeviceResponse] = []
    for spec in DEMO_DEVICES:
        existing = (
            db.query(IoTDevice)
            .filter(
                IoTDevice.user_id == user.id,
                IoTDevice.mac_address == spec["mac_address"],
            )
            .first()
        )
        if existing:
            created.append(_device_to_response(existing, _open_alert_count(db, existing.id)))
            continue

        device = IoTDevice(
            id=uuid.uuid4(),
            user_id=user.id,
            name=spec["name"],
            type=spec["type"],
            location=spec["location"],
            mac_address=spec["mac_address"],
            status="offline",
            risk_score=0,
            risk_label="safe",
        )
        db.add(device)
        db.flush()
        created.append(_device_to_response(device, 0))

    db.commit()
    return created


def resolve_alert(db: Session, user: User, alert_id: str) -> Optional[IoTAlert]:
    try:
        alert_uuid = uuid.UUID(alert_id)
    except ValueError:
        return None

    alert = (
        db.query(IoTAlert)
        .filter(IoTAlert.id == alert_uuid, IoTAlert.user_id == user.id)
        .first()
    )
    if not alert:
        return None

    alert.is_resolved = True
    db.commit()

    if alert.device_id:
        device = db.query(IoTDevice).filter(IoTDevice.id == alert.device_id).first()
        if device:
            _recompute_device_risk(db, device)
            db.commit()

    db.refresh(alert)
    return alert


def list_alerts(
    db: Session,
    user: User,
    *,
    page: int = 1,
    limit: int = 20,
    severity: Optional[str] = None,
    is_resolved: Optional[bool] = None,
    device_id: Optional[str] = None,
) -> tuple[int, List[Dict[str, Any]]]:
    query = db.query(IoTAlert).filter(IoTAlert.user_id == user.id)

    if severity:
        query = query.filter(IoTAlert.severity == severity)
    if is_resolved is not None:
        query = query.filter(IoTAlert.is_resolved == is_resolved)
    if device_id:
        try:
            query = query.filter(IoTAlert.device_id == uuid.UUID(device_id))
        except ValueError:
            return 0, []

    total = query.count()
    rows = (
        query.order_by(IoTAlert.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    items: List[Dict[str, Any]] = []
    for alert in rows:
        device_name = None
        if alert.device_id:
            device = db.query(IoTDevice).filter(IoTDevice.id == alert.device_id).first()
            device_name = device.name if device else None

        items.append(
            {
                "id": str(alert.id),
                "device_id": str(alert.device_id) if alert.device_id else None,
                "device_name": device_name,
                "rule_triggered": alert.rule_triggered,
                "severity": alert.severity,
                "description": alert.description,
                "is_resolved": alert.is_resolved,
                "created_at": alert.created_at,
            }
        )

    return total, items


def _resolve_device(
    db: Session,
    *,
    device_id: Optional[str],
    mac_address: Optional[str],
    user_id: Optional[str],
) -> tuple[Optional[IoTDevice], Optional[uuid.UUID]]:
    device: Optional[IoTDevice] = None
    owner_id: Optional[uuid.UUID] = None

    if device_id:
        try:
            dev_uuid = uuid.UUID(device_id)
            device = db.query(IoTDevice).filter(IoTDevice.id == dev_uuid).first()
            if device:
                owner_id = device.user_id
        except ValueError:
            pass

    if not device and mac_address:
        mac = _normalize_mac(mac_address)
        device = db.query(IoTDevice).filter(IoTDevice.mac_address == mac).first()
        if device:
            owner_id = device.user_id

    if not owner_id and user_id:
        try:
            owner_id = uuid.UUID(user_id)
        except ValueError:
            owner_id = None

    return device, owner_id


def process_telemetry(db: Session, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ingest one telemetry message and run the rule engine.

    Accepts a flat dict with keys:
        device_id   – UUID string of the registered virtual device
        event_type  – connection | motion | traffic
        data        – free-form dict payload evaluated by the rule engine
        mac_address – optional, used for unknown-device detection
        user_id     – optional owner hint (not needed when device_id is present)
        timestamp   – optional ISO-8601 string; defaults to utcnow()

    Returns a dict that the HTTP endpoint serialises as TelemetryIngestResponse.
    Also called directly by the MQTT service (which ignores the return value).
    """
    event_type = payload.get("event_type")
    if event_type not in ("connection", "motion", "traffic"):
        logger.warning("Ignoring telemetry with invalid event_type: %s", event_type)
        return {"error": "invalid_event_type"}

    data = payload.get("data") or {}
    if not isinstance(data, dict):
        data = {}

    device_id = payload.get("device_id")
    mac_address = payload.get("mac_address") or data.get("mac_address")
    user_id_str = payload.get("user_id")

    device, owner_id = _resolve_device(
        db,
        device_id=str(device_id) if device_id else None,
        mac_address=str(mac_address) if mac_address else None,
        user_id=str(user_id_str) if user_id_str else None,
    )

    if not owner_id:
        logger.warning("Telemetry ignored — could not resolve device owner")
        return {"error": "owner_not_found"}

    timestamp_raw = payload.get("timestamp")
    event_time = _utcnow()
    if timestamp_raw:
        try:
            event_time = datetime.fromisoformat(str(timestamp_raw).replace("Z", "+00:00"))
        except ValueError:
            pass

    telemetry = IoTTelemetry(
        id=uuid.uuid4(),
        device_id=device.id if device else None,
        user_id=owner_id,
        event_type=event_type,
        data=data,
        created_at=event_time,
    )
    db.add(telemetry)
    telemetry_id = str(telemetry.id)

    if device:
        device.last_seen = event_time
        device.status = "online"
        # Auto-resolve any open device_offline alert since the device is now active
        if _has_open_alert(db, device.id, owner_id, "device_offline"):
            offline_alert = (
                db.query(IoTAlert)
                .filter(
                    IoTAlert.device_id == device.id,
                    IoTAlert.rule_triggered == "device_offline",
                    IoTAlert.is_resolved.is_(False),
                )
                .first()
            )
            if offline_alert:
                offline_alert.is_resolved = True

    matches = evaluate_telemetry_rules(
        event_type,
        data,
        device_known=device is not None,
        mac_address=str(mac_address) if mac_address else None,
    )

    alerts_created = 0
    for match in matches:
        if _has_open_alert(db, device.id if device else None, owner_id, match.rule_id):
            continue
        _create_alert(
            db,
            user_id=owner_id,
            device_id=device.id if device else None,
            rule_match=match,
        )
        alerts_created += 1

    if device:
        _recompute_device_risk(db, device)

    db.commit()

    risk_score = device.risk_score if device else 0
    risk_label = device.risk_label if device else "safe"

    return {
        "telemetry_id": telemetry_id,
        "device_id": str(device.id) if device else None,
        "event_type": event_type,
        "alerts_created": alerts_created,
        "risk_score": risk_score,
        "risk_label": risk_label,
    }


def get_telemetry_history(
    db: Session,
    user: User,
    *,
    device_id: str,
    page: int = 1,
    limit: int = 20,
) -> tuple[int, List[Dict[str, Any]]]:
    """
    Return paginated telemetry history for a device, annotated with whether
    each event triggered at least one alert (for the history panel).
    """
    try:
        dev_uuid = uuid.UUID(device_id)
    except ValueError:
        return 0, []

    # Verify the device belongs to this user
    device = (
        db.query(IoTDevice)
        .filter(IoTDevice.id == dev_uuid, IoTDevice.user_id == user.id)
        .first()
    )
    if not device:
        return 0, []

    query = (
        db.query(IoTTelemetry)
        .filter(IoTTelemetry.device_id == dev_uuid)
        .order_by(IoTTelemetry.created_at.desc())
    )
    total = query.count()
    rows = query.offset((page - 1) * limit).limit(limit).all()

    # Collect the telemetry IDs that have at least one associated alert.
    # Alerts store device_id but not telemetry_id, so we approximate:
    # an event "triggered an alert" when the alert was created within
    # 2 seconds of the telemetry timestamp.
    items: List[Dict[str, Any]] = []
    for row in rows:
        # Check whether any alert was created close to this telemetry event
        from sqlalchemy import func as sa_func
        alert_near = (
            db.query(IoTAlert)
            .filter(
                IoTAlert.device_id == dev_uuid,
                IoTAlert.created_at >= row.created_at - timedelta(seconds=2),
                IoTAlert.created_at <= row.created_at + timedelta(seconds=2),
            )
            .first()
        )
        items.append(
            {
                "id": str(row.id),
                "device_id": str(row.device_id) if row.device_id else None,
                "event_type": row.event_type,
                "data": row.data,
                "alert_triggered": alert_near is not None,
                "created_at": row.created_at,
            }
        )

    return total, items