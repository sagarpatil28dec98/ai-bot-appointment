import pytest
from datetime import date, datetime, timedelta
from app.services.appointment_service import AppointmentService
from app.agents.healthai_agent import HealthAIAgent

def test_heuristic_intent_extractor():
    agent = HealthAIAgent()
    
    # 1. Booking test
    res = agent._heuristic_intent_extractor("I want to book an appointment with a cardiologist tomorrow")
    assert "BOOK_APPOINTMENT" in res
    assert "cardiologist" in res

    # 2. Availability test
    res2 = agent._heuristic_intent_extractor("Are there any free slots for general physician?")
    assert "CHECK_AVAILABILITY" in res2 or "BOOK_APPOINTMENT" in res2

    # 3. Clinic Info test
    res3 = agent._heuristic_intent_extractor("Where is your clinic located and what are the opening hours?")
    assert "CLINIC_INFO" in res3

    # 4. Cancellation test
    res4 = agent._heuristic_intent_extractor("I need to cancel my appointment")
    assert "CANCEL_APPOINTMENT" in res4
