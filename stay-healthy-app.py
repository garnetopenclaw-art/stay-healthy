#!/usr/bin/env python3
"""
Stay Healthy 💊 - API Backend
Handles medication logging, reminders, and adherence tracking
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")
from twilio.rest import Client
import os

app = Flask(__name__, static_folder='.')
CORS(app)

@app.route('/')
def index():
    return send_from_directory('.', 'log-app.html')

@app.route('/dashboard')
def dashboard():
    return send_from_directory('.', 'dashboard.html')

# Configuration
AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN", "")
BASE_ID = "appDU7KETQWA2nEO9"

# Medication record IDs in Airtable (linked record)
MEDICATION_IDS = {
    "rosu": "recNeceFIU2ncSarY",
    "repa": "recITzLhBwyA296tN"
}
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE = os.getenv("TWILIO_PHONE", "")
USER_PHONE = "+16177926811"

# Airtable helpers
def airtable_request(method, path, data=None):
    """Make request to Airtable API"""
    url = f"https://api.airtable.com/v0/{BASE_ID}/{path}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json"
    }
    
    if data:
        data = json.dumps(data).encode('utf-8')
    
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        print(f"Airtable error {e.code}: {e.read().decode()}")
        return None

# Medication logging
@app.route('/api/log-medication', methods=['POST'])
def log_medication():
    """Log that user took a medication"""
    data = request.json
    medication = data.get('medication')  # 'rosu' or 'repa'
    
    if not medication:
        return jsonify({"error": "medication required"}), 400
    
    # Resolve medication to Airtable record ID
    med_record_id = MEDICATION_IDS.get(medication)
    if not med_record_id:
        return jsonify({"error": f"Unknown medication: {medication}"}), 400

    # Add record to Adherence Log
    now_et = datetime.now(EASTERN)
    record = {
        "fields": {
            "Date": now_et.date().isoformat(),
            "Medication": [med_record_id],
            "Taken": True,
            "Timestamp": now_et.isoformat()
        }
    }
    
    result = airtable_request("POST", "Adherence%20Log", record)
    
    if result:
        return jsonify({"success": True, "id": result['id']})
    else:
        return jsonify({"error": "Failed to log medication"}), 500

# Get adherence data
@app.route('/api/adherence', methods=['GET'])
def get_adherence():
    """Get adherence history"""
    result = airtable_request("GET", "Adherence%20Log?sort[0][field]=Date&sort[0][direction]=desc&maxRecords=365")
    
    if result:
        return jsonify(result['records'])
    else:
        return jsonify([])

# Dismiss reminder
@app.route('/api/dismiss-reminder', methods=['POST'])
def dismiss_reminder():
    """Mark reminder as dismissed"""
    data = request.json
    reminder_id = data.get('reminder_id')
    
    if not reminder_id:
        return jsonify({"error": "reminder_id required"}), 400
    
    result = airtable_request("PATCH", f"Reminders/{reminder_id}", {
        "fields": {"Dismissed": True}
    })
    
    if result:
        return jsonify({"success": True})
    else:
        return jsonify({"error": "Failed to dismiss"}), 500

# Send SMS reminder
def send_sms(message):
    """Send SMS via Twilio"""
    if not TWILIO_ACCOUNT_SID:
        print(f"SMS (no Twilio): {message}")
        return True
    
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        client.messages.create(
            body=message,
            from_=TWILIO_PHONE,
            to=USER_PHONE
        )
        return True
    except Exception as e:
        print(f"Twilio error: {e}")
        return False

# Health check
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

# ── Cycle Tracker Webhook ─────────────────────────────────────────────────────

CYCLE_BOT_TOKEN = os.getenv("CYCLE_BOT_TOKEN", "8772392334:AAEoM6hareKFWPxACMY3lKlLwGew6YIEkD8")
CYCLE_AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN", "")
CYCLE_BASE_ID = "appoLZd6uL0qCVfUA"
MESSAGES_TABLE = "tblqq9ofVl6CTingY"
CYCLE_DAYS_TABLE = "tblV7vUrTUWP65BAD"
MJ_CHAT_ID = "1595780133"
HER_CHAT_ID = "8566776829"
CYCLE_START = datetime(2026, 4, 7, tzinfo=EASTERN).date()

def cycle_day():
    today = datetime.now(EASTERN).date()
    return (today - CYCLE_START).days + 1

def cycle_airtable_get(path):
    url = f"https://api.airtable.com/v0/{CYCLE_BASE_ID}/{path}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {CYCLE_AIRTABLE_TOKEN}"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"Airtable error: {e}")
        return None

def cycle_airtable_post(fields):
    url = f"https://api.airtable.com/v0/{CYCLE_BASE_ID}/{MESSAGES_TABLE}"
    body = json.dumps({"records": [{"fields": fields}]}).encode()
    req = urllib.request.Request(url, data=body,
        headers={"Authorization": f"Bearer {CYCLE_AIRTABLE_TOKEN}", "Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"Airtable POST error: {e}")
        return None

def get_day_record_id(day_num):
    result = cycle_airtable_get(f"{CYCLE_DAYS_TABLE}?filterByFormula={{Day}}={day_num}")
    if result and result.get('records'):
        return result['records'][0]['id']
    return None

def send_cycle_telegram(chat_id, text):
    body = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{CYCLE_BOT_TOKEN}/sendMessage",
        data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"Telegram error: {e}")
        return None

@app.route('/api/cycle-webhook', methods=['POST'])
def cycle_webhook():
    """Receive Telegram messages in real time and log to Airtable"""
    data = request.json
    if not data:
        return jsonify({"ok": True})

    msg = data.get('message', {})
    chat_id = str(msg.get('chat', {}).get('id', ''))
    text = msg.get('text', '').strip()

    # Ignore bot commands
    if not text or text.startswith('/'):
        return jsonify({"ok": True})

    # Determine recipient label
    if chat_id == HER_CHAT_ID:
        recipient = "Woman"
    elif chat_id == MJ_CHAT_ID:
        recipient = "Partner"
    else:
        return jsonify({"ok": True})  # Unknown sender

    day = cycle_day()
    day_record_id = get_day_record_id(day)

    # Save to Airtable
    fields = {
        "Date": datetime.now(EASTERN).date().isoformat(),
        "Message": text,
        "Recipient": recipient,
        "Notes (for message replied)": text,
    }
    if day_record_id:
        fields["Day of Cycle"] = [day_record_id]
    cycle_airtable_post(fields)
    print(f"✅ Logged from {recipient} (chat {chat_id}): {text[:60]}")

    # If she confirms cycle reset
    if chat_id == HER_CHAT_ID:
        lower = text.lower()
        if any(kw in lower for kw in ['started', 'day 1', 'new cycle', 'period started', 'just started']):
            send_cycle_telegram(HER_CHAT_ID, "Got it! 🌸 I'll let MJ know and reset your cycle to Day 1. Take care of yourself! 💕")
            send_cycle_telegram(MJ_CHAT_ID, "📅 Bonnie's cycle just reset — today is Day 1. She may need extra comfort today. 💙")

    # Acknowledge her
    if chat_id == HER_CHAT_ID:
        send_cycle_telegram(HER_CHAT_ID, "Got it, thank you for sharing 💕 I've noted that for tomorrow.")

    return jsonify({"ok": True})

if __name__ == '__main__':
    app.run(debug=False, port=5000)
