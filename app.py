from flask import Flask, request, jsonify, render_template

import db

import traceback

import os

import datetime

from werkzeug.utils import secure_filename

app = Flask(__name__, template_folder='templates')

UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

latest_ocr_scan = {

    "image_url": None,

    "detected_text": None,

    "status": "IDLE",

    "timestamp": None,

    "message": "Awaiting scan..."

}

EASYOCR_AVAILABLE = False

reader = None

try:

    import sys, io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    import easyocr

    reader = easyocr.Reader(['en'], gpu=False)

    EASYOCR_AVAILABLE = True

    print("EasyOCR successfully initialized and loaded!")

except Exception as e:

    print(f"EasyOCR could not load ({e}). Falling back to Simulation Mode (plate parsed from filename).")

def perform_ocr(image_path):

    if EASYOCR_AVAILABLE and reader is not None:

        try:

            results = reader.readtext(image_path)

            text = " ".join([res[1] for res in results])

            if text.strip():

                print(f"EasyOCR Text Extracted: '{text}'")

                return text

        except Exception as e:

            print(f"EasyOCR Error: {e}. Falling back to Simulation Mode.")

    filename = os.path.basename(image_path).lower()

    name_part = os.path.splitext(filename)[0]

    if name_part.startswith("scan_") and len(name_part) > 20:

        parts = name_part.split("_", 3)

        if len(parts) >= 4:

            name_part = parts[3]

    simulated_text = name_part.replace("_", "-").upper()

    if simulated_text in ('SCAN', ''):

        print(f"Generic filename detected: '{simulated_text}'. Returning None.")

        return None

    else:

        print(f"Simulation Mode OCR (Extracted from filename): '{simulated_text}'")

        return simulated_text

db.init_db()

@app.after_request

def add_cors_headers(response):

    response.headers['Access-Control-Allow-Origin'] = '*'

    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'

    response.headers['Access-Control-Allow-Methods'] = 'GET,PUT,POST,DELETE,OPTIONS'

    return response

@app.route('/')

def dashboard():

    return render_template('index.html')

@app.route('/api/accounts', methods=['GET'])

def get_accounts():

    try:

        accounts = db.get_accounts()

        return jsonify(accounts), 200

    except Exception as e:

        return jsonify({"error": str(e)}), 500

@app.route('/api/accounts', methods=['POST'])

def create_account():

    data = request.get_json() or {}

    owner_name = data.get('owner_name')

    initial_balance = data.get('initial_balance', 0.0)

    if not owner_name:

        return jsonify({"error": "Missing required field: 'owner_name' is required."}), 400

    try:

        initial_balance = float(initial_balance)

    except ValueError:

        return jsonify({"error": "'initial_balance' must be a valid number."}), 400

    try:

        result = db.create_bank_account(owner_name, initial_balance)

        return jsonify({

            "message": "Bank account created successfully.",

            "id": result['id'],

            "account_number": result['account_number'],

            "owner_name": result['owner_name'],

            "balance": result['balance']

        }), 201

    except Exception as e:

        return jsonify({"error": "Internal server error: " + str(e)}), 500

@app.route('/api/vehicles', methods=['GET'])

def get_vehicles():

    try:

        vehicles = db.get_vehicles()

        return jsonify(vehicles), 200

    except Exception as e:

        return jsonify({"error": str(e)}), 500

@app.route('/api/vehicles', methods=['POST'])

def register_vehicle():

    data = request.get_json() or {}

    car_reg = data.get('car_reg')

    vehicle_type = data.get('vehicle_type')

    rfid_tag = data.get('rfid_tag') or None

    bank_account_id = data.get('bank_account_id')

    if not car_reg or not vehicle_type or not bank_account_id:

        return jsonify({"error": "Missing fields: 'car_reg', 'vehicle_type', and 'bank_account_id' are required."}), 400

    try:

        bank_account_id = int(bank_account_id)

    except ValueError:

        return jsonify({"error": "'bank_account_id' must be an integer."}), 400

    try:

        vehicle_id = db.register_vehicle(car_reg, vehicle_type, rfid_tag, bank_account_id)

        return jsonify({

            "message": "Vehicle registered successfully.",

            "vehicle_id": vehicle_id,

            "car_reg": car_reg.upper(),

            "vehicle_type": vehicle_type.upper(),

            "rfid_tag": rfid_tag.upper() if rfid_tag else None,

            "bank_account_id": bank_account_id

        }), 201

    except ValueError as e:

        return jsonify({"error": str(e)}), 400

    except Exception as e:

        return jsonify({"error": "Internal server error: " + str(e)}), 500

