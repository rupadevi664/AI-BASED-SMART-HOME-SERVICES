"""Public service catalogue endpoints (any authenticated or anonymous user)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Service
from app.models.service import ServiceStatus
from app.schemas.service import ServiceResponse

router = APIRouter(prefix="/services", tags=["Services"])


@router.get("", response_model=list[ServiceResponse], summary="List active services")
def list_services(db: Session = Depends(get_db)) -> list[Service]:
    """All ACTIVE services, ordered by name. (Inactive ones are admin-visible only.)"""
    return list(
        db.execute(
            select(Service)
            .where(Service.status == ServiceStatus.ACTIVE)
            .order_by(Service.name)
        )
        .scalars()
        .all()
    )


@router.get("/{service_id}", response_model=ServiceResponse, summary="Get one service")
def get_service(service_id: int, db: Session = Depends(get_db)) -> Service:
    """Returns the service; 404 when it does not exist. Inactive services are
    still returned here (with their status field) so clients can inspect them."""
    service = db.get(Service, service_id)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service {service_id} not found",
        )
    return service
