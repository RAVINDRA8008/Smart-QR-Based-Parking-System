from flask import Flask, render_template, request, jsonify, redirect
from twilio.rest import Client
import random
import json
import time
import base64
import qrcode
import io
import re

app = Flask(__name__)

# In-memory block/slot storage
blocks = {
    "techpark": {str(i): {"status": "available", "device_info": None, "release_qr": None} for i in range(1,51)},
    "medical": {str(i): {"status": "available", "device_info": None, "release_qr": None} for i in range(1, 51)},
    "mba": {str(i): {"status": "available", "device_info": None, "release_qr": None} for i in range(1, 51)},
    "java": {str(i): {"status": "available", "device_info": None, "release_qr": None} for i in range(1, 51)},
    "fablab": {str(i): {"status": "available", "device_info": None, "release_qr": None} for i in range(1, 51)},
    "dental": {str(i): {"status": "available", "device_info": None, "release_qr": None} for i in range(1, 51)},
}

otps = {}

# Twilio config
ACCOUNT_SID = "AC5bc378155c279cc703a2214cc4d63770"
AUTH_TOKEN = "6d5deefbdf0e909015826091ce679a1d"
FROM_PHONE_NUMBER = '+19714174811'
client = Client(ACCOUNT_SID, AUTH_TOKEN)

# === Utilities ===
BASE_URL = os.environ.get("BASE_URL", "http://34.201.105.37:5000/")


def normalize_phone(phone):
    digits = re.sub(r'\D', '', phone)
    if digits.startswith("91") and len(digits) == 12:
        return "+" + digits
    if len(digits) == 10 and digits[0] in "6789":
        return "+91" + digits
    raise ValueError("Invalid phone number format")

def generate_qr(data):
    qr = qrcode.make(data)
    buffer = io.BytesIO()
    qr.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

def generate_otp():
    return str(random.randint(100000, 999999))

def get_booking_message(otp):
    return f"""🌟 Your OTP is: {otp}

You're almost there! Let's make today amazing 🌈✨

– Team Smart Parking 💛"""

def get_release_message(otp):
    return f"""🔓 Your release OTP is: {otp}

Thanks for making space! Keep shining 🌟✨

– Team Smart Parking 💛"""

def send_otp(phone_number, otp, message_text):
    try:
        phone_number = normalize_phone(phone_number)
        message = client.messages.create(
            body=message_text,
            from_=FROM_PHONE_NUMBER,
            to=phone_number
        )
        print(f"✅ OTP sent! SID: {message.sid}, Status: {message.status}")
        return True
    except Exception as e:
        print(f"❌ Error sending OTP: {e}")
        return False

def save_booking_info(block, slot, phone_number, device_info):
    try:
        with open("bookings.json", "r") as f:
            bookings = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        bookings = {}

    bookings[f"{block}_{slot}"] = {
        "phone_number": phone_number,
        "device_info": device_info,
        "timestamp": int(time.time())
    }

    with open("bookings.json", "w") as f:
        json.dump(bookings, f, indent=2)

# === Routes ===

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/status/<block>")
def status(block):
    if block in blocks:
        return jsonify(blocks[block])
    return jsonify({"error": "Block not found"}), 404

@app.route("/generate_qr/<block>/<slot>", methods=["POST"])
def generate_booking_qr(block, slot):
    if block in blocks and slot in blocks[block] and blocks[block][slot]["status"] == "available":
        data = request.get_json()
        device_info = data.get("device_info", {})
        encoded_device = base64.b64encode(json.dumps(device_info).encode()).decode()
        booking_url = f"{BASE_URL}/book/{block}/{slot}/{encoded_device}"
        qr_code = generate_qr(booking_url)
        return jsonify({"qr_code": qr_code}), 200
    return jsonify({"error": "Slot not available"}), 400

@app.route("/send_otp/<block>/<slot>", methods=["POST"])
def send_booking_otp(block, slot):
    data = request.get_json()
    phone_number = data.get("phone_number")
    if not phone_number:
        return jsonify({"error": "Phone number required"}), 400

    try:
        phone_number = normalize_phone(phone_number)
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400

    otp = generate_otp()
    otps[phone_number] = {
        "otp": otp,
        "block": block,
        "slot": slot,
        "expires_at": time.time() + 300
    }

    if send_otp(phone_number, otp, get_booking_message(otp)):
        return jsonify({"success": True}), 200
    return jsonify({"success": False, "message": "Failed to send OTP"}), 500

@app.route("/verify_otp", methods=["POST"])
def verify_otp():
    data = request.get_json()
    try:
        phone_number = normalize_phone(data.get("phone_number"))
    except ValueError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400

    otp = str(data.get("otp")).strip()
    record = otps.get(phone_number)

    if not record:
        return jsonify({"success": False, "message": "OTP not found"}), 400
    if time.time() > record["expires_at"]:
        return jsonify({"success": False, "message": "OTP expired"}), 400
    if record["otp"] == otp:
        block = record["block"]
        slot = record["slot"]
        if blocks[block][slot]["status"] == "available":
            encoded_device = base64.b64encode(phone_number.encode()).decode()
            release_url_with_device = f"{BASE_URL}/release/{block}/{slot}/{encoded_device}"
            release_url_simple = f"{BASE_URL}/release/{block}/{slot}"

            blocks[block][slot]["status"] = "occupied"
            blocks[block][slot]["device_info"] = phone_number
            blocks[block][slot]["release_qr"] = generate_qr(release_url_with_device)

            # Generate the release QR code
            release_qr_image = generate_qr(release_url_with_device)

            # Create a downloadable file for the release QR
            qr_file_name = f"release_qr_{block}_{slot}.png"
            with open(f"static/{qr_file_name}", "wb") as qr_file:
                qr_file.write(base64.b64decode(release_qr_image))

            device_info = {
                "userAgent": request.headers.get("User-Agent"),
                "ip": request.remote_addr,
                "timestamp": int(time.time())
            }
            save_booking_info(block, slot, phone_number, device_info)

            otps.pop(phone_number, None)

            return jsonify({
                "success": True,
                "message": f"Slot {slot} in {block} booked successfully!",
                "release_qr": blocks[block][slot]["release_qr"],
                "release_url": release_url_simple,
                "qr_download_link": f"/static/{qr_file_name}"  # Link to download the QR code
            }), 200

        return jsonify({"success": False, "message": "Slot already occupied"}), 403

    return jsonify({"success": False, "message": "Invalid OTP"}), 400


