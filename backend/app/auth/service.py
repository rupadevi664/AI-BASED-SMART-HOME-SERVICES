"""Auth business logic: registration and login."""
import logging

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.security import create_access_token, hash_password, verify_password
from app.models import ExpertProfile, ExpertService, Service, User
from app.models.expert import VerificationStatus
from app.models.user import UserRole

logger = logging.getLogger(__name__)

GENERIC_LOGIN_ERROR = "Incorrect email or password"

# bcrypt hash of a throwaway string; used to equalize response timing when the
# email is unknown (never reveals whether an email is registered).
DUMMY_HASH = hash_password("timing-equalizer")


class AuthService:
    """All database access happens inside a session from SessionLocal."""

    @staticmethod
    def _get_by_email(db, email: str) -> User | None:
        return db.execute(
            select(User).where(User.email == email.lower().strip())
        ).scalar_one_or_none()

    @staticmethod
    def _resolve_service_ids(db, service_ids: list[int] | None) -> list[Service]:
        """Load and validate the requested services; 404 on any unknown id.
        Duplicates in the payload are silently de-duplicated."""
        if not service_ids:
            return []
        unique_ids = sorted(set(service_ids))
        found = db.execute(select(Service).where(Service.id.in_(unique_ids))).scalars().all()
        found_ids = {service.id for service in found}
        missing = [sid for sid in unique_ids if sid not in found_ids]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service(s) not found: {missing}",
            )
        return list(found)

    @staticmethod
    def register_customer(db, data) -> User:
        """Create a CUSTOMER user. The role is assigned server-side and is never
        trusted from the request body."""
        if AuthService._get_by_email(db, data.email) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists",
            )

        user = User(
            name=data.name.strip(),
            email=data.email.lower().strip(),
            phone=data.phone.strip(),
            password_hash=hash_password(data.password),
            role=UserRole.CUSTOMER,  # forced server-side
            is_active=True,
        )
        db.add(user)
        try:
            db.commit()
        except IntegrityError as exc:
            # Race safety net: unique constraint on users.email.
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists",
            ) from exc
        except SQLAlchemyError as exc:
            db.rollback()
            logger.exception("Database error during customer registration")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error, please try again later",
            ) from exc
        db.refresh(user)
        return user

    @staticmethod
    def register_expert(db, data) -> tuple[User, ExpertProfile]:
        """Create EXPERT user + ExpertProfile + service links in ONE transaction.

        If anything fails (duplicate email, unknown service id, DB error), the
        whole transaction is rolled back — no partial records are left behind.
        """
        if AuthService._get_by_email(db, data.email) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists",
            )

        # Validate all requested services up front (also detects duplicates).
        services = AuthService._resolve_service_ids(db, data.service_ids)

        user = User(
            name=data.name.strip(),
            email=data.email.lower().strip(),
            phone=data.phone.strip(),
            password_hash=hash_password(data.password),
            role=UserRole.EXPERT,  # forced server-side
            is_active=True,
        )
        profile = ExpertProfile(
            skills=data.skills.strip(),
            experience_years=data.experience_years,  # manually entered
            location=data.location.strip(),
            latitude=data.latitude,
            longitude=data.longitude,
            verification_status=VerificationStatus.PENDING,  # default status
            availability=data.availability,
        )
        profile.user = user
        profile.service_links = [
            ExpertService(service_id=service.id) for service in services
        ]
        db.add(profile)  # cascades the user insert within the same transaction

        try:
            db.commit()
        except IntegrityError as exc:
            # Race safety net: unique users.email / expert_profiles.user_id.
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists",
            ) from exc
        except SQLAlchemyError as exc:
            db.rollback()
            logger.exception("Database error during expert registration")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error, please try again later",
            ) from exc
        db.refresh(user)
        db.refresh(profile)
        return user, profile

    @staticmethod
    def login(db, email: str, password: str) -> str:
        """Verify credentials and return a signed JWT.

        Any credential failure returns the same generic error message.
        """
        user = AuthService._get_by_email(db, email)

        if user is None:
            verify_password(password, DUMMY_HASH)  # keep timing similar
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=GENERIC_LOGIN_ERROR,
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=GENERIC_LOGIN_ERROR,
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account has been deactivated",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return create_access_token(
            subject=str(user.id),
            extra_claims={"role": user.role.value},
        )
