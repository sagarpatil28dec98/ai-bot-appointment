const wppconnect = require('@wppconnect-team/wppconnect');
const express = require('express');
const axios = require('axios');
const path = require('path');

const app = express();
app.use(express.json());

const PORT = 2785;
const FASTAPI_WEBHOOK = process.env.FASTAPI_WEBHOOK || 'http://127.0.0.1:8000/api/chat';

let currentClient = null;
let currentQrCodeData = null;
let isConnected = false;

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
            ${isConnected 
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
    res.setHeader('Access-Control-Allow-Origin', '*');
    let phone = null;
    try {
        if (currentClient && currentClient.session) {
            phone = currentClient.session;
        }
    } catch(e) {}
    res.json({
        connected: isConnected,
        qr_code: currentQrCodeData,
        phone: phone || (isConnected ? 'Active Clinic Phone' : null)
    });
});

// Switch / Reconnect Clinic Number (clears session and generates fresh QR)
app.post('/api/logout', async (req, res) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    try {
        if (currentClient) {
            try { await currentClient.logout(); } catch(e) {}
        }
        isConnected = false;
        currentQrCodeData = null;
        res.json({ success: true, message: 'Disconnected. Ready for new clinic phone scan.' });
    } catch(err) {
        res.status(500).json({ error: err.message });
    }
});

// Outbound message endpoint (FastAPI -> WhatsApp)
app.post('/api/send-message', async (req, res) => {
    const { to, content } = req.body;
    if (!currentClient || !isConnected) {
        return res.status(503).json({ error: 'WhatsApp client is not connected yet' });
    }
    try {
        let jid = to;
        if (!jid.includes('@c.us') && !jid.includes('@lid')) {
            jid = `${to}@c.us`;
        }
        await currentClient.sendText(jid, content);
        return res.json({ status: 'sent', to: jid });
    } catch (err) {
        console.error('Error sending message:', err.message);
        return res.status(500).json({ error: err.message });
    }
});

// Start WPPConnect client with extended timeout and stability flags
wppconnect.create({
    session: 'clinic-session',
    catchQR: (base64Qr, asciiQR) => {
        currentQrCodeData = base64Qr;
        isConnected = false;
        console.log('Fresh WhatsApp QR Code generated!');
    },
    statusFind: (statusSession, session) => {
        console.log('Status Session:', statusSession);
        if (statusSession === 'isLogged' || statusSession === 'inChat' || statusSession === 'chatsAvailable') {
            isConnected = true;
            currentQrCodeData = null;
        }
    },
    autoClose: 0, disableWelcome: true, // Disable auto close so QR never expires while scanning
    waitForLogin: true,
    headless: true,
    devtools: false,
    useChrome: true,
    debug: false,
    logQR: false,
    puppeteerOptions: {
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--disable-gpu'
        ]
    }
}).then((client) => {
    currentClient = client;
    isConnected = true;
    console.log('WhatsApp client initialized successfully!');

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
    console.error('Error launching WPPConnect:', err);
});

app.listen(PORT, '0.0.0.0', () => {
    console.log(`WhatsApp Gateway Server listening on http://localhost:${PORT}`);
});