@app.route('/api/deposit', methods=['POST'])

def deposit():

    data = request.get_json() or {}

    identifier = data.get('identifier')

    amount = data.get('amount')

    if not identifier or amount is None:

        return jsonify({"error": "Missing required fields: 'identifier' (account number or vehicle plate) and 'amount' are required."}), 400

    try:

        amount = float(amount)

    except ValueError:

        return jsonify({"error": "'amount' must be a valid number."}), 400

    try:

        result = db.deposit_money(identifier, amount)

        return jsonify({

            "message": "Deposit successful.",

            "account_number": result['account_number'],

            "deposited_amount": amount,

            "new_balance": result['new_balance']

        }), 200

    except ValueError as e:

        return jsonify({"error": str(e)}), 400

    except Exception as e:

        return jsonify({"error": "Internal server error: " + str(e)}), 500

@app.route('/api/toll-pay', methods=['POST'])

def toll_pay():

    data = request.get_json() or {}

    identifier = data.get('identifier')

    amount = data.get('amount')

    toll_booth = data.get('toll_booth', 'MAIN_PLAZA')

    if not identifier:

        return jsonify({"error": "Missing required field: 'identifier' (car_reg or rfid_tag) is required."}), 400

    if amount is not None:

        try:

            amount = float(amount)

        except ValueError:

            return jsonify({"error": "'amount' must be a valid number if provided."}), 400

    try:

        result = db.charge_toll(identifier, amount, toll_booth)

        return jsonify({

            "message": "Toll deduction successful.",

            "status": "SUCCESS",

            "car_reg": result['car_reg'],

            "vehicle_type": result['vehicle_type'],

            "account_number": result['account_number'],

            "previous_balance": result['previous_balance'],

            "deducted_amount": result['deducted_amount'],

            "new_balance": result['new_balance'],

            "toll_booth": toll_booth

        }), 200

    except ValueError as e:

        error_msg = str(e)

        if "Insufficient funds" in error_msg:

            return jsonify({

                "message": "Toll deduction failed due to insufficient funds.",

                "status": "INSUFFICIENT_FUNDS",

                "error": error_msg

            }), 400

        elif "not registered" in error_msg:

            return jsonify({

                "message": "Toll deduction failed. Vehicle not registered.",

                "status": "ACCOUNT_NOT_FOUND",

                "error": error_msg

            }), 404

        else:

            return jsonify({

                "message": "Toll deduction failed.",

                "status": "ERROR",

                "error": error_msg

            }), 400

    except Exception as e:

        return jsonify({"error": "Internal server error: " + str(e)}), 500

@app.route('/api/transactions', methods=['GET'])

def get_transactions():

    car_reg = request.args.get('car_reg')

    try:

        transactions = db.get_transactions(car_reg)

        return jsonify(transactions), 200

    except Exception as e:

        return jsonify({"error": str(e)}), 500

@app.route('/api/<path:path>', methods=['OPTIONS'])

def options_handler(path):

    return jsonify({}), 200

@app.route('/api/latest-scan', methods=['GET'])

def get_latest_scan():

    return jsonify(latest_ocr_scan), 200

@app.route('/api/car-detected', methods=['POST'])

def car_detected():

    global latest_ocr_scan

    latest_ocr_scan = {

        "image_url": None,

        "detected_text": None,

        "status": "WAITING",

        "timestamp": datetime.datetime.now().strftime("%I:%M:%S %p"),

        "message": "Car detected. Waiting for scan..."

    }

    print(">>> Car detected! Scan status reset. Gate closed.")

    return jsonify({"message": "Car detected. Ready to scan.", "status": "WAITING"}), 200

@app.route('/api/manual-trigger', methods=['GET'])

def manual_trigger():

    global latest_ocr_scan

    latest_ocr_scan = {

        "image_url": None,

        "detected_text": None,

        "status": "WAITING",

        "timestamp": datetime.datetime.now().strftime("%I:%M:%S %p"),

        "message": "Manual trigger! Waiting for camera scan..."

    }

    print(">>> MANUAL TRIGGER activated! Status set to WAITING.")

    return jsonify({"message": "Trigger activated! ESP32-CAM will now take a photo.", "status": "WAITING"}), 200

