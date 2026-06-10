"""
Trips router.
"""

import asyncio
import logging

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from agentic_traveler.interfaces.dependencies import WebUserCtx, verify_supabase_jwt
from agentic_traveler.tools.trip_repo import TripRepository
from agentic_traveler.tools.user_repo import UserRepository
from agentic_traveler.economy import credit_manager
from agentic_traveler.orchestrator.sagas.country_intel import CountryIntelSaga

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trips", tags=["Trips"])

@router.post("/{trip_id}/intel/refresh")
async def refresh_country_intel(
    trip_id: UUID,
    iso: str = Query(..., min_length=2, max_length=2),
    ctx: WebUserCtx = Depends(verify_supabase_jwt),
):
    """
    Manually triggers a refresh of the country intel for the specified ISO.
    Enqueues the fetch as a background task.
    """
    trip_id_str = str(trip_id)
    iso = iso.upper()
    repo = TripRepository()
    
    # Check credits
    user_repo = UserRepository()
    user_doc = user_repo.get_user_by_id(ctx.user_id)
    if not user_doc or not credit_manager.has_credits(user_doc):
        raise HTTPException(status_code=402, detail="No credits remaining.")
    
    
    # Verify ownership and existence
    try:
        repo._assert_owner(trip_id_str, ctx.user_id)
        trip = repo.get_trip(trip_id_str)
        if not trip:
            raise HTTPException(status_code=404, detail="Trip not found.")
    except Exception as e:
        logger.warning(f"Refresh denied for trip {trip_id_str}: {e}")
        raise HTTPException(status_code=404, detail="Trip not found or access denied.")
        
    # Find the country name from trip destinations
    country_name = "Unknown"
    for dest in trip.destinations:
        if dest.iso_country == iso:
            country_name = dest.name
            break
            
    # Trigger the saga refresh
    saga = CountryIntelSaga(client=None) 
    
    logger.info("Manual intel refresh triggered for trip %s, iso %s (%s)", trip_id_str, iso, country_name)
    asyncio.create_task(
        saga._run_fetch_async(
            trip_id=trip_id_str,
            user_id=ctx.user_id,
            iso_country=iso,
            country_name=country_name,
            month_name=saga._get_trip_month(trip.model_dump()),
        )
    )
    
    return {"status": "enqueued", "iso_country": iso}
