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
    record = {
        "fields": {
            "Date": datetime.now().date().isoformat(),
            "Medication": [med_record_id],
            "Taken": True,
            "Timestamp": datetime.now().isoformat()
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

if __name__ == '__main__':
    app.run(debug=False, port=5000)
