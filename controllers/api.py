from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from services.audit_service import AuditService
from services.db_service import DbService
from services.user_service import UserService
from services.room_service import RoomService
from services.reservation_service import ReservationService

api = Blueprint("api", __name__, url_prefix="/api")
tz = ZoneInfo("America/Toronto")


def authenticated():
    return "user_id" in session


def is_admin():
    return session.get("role") == "admin"


def require_auth():
    if not authenticated():
        return jsonify({"error": "Please log in first"}), 401

    return None


def require_admin():
    if not authenticated():
        return jsonify({"error": "Admin authentication required"}), 401

    if not is_admin():
        return jsonify({"error": "Forbidden"}), 403

    return None


def clean_user(user):
    if user is None:
        return None

    user = dict(user)
    user.pop("password_hash", None)

    return user


def clean_users(users):
    return [clean_user(user) for user in users]


def apply_toronto_timezone(value):
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=tz)

    return value.astimezone(tz)


def clean_reservation(reservation):
    reservation = dict(reservation)

    for field in ("start_time", "end_time", "created_at", "updated_at"):
        if isinstance(reservation.get(field), datetime):
            reservation[field] = apply_toronto_timezone(reservation[field]).isoformat()

    return reservation


def clean_reservations(reservations):
    return [clean_reservation(reservation) for reservation in reservations]


@api.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}

    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "")

    if not username or not email or not password:
        return jsonify({"error": "username, email and password are required"}), 400

    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    if UserService.get_by_username(username):
        return jsonify({"error": "Username already exists"}), 409

    if UserService.get_by_email(email):
        return jsonify({"error": "Email already exists"}), 409

    try:
        user = UserService.create(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            role="user",
        )
    except Exception as error:
        return jsonify({"error": str(error)}), 400

    return jsonify(clean_user(user)), 201


@api.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}

    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    user = UserService.get_by_username(username)

    if user is None or not check_password_hash(
        user["password_hash"],
        password,
    ):
        return jsonify({"error": "Invalid username or password"}), 401

    session.clear()

    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["role"] = user["role"]

    return (
        jsonify(
            {
                "message": "Login successful",
                "user": clean_user(user),
            }
        ),
        200,
    )


@api.route("/auth/logout", methods=["POST"])
def logout():
    session.clear()

    return jsonify({"message": "Logout successful"}), 200


@api.route("/auth/me", methods=["GET"])
def me():
    error = require_auth()

    if error:
        return error

    user = UserService.get_by_id(session["user_id"])

    if user is None:
        session.clear()
        return jsonify({"error": "User not found"}), 404

    return jsonify(clean_user(user)), 200


@api.route("/admin/users", methods=["GET"])
def get_users():
    error = require_admin()

    if error:
        return error

    return jsonify(clean_users(UserService.get_all())), 200


@api.route("/admin/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    error = require_admin()

    if error:
        return error

    user = UserService.get_by_id(user_id)

    if user is None:
        return jsonify({"error": "User not found"}), 404

    return jsonify(clean_user(user)), 200


@api.route("/admin/users", methods=["POST"])
def create_user():
    error = require_admin()

    if error:
        return error

    data = request.get_json(silent=True) or {}

    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "")
    role = data.get("role", "user")

    if not username or not email or not password:
        return jsonify({"error": "username, email and password are required"}), 400

    if role not in ("user", "admin"):
        return jsonify({"error": "Invalid role"}), 400

    if UserService.get_by_username(username):
        return jsonify({"error": "Username already exists"}), 409

    if UserService.get_by_email(email):
        return jsonify({"error": "Email already exists"}), 409

    user = UserService.create(
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
        role=role,
    )

    return jsonify(clean_user(user)), 201