@app.route('/api/camera-trigger', methods=['GET'])

def camera_trigger():

    trigger = (latest_ocr_scan.get("status") == "WAITING")

    return jsonify({"trigger": trigger}), 200

@app.route('/api/toll-pay-image', methods=['POST'])

def toll_pay_image():

    global latest_ocr_scan

    if 'image' not in request.files:

        return jsonify({"error": "No file uploaded. Expected 'image' field."}), 400

    file = request.files['image']

    if file.filename == '':

        return jsonify({"error": "Empty filename."}), 400

    toll_booth = request.form.get('toll_booth', 'OCR_CAMERA_GATE')

    try:

        timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        safe_name = f"scan_{timestamp_str}_{secure_filename(file.filename)}"

        file_path = os.path.join(UPLOAD_FOLDER, safe_name)

        file.save(file_path)

        ocr_text = perform_ocr(file_path)

        if not ocr_text or not ocr_text.strip():

            latest_ocr_scan = {

                "image_url": f"/static/uploads/{safe_name}",

                "detected_text": "EMPTY_TEXT",

                "status": "FAILED",

                "timestamp": datetime.datetime.now().strftime("%I:%M:%S %p"),

                "message": "OCR failed to read license plate"

            }

            return jsonify({

                "status": "OCR_FAILED",

                "message": "Toll deduction failed. OCR could not extract any text from the image.",

                "image_url": f"/static/uploads/{safe_name}"

            }), 400

        vehicle = db.get_vehicle_by_normalized_plate(ocr_text)

        if not vehicle:

            latest_ocr_scan = {

                "image_url": f"/static/uploads/{safe_name}",

                "detected_text": ocr_text,

                "status": "FAILED",

                "timestamp": datetime.datetime.now().strftime("%I:%M:%S %p"),

                "message": f"Plate '{ocr_text}' not registered"

            }

            return jsonify({

                "status": "ACCOUNT_NOT_FOUND",

                "message": f"Toll deduction failed. Plate read '{ocr_text}' is not registered in the system.",

                "error": f"Plate '{ocr_text}' not registered.",

                "image_url": f"/static/uploads/{safe_name}",

                "detected_text": ocr_text

            }), 404

        result = db.charge_toll(vehicle['car_reg'], None, toll_booth)

        latest_ocr_scan = {

            "image_url": f"/static/uploads/{safe_name}",

            "detected_text": ocr_text,

            "status": "SUCCESS",

            "timestamp": datetime.datetime.now().strftime("%I:%M:%S %p"),

            "message": f"Charged ৳{result['deducted_amount']} | Car: {result['car_reg']}"

        }

        return jsonify({

            "message": "Toll deduction successful via OCR.",

            "status": "SUCCESS",

            "car_reg": result['car_reg'],

            "vehicle_type": result['vehicle_type'],

            "account_number": result['account_number'],

            "previous_balance": result['previous_balance'],

            "deducted_amount": result['deducted_amount'],

            "new_balance": result['new_balance'],

            "toll_booth": toll_booth,

            "detected_text": ocr_text,

            "image_url": f"/static/uploads/{safe_name}"

        }), 200

    except ValueError as e:

        error_msg = str(e)

        status_lbl = "ERROR"

        if "Insufficient funds" in error_msg:

            status_lbl = "INSUFFICIENT_FUNDS"

        latest_ocr_scan = {

            "image_url": f"/static/uploads/{safe_name}",

            "detected_text": ocr_text,

            "status": "FAILED",

            "timestamp": datetime.datetime.now().strftime("%I:%M:%S %p"),

            "message": f"Declined: Insufficient Funds"

        }

        return jsonify({

            "message": f"Toll deduction failed: {error_msg}",

            "status": status_lbl,

            "error": error_msg,

            "image_url": f"/static/uploads/{safe_name}",

            "detected_text": ocr_text

        }), 400

    except Exception as e:

        return jsonify({"error": "Internal server error: " + str(e)}), 500

if __name__ == '__main__':

    app.run(host='0.0.0.0', port=5000, debug=True)
