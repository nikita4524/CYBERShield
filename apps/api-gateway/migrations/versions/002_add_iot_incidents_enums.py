"""add_iot_incidents_and_missing_enums

Revision ID: 002
Revises: 001
Create Date: 2025-01-15

Adds:
- security_incidents table
- iot_devices, iot_telemetry, iot_alerts tables
- 'image' value to analysis_type ENUM
- 'smart_home' value to quiz_category ENUM
- All IoT ENUM types
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ═══════════════════════════════════════════════════════════════════
    # 1. ADD MISSING ENUM VALUES TO EXISTING TYPES
    # ═══════════════════════════════════════════════════════════════════
    
    # Add 'image' to analysis_type ENUM
    op.execute("ALTER TYPE analysis_type ADD VALUE IF NOT EXISTS 'image'")
    
    # Add 'smart_home' to quiz_category ENUM
    op.execute("ALTER TYPE quiz_category ADD VALUE IF NOT EXISTS 'smart_home'")
    
    # ═══════════════════════════════════════════════════════════════════
    # 2. CREATE NEW ENUM TYPES FOR IOT
    # ═══════════════════════════════════════════════════════════════════
    
    iot_device_type = postgresql.ENUM(
        'camera', 'plug', 'router', 'speaker',
        name='iot_device_type',
        create_type=False
    )
    iot_device_type.create(op.get_bind(), checkfirst=True)
    
    iot_device_status = postgresql.ENUM(
        'online', 'offline',
        name='iot_device_status',
        create_type=False
    )
    iot_device_status.create(op.get_bind(), checkfirst=True)
    
    iot_risk_label = postgresql.ENUM(
        'safe', 'suspicious', 'dangerous',
        name='iot_risk_label',
        create_type=False
    )
    iot_risk_label.create(op.get_bind(), checkfirst=True)
    
    iot_event_type = postgresql.ENUM(
        'connection', 'motion', 'traffic',
        name='iot_event_type',
        create_type=False
    )
    iot_event_type.create(op.get_bind(), checkfirst=True)
    
    iot_alert_severity = postgresql.ENUM(
        'low', 'medium', 'high',
        name='iot_alert_severity',
        create_type=False
    )
    iot_alert_severity.create(op.get_bind(), checkfirst=True)
    
    # ENUM types for security_incidents
    prevention_action = postgresql.ENUM(
        'ALLOW', 'WARN', 'RESTRICT', 'BLOCK', 'QUARANTINE', 'FLAG',
        name='prevention_action',
        create_type=False
    )
    prevention_action.create(op.get_bind(), checkfirst=True)
    
    prevention_severity = postgresql.ENUM(
        'SAFE', 'MEDIUM', 'HIGH', 'CRITICAL',
        name='prevention_severity',
        create_type=False
    )
    prevention_severity.create(op.get_bind(), checkfirst=True)
    
    incident_status = postgresql.ENUM(
        'OPEN', 'REVIEWING', 'RESOLVED', 'FALSE_POSITIVE',
        name='incident_status',
        create_type=False
    )
    incident_status.create(op.get_bind(), checkfirst=True)
    
    incident_source = postgresql.ENUM(
        'url', 'email', 'qr', 'audio', 'video', 'image',
        name='incident_source',
        create_type=False
    )
    incident_source.create(op.get_bind(), checkfirst=True)
    
    # ═══════════════════════════════════════════════════════════════════
    # 3. CREATE IOT_DEVICES TABLE
    # ═══════════════════════════════════════════════════════════════════
    
    op.create_table(
        'iot_devices',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('type', iot_device_type, nullable=False),
        sa.Column('location', sa.String(120), nullable=False, server_default='Unknown'),
        sa.Column('status', iot_device_status, nullable=False, server_default='offline'),
        sa.Column('mac_address', sa.String(17), nullable=True, index=True),
        sa.Column('risk_score', sa.SmallInteger(), nullable=False, server_default='0'),
        sa.Column('risk_label', iot_risk_label, nullable=False, server_default='safe'),
        sa.Column('last_seen', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint('risk_score >= 0 AND risk_score <= 100', name='ck_iot_risk_score_range'),
    )
    
    # ═══════════════════════════════════════════════════════════════════
    # 4. CREATE IOT_TELEMETRY TABLE
    # ═══════════════════════════════════════════════════════════════════
    
    op.create_table(
        'iot_telemetry',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('device_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('iot_devices.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('event_type', iot_event_type, nullable=False),
        sa.Column('data', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), index=True),
    )
    op.create_index('ix_iot_telemetry_device_created', 'iot_telemetry', ['device_id', 'created_at'])
    
    # ═══════════════════════════════════════════════════════════════════
    # 5. CREATE IOT_ALERTS TABLE
    # ═══════════════════════════════════════════════════════════════════
    
    op.create_table(
        'iot_alerts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('device_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('iot_devices.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('rule_triggered', sa.String(64), nullable=False, index=True),
        sa.Column('severity', iot_alert_severity, nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('is_resolved', sa.Boolean(), nullable=False, server_default='false', index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), index=True),
    )
    
    # ═══════════════════════════════════════════════════════════════════
    # 6. CREATE SECURITY_INCIDENTS TABLE
    # ═══════════════════════════════════════════════════════════════════
    
    op.create_table(
        'security_incidents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('incident_number', sa.String(20), nullable=False, unique=True, index=True),
        sa.Column('threat_type', sa.String(50), nullable=False, index=True),
        sa.Column('source', incident_source, nullable=False, index=True),
        sa.Column('input_reference', sa.Text(), nullable=True),
        sa.Column('risk_score', sa.SmallInteger(), nullable=False),
        sa.Column('severity', prevention_severity, nullable=False, index=True),
        sa.Column('action', prevention_action, nullable=False, index=True),
        sa.Column('reasons', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('status', incident_status, nullable=False, server_default='OPEN', index=True),
        sa.Column('resolution_note', sa.Text(), nullable=True),
        sa.Column('analysis_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('analyses.id', ondelete='SET NULL'), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), index=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint('risk_score >= 0 AND risk_score <= 100', name='ck_incident_risk_score_range'),
    )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('security_incidents')
    op.drop_table('iot_alerts')
    op.drop_table('iot_telemetry')
    op.drop_table('iot_devices')
    
    # Drop new ENUM types
    for enum_name in [
        'incident_source',
        'incident_status',
        'prevention_severity',
        'prevention_action',
        'iot_alert_severity',
        'iot_event_type',
        'iot_risk_label',
        'iot_device_status',
        'iot_device_type',
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
    
    # Note: PostgreSQL does not support removing values from ENUMs directly.
    # The 'image' and 'smart_home' values added to existing ENUMs will persist
    # after downgrade. To fully reverse, you would need to:
    # 1. Drop all dependent tables/columns
    # 2. Drop the ENUM type
    # 3. Recreate it without the new values
    # This is intentionally left as-is since downgrading ENUMs with existing
    # data is destructive and rarely needed in production.
