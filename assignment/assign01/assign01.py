from flask import Flask
from flask import request
from datetime import datetime
import uuid
# import json

app = Flask(__name__)

mock_database = [{
        "id": 1,
        "name": "Leanne Graham",
        "email": "Sincere@april.biz",
        "address": {
            "street": "Kulas Light",
            "suite": "Apt. 556",
            "city": "Gwenborough",
            "zipcode": "92998-3874"
        },
        "phone": "1-770-736-8031 x56442"
    },
    {
        "id": 2,
        "name": "Ervin Howell",
        "email": "Shanna@melissa.tv",
        "address": {
            "street": "Victor Plains",
            "suite": "Suite 879",
            "city": "Wisokyburgh",
            "zipcode": "90566-7771"
        },
        "phone": "010-692-6593 x09125"
    }
]

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
    target = [user for user in mock_database if str(user["id"]) == id]

    if target:
        return response_field(200, data=target[0]), 200
    else:
        return response_field(404, data={"error": "not found"}), 404


@app.route("/info", methods=["POST"])
def create_id():
    receive_data = request.json
    
    if not receive_data.get("id"):
        return response_field(400, data={"error": "missing id"}), 400
    
    if any(user["id"] == receive_data["id"] for user in mock_database):
        return response_field(409, data={"conflict": "already exists"}), 409

    mock_database.append(receive_data)
    return response_field(201, data=receive_data), 201
    
app.run(port=2026)