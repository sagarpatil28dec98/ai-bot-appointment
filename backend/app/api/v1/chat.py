from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from app.database.session import get_db
from app.schemas.all_schemas import InboundChatMessage, OutboundChatResponse
from app.agents.healthai_agent import agent
from app.services.openwa_service import openwa_service
from app.core.config import settings

router = APIRouter(prefix="/chat", tags=["Chat & Webhook"])

@router.post("/message")
async def handle_incoming_message(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    x_webhook_secret: Optional[str] = Header(None)
):
    """
    Core entrypoint for WhatsApp messages triggered by OpenWA direct webhook or n8n.
    Normalizes OpenWA webhook formats as well as flat JSON.
    """
    if settings.ENVIRONMENT == "production" and x_webhook_secret != settings.WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature / secret"
        )

    # Normalize OpenWA payload structures (e.g. data / body nested or flat)
    raw_body = payload.get("data") if isinstance(payload.get("data"), dict) else payload

    # Extract sender phone number
    from_raw = raw_body.get("from") or raw_body.get("from_number") or raw_body.get("sender", {}).get("id", "")
    from_number = str(from_raw).replace("@c.us", "").replace("@s.whatsapp.net", "")

    # Extract message content
    message_text = (
        raw_body.get("body")
        or raw_body.get("content")
        or raw_body.get("message_text")
        or raw_body.get("text")
        or ""
    )

    # Extract sender name
    sender_name = (
        raw_body.get("sender", {}).get("pushname")
        or raw_body.get("notifyName")
        or raw_body.get("sender_name")
        or "WhatsApp Patient"
    )

    # Avoid processing our own outbound messages if looped
    if raw_body.get("fromMe") is True or not message_text.strip():
        return {"status": "ignored", "reason": "empty_or_outbound"}

    response_data = await agent.process_message(
        db=db,
        from_number=from_number,
        message_text=message_text,
        sender_name=sender_name
    )

    # Automatically dispatch reply to WhatsApp via OpenWA on port 2785
    await openwa_service.send_message(
        to_phone=response_data["to_number"],
        message=response_data["reply_text"]
    )

    return response_data
