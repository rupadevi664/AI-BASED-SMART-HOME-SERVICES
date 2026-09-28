"""Customer-only endpoints."""
from fastapi import APIRouter, Depends

from app.auth.dependencies import require_customer
from app.models import User

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/customer", summary="Customer-only endpoint")
def customer_home(current_user: User = Depends(require_customer)) -> dict:
    """Accessible only to CUSTOMER accounts."""
    return {
        "message": f"Welcome, {current_user.name}! This is the customer area.",
        "user_id": current_user.id,
        "role": current_user.role.value,
    }
