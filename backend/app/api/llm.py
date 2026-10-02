"""LLM endpoints (Phase 7): AI assistant chat.

Auth model (unchanged from the rest of the app): `require_roles` builds on
`get_current_user` to resolve the JWT, then enforces roles. Customers and
experts may use the assistant; admins manage instead of asking it.
"""
from fastapi import APIRouter, Depends

from app.auth.dependencies import require_roles
from app.models import User
from app.models.user import UserRole
from app.schemas.llm import LLMRequest, LLMResponse
from app.services.gemini_service import GeminiService

router = APIRouter(prefix="/llm", tags=["LLM"])


@router.post(
    "/chat",
    response_model=LLMResponse,
    summary="Ask the Smart Home AI Assistant (CUSTOMER or EXPERT)",
    responses={
        401: {"description": "Missing/invalid JWT"},
        403: {"description": "Role not allowed (e.g. ADMIN)"},
        422: {"description": "Validation error (blank/over-long message, bad history)"},
        429: {"description": "Gemini rate limited"},
        502: {"description": "Gemini unavailable, key rejected, or empty answer"},
        503: {"description": "GEMINI_API_KEY not configured on this server"},
        504: {"description": "Gemini request timed out"},
    },
)
def chat_with_assistant(
    payload: LLMRequest,
    current_user: User = Depends(require_roles(UserRole.CUSTOMER, UserRole.EXPERT)),
) -> LLMResponse:
    """Send one question (plus optional short client-side history) to Gemini.

    Returns `{"response": "<clean text>"}` — the raw provider payload is never
    forwarded. The assistant only suggests service categories; bookings and
    payments still go through their own APIs.
    """
    reply = GeminiService.generate_reply(
        payload.message,
        service_context=payload.service_context,
        history=[{"role": t.role, "text": t.text} for t in payload.history],
    )
    return LLMResponse(response=reply)
