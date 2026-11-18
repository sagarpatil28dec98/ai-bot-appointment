const wppconnect = require('@wppconnect-team/wppconnect');
const express = require('express');
const axios = require('axios');
const path = require('path');
const fs = require('fs');

const app = express();
app.use(express.json());
app.use((req, res, next) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, PUT, DELETE');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
    if (req.method === 'OPTIONS') {
        return res.sendStatus(200);
    }
    next();
});

const PORT = 2785;
const FASTAPI_WEBHOOK = process.env.FASTAPI_WEBHOOK || 'http://127.0.0.1:8000/api/chat';

let currentClient = null;
let currentQrCodeData = null;
let clientState = 'idle'; // 'idle' | 'starting' | 'qr_ready' | 'connected'
let retryTimer = null;

function cleanStaleSession() {
    try {
        const { execSync } = require('child_process');
        try { execSync('pkill -f "tokens/clinic-session" || true'); } catch(e) {}
        const tokenDir = path.join(__dirname, 'tokens/clinic-session');
        const lockFiles = ['SingletonLock', 'SingletonSocket', 'SingletonCookie', 'DevToolsActivePort', 'RunningChromeVersion'];
        for (const file of lockFiles) {
            try {
                fs.unlinkSync(path.join(tokenDir, file));
            } catch(e) {}
        }
    } catch(e) {}
}

function resetSession() {
    cleanStaleSession();
    try {
        const tokenDir = path.join(__dirname, 'tokens/clinic-session');
        if (fs.existsSync(tokenDir)) {
            fs.rmSync(tokenDir, { recursive: true, force: true });
        }
    } catch(e) {}
}

function scheduleReconnect(delayMs = 4000) {
    if (retryTimer) clearTimeout(retryTimer);
    retryTimer = setTimeout(() => {
        retryTimer = null;
        initWhatsAppClient();
    }, delayMs);
}

app.get('/', (req, res) => {
    res.send(`
    <!DOCTYPE html>
    <html>
    <head>
        <title>WhatsApp AI Bot - QR Code</title>
        <meta http-equiv="refresh" content="5">
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; margin: 0; background: #0b141a; color: #e9edef; }
            .card { background: #111b21; border-radius: 12px; padding: 32px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); text-align: center; max-width: 420px; border: 1px solid #222e35; }
            h2 { color: #00a884; margin-top: 0; }
            img { width: 280px; height: 280px; border-radius: 8px; margin: 16px 0; background: white; padding: 12px; }
            .status { font-size: 14px; color: #8696a0; margin-top: 8px; }
            .success { color: #00a884; font-weight: bold; font-size: 18px; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>WhatsApp AI Assistant</h2>
            ${clientState === 'connected'
                ? '<div class="success">Connected to WhatsApp! The AI Assistant is active and ready to reply.</div>' 
                : currentQrCodeData 
                    ? '<p>Scan with your WhatsApp phone app:</p><img src="' + currentQrCodeData + '" alt="QR Code"/><div class="status">Go to WhatsApp &gt; Linked Devices &gt; Link a Device</div>' 
                    : '<p>Starting WhatsApp engine and generating QR code... (auto-refreshes every 5s)</p>'
            }
        </div>
    </body>
    </html>
    `);
});

// API Status Endpoint for the Main Portal UI
app.get('/api/status', (req, res) => {
    let phone = null;
    try {
        if (currentClient && currentClient.session) {
            phone = currentClient.session;
        }
    } catch(e) {}

    res.json({
        connected: clientState === 'connected',
        qr_code: currentQrCodeData,
        phone: phone || (clientState === 'connected' ? 'Active Clinic Phone' : null),
        status: clientState === 'connected' ? 'connected' : (currentQrCodeData ? 'qr_ready' : clientState)
    });
});

// Switch / Reconnect Clinic Number (clears session and generates fresh QR)
app.post('/api/logout', async (req, res) => {
    try {
        if (currentClient) {
            try { await currentClient.logout(); } catch(e) {}
            try { await currentClient.close(); } catch(e) {}
        }
    } catch(err) {}
    clientState = 'idle';
    currentClient = null;
    currentQrCodeData = null;
    resetSession();
    scheduleReconnect(1000);
    res.json({ success: true, message: 'Disconnected. Generating fresh QR code...' });
});

// Outbound message endpoint (FastAPI -> WhatsApp)
app.post('/api/send-message', async (req, res) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    const to = req.body.to || req.body.phone;
    const content = req.body.content || req.body.message;

    if (!to || !content) {
        return res.status(400).json({ error: 'Missing destination (to/phone) or message content' });
    }

    if (!currentClient || clientState !== 'connected') {
        console.log(`[Outbound Queued/Simulated] WhatsApp client not connected. Target: ${to}, Message preview: ${content.substring(0, 40)}...`);
        return res.json({ status: 'simulated_or_queued', to: to, warning: 'WhatsApp phone not linked; notification simulated' });
    }

    try {
        let jid = String(to).replace(/[^0-9]/g, '');
        if (!jid.includes('@c.us') && !jid.includes('@lid')) {
            jid = `${jid}@c.us`;
        }
        await currentClient.sendText(jid, content);
        console.log(`[Outbound WhatsApp Sent] Dispatched to ${jid}`);
        return res.json({ status: 'sent', to: jid });
    } catch (err) {
        console.error('Error sending message:', err.message);
        return res.status(500).json({ error: err.message });
    }
});

