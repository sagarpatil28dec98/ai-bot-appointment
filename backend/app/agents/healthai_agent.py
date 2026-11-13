import logging
import json
import re
from typing import Dict, Any, Optional
from datetime import datetime, date, timedelta
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.database.models import ConversationSession, ConversationMessage, ConversationState, MessageDirection, Patient
from app.services.appointment_service import appointment_service
from app.agents.prompts import SYSTEM_PROMPT, INTENT_EXTRACTION_PROMPT

logger = logging.getLogger("HealthAI.Agent")

class HealthAIAgent:
    """
    Intelligent Conversational Agent with deterministic state machine execution.
    Combines LLM intent understanding (Ollama / Cloud LLM) with strictly validated
    backend service tool execution.
    """

    async def _call_llm(self, prompt: str, system_prompt: str = SYSTEM_PROMPT) -> str:
        """Invokes configured LLM provider (Ollama or external) with fallback."""
        if settings.LLM_PROVIDER == "ollama":
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(
                        f"{settings.OLLAMA_BASE_URL}/api/generate",
                        json={
                            "model": settings.OLLAMA_MODEL,
                            "prompt": prompt,
                            "system": system_prompt,
                            "stream": False,
                            "format": "json"
                        }
                    )
                    if resp.status_code == 200:
                        return resp.json().get("response", "")
            except Exception as e:
                logger.warning(f"Ollama call failed or not reachable: {e}. Utilizing fast rule-based parsing.")
        
        # Fast fallback deterministic rule engine if LLM is offline
        return self._heuristic_intent_extractor(prompt)

    def _heuristic_intent_extractor(self, text: str) -> str:
        lower = text.lower()
        res = {
            "intent": "GENERAL_QUERY",
            "specialization": None,
            "doctor_name": None,
            "target_date": None,
            "target_time": None,
            "patient_name": None,
            "appointment_id": None
        }

        # Intent detection
        if any(w in lower for w in ["book", "appointment", "doctor", "consult", "schedule", "see a"]):
            res["intent"] = "BOOK_APPOINTMENT"
        elif any(w in lower for w in ["available", "slots", "free", "timing", "hours"]):
            res["intent"] = "CHECK_AVAILABILITY"
        elif any(w in lower for w in ["reschedule", "change time", "postpone"]):
            res["intent"] = "RESCHEDULE_APPOINTMENT"
        elif any(w in lower for w in ["cancel", "drop"]):
            res["intent"] = "CANCEL_APPOINTMENT"
        elif any(w in lower for w in ["location", "address", "open", "timing", "where"]):
            res["intent"] = "CLINIC_INFO"

        # Specialization matching
        for spec in ["cardiologist", "dermatologist", "pediatrician", "dentist", "general physician", "orthopedic"]:
            if spec in lower:
                res["specialization"] = spec
                break

        # Date heuristic
        if "tomorrow" in lower:
            res["target_date"] = (date.today() + timedelta(days=1)).isoformat()
        elif "today" in lower:
            res["target_date"] = date.today().isoformat()

        # Time heuristic (matches e.g. 09:00 AM, 10am, 2:30 pm, 11:00)
        time_match = re.search(r'\b(0?[1-9]|1[0-2])(?::([0-5][0-9]))?\s*(am|pm)\b|\b([01]?[0-9]|2[0-3]):([0-5][0-9])\b', lower)
        if time_match:
            res["target_time"] = time_match.group(0).strip().upper()
            if res["intent"] == "GENERAL_QUERY":
                res["intent"] = "BOOK_APPOINTMENT"

        return json.dumps(res)

    async def get_or_create_session(self, db: AsyncSession, phone_number: str, sender_name: Optional[str] = None) -> ConversationSession:
        result = await db.execute(
            select(ConversationSession)
            .where(ConversationSession.phone_number == phone_number)
            .order_by(ConversationSession.updated_at.desc())
        )
        session = result.scalars().first()

        if not session:
            # Check if patient exists
            p_res = await db.execute(select(Patient).where(Patient.phone_number == phone_number))
            patient = p_res.scalar_one_or_none()

            session = ConversationSession(
                phone_number=phone_number,
                patient_id=patient.id if patient else None,
                current_state=ConversationState.NEW,
                context_data={"patient_name": sender_name or (patient.full_name if patient else None)}
            )
            db.add(session)
            await db.commit()
            await db.refresh(session)
        return session

    async def process_message(
        self,
        db: AsyncSession,
        from_number: str,
        message_text: str,
        sender_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main pipeline: Ingest WhatsApp text -> State Machine -> Deterministic Tools -> Return Reply
        """
        session = await self.get_or_create_session(db, from_number, sender_name)
        ctx = dict(session.context_data or {})

        # 1. Log inbound message
        in_msg = ConversationMessage(
            session_id=session.id,
            direction=MessageDirection.INBOUND,
            message_text=message_text,
            payload_metadata={}
        )
        db.add(in_msg)
        await db.commit()

        # 2. Extract Intent and Entities
        # If in COLLECTING_TIME state, check if user provided time directly
        if session.current_state == ConversationState.COLLECTING_TIME:
            time_match = re.search(r'\b(0?[1-9]|1[0-2])(?::([0-5][0-9]))?\s*(am|pm)\b|\b([01]?[0-9]|2[0-3]):([0-5][0-9])\b', message_text.lower())
            if time_match:
                ctx["target_time"] = time_match.group(0).strip().upper()
                extracted = {"intent": "BOOK_APPOINTMENT", "target_time": ctx["target_time"]}
            else:
                extracted = json.loads(self._heuristic_intent_extractor(message_text))
        else:
            intent_raw = await self._call_llm(
                prompt=f"Message: '{message_text}'\nConversation context: {json.dumps(ctx)}\nExtract JSON parameters.",
                system_prompt=INTENT_EXTRACTION_PROMPT
            )
            try:
                extracted = json.loads(intent_raw) if isinstance(intent_raw, str) else intent_raw
            except Exception:
                extracted = json.loads(self._heuristic_intent_extractor(message_text))

        # Update context
        for key in ["specialization", "doctor_name", "target_date", "target_time", "patient_name", "appointment_id"]:
            if extracted.get(key):
                ctx[key] = extracted[key]

        intent = extracted.get("intent", "GENERAL_QUERY")

        reply_text = ""
        suggested_actions = []

        # 3. State Machine Execution
        if intent == "CLINIC_INFO":
            reply_text = (
                "🏥 *City Health Clinic*\n\n"
                "📍 *Address:* 123 Healthcare Ave, Medical Center, Suite 400\n"
                "⏰ *Hours:* Mon - Sat: 8:00 AM - 8:00 PM | Sun: Closed\n"
                "📞 *Contact:* +1 (555) 019-2834\n\n"
                "How can I help you today? You can say *'Book an appointment'* or *'Check doctor availability'*."
            )
            session.current_state = ConversationState.NEW

        elif intent in ["BOOK_APPOINTMENT", "CHECK_AVAILABILITY"] or session.current_state in [
            ConversationState.COLLECTING_DOCTOR,
            ConversationState.COLLECTING_DATE,
            ConversationState.COLLECTING_TIME,
            ConversationState.AWAITING_CONFIRMATION
        ]:
            # Step A: Need Specialization / Doctor
            doctors = await appointment_service.get_available_doctors(db, ctx.get("specialization"))

            if not doctors:
                reply_text = (
                    "👨‍⚕️ We couldn't find a doctor with that specialization.\n\n"
                    "We have specialists in:\n"
                    "• *Cardiology*\n• *General Medicine*\n• *Pediatrics*\n• *Dermatology*\n\n"
                    "Which department or doctor would you like to consult?"
                )
                session.current_state = ConversationState.COLLECTING_DOCTOR

            elif not ctx.get("doctor_id") and len(doctors) > 1 and not ctx.get("target_date"):
                doc_list = "\n".join([f"• Dr. {d.full_name} ({d.specialization})" for d in doctors])
                reply_text = (
                    f"Here are our available doctors:\n{doc_list}\n\n"
                    f"Which doctor would you like to see, and on what date? (e.g. *Tomorrow* or *YYYY-MM-DD*)"
                )
                session.current_state = ConversationState.COLLECTING_DOCTOR

            else:
                # Select first matching doctor if not already pinned
                selected_doc = doctors[0]
                ctx["doctor_id"] = str(selected_doc.id)
                ctx["doctor_name"] = selected_doc.full_name

                # Step B: Need Date
                if not ctx.get("target_date"):
                    reply_text = (
                        f"Great! Scheduling with *Dr. {selected_doc.full_name}* ({selected_doc.specialization}).\n\n"
                        f"📅 Which date would you prefer? You can say *'today'*, *'tomorrow'*, or a date like *'2026-11-05'*."
                    )
                    session.current_state = ConversationState.COLLECTING_DATE
                else:
                    try:
                        target_d = date.fromisoformat(ctx["target_date"])
                    except Exception:
                        target_d = date.today() + timedelta(days=1)
                        ctx["target_date"] = target_d.isoformat()

                    # Step C: Retrieve actual slots from deterministic service
                    slots = await appointment_service.get_doctor_available_slots(db, selected_doc.id, target_d)
                    available_slots = [s for s in slots if s.is_available]

                    if not available_slots:
                        reply_text = (
                            f"Sorry, Dr. {selected_doc.full_name} has no available slots on *{ctx['target_date']}*.\n"
                            f"Would you like to try another date?"
                        )
                        session.current_state = ConversationState.COLLECTING_DATE
                    elif not ctx.get("target_time"):
                        slot_strs = [s.start_time.strftime("%I:%M %p") for s in available_slots[:6]]
                        reply_text = (
                            f"Available slots for *Dr. {selected_doc.full_name}* on *{ctx['target_date']}*:\n\n"
                            + "\n".join([f"🕒 *{time_s}*" for time_s in slot_strs]) +
                            f"\n\nPlease reply with your preferred time."
                        )
                        session.current_state = ConversationState.COLLECTING_TIME
                    else:
                        # Step D: Confirm and Book
                        # Match target time to slot
                        matched_slot = None
                        target_t_clean = ctx["target_time"].replace(" ", "").upper()
                        for s in available_slots:
                            s_str = s.start_time.strftime("%I:%M%p").upper()
                            s_24 = s.start_time.strftime("%H:%M")
                            if target_t_clean in s_str or target_t_clean in s_24:
                                matched_slot = s
                                break

                        if not matched_slot and available_slots:
                            matched_slot = available_slots[0]  # default to first if ambiguous

                        # Execute booking via service
                        p_name = ctx.get("patient_name") or sender_name or "Valued Patient"
                        appt = await appointment_service.book_appointment(
                            db=db,
                            patient_phone=from_number,
                            doctor_id=selected_doc.id,
                            start_time=matched_slot.start_time,
                            patient_name=p_name,
                            symptoms_notes=f"Booked via WhatsApp Assistant. Specialization: {selected_doc.specialization}"
                        )

                        reply_text = (
                            f"✅ *Appointment Confirmed!*\n\n"
                            f"🆔 *Appointment ID:* #{str(appt.id)[:8]}\n"
                            f"👨‍⚕️ *Doctor:* Dr. {selected_doc.full_name} ({selected_doc.specialization})\n"
                            f"📅 *Date:* {matched_slot.start_time.strftime('%A, %B %d, %Y')}\n"
                            f"⏰ *Time:* {matched_slot.start_time.strftime('%I:%M %p')} - {matched_slot.end_time.strftime('%I:%M %p')}\n"
                            f"👤 *Patient:* {p_name}\n"
                            f"📍 *Clinic:* City Health Clinic, Suite 400\n\n"
                            f"To reschedule or cancel anytime, simply message us here."
                        )
                        session.current_state = ConversationState.BOOKED
                        ctx = {}  # Clear workflow context after successful confirmation

        elif intent == "CANCEL_APPOINTMENT":
            reply_text = (
                "Please provide your Appointment ID (e.g. #a1b2c3d4) that you wish to cancel."
            )
            session.current_state = ConversationState.CANCELLING

        else:
            reply_text = (
                "Hello! 👋 I am your HealthAI Clinic Assistant.\n\n"
                "I can assist you with:\n"
                "1️⃣ *Booking an appointment* with a doctor\n"
                "2️⃣ *Checking available timings*\n"
                "3️⃣ *Rescheduling or cancelling*\n"
                "4️⃣ *Clinic hours and location*\n\n"
                "How may I help you today?"
            )
            session.current_state = ConversationState.NEW

        # Save session updates
        session.context_data = ctx
        session.last_interaction_at = datetime.utcnow()

        # Log outbound message
        out_msg = ConversationMessage(
            session_id=session.id,
            direction=MessageDirection.OUTBOUND,
            message_text=reply_text,
            payload_metadata={"state": session.current_state.value}
        )
        db.add(out_msg)
        await db.commit()

        return {
            "to_number": from_number,
            "reply_text": reply_text,
            "intent": intent,
            "state": session.current_state.value,
            "suggested_actions": suggested_actions
        }

agent = HealthAIAgent()
