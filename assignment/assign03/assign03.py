from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone, timedelta
import uuid
import re
import jwt


EMAIL_REGEX = re.compile(r"[^@]+@[^@]+\.[^@]+")
JWT_SECRET  = "supersecret"
JWT_ALGO    = "HS256"

app = Flask(__name__)
CORS(app)


DB_URL = "postgresql+psycopg://postgres:pass@127.0.0.1:5432/assign03_db"
app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# roles
VALID_ROLES = ["admin", "editor", "viewer"]

class User(db.Model):
    __tablename__ = 'users'
    id       = db.Column(db.Integer, primary_key=True)
    name     = db.Column(db.String(100), nullable=False)
    email    = db.Column(db.String(120), nullable=False, unique=True)
    phone    = db.Column(db.String(20),  nullable=True)
    password = db.Column(db.String(100), nullable=False)
    role     = db.Column(db.String(20),  nullable=False, default="viewer")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "role":  self.role
        }

with app.app_context():
    db.create_all()

def response_field(status_code, data=None, message=None):
    default_messages = {
        200: "Success",
        201: "User created successfully",
        400: "Bad Request: missing required fields",
        401: "Unauthorized",
        403: "Forbidden",
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


def create_token(user):
    now = datetime.now(timezone.utc)
    payload = {
        "user_id":  user.id,
        "username": user.name,
        "role":     user.role,
        "iat":      now,
        "exp":      now + timedelta(hours=1),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

def decode_token():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None, ("Missing or bad Authorization header", 401)

    token = auth[len("Bearer "):].strip()
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.ExpiredSignatureError:
        return None, ("Token expired", 401)
    except jwt.InvalidTokenError:
        return None, ("Invalid token", 401)
    return data, None

def require_role(*allowed_roles):
    data, err = decode_token()
    if err:
        return None, err
    if data["role"] not in allowed_roles:
        return None, ("Access denied: insufficient permissions", 403)
    return data, None


@app.route("/register", methods=["POST"])
def register():
    body = request.get_json()
    if not body:
        return jsonify(response_field(400, message="Request body is empty")), 400

    name     = body.get("name")
    email    = body.get("email")
    password = body.get("password")
    role     = body.get("role", "viewer")

    if not name or not email or not password:
        return jsonify(response_field(400, message="name, email, and password are required")), 400
    if not EMAIL_REGEX.match(email):
        return jsonify(response_field(400, message="Invalid email format")), 400
    if role not in VALID_ROLES:
        return jsonify(response_field(400, message=f"role must be one of {VALID_ROLES}")), 400

    new_user = User(
        name=name, email=email, phone=body.get("phone"),
        password=password, role=role
    )

    try:
        db.session.add(new_user)
        db.session.commit()
        return jsonify(response_field(201, data=new_user.to_dict())), 201
    except IntegrityError:
        db.session.rollback()
        return jsonify(response_field(409, message="Email already registered")), 409
    except Exception as e:
        db.session.rollback()
        return jsonify(response_field(500, message=str(e))), 500


@app.route("/login", methods=["POST"])
def login():
    body = request.get_json()
    if not body:
        return jsonify(response_field(400, message="Request body is empty")), 400

    email    = body.get("email")
    password = body.get("password")
    if not email or not password:
        return jsonify(response_field(400, message="email and password are required")), 400

    user = User.query.filter_by(email=email).first()
    if not user or user.password != password:
        return jsonify(response_field(401, message="Invalid email or password")), 401

    token = create_token(user)
    return jsonify(response_field(200, data={
        "token": token,
        "user":  user.to_dict()
    })), 200



@app.route("/info/<int:user_id>", methods=["GET"])
def get_info(user_id):
    data, err = require_role("admin", "editor", "viewer")
    if err:
        msg, code = err
        return jsonify(response_field(code, message=msg)), code

    user = db.session.get(User, user_id)
    if user:
        return jsonify(response_field(200, data=user.to_dict())), 200
    else:
        return jsonify(response_field(404)), 404


# POST /info – admin, editor
@app.route("/info", methods=["POST"])
def create_user():
    data, err = require_role("admin", "editor")
    if err:
        msg, code = err
        return jsonify(response_field(code, message=msg)), code

    receive_data = request.get_json()
    if not receive_data or not receive_data.get("name") or not receive_data.get("email"):
        return jsonify(response_field(400, message="Missing name or email")), 400
    if not EMAIL_REGEX.match(receive_data.get("email", "")):
        return jsonify(response_field(400, message="Invalid email format")), 400

    new_user = User(
        name=receive_data.get("name"),
        email=receive_data.get("email"),
        phone=receive_data.get("phone"),
        password=receive_data.get("password", "default"),
        role=receive_data.get("role", "viewer")
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


@app.route("/info/<int:user_id>", methods=["PUT"])
def update_user(user_id):
    data, err = require_role("admin", "editor")
    if err:
        msg, code = err
        return jsonify(response_field(code, message=msg)), code

    user = db.session.get(User, user_id)
    if not user:
        return jsonify(response_field(404)), 404

    body = request.get_json()
    if not body:
        return jsonify(response_field(400, message="Request body is empty")), 400

    if "name" in body:
        user.name = body["name"]
    if "email" in body:
        if not EMAIL_REGEX.match(body["email"]):
            return jsonify(response_field(400, message="Invalid email format")), 400
        user.email = body["email"]
    if "phone" in body:
        user.phone = body["phone"]

    try:
        db.session.commit()
        return jsonify(response_field(200, data=user.to_dict(), message="User updated")), 200
    except IntegrityError:
        db.session.rollback()
        return jsonify(response_field(409, message="Email already in use")), 409

# GET ALL - admin only
@app.route("/info/all", methods=["GET"])
def list_all_users():
    data, err = require_role("admin")
    if err:
        msg, code = err
        return jsonify(response_field(code, message=msg)), code

    users = User.query.all()
    return jsonify(response_field(200, data=[u.to_dict() for u in users])), 200


# DELETE - admin only
@app.route("/info/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    data, err = require_role("admin")
    if err:
        msg, code = err
        return jsonify(response_field(code, message=msg)), code

    user = db.session.get(User, user_id)
    if not user:
        return jsonify(response_field(404)), 404

    db.session.delete(user)
    db.session.commit()
    return jsonify(response_field(200, data=user.to_dict(), message="User deleted")), 200




if __name__ == "__main__":
    app.run(port=2026)