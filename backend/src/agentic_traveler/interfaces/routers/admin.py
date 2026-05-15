from fastapi import APIRouter, Depends, HTTPException

from agentic_traveler.economy import credit_manager
from agentic_traveler.interfaces.dependencies import verify_admin_key
from agentic_traveler.interfaces.schemas import AddCreditsRequest
from agentic_traveler.tools.user_repo import UserRepository

router = APIRouter(dependencies=[Depends(verify_admin_key)])

@router.post("/add-credits")
async def admin_add_credits(payload: AddCreditsRequest):
    """Add credits to a user. Requires X-Admin-Key header."""
    user_repo = UserRepository()
    user_uuid = user_repo.get_user_ref_by_telegram_id(payload.user_id)
    
    if not user_uuid:
        raise HTTPException(status_code=404, detail=f"User {payload.user_id} not found")

    credit_manager.add_credits(user_uuid, payload.amount)
    return {"ok": True, "added": payload.amount, "user_id": payload.user_id}
