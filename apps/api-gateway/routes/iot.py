"""
IoT security routes — device management, alerts, demo seed.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user_required
from models.user import User
from schemas.iot import (
    AlertListResponse,
    AlertResponse,
    DeviceListResponse,
    DeviceRegisterRequest,
    DeviceResponse,
    SeedDemoResponse,
)
from services import iot_service

router = APIRouter()


@router.post(
    "/devices/register",
    response_model=DeviceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register an IoT device",
)
async def register_device(
    payload: DeviceRegisterRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    return iot_service.register_device(db, current_user, payload)


@router.get(
    "/devices",
    response_model=DeviceListResponse,
    summary="List registered IoT devices",
)
async def list_devices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    items = iot_service.list_devices(db, current_user)
    return DeviceListResponse(total=len(items), items=items)


@router.delete(
    "/devices/{device_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an IoT device",
)
async def delete_device(
    device_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    deleted = iot_service.delete_device(db, current_user, device_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")


@router.post(
    "/devices/seed-demo",
    response_model=SeedDemoResponse,
    summary="Seed demo IoT devices for the current user",
)
async def seed_demo_devices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    devices = iot_service.seed_demo_devices(db, current_user)
    return SeedDemoResponse(
        message="Demo devices ready",
        devices=devices,
    )


@router.get(
    "/alerts",
    response_model=AlertListResponse,
    summary="List IoT security alerts",
)
async def list_alerts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    severity: Optional[str] = Query(None),
    is_resolved: Optional[bool] = Query(None),
    device_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    total, items = iot_service.list_alerts(
        db,
        current_user,
        page=page,
        limit=limit,
        severity=severity,
        is_resolved=is_resolved,
        device_id=device_id,
    )
    return AlertListResponse(
        total=total,
        page=page,
        limit=limit,
        items=[AlertResponse(**item) for item in items],
    )


@router.patch(
    "/alerts/{alert_id}/resolve",
    response_model=AlertResponse,
    summary="Resolve an IoT alert",
)
async def resolve_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    alert = iot_service.resolve_alert(db, current_user, alert_id)
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    device_name = None
    if alert.device_id:
        from models.iot import IoTDevice

        device = db.query(IoTDevice).filter(IoTDevice.id == alert.device_id).first()
        device_name = device.name if device else None

    return AlertResponse(
        id=str(alert.id),
        device_id=str(alert.device_id) if alert.device_id else None,
        device_name=device_name,
        rule_triggered=alert.rule_triggered,
        severity=alert.severity,
        description=alert.description,
        is_resolved=alert.is_resolved,
        created_at=alert.created_at,
    )

@router.post(
    "/telemetry",
    summary="Ingest IoT telemetry data",
)
async def ingest_telemetry(
    payload: dict,  # Temporary, use proper schema
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """Ingest telemetry and trigger risk scoring"""
    try:
        from services.iot_service import process_telemetry
        
        device_id = payload.get("device_id")
        event_type = payload.get("event_type")
        data = payload.get("data", {})
        
        if not device_id or not event_type:
            raise HTTPException(status_code=400, detail="device_id and event_type required")
        
        result = await process_telemetry(
            db=db,
            user_id=current_user.id,
            device_id=device_id,
            event_type=event_type,
            data=data
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
