from __future__ import annotations

import logging

from fastapi import APIRouter

from app.models.notification import IncomingEvent
from app.services.notification_service import process_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/events", tags=["events"])


@router.post(
    "/emit",
    summary="Receive an event from another service and process it into a notification",
    status_code=202,
)
async def emit_event(event: IncomingEvent) -> dict:
    """
    Internal endpoint for other microservices to emit events.
    No JWT required — inter-service communication uses trusted network.
    """
    notification = await process_event(event)
    if notification:
        return {"status": "delivered", "notification_id": notification["id"]}
    return {"status": "skipped", "reason": "duplicate, suppressed, or below threshold"}
