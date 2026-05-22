from flask import Flask
from flask import request
from flask_cors import CORS
from datetime import datetime
import uuid
import json

app = Flask(__name__)
CORS(app)

def response_field(status_code, data=None, message=None):
    default_messages = {
        200: "Success",
        201: "User created successfully",
        400: "Bad Request: missing required fields",
        404: "Resource not found",
        409: "Conflict: resource already exists",
        500: "Internal server error"
    }

    response_payload = {
        "code" : status_code,
        "message" : message if message else default_messages.get(status_code, "Unknown status"),
        "data" : data if data else {},
        "meta" : {
            "timestamp": datetime.now().isoformat(),
            "trace":uuid.uuid4().hex
        }
    }
    
    return response_payload



@app.route("/info/<id>", methods=["GET"])
def get_info(id):
    try:
        with open("data.json", "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        return response_field(500), 500

    target = [user for user in data if str(user["id"]) == id]

    if target:
        return response_field(200, data=target[0]), 200
    else:
        return response_field(404, data={"error": "not found"}), 404


@app.route("/info", methods=["POST"])
def create_id():
    receive_data = request.json
    try:
        with open("data.json", "r") as f:
            f_data = json.load(f)
    except FileNotFoundError:
        f_data = [] 

    if not receive_data.get("id"):
        return response_field(400, data={"error": "missing id"}), 400
    
    if any(user["id"] == receive_data["id"] for user in f_data):
        return response_field(409, data={"conflict": "already exists"}), 409

    f_data.append(receive_data)
    try:
        with open("data.json", "w") as f:
            json.dump(f_data, f, indent=4)
    except Exception:
        return response_field(500, message="Failed to save data"), 500

    return response_field(201, data=receive_data), 201
    
app.run(port=2026)