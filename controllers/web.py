from datetime import datetime, timedelta
from functools import wraps
from zoneinfo import ZoneInfo

from flask import (
    Blueprint,
    render_template,
    request,
    session,
    redirect,
    url_for,
)

from services.room_service import RoomService
from services.reservation_service import ReservationService
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
    return render_template(
        "index.html",
        user=session.get("username"),
        role=session.get("role"),
    )


@web.route("/health")
def health():
    return {"status": "ok"}, 200


@web.route("/register")
def register():
    return render_template("register.html")


@web.route("/login")
def login():
    return render_template(
        "login.html",
        next=request.args.get("next"),
    )


@web.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("web.index"))


@web.route("/schedule")
def schedule():
    now = datetime.now()
    today = now.date()

    if (
        now.time()
        > datetime.strptime(
            "20:30",
            "%H:%M",
        ).time()
    ):
        today += timedelta(days=1)

    max_date = today + timedelta(days=7)

    date_value = request.args.get(
        "date",
        today.isoformat(),
    )

    try:
        selected_date = datetime.strptime(
            date_value,
            "%Y-%m-%d",
        ).date()
    except ValueError:
        selected_date = today

    if selected_date < today:
        selected_date = today

    if selected_date > max_date:
        selected_date = max_date

    rooms = RoomService.get_daily_schedule(selected_date)

    for room in rooms:
        for reservation in room["reservations"]:
            start_time = reservation["start_time"]
            end_time = reservation["end_time"]

            if hasattr(start_time, "isoformat"):
                reservation["start_time"] = start_time.isoformat()

            if hasattr(end_time, "isoformat"):
                reservation["end_time"] = end_time.isoformat()

            start_minutes = start_time.hour * 60 + start_time.minute - 540

            end_minutes = end_time.hour * 60 + end_time.minute - 540

            reservation["left"] = (start_minutes / 720) * 100

            reservation["width"] = ((end_minutes - start_minutes) / 720) * 100

    previous_date = None
    next_date = None

    if selected_date > today:
        previous_date = selected_date - timedelta(days=1)

    if selected_date < max_date:
        next_date = selected_date + timedelta(days=1)

    return render_template(
        "schedule.html",
        rooms=rooms,
        selected_date=selected_date.strftime("%b %-d, %Y"),
        selected_date_value=selected_date.isoformat(),
        previous_date=(previous_date.isoformat() if previous_date else None),
        next_date=(next_date.isoformat() if next_date else None),
    )


@web.route("/reservations")
@login_required
def reservations():
    reservations = ReservationService.get_for_user(session["user_id"])

    return render_template("reservations.html", reservations=reservations)


@web.route("/admin/users")
@admin_required
def admin_users():
    users = UserService.get_all()

    eastern = ZoneInfo("America/Toronto")

    for user in users:
        created_at = user.get("created_at")

        if created_at is not None:
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=ZoneInfo("UTC"))

            user["created_at"] = created_at.astimezone(eastern)

    return render_template(
        "admin_users.html",
        users=users,
    )


@web.route("/admin/reservations")
@admin_required
def admin_reservations():
    reservations = ReservationService.get_all()

    return render_template(
        "admin_reservations.html",
        reservations=reservations,
    )


@web.route("/admin/rooms")
@admin_required
def admin_rooms():
    rooms = RoomService.get_all(active_only=False)

    return render_template(
        "admin_rooms.html",
        rooms=rooms,
    )
