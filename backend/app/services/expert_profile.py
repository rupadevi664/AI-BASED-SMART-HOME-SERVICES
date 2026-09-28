"""Expert profile business logic (Phase 2)."""
import logging

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import ExpertProfile, ExpertService, Service
from app.schemas.expert import ExpertProfileUpdate

logger = logging.getLogger(__name__)


class ExpertProfileService:
    @staticmethod
    def update_profile(db: Session, profile: ExpertProfile, payload: ExpertProfileUpdate) -> None:
        """Apply a partial profile update in ONE transaction.

        `service_ids` (when provided) atomically replaces the offered services;
        unknown ids raise 404 and leave the profile untouched.
        """
        data = payload.model_dump(exclude_unset=True)
        new_service_ids = data.pop("service_ids", None)

        if new_service_ids is not None:
            unique_ids = sorted(set(new_service_ids))
            if unique_ids:
                found = (
                    db.execute(select(Service).where(Service.id.in_(unique_ids))).scalars().all()
                )
                found_ids = {service.id for service in found}
                missing = [sid for sid in unique_ids if sid not in found_ids]
                if missing:
                    db.rollback()
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Service(s) not found: {missing}",
                    )
            # Simple assignment lets the session delete + insert link rows in
            # the same transaction as the column updates.
            profile.service_links = [
                ExpertService(service_id=sid) for sid in unique_ids
            ]

        for field, value in data.items():
            setattr(profile, field, value)

        try:
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            logger.exception("Database error during expert profile update")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error, please try again later",
            ) from exc
