from datetime import datetime
from functools import wraps

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from services.reservation_service import ReservationService
from services.room_service import RoomService
from services.user_service import UserService

web = Blueprint("web", __name__)

def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("web.login", next=request.url))

        return view(*args, **kwargs)

    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("web.login", next=request.url))

        if session.get("role") != "admin":
            return "Forbidden", 403

        return view(*args, **kwargs)

    return wrapped_view


@web.route("/")
def index():
    return render_template("index.html", user=session.get("username"), role=session.get("role"))


@web.route("/health")
def health():
    return {"status": "ok"}, 200


@web.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not username or not email or not password:
        flash("All fields are required.")
        return redirect(url_for("web.register"))

    if len(password) < 8:
        flash("Password must be at least 8 characters.")
        return redirect(url_for("web.register"))

    if UserService.get_by_username(username):
        flash("Username already exists.")
        return redirect(url_for("web.register"))

    if UserService.get_by_email(email):
        flash("Email already exists.")
        return redirect(url_for("web.register"))

    try:
        UserService.create(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            role="user",
        )
    except Exception:
        flash("Could not create account.")
        return redirect(url_for("web.register"))

    flash("Account created. Please log in.")
    return redirect(url_for("web.login"))


@web.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html", next=request.args.get("next"))

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    user = UserService.get_by_username(username)

    if user is None or not check_password_hash(user["password_hash"], password):
        flash("Invalid username or password.")

        return redirect(url_for("web.login", next=request.args.get("next")))

    session.clear()

    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["role"] = user["role"]
    next_url = request.args.get("next")

    if next_url and next_url.startswith("/"):
        return redirect(next_url)

    return redirect(url_for("web.index"))


@web.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("web.index"))


@web.route("/schedule")
def schedule():
    rooms = RoomService.get_all(active_only=True)

    return render_template("schedule.html", rooms=rooms)


@web.route("/available_rooms")
def available_rooms():
    date = request.args.get("date", "")
    start = request.args.get("start", "")
    end = request.args.get("end", "")

    if not date or not start or not end:
        flash("Date, start time and end time are required.")
        return redirect(url_for("web.schedule"))

    try:
        start_time = datetime.strptime(f"{date} {start}", "%Y-%m-%d %H:%M")

        end_time = datetime.strptime(f"{date} {end}", "%Y-%m-%d %H:%M")

    except ValueError:
        flash("Invalid date or time.")
        return redirect(url_for("web.schedule"))

    if end_time <= start_time:
        flash("End time must be after start time.")
        return redirect(url_for("web.schedule"))

    rooms = RoomService.get_available(start_time, end_time)

    return render_template(
        "available_rooms.html",
        rooms=rooms,
        date=date,
        start=start,
        end=end,
    )


@web.route("/confirm_reservation", methods=["GET", "POST"])
def confirm_reservation():
    room_id = request.values.get("room_id")
    date = request.values.get("date")
    start = request.values.get("start")
    end = request.values.get("end")

    if not room_id or not date or not start or not end:
        flash("Invalid reservation request.")
        return redirect(url_for("web.schedule"))

    try:
        room_id = int(room_id)

        start_time = datetime.strptime(f"{date} {start}", "%Y-%m-%d %H:%M")

        end_time = datetime.strptime(f"{date} {end}", "%Y-%m-%d %H:%M")

    except (ValueError, TypeError):
        flash("Invalid reservation details.")
        return redirect(url_for("web.schedule"))

    if end_time <= start_time:
        flash("End time must be after start time.")
        return redirect(url_for("web.schedule"))

    room = RoomService.get_by_id(room_id)

    if room is None or not room["active"]:
        flash("Room is unavailable.")
        return redirect(url_for("web.schedule"))

    if request.method == "GET":
        return render_template(
            "confirm_reservation.html",
            room=room,
            date=date,
            start=start,
            end=end,
        )

    if "user_id" not in session:
        next_url = url_for(
            "web.confirm_reservation",
            room_id=room_id,
            date=date,
            start=start,
            end=end,
        )

        return redirect(
            url_for(
                "web.login",
                next=next_url,
            )
        )

    title = request.form.get("title", "").strip()

    if not title:
        flash("Meeting title is required.")

        return render_template(
            "confirm_reservation.html",
            room=room,
            date=date,
            start=start,
            end=end,
        )

    try:
        ReservationService.create(
            user_id=session["user_id"],
            room_id=room_id,
            title=title,
            start_time=start_time,
            end_time=end_time,
        )
    except ValueError as error:
        flash(str(error))

        return render_template(
            "confirm_reservation.html",
            room=room,
            date=date,
            start=start,
            end=end,
        )

    flash("Reservation created successfully.")

    return redirect(url_for("web.reservations"))


@web.route("/reservations")
@login_required
def reservations():
    reservations = ReservationService.get_for_user(session["user_id"])

    return render_template("reservations.html", reservations=reservations)


@web.route("/reservations/<int:reservation_id>/delete", methods=["POST"])
@login_required
def delete_reservation(reservation_id):
    reservation = ReservationService.get_by_id(reservation_id)

    if reservation is None:
        flash("Reservation not found.")
        return redirect(url_for("web.reservations"))

    if reservation["user_id"] != session["user_id"] and session.get("role") != "admin":
        return "Forbidden", 403

    try:
        ReservationService.delete(reservation_id, session["user_id"])

    except ValueError as error:
        flash(str(error))
        return redirect(url_for("web.reservations"))

    flash("Reservation deleted.")

    return redirect(url_for("web.reservations"))


@web.route("/admin/users")
@admin_required
def admin_users():
    users = UserService.get_all()

    return render_template("admin_users.html", users=users)


@web.route("/admin/reservations")
@admin_required
def admin_reservations():
    reservations = ReservationService.get_all()

    return render_template("admin_reservations.html",reservations=reservations)
