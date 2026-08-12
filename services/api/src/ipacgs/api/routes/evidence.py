"""Evidence HTTP routes — Figure 2 of the architecture document, reachable
over the wire. Same authorization note as api/routes/opboh.py: identity is
required, role-based restriction on top of it is a follow-up.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.api.schemas.evidence import CreateEvidenceRequest, EvidenceOut, RejectEvidenceRequest
from ipacgs.core.db import get_db
from ipacgs.core.security import CurrentUser, get_current_user
from ipacgs.models.evidence import EvidenceDocument
from ipacgs.models.organisation import Organisation
from ipacgs.services import evidence as evidence_service

router = APIRouter(prefix="/evidence", tags=["evidence"])


async def _get_evidence_or_404(session: AsyncSession, evidence_id: uuid.UUID) -> EvidenceDocument:
    doc = await session.get(EvidenceDocument, evidence_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No evidence document {evidence_id}.")
    return doc


@router.post("", response_model=EvidenceOut, status_code=status.HTTP_201_CREATED)
async def request_evidence(
    body: CreateEvidenceRequest,
    tenant_organisation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> EvidenceDocument:
    """`tenant_organisation_id` identifies which tenant this evidence
    belongs to, the same indirect way opboh.py's create_assessment derives
    a tenant — via an Organisation row, not a client-supplied tenant_id.
    A query param here rather than a path segment because evidence isn't
    owned by one organisation the way an OPBOH assessment is; it just needs
    *a* valid one to resolve which tenant it's scoped to."""
    organisation = await db.get(Organisation, tenant_organisation_id)
    if organisation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No organisation {tenant_organisation_id}.")

    doc = EvidenceDocument(
        id=uuid.uuid4(),
        tenant_id=organisation.tenant_id,
        title=body.title,
        document_type=body.document_type,
        source=body.source,
        valid_from=body.valid_from,
        valid_until=body.valid_until,
        is_independent_source=body.is_independent_source,
        confidentiality_level=body.confidentiality_level,
        created_by=user.object_id,
        updated_by=user.object_id,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


@router.get("/{evidence_id}", response_model=EvidenceOut)
async def get_evidence(
    evidence_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> EvidenceDocument:
    return await _get_evidence_or_404(db, evidence_id)


@router.post("/{evidence_id}/submit", response_model=EvidenceOut)
async def submit_evidence_route(
    evidence_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> EvidenceDocument:
    doc = await _get_evidence_or_404(db, evidence_id)
    await evidence_service.submit_evidence(
        db, doc, submitter=user.object_id, correlation_id=uuid.uuid4()
    )
    await db.commit()
    await db.refresh(doc)
    return doc


@router.post("/{evidence_id}/accept", response_model=EvidenceOut)
async def accept_evidence_route(
    evidence_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> EvidenceDocument:
    doc = await _get_evidence_or_404(db, evidence_id)
    await evidence_service.accept_evidence(
        db, doc, reviewer=user.object_id, correlation_id=uuid.uuid4()
    )
    await db.commit()
    await db.refresh(doc)
    return doc


@router.post("/{evidence_id}/reject", response_model=EvidenceOut)
async def reject_evidence_route(
    evidence_id: uuid.UUID,
    body: RejectEvidenceRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> EvidenceDocument:
    doc = await _get_evidence_or_404(db, evidence_id)
    await evidence_service.reject_evidence(
        db, doc, reviewer=user.object_id, reason=body.reason, correlation_id=uuid.uuid4()
    )
    await db.commit()
    await db.refresh(doc)
    return doc
