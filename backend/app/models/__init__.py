"""Import all models so Base.metadata knows every table."""
from app.models.associations import ExpertService
from app.models.booking import Booking, BookingStatus
from app.models.expert import AvailabilityStatus, ExpertProfile, VerificationStatus
from app.models.message import Message
from app.models.service import Service, ServiceStatus
from app.models.user import User, UserRole

__all__ = [
    "AvailabilityStatus",
    "Booking",
    "BookingStatus",
    "ExpertProfile",
    "ExpertService",
    "Message",
    "Service",
    "ServiceStatus",
    "User",
    "UserRole",
    "VerificationStatus",
]
