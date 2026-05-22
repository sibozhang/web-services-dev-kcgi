from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import uuid
import re

EMAIL_REGEX = re.compile(r"[^@]+@[^@]+\.[^@]+")

app = Flask(__name__)
CORS(app)


DB_URL = "postgresql+psycopg://postgres:pass@127.0.0.1:5432/assign03_db"
app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True) 
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True)
    phone = db.Column(db.String(20), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone
        }

with app.app_context():
    db.create_all()

def response_field(status_code, data=None, message=None):
    default_messages = {
        200: "Success",
        201: "User created successfully",
        400: "Bad Request: missing required fields",
        404: "Resource not found",
        409: "Conflict: resource already exists",
        500: "Internal server error"
    }
    return {
        "code": status_code,
        "message": message if message else default_messages.get(status_code, "Unknown status"),
        "data": data if data else {},
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "trace": uuid.uuid4().hex
        }
    }


@app.route("/info/<int:user_id>", methods=["GET"])
def get_info(user_id):
    user = db.session.get(User, user_id)
    if user:
        return jsonify(response_field(200, data=user.to_dict())), 200
    else:
        return jsonify(response_field(404, data={"error": "not found"})), 404

@app.route("/info", methods=["POST"])
def create_user():
    receive_data = request.get_json()
    
    if not receive_data or not receive_data.get("name") or not receive_data.get("email"):
        return jsonify(response_field(400, data={"error": "missing name or email"})), 400
    
    if not EMAIL_REGEX.match(receive_data.get("email", "")):
        return jsonify(response_field(400, data={"error": "invalid email format"})), 400

    new_user = User(
        name=receive_data.get("name"),
        email=receive_data.get("email"),
        phone=receive_data.get("phone") 
    )
    
    try:
        db.session.add(new_user)
        db.session.commit()
        return jsonify(response_field(201, data=new_user.to_dict())), 201
    except IntegrityError:
        db.session.rollback()
        return jsonify(response_field(409)), 409
    except Exception as e:
        db.session.rollback() 
        return jsonify(response_field(500, message=str(e))), 500

if __name__ == "__main__":
    app.run(port=2026)