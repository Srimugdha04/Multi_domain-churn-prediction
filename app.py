from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import pandas as pd
import numpy as np
import joblib
import os

# ---- Paths ----
SRC_DIR = os.path.join(os.path.dirname(__file__), 'src')

# ===============================
# Optional: TensorFlow
# ===============================
try:
    import tensorflow as tf
    model = tf.keras.models.load_model('nndl_churn_model.h5')
    print("[OK] TensorFlow model loaded.")
    TF_AVAILABLE = True
except Exception as e:
    print(f"[WARNING] TensorFlow not available: {e}")
    print("[INFO] Prediction routes will return dummy data.")
    TF_AVAILABLE = False
    model = None

# ===============================
# Optional: Gemini AI
# ===============================
try:
    import google.generativeai as genai
    genai.configure(api_key="YOUR_GEMINI_API_KEY")
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')
    print("[OK] Gemini AI configured.")
    GEMINI_AVAILABLE = True
except Exception as e:
    print(f"[WARNING] Gemini AI not available: {e}")
    GEMINI_AVAILABLE = False
    gemini_model = None

app = Flask(__name__)
app.secret_key = "be8877e65b2029695107d6455fc2e78fec4e3942f34d2bfa"
CORS(app)

# Load Other Assets
try:
    scaler = joblib.load('scaler.pkl')
    feature_cols = joblib.load('model_features.pkl')
    print("[OK] Scaler and feature columns loaded.")
    SCALER_AVAILABLE = True
except Exception as e:
    print(f"[WARNING] Could not load scaler/features: {e}")
    print("[INFO] Predictions will return dummy data.")
    scaler = None
    feature_cols = None
    SCALER_AVAILABLE = False

df = pd.read_csv('bank_customers_data.csv')
print(f"[OK] CSV loaded: {len(df)} customers across {df['bankId'].nunique()} banks.")

def analyze_bank_risks(bank_id):
    bank_df = df[df['bankId'] == bank_id].copy()
    if bank_df.empty or not TF_AVAILABLE or not SCALER_AVAILABLE:
        if not bank_df.empty:
            # Return random dummy predictions if TF/scaler not available
            bank_df['prob'] = np.random.uniform(10, 95, size=len(bank_df))
        return bank_df
    X = bank_df.drop(columns=['customerId','bankId','name','bankName','managerId','managerName','Churn'], errors='ignore')
    X = pd.get_dummies(X, drop_first=True).reindex(columns=feature_cols, fill_value=0)
    preds = model.predict(scaler.transform(X)).flatten() * 100
    bank_df['prob'] = preds
    return bank_df

# ===============================
# Routes
# ===============================

@app.route("/")
def home():
    """Serve the main app from src/index.html"""
    return send_from_directory(SRC_DIR, "index.html")

@app.route("/<path:filename>")
def serve_files(filename):
    """Serve other HTML or generic files from src/"""
    return send_from_directory(SRC_DIR, filename)

@app.route("/assets/<path:filename>")
def serve_assets(filename):
    """Serve images and js from src/assets/"""
    return send_from_directory(os.path.join(SRC_DIR, 'assets'), filename)

@app.route("/static/css/<path:filename>")
def serve_css(filename):
    """Serve CSS files from src/css/"""
    return send_from_directory(os.path.join(SRC_DIR, 'css'), filename)

@app.route("/static/js/<path:filename>")
def serve_js(filename):
    """Serve JS files from src/js/"""
    return send_from_directory(os.path.join(SRC_DIR, 'js'), filename)

@app.route('/api/auth/login', methods=['POST'])
def login():
    creds = {
        "teja@icici.com": {"pass": "admin123", "name": "VENKATA TEJA", "bankId": "B2"},
        "bharath@sbi.com": {"pass": "admin123", "name": "BHARATH", "bankId": "B1"}
    }
    data = request.json
    email, password = data.get('email'), data.get('password')
    if email in creds and creds[email]['pass'] == password:
        return jsonify({"status": "success", "data": creds[email]})
    return jsonify({"status": "error"}), 401

@app.route('/api/bank/<bank_id>')
def get_bank_data(bank_id):
    bank_df = df[df['bankId'] == bank_id]
    if bank_df.empty:
        return jsonify({"error": "Bank not found"}), 404
    return jsonify({
        'bank_name': str(bank_df['bankName'].iloc[0]),
        'customers': bank_df[['customerId', 'name', 'tenure', 'monthlyCharges']].to_dict('records')
    })

@app.route('/api/predict/all/<bank_id>')
def predict_all(bank_id):
    results_df = analyze_bank_risks(bank_id)
    if results_df.empty:
        return jsonify([])
    return jsonify(results_df[['customerId', 'prob']].to_dict('records'))

@app.route('/api/predict/single', methods=['POST'])
def predict_single():
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    # Normally we would run `model.predict(scaler.transform([features]))`
    # Here we simulate with a dummy response for the frontend UI.
    prob = np.random.uniform(5, 95)
    
    risk_level = "High" if prob >= 70 else "Medium" if prob >= 40 else "Low"
    is_high_risk = prob >= 50
    
    return jsonify({
        "status": "success",
        "probability": float(prob),
        "riskText": f"{risk_level} Risk of Churn",
        "reasons": ["Declining activity over last 3 months", "Low engagement with new products"] if is_high_risk else ["Consistent account balance", "Frequent transactions"],
        "recommendations": ["Offer premium account discount", "Call customer to discuss satisfaction"] if is_high_risk else ["No action required currently"]
    })

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    msg = data.get('message', '').lower()
    bank_id = data.get('bankId')
    results_df = analyze_bank_risks(bank_id)

    if "count" in msg and ("90" in msg or "high risk" in msg):
        count = len(results_df[results_df['prob'] > 90])
        return jsonify({"reply": f"Scanning the ledger... I found {count} customers with a churn risk over 90%."})

    if GEMINI_AVAILABLE:
        try:
            response = gemini_model.generate_content(f"You are Nexa AI for {bank_id}. Answer: {msg}")
            return jsonify({"reply": response.text})
        except:
            pass

    return jsonify({"reply": "I am online and ready to analyze your ledger. (Gemini AI not configured)"})

if __name__ == '__main__':
    print("\n========================================")
    print("  Nexa AI Dashboard - Starting Server")
    print("  URL: http://localhost:5000")
    print("========================================\n")
    app.run(host='0.0.0.0', port=5000, debug=True)