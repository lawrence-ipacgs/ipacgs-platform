import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.core.audit import record_audit_event
from ipacgs.models import AuditAction, AuditEvent, Organisation, Tenant


async def test_tenant_and_organisation_round_trip(db_session: AsyncSession) -> None:
    tenant = Tenant(
        id=uuid.uuid4(),
        name="KMI Africa",
        slug="kmi-africa",
        created_by="system-seed",
    )
    db_session.add(tenant)
    await db_session.flush()

    org = Organisation(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        legal_name="KMI Africa Group",
        is_own_tenant_entity=True,
        created_by="system-seed",
        updated_by="system-seed",
    )
    db_session.add(org)
    await db_session.commit()

    result = await db_session.execute(select(Organisation).where(Organisation.tenant_id == tenant.id))
    fetched = result.scalar_one()
    assert fetched.legal_name == "KMI Africa Group"
    assert fetched.is_own_tenant_entity is True
    # Row-level audit metadata (AuditedMixin) was populated without the test
    # setting it explicitly — server_default did its job.
    assert fetched.created_at is not None


async def test_record_audit_event_is_queryable(db_session: AsyncSession) -> None:
    tenant_id = uuid.uuid4()
    db_session.add(Tenant(id=tenant_id, name="Test Tenant", slug=f"test-{tenant_id}", created_by="seed"))
    await db_session.flush()

    entity_id = uuid.uuid4()
    correlation_id = uuid.uuid4()
    await record_audit_event(
        db_session,
        tenant_id=tenant_id,
        actor_object_id="33333333-3333-3333-3333-333333333333",
        action=AuditAction.CREATE,
        entity_type="organisation",
        entity_id=entity_id,
        correlation_id=correlation_id,
        after_values={"legal_name": "Example Sponsor Ltd"},
    )
    await db_session.commit()

    result = await db_session.execute(select(AuditEvent).where(AuditEvent.entity_id == entity_id))
    event = result.scalar_one()
    assert event.action == AuditAction.CREATE
    assert event.after_values == {"legal_name": "Example Sponsor Ltd"}
    assert event.correlation_id == correlation_id
