from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import urllib.request
import urllib.error
from datetime import datetime
import os

app = Flask(__name__)
CORS(app)

# Configuration from env
AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN", "")
BASE_ID = os.getenv("BASE_ID", "")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE = os.getenv("TWILIO_PHONE", "+18339142889")
USER_PHONE = "+16177926811"

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

@app.route('/api/log-medication', methods=['POST'])
def log_medication():
    """Log that user took a medication"""
    data = request.json
    medication = data.get('medication')
    
    if not medication:
        return jsonify({"error": "medication required"}), 400
    
    record = {
        "fields": {
            "Date": datetime.now().date().isoformat(),
            "Medication": medication,
            "Taken": True,
            "Timestamp": datetime.now().isoformat()
        }
    }
    
    result = airtable_request("POST", "Adherence%20Log", record)
    
    if result:
        return jsonify({"success": True, "id": result.get('id', 'unknown')})
    else:
        print(f"Error creating record: {result}")
        return jsonify({"error": "Failed to log medication"}), 500

@app.route('/api/adherence', methods=['GET'])
def get_adherence():
    """Get adherence history"""
    result = airtable_request("GET", "Adherence%20Log?sort[0][field]=Date&sort[0][direction]=desc&maxRecords=365")
    
    if result:
        return jsonify(result.get('records', []))
    else:
        return jsonify([])

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})

if __name__ == '__main__':
    app.run(debug=False)
