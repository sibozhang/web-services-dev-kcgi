from flask import Flask
from flask import request
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

@app.route("/info/<id>", methods=["GET"])
def get_info(id):
    target = [user for user in mock_database if str(user["id"]) == id]

    if target:
        return target[0]
    else:
        return {"error": "not found"}, 404


@app.route("/info", methods=["POST"])
def create_id():
    receive_data = request.json
    
    if any(user["id"] == receive_data["id"] for user in mock_database):
        return {"conflict": "already exists"}, 409

    if receive_data.get("id"):
        mock_database.append(receive_data)
        return {"received": receive_data}, 201
    else:
        return {"error": "missing id"}, 400

app.run(port=2026)