"""Notification business logic: creation, listing, marking as read."""
import logging
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.notification import Notification

logger = logging.getLogger(__name__)


class NotificationService:
    @staticmethod
    def create_notification(
        db: Session,
        *,
        user_id: int,
        title: str,
        message: str,
        type: str = "SYSTEM",
        link: str | None = None,
    ) -> Notification | None:
        """Create and commit a notification. Fails soft so business transactions
        are never broken by notification logging."""
        try:
            notification = Notification(
                user_id=user_id,
                title=title,
                message=message,
                type=type,
                link=link,
                is_read=False,
            )
            db.add(notification)
            db.commit()
            db.refresh(notification)
            return notification
        except Exception:
            logger.exception("Failed to create notification for user %s", user_id)
            db.rollback()
            return None

    @staticmethod
    def list_for_user(
        db: Session,
        user_id: int,
        *,
        unread_only: bool = False,
        limit: int = 50,
    ) -> list[Notification]:
        stmt = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        if unread_only:
            stmt = stmt.where(Notification.is_read.is_(False))
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def get_unread_count(db: Session, user_id: int) -> int:
        count = db.execute(
            select(func.count(Notification.id)).where(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
        ).scalar()
        return int(count or 0)

    @staticmethod
    def mark_as_read(db: Session, notification_id: int, user_id: int) -> Notification | None:
        notification = db.get(Notification, notification_id)
        if notification is None or notification.user_id != user_id:
            return None
        notification.is_read = True
        db.commit()
        db.refresh(notification)
        return notification

    @staticmethod
    def mark_all_as_read(db: Session, user_id: int) -> int:
        notifications = (
            db.execute(
                select(Notification).where(
                    Notification.user_id == user_id,
                    Notification.is_read.is_(False),
                )
            )
            .scalars()
            .all()
        )
        for n in notifications:
            n.is_read = True
        db.commit()
        return len(notifications)

    @staticmethod
    def delete_notification(db: Session, notification_id: int, user_id: int) -> bool:
        notification = db.get(Notification, notification_id)
        if notification is None or notification.user_id != user_id:
            return False
        db.delete(notification)
        db.commit()
        return True
