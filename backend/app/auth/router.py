"""Authentication endpoints."""
from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.schemas import (
    CustomerRegister,
    ExpertRegister,
    LoginRequest,
    MeResponse,
    TokenResponse,
)
from app.auth.service import AuthService
from app.core.database import get_db
from app.models import User
from app.schemas.expert import ExpertRegisterResponse
from app.schemas.user import UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a customer account",
)
def register_customer(payload: CustomerRegister, db: Session = Depends(get_db)) -> User:
    """Creates a CUSTOMER user. The role is assigned by the backend — any role
    sent by a client is ignored."""
    return AuthService.register_customer(db, payload)


@router.post(
    "/register-expert",
    response_model=ExpertRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register an expert account (user + expert profile)",
)
def register_expert(payload: ExpertRegister, db: Session = Depends(get_db)) -> dict:
    """Creates an EXPERT user plus the ExpertProfile (and service links) in one
    transaction. verification_status starts at PENDING."""
    user, profile = AuthService.register_expert(db, payload)
    return {
        "user": user,
        "expert_profile": {
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
            "services": profile.services,
            "created_at": profile.created_at,
        },
    }


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login with JSON and receive a JWT access token",
)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Returns `{access_token, token_type:"bearer"}`; invalid credentials get a
    generic 401."""
    token = AuthService.login(db, payload.email, payload.password)
    return TokenResponse(access_token=token)


@router.post(
    "/login-form",
    response_model=TokenResponse,
    summary="Login with form data (this is what Swagger's Authorize button uses)",
)
def login_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Same authentication as `/auth/login` but accepts the standard
    `application/x-www-form-urlencoded` OAuth2 form so the interactive docs work."""
    token = AuthService.login(db, form_data.username, form_data.password)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=MeResponse, summary="Current user information")
def read_current_user(current_user: User = Depends(get_current_user)) -> dict:
    """Returns the authenticated user (plus expert profile fields for EXPERTs).
    Never includes password_hash."""
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "phone": current_user.phone,
        "role": current_user.role,
        "is_active": current_user.is_active,
        "expert_profile": current_user.expert_profile,
    }
