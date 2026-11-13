# HealthAI Assistant — Setup & Deployment Runbook

A complete production-oriented, modular, Docker-based healthcare appointment booking assistant for WhatsApp.

---

## 1. Quick Start

### Prerequisites
- Docker & Docker Desktop installed and running
- (Optional) Ollama running locally on port 11434 (`ollama run llama3.2`)

### Step 1: Initialize Environment Variables
```bash
cp .env.example .env
```

### Step 2: Launch All Services with Docker Compose
```bash
docker compose up -d --build
```

Services started:
- **FastAPI Core Agent:** `http://localhost:8000` (Docs at `/docs`)
- **PostgreSQL 16:** `localhost:5432`
- **Redis 7:** `localhost:6379`
- **OpenWA WhatsApp Gateway:** `http://localhost:8080`
- **n8n Orchestration Dashboard:** `http://localhost:5678` (Credentials: `admin` / `admin_secure_password`)
- **Nginx Reverse Proxy:** `http://localhost:80`

---

## 2. WhatsApp Pairing (OpenWA)

1. Open `http://localhost:8080` or view the OpenWA container logs:
   ```bash
   docker compose logs -f openwa
   ```
2. Scan the generated QR code with WhatsApp on the clinic's phone.
3. Once authenticated, the session state is saved in the persistent volume `openwa_sessions`.

---

## 3. n8n Workflow Activation

1. Access n8n at `http://localhost:5678`.
2. Login with:
   - **Username:** `admin`
   - **Password:** `admin_secure_password`
3. Click **Workflows** -> **Import from File**, and select `n8n/workflows/incoming_whatsapp.json`.
4. Turn the toggle to **Active**.

---

## 4. Testing WhatsApp Booking via API

You can simulate a patient message without needing a real phone using curl:

```bash
curl -X POST http://localhost:8000/api/v1/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "from_number": "919876543210",
    "message_text": "I want to book an appointment with a cardiologist tomorrow",
    "sender_name": "John Doe"
  }'
```

### Response:
```json
{
  "to_number": "919876543210",
  "reply_text": "Available slots for Dr. Sarah Jenkins on 2026-11-05:\n\n🕒 09:00 AM\n🕒 09:35 AM\n🕒 10:10 AM\n...",
  "intent": "BOOK_APPOINTMENT",
  "state": "COLLECTING_TIME"
}
```

Now select a time slot:
```bash
curl -X POST http://localhost:8000/api/v1/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "from_number": "919876543210",
    "message_text": "09:00 AM",
    "sender_name": "John Doe"
  }'
```

The system will confirm the slot, register the patient in PostgreSQL, and sync to Google Calendar:
```json
{
  "reply_text": "✅ Appointment Confirmed!\n\n🆔 Appointment ID: #f48ab2c1\n👨‍⚕️ Doctor: Dr. Sarah Jenkins (Cardiologist)..."
}
```

---

## 5. Admin Dashboard (React Frontend)

To run the admin frontend locally:
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:3000` to view the clinic dashboard, active doctor statuses, confirmed bookings, and live telemetry.
