"""Expert endpoints: own-profile management and nearby search."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import get_current_user
from app.core.database import get_db
from app.models import Booking, BookingStatus, ExpertProfile, ExpertService, Service, User
from app.models.expert import AvailabilityStatus, VerificationStatus
from app.schemas.booking import BookingRejectRequest, BookingResponse
from app.schemas.expert import (
    MAX_LATITUDE,
    MAX_LONGITUDE,
    MAX_RADIUS_KM,
    MIN_LATITUDE,
    MIN_LONGITUDE,
    ExpertProfileResponse,
    ExpertProfileUpdate,
    NearbyExpertResponse,
)
from app.services.booking_service import BookingService, _fail
from app.services.expert_profile import ExpertProfileService
from app.utils.geo import calculate_distance

router = APIRouter(prefix="/experts", tags=["Experts"])


def _profile_or_404(user: User) -> ExpertProfile:
    profile = user.expert_profile
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expert profile not found for this user",
        )
    return profile


@router.get(
    "/profile",
    response_model=ExpertProfileResponse,
    summary="Expert's own profile (with offered services)",
)
def read_expert_profile(current_user: User = Depends(get_current_user)) -> dict:
    """EXPERT only: full profile including user info, coordinates and services.
    Never includes password_hash."""
    if current_user.role != "EXPERT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this resource",
        )
    profile = _profile_or_404(current_user)
    return {
        "id": profile.id,
        "user_id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "phone": current_user.phone,
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


@router.put(
    "/profile",
    response_model=ExpertProfileResponse,
    summary="Update expert's own profile",
)
def update_expert_profile(
    payload: ExpertProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """EXPERT only. Partial update; `service_ids` atomically replaces the
    offered services. Coordinates are manual — never computed."""
    if current_user.role != "EXPERT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this resource",
        )
    profile = _profile_or_404(current_user)
    ExpertProfileService.update_profile(db, profile, payload)
    db.refresh(profile)
    return {
        "id": profile.id,
        "user_id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "phone": current_user.phone,
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


@router.get(
    "/nearby",
    response_model=list[NearbyExpertResponse],
    summary="Search verified experts near a coordinate",
)
def nearby_experts(
    latitude: float = Query(ge=MIN_LATITUDE, le=MAX_LATITUDE),
    longitude: float = Query(ge=MIN_LONGITUDE, le=MAX_LONGITUDE),
    radius_km: float = Query(gt=0, le=MAX_RADIUS_KM),
    service_id: int | None = Query(default=None, gt=0),
    availability: AvailabilityStatus | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Any authenticated user (customer, expert, admin): Haversine search.

    Only VERIFIED experts with ACTIVE accounts and valid coordinates are
    considered; results are sorted nearest-first. No matches → 200 with [].
    """
    if service_id is not None:
        service = db.get(Service, service_id)
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service {service_id} not found",
            )

    query = (
        select(ExpertProfile)
        .options(
            selectinload(ExpertProfile.service_links).selectinload(ExpertService.service),
            selectinload(ExpertProfile.user),
        )
        .join(User, ExpertProfile.user_id == User.id)
        .where(
            User.is_active.is_(True),
            ExpertProfile.verification_status == VerificationStatus.VERIFIED,
            ExpertProfile.latitude.is_not(None),
            ExpertProfile.longitude.is_not(None),
        )
    )
    if service_id is not None:
        query = query.where(ExpertProfile.service_links.any(service_id=service_id))
    if availability is not None:
        query = query.where(ExpertProfile.availability == availability)

    profiles = db.execute(query).scalars().unique().all()

    results = []
    for profile in profiles:
        distance = calculate_distance(
            latitude, longitude, float(profile.latitude), float(profile.longitude)
        )
        if distance <= radius_km:
            results.append(
                {
                    "expert_id": profile.id,
                    "user_id": profile.user_id,
                    "name": profile.user.name,
                    "skills": profile.skills,
                    "experience_years": profile.experience_years,
                    "location": profile.location,
                    "latitude": profile.latitude,
                    "longitude": profile.longitude,
                    "availability": profile.availability,
                    "verification_status": profile.verification_status,
                    "rating_avg": profile.rating_avg,
                    "rating_count": profile.rating_count,
                    "distance_km": round(distance, 2),
                    "services": [
                        {"id": link.service.id, "name": link.service.name}
                        for link in profile.service_links
                    ],
                }
            )
    results.sort(key=lambda item: item["distance_km"])
    return results


# --- Booking request management (Phase 3) ------------------------------------


def _own_expert_profile(user: User) -> ExpertProfile:
    profile = user.expert_profile
    if profile is None:
        raise _fail("EXPERT_PROFILE_NOT_FOUND", 404, "Expert profile not found for this user")
    return profile


def _own_booking_or_fail(booking_id: int, profile: ExpertProfile, db: Session) -> Booking:
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise _fail("BOOKING_NOT_FOUND", 404, f"Booking {booking_id} not found")
    if booking.expert_id != profile.id:
        raise _fail("BOOKING_ACCESS_DENIED", 403, "This booking is not assigned to you")
    return booking


@router.get(
    "/bookings",
    response_model=list[BookingResponse],
    summary="Expert's booking requests (own only)",
)
def expert_bookings(
    status_filter: BookingStatus | None = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Booking]:
    if current_user.role != "EXPERT":
        raise _fail("INVALID_ROLE", 403, "Only experts can view booking requests")
    profile = _own_expert_profile(current_user)
    return BookingService.list_for_expert(db, profile.id, status_filter)


@router.put(
    "/bookings/{booking_id}/accept",
    response_model=BookingResponse,
    summary="Accept a PENDING booking (own only)",
)
def accept_booking(
    booking_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Booking:
    if current_user.role != "EXPERT":
        raise _fail("INVALID_ROLE", 403, "Only experts can accept bookings")
    profile = _own_expert_profile(current_user)
    if not current_user.is_active:
        raise _fail("EXPERT_INACTIVE", 400, "Expert account is not active")
    if profile.verification_status != VerificationStatus.VERIFIED:
        raise _fail("EXPERT_NOT_VERIFIED", 400, "Expert is not verified yet")
    if profile.availability != AvailabilityStatus.AVAILABLE:
        raise _fail("EXPERT_UNAVAILABLE", 400, "Set your availability to AVAILABLE first")

    booking = _own_booking_or_fail(booking_id, profile, db)
    return BookingService.transition(db, booking, BookingStatus.ACCEPTED)


@router.put(
    "/bookings/{booking_id}/reject",
    response_model=BookingResponse,
    summary="Reject a PENDING booking (own only)",
)
def reject_booking(
    booking_id: int,
    payload: BookingRejectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Booking:
    if current_user.role != "EXPERT":
        raise _fail("INVALID_ROLE", 403, "Only experts can reject bookings")
    profile = _own_expert_profile(current_user)
    booking = _own_booking_or_fail(booking_id, profile, db)
    return BookingService.transition(
        db, booking, BookingStatus.REJECTED, reason=payload.reason
    )


@router.put(
    "/bookings/{booking_id}/complete",
    response_model=BookingResponse,
    summary="Complete an ACCEPTED booking (own only)",
)
def complete_booking(
    booking_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Booking:
    if current_user.role != "EXPERT":
        raise _fail("INVALID_ROLE", 403, "Only experts can complete bookings")
    profile = _own_expert_profile(current_user)
    booking = _own_booking_or_fail(booking_id, profile, db)
    return BookingService.transition(db, booking, BookingStatus.COMPLETED)
