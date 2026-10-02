"""Admin-only endpoints: dashboard, service management, expert verification."""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import require_admin
from app.core.database import get_db
from app.models import Booking, BookingStatus, ExpertProfile, ExpertService, Service, User
from app.models.expert import VerificationStatus
from app.models.user import UserRole
from app.schemas.booking import BookingResponse
from app.schemas.expert import ExpertProfileResponse
from app.schemas.service import ServiceCreate, ServiceResponse, ServiceUpdate
from app.services.booking_service import BookingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get(
    "/bookings",
    response_model=list[BookingResponse],
    summary="All bookings (ADMIN only)",
)
def admin_bookings(
    status: BookingStatus | None = None,
    service_id: int | None = None,
    expert_id: int | None = None,
    customer_id: int | None = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[Booking]:
    """Inspect booking records with optional filters (no analytics)."""
    return BookingService.list_for_admin(
        db,
        status_filter=status,
        service_id=service_id,
        expert_id=expert_id,
        customer_id=customer_id,
    )


@router.get("/dashboard", summary="Admin-only dashboard")
def admin_dashboard(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Accessible only to ADMIN accounts; simple Phase 1 statistics."""
    total_users = db.execute(select(func.count()).select_from(User)).scalar_one()
    total_experts = db.execute(
        select(func.count()).select_from(User).where(User.role == UserRole.EXPERT)
    ).scalar_one()
    total_customers = db.execute(
        select(func.count()).select_from(User).where(User.role == UserRole.CUSTOMER)
    ).scalar_one()
    total_services = db.execute(select(func.count()).select_from(Service)).scalar_one()
    pending_verifications = db.execute(
        select(func.count())
        .select_from(ExpertProfile)
        .where(ExpertProfile.verification_status == VerificationStatus.PENDING)
    ).scalar_one()

    return {
        "message": f"Welcome, {current_user.name}! This is the admin dashboard.",
        "stats": {
            "total_users": total_users,
            "total_customers": total_customers,
            "total_experts": total_experts,
            "total_services": total_services,
            "pending_verifications": pending_verifications,
        },
    }


# --- Service management (ADMIN only) ----------------------------------------


@router.post(
    "/services",
    response_model=ServiceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a service (ADMIN only)",
)
def create_service(
    payload: ServiceCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Service:
    """Customers/experts get 403 via the role dependency."""
    existing = db.execute(
        select(Service).where(Service.name == payload.name.strip())
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Service {payload.name.strip()!r} already exists",
        )
    service = Service(
        name=payload.name.strip(),
        description=payload.description,
        base_price=payload.base_price,
        status=payload.status,
    )
    db.add(service)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Service {payload.name.strip()!r} already exists",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Database error creating service")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error, please try again later",
        ) from exc
    db.refresh(service)
    return service


@router.put(
    "/services/{service_id}",
    response_model=ServiceResponse,
    summary="Update a service (ADMIN only)",
)
def update_service(
    service_id: int,
    payload: ServiceUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Service:
    """Partial update; the service id itself can never be changed."""
    service = db.get(Service, service_id)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service {service_id} not found",
        )
    data = payload.model_dump(exclude_unset=True)
    if "name" in data:
        new_name = data["name"].strip()
        clash = db.execute(
            select(Service).where(Service.name == new_name, Service.id != service_id)
        ).scalar_one_or_none()
        if clash is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Service {new_name!r} already exists",
            )
        data["name"] = new_name
    for field, value in data.items():
        setattr(service, field, value)
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Database error updating service")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error, please try again later",
        ) from exc
    db.refresh(service)
    return service


# --- Expert verification (ADMIN only) ----------------------------------------


@router.get(
    "/experts",
    response_model=list[ExpertProfileResponse],
    summary="List all expert profiles (ADMIN only)",
)
def list_experts(
    verification_status: VerificationStatus | None = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Admin view of expert profiles with user info and services."""
    query = (
        select(ExpertProfile)
        .options(
            selectinload(ExpertProfile.user),
            selectinload(ExpertProfile.service_links).selectinload(ExpertService.service),
        )
        .order_by(ExpertProfile.id)
    )
    if verification_status is not None:
        query = query.where(ExpertProfile.verification_status == verification_status)

    items = []
    for profile in db.execute(query).scalars().unique().all():
        items.append(
            {
                "id": profile.id,
                "user_id": profile.user_id,
                "name": profile.user.name,
                "email": profile.user.email,
                "phone": profile.user.phone,
                "skills": profile.skills,
                "experience_years": profile.experience_years,
                "location": profile.location,
                "latitude": profile.latitude,
                "longitude": profile.longitude,
                "verification_status": profile.verification_status,
                "availability": profile.availability,
                "rating_avg": profile.rating_avg,
                "rating_count": profile.rating_count,
                "services": profile.services,
                "created_at": profile.created_at,
            }
        )
    return items


@router.put(
    "/experts/{expert_id}/verification",
    response_model=ExpertProfileResponse,
    summary="Set expert verification status (ADMIN only)",
)
def set_expert_verification(
    expert_id: int,
    verification_status: VerificationStatus,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Allowed statuses: PENDING / VERIFIED / REJECTED (validated by the enum)."""
    profile = db.get(ExpertProfile, expert_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expert profile {expert_id} not found",
        )
    profile.verification_status = verification_status
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Database error updating verification")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error, please try again later",
        ) from exc
    db.refresh(profile)
    user = profile.user
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "skills": profile.skills,
        "experience_years": profile.experience_years,
        "location": profile.location,
        "latitude": profile.latitude,
        "longitude": profile.longitude,
        "verification_status": profile.verification_status,
        "availability": profile.availability,
        "rating_avg": profile.rating_avg,
        "rating_count": profile.rating_count,
        "services": profile.services,
        "created_at": profile.created_at,
    }