@app.route("/book/<block>/<slot>/<encoded_device>")
def book_slot(block, slot, encoded_device):
    return render_template("index.html", preselected_block=block, preselected_slot=slot)

@app.route("/release/<block>/<slot>", defaults={"encoded_device": None})
@app.route("/release/<block>/<slot>/<encoded_device>")
def release_slot(block, slot, encoded_device):
    if encoded_device is None:
        try:
            with open("bookings.json", "r") as f:
                bookings = json.load(f)
            booking = bookings.get(f"{block}_{slot}")
            if booking:
                phone_number = booking["phone_number"]
                encoded_device = base64.b64encode(phone_number.encode()).decode()
                return redirect(f"/release/{block}/{slot}/{encoded_device}")
            else:
                return "No booking found to release", 404
        except Exception as e:
            return f"Error reading booking: {e}", 500

    try:
        phone_number = base64.b64decode(encoded_device).decode()
        phone_number = normalize_phone(phone_number)
    except Exception as e:
        return f"Invalid encoded device info: {e}", 400

    print(f"Decoded phone: {phone_number}, Slot Status: {blocks[block][slot]}")

    if blocks[block][slot]["status"] == "occupied" and blocks[block][slot]["device_info"] == phone_number:
        otp = generate_otp()
        otps[phone_number] = {
            "otp": otp,
            "block": block,
            "slot": slot,
            "release": True,
            "expires_at": time.time() + 300
        }
        print(f"Generated Release OTP: {otp}")
        send_otp(phone_number, otp, get_release_message(otp))

    return render_template("release.html", block=block, slot=slot, encoded_device=encoded_device)

@app.route("/release_request/<block>/<slot>", methods=["POST"])
def release_request(block, slot):
    data = request.get_json()
    phone_number = data.get("phone_number")
    if not phone_number:
        return jsonify({"error": "Phone number required"}), 400

    try:
        phone_number = normalize_phone(phone_number)
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400

    if blocks[block][slot]["status"] == "occupied" and blocks[block][slot]["device_info"] == phone_number:
        otp = generate_otp()
        otps[phone_number] = {
            "otp": otp,
            "block": block,
            "slot": slot,
            "release": True,
            "expires_at": time.time() + 300
        }

        if send_otp(phone_number, otp, get_release_message(otp)):
            return jsonify({"success": True}), 200

    return jsonify({"success": False, "message": "Failed to send OTP"}), 500

@app.route("/verify_release_otp", methods=["POST"])
def verify_release_otp():
    data = request.get_json()
    try:
        phone_number = normalize_phone(data.get("phone_number"))
    except ValueError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400

    otp = str(data.get("otp")).strip()
    record = otps.get(phone_number)

    if not record or not record.get("release"):
        return jsonify({"success": False, "message": "Invalid or expired OTP"}), 400
    if time.time() > record["expires_at"]:
        return jsonify({"success": False, "message": "OTP expired"}), 400
    if record["otp"] == otp:
        block = record["block"]
        slot = record["slot"]
        blocks[block][slot]["status"] = "available"
        blocks[block][slot]["device_info"] = None
        blocks[block][slot]["release_qr"] = None
        otps.pop(phone_number, None)
        return jsonify({"success": True, "message": f"Slot {slot} in {block} released successfully!"}), 200

    return jsonify({"success": False, "message": "Invalid OTP"}), 400

@app.route("/auto_send_otp/<block>/<slot>", methods=["POST"])
def auto_send_otp(block, slot):
    try:
        with open("bookings.json", "r") as f:
            bookings = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({"error": "No bookings yet"}), 404

    booking_key = f"{block}_{slot}"
    booking = bookings.get(booking_key)
    if not booking:
        return jsonify({"error": "No booking found for this slot"}), 404

    phone_number = booking.get("phone_number")
    if not phone_number:
        return jsonify({"error": "Phone number missing in booking"}), 400

    try:
        phone_number = normalize_phone(phone_number)
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400

    otp = generate_otp()
    otps[phone_number] = {
        "otp": otp,
        "block": block,
        "slot": slot,
        "expires_at": time.time() + 300
    }

    if send_otp(phone_number, otp, get_booking_message(otp)):
        return jsonify({"success": True, "phone_number": phone_number}), 200
    else:
        return jsonify({"success": False, "message": "Failed to send OTP"}), 500

@app.route("/reset", methods=["POST"])
def reset_all():
    global blocks
    for block in blocks:
        for slot in blocks[block]:
            blocks[block][slot] = {"status": "available", "device_info": None, "release_qr": None}
    return jsonify({"status": "reset"})

@app.route("/release")
def handle_release_query():
    block = request.args.get("block")
    slot = request.args.get("slot")
    encoded_device = request.args.get("device")

    if not block or not slot or not encoded_device:
        return "Missing required parameters", 400

    return render_template(
        "index.html",
        preselected_block=block,
        preselected_slot=slot,
        encoded_device=encoded_device,
        release_mode=True
    )

if __name__ == "__main__":
    app.run(debug=True)