@api.route("/admin/users/<int:user_id>", methods=["PUT"])
def update_user(user_id):
    error = require_admin()

    if error:
        return error

    data = request.get_json(silent=True) or {}

    username = data.get("username", "").strip()
    email = data.get("email", "").strip()

    if not username or not email:
        return jsonify({"error": "username and email are required"}), 400

    existing = UserService.get_by_id(user_id)

    if existing is None:
        return jsonify({"error": "User not found"}), 404

    try:
        user = UserService.update(
            user_id=user_id,
            username=username,
            email=email,
            role=existing["role"],
            actor_id=session["user_id"],
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    return jsonify(clean_user(user)), 200


@api.route("/admin/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    error = require_admin()

    if error:
        return error

    if user_id == session["user_id"]:
        return jsonify({"error": "Cannot delete your own account"}), 400

    try:
        UserService.delete(
            user_id,
            session["user_id"],
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 404

    return "", 204


@api.route("/rooms", methods=["GET"])
def get_rooms():
    active_only = request.args.get("active_only", "true").lower() == "true"

    return jsonify(RoomService.get_all(active_only)), 200


@api.route("/rooms/<int:room_id>", methods=["GET"])
def get_room(room_id):
    room = RoomService.get_by_id(room_id)

    if room is None:
        return jsonify({"error": "Room not found"}), 404

    return jsonify(room), 200


@api.route("/rooms/schedule", methods=["GET"])
def get_room_schedule():
    date_value = request.args.get("date")

    if not date_value:
        return jsonify({"error": "date is required"}), 400

    try:
        selected_date = datetime.strptime(
            date_value,
            "%Y-%m-%d",
        ).date()
    except ValueError:
        return jsonify({"error": "Invalid date format"}), 400

    return jsonify(RoomService.get_daily_schedule(selected_date)), 200


@api.route("/rooms/available", methods=["GET"])
def get_available_rooms():
    start = request.args.get("start")
    end = request.args.get("end")

    if not start or not end:
        return jsonify({"error": "start and end are required"}), 400

    try:
        start_time = datetime.fromisoformat(start).replace(tzinfo=tz)
        end_time = datetime.fromisoformat(end).replace(tzinfo=tz)
    except ValueError:
        return jsonify({"error": "Invalid datetime format"}), 400

    if end_time <= start_time:
        return jsonify({"error": "End time must be after start time"}), 400

    return (
        jsonify(
            RoomService.get_available(
                start_time,
                end_time,
            )
        ),
        200,
    )


@api.route("/rooms", methods=["POST"])
def create_room():
    error = require_admin()

    if error:
        return error

    data = request.get_json(silent=True) or {}

    required = ("name", "capacity")

    if any(field not in data for field in required):
        return jsonify({"error": "name and capacity are required"}), 400

    try:
        room = RoomService.create(
            name=data["name"],
            capacity=data["capacity"],
            location=data.get("location"),
            description=data.get("description"),
            actor_id=session["user_id"],
        )
    except Exception as error:
        return jsonify({"error": str(error)}), 400

    return jsonify(room), 201


@api.route("/rooms/<int:room_id>", methods=["PUT"])
def update_room(room_id):
    error = require_admin()

    if error:
        return error

    data = request.get_json(silent=True) or {}

    required = ("name", "capacity", "active")

    if any(field not in data for field in required):
        return jsonify({"error": "name, capacity and active are required"}), 400

    try:
        room = RoomService.update(
            room_id=room_id,
            name=data["name"],
            capacity=data["capacity"],
            location=data.get("location"),
            description=data.get("description"),
            active=data["active"],
            actor_id=session["user_id"],
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 404

    return jsonify(room), 200


@api.route("/rooms/<int:room_id>", methods=["DELETE"])
def delete_room(room_id):
    error = require_admin()

    if error:
        return error

    try:
        RoomService.delete(
            room_id,
            session["user_id"],
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 404

    return "", 204


@api.route("/reservations/validate", methods=["POST"])
def validate_reservation():
    error = require_auth()

    if error:
        return error

    data = request.get_json(silent=True) or {}

    required = (
        "room_id",
        "start_time",
        "end_time",
    )

    if any(field not in data for field in required):
        return jsonify({"error": "room_id, start_time and end_time are required"}), 400

    try:
        room_id = int(data["room_id"])
        start_time = datetime.fromisoformat(data["start_time"]).replace(tzinfo=tz)
        end_time = datetime.fromisoformat(data["end_time"]).replace(tzinfo=tz)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid reservation details"}), 400

    try:
        ReservationService.validate_request(
            user_id=session["user_id"],
            room_id=room_id,
            start_time=start_time,
            end_time=end_time,
        )
    except ValueError as error:
        return (
            jsonify(
                {
                    "valid": False,
                    "error": str(error),
                }
            ),
            400,
        )

    return jsonify({"valid": True}), 200


@api.route("/reservations/<int:reservation_id>", methods=["GET"])
def get_reservation(reservation_id):
    error = require_auth()

    if error:
        return error

    reservation = ReservationService.get_by_id(reservation_id)

    if reservation is None:
        return jsonify({"error": "Reservation not found"}), 404

    if reservation["user_id"] != session["user_id"] and not is_admin():
        return jsonify({"error": "Forbidden"}), 403

    return jsonify(clean_reservation(reservation)), 200


@api.route("/reservations", methods=["POST"])
def create_reservation():
    error = require_auth()

    if error:
        return error

    data = request.get_json(silent=True) or {}

    required = (
        "room_id",
        "title",
        "start_time",
        "end_time",
    )

    if any(field not in data for field in required):
        return jsonify({"error": "Missing required fields"}), 400

    try:
        reservation = ReservationService.create(
            user_id=session["user_id"],
            room_id=int(data["room_id"]),
            title=data["title"],
            start_time=datetime.fromisoformat(data["start_time"]).replace(tzinfo=tz),
            end_time=datetime.fromisoformat(data["end_time"]).replace(tzinfo=tz),
        )
    except (ValueError, TypeError) as error:
        return jsonify({"error": str(error)}), 400

    return jsonify(clean_reservation(reservation)), 201


@api.route("/reservations/<int:reservation_id>", methods=["PUT"])
def update_reservation(reservation_id):
    error = require_auth()

    if error:
        return error

    existing = ReservationService.get_by_id(reservation_id)

    if existing is None:
        return jsonify({"error": "Reservation not found"}), 404

    if existing["user_id"] != session["user_id"] and not is_admin():
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json(silent=True) or {}

    required = (
        "room_id",
        "title",
        "start_time",
        "end_time",
        "status",
    )

    if any(field not in data for field in required):
        return jsonify({"error": "Missing required fields"}), 400

    try:
        reservation = ReservationService.update(
            reservation_id=reservation_id,
            room_id=int(data["room_id"]),
            title=data["title"],
            start_time=datetime.fromisoformat(data["start_time"]).replace(tzinfo=tz),
            end_time=datetime.fromisoformat(data["end_time"]).replace(tzinfo=tz),
            status=data["status"],
            actor_id=session["user_id"],
        )
    except (ValueError, TypeError) as error:
        return jsonify({"error": str(error)}), 400

    return jsonify(clean_reservation(reservation)), 200


@api.route("/reservations/<int:reservation_id>", methods=["DELETE"])
def delete_reservation(reservation_id):
    error = require_auth()

    if error:
        return error

    existing = ReservationService.get_by_id(reservation_id)

    if existing is None:
        return jsonify({"error": "Reservation not found"}), 404

    if existing["user_id"] != session["user_id"] and not is_admin():
        return jsonify({"error": "Forbidden"}), 403

    try:
        ReservationService.delete(
            reservation_id=reservation_id,
            actor_id=session["user_id"],
            actor_role=session["role"],
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    return "", 204