// Interactive Simulator Endpoint for In-Browser Testing
app.post('/api/simulate-chat', async (req, res) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    const { message, phone, patient_name, clinic_id, clinic_name } = req.body;
    const senderPhone = (phone || '919876543210').replace(/[^0-9]/g, '');
    const patientName = patient_name || 'Patient';

    try {
        const payload = {
            message: message || 'Hi, need appointment in Surat',
            session_id: `wa_${senderPhone}`,
            phone: senderPhone,
            patient_name: patientName
        };
        if (clinic_id) payload.clinic_id = clinic_id;
        if (clinic_name) payload.clinic_name = clinic_name;

        const resp = await axios.post(FASTAPI_WEBHOOK, payload);
        return res.json({
            success: true,
            phone: senderPhone,
            reply: resp.data.message || 'Consultation details recorded.',
            clinic: resp.data.clinic || null,
            booking: resp.data.booking || null
        });
    } catch (err) {
        console.error('Simulation error:', err.message);
        return res.status(500).json({ success: false, error: err.message });
    }
});

function initWhatsAppClient() {
    if (clientState === 'starting' || clientState === 'connected') return;
    clientState = 'starting';
    console.log('Initializing WPPConnect WhatsApp Client...');

    wppconnect.create({
        session: 'clinic-session',
        catchQR: (base64Qr, asciiQR, attempts, urlCode) => {
            currentQrCodeData = base64Qr;
            clientState = 'qr_ready';
            console.log(`Fresh WhatsApp QR Code generated (attempt ${attempts || 1}) and ready to scan!`);
            try {
                const base64Data = base64Qr.replace(/^data:image\/png;base64,/, "");
                fs.writeFileSync(path.join(__dirname, 'qr.png'), base64Data, 'base64');
            } catch(e) {}
        },
        statusFind: (statusSession, session) => {
            console.log('Status Session:', statusSession);
            if (statusSession === 'isLogged' || statusSession === 'inChat' || statusSession === 'chatsAvailable') {
                clientState = 'connected';
                currentQrCodeData = null;
                console.log('*** WhatsApp Client Successfully Logged In and Ready! ***');
            } else if (statusSession === 'browserClose' || statusSession === 'disconnected') {
                console.log(`WhatsApp session state shifted to: ${statusSession}`);
                clientState = 'idle';
                currentClient = null;
                currentQrCodeData = null;
                cleanStaleSession();
                scheduleReconnect(3000);
            }
        },
        autoClose: 0,
        disableWelcome: true,
        waitForLogin: true,
        headless: true,
        devtools: false,
        useChrome: false,
        debug: false,
        logQR: true,
        puppeteerOptions: {
            args: [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage'
            ]
        }
    }).then((client) => {
        currentClient = client;
        clientState = 'connected';
        console.log('WhatsApp client connected and ready to receive messages!');

        // Inbound listener -> forward to FastAPI
        client.onMessage(async (message) => {
            if (message.fromMe || !message.body) return;
            const senderId = message.from || '';
            if (senderId.includes('@newsletter') || senderId.includes('status@broadcast') || senderId.includes('@broadcast') || senderId.includes('@g.us')) {
                return;
            }
            try {
                console.log(`Received WhatsApp message from ${message.from}: ${message.body}`);
                const senderPhone = (message.from || '').replace('@c.us', '').replace('@lid', '').replace('@s.whatsapp.net', '');
                
                // Forward to active local Healthcare AI Assistant on port 8000
                // Target clinic is dynamically determined by matching phone or active clinic
                const resp = await axios.post(FASTAPI_WEBHOOK, {
                    message: message.body,
                    session_id: senderPhone,
                    phone: senderPhone,
                    patient_name: message.notifyName || (message.sender && message.sender.pushname) || 'Patient'
                });

                console.log('Healthcare AI reply generated:', resp.data.message ? resp.data.message.substring(0, 60) + '...' : 'Done');
                
                // Send reply directly back to WhatsApp patient!
                if (resp.data && resp.data.message && currentClient) {
                    await currentClient.sendText(message.from, resp.data.message);
                    console.log(`Replied directly to ${message.from} via WhatsApp!`);
                }
            } catch (err) {
                console.error('Failed to dispatch message to FastAPI:', err.message);
            }
        });
    }).catch((err) => {
        clientState = 'idle';
        console.error('WPPConnect launch error (Gateway will retry):', err.message);
        cleanStaleSession();
        scheduleReconnect(5000);
    });
}

// Start client initialization after clearing any stale locks
cleanStaleSession();
initWhatsAppClient();

app.listen(PORT, '0.0.0.0', () => {
    console.log(`WhatsApp Gateway Server listening on http://localhost:${PORT}`);
});
