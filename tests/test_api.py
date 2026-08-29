import pytest

from app import create_app


@pytest.fixture
def app():
    app = create_app()
    app.config.update(
        TESTING=True,
        SECRET_KEY="test-secret",
    )
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, user_id=1, role="user"):
    with client.session_transaction() as session:
        session["user_id"] = user_id
        session["role"] = role


def test_admin_users_requires_authentication(client):
    response = client.get("/api/admin/users")

    assert response.status_code == 401
    assert response.json == {"error": "Admin authentication required"}


def test_admin_users_forbids_normal_user(client):
    login(client, role="user")

    response = client.get("/api/admin/users")

    assert response.status_code == 403
    assert response.json == {"error": "Forbidden"}


def test_admin_can_read_users(client, monkeypatch):
    login(client, role="admin")

    users = [
        {
            "id": 1,
            "username": "alice",
            "email": "alice@example.com",
            "password_hash": "secret",
            "role": "user",
        }
    ]

    monkeypatch.setattr(
        "controllers.api.UserService.get_all",
        lambda: users,
    )

    response = client.get("/api/admin/users")

    assert response.status_code == 200
    assert response.json[0]["username"] == "alice"
    assert "password_hash" not in response.json[0]


def test_admin_can_create_user(client, monkeypatch):
    login(client, role="admin")

    monkeypatch.setattr(
        "controllers.api.UserService.get_by_username",
        lambda username: None,
    )

    monkeypatch.setattr(
        "controllers.api.UserService.get_by_email",
        lambda email: None,
    )

    captured = {}

    def fake_create(username, email, password_hash, role):
        captured.update(
            username=username,
            email=email,
            password_hash=password_hash,
            role=role,
        )

        return {
            "id": 2,
            "username": username,
            "email": email,
            "password_hash": password_hash,
            "role": role,
        }

    monkeypatch.setattr(
        "controllers.api.UserService.create",
        fake_create,
    )

    response = client.post(
        "/api/admin/users",
        json={
            "username": "bob",
            "email": "bob@example.com",
            "password": "password123",
            "role": "user",
        },
    )

    assert response.status_code == 201
    assert response.json["username"] == "bob"
    assert "password_hash" not in response.json
    assert captured["password_hash"] != "password123"


def test_admin_can_update_user(client, monkeypatch):
    login(client, role="admin")

    monkeypatch.setattr(
        "controllers.api.UserService.get_by_id",
        lambda user_id: {
            "id": user_id,
            "username": "bob",
            "email": "bob@example.com",
            "password_hash": "secret",
            "role": "user",
        },
    )

    monkeypatch.setattr(
        "controllers.api.UserService.update",
        lambda **kwargs: {
            "id": kwargs["user_id"],
            "username": kwargs["username"],
            "email": kwargs["email"],
            "password_hash": "secret",
            "role": kwargs["role"],
        },
    )

    response = client.put(
        "/api/admin/users/2",
        json={
            "username": "bob2",
            "email": "bob2@example.com",
        },
    )

    assert response.status_code == 200
    assert response.json["username"] == "bob2"
    assert response.json["email"] == "bob2@example.com"
    assert response.json["role"] == "user"
    assert "password_hash" not in response.json


def test_admin_update_user_requires_username_and_email(client):
    login(client, role="admin")

    response = client.put(
        "/api/admin/users/2",
        json={
            "username": "bob2",
        },
    )

    assert response.status_code == 400
    assert response.json == {"error": "username and email are required"}


def test_admin_cannot_update_missing_user(client, monkeypatch):
    login(client, role="admin")

    monkeypatch.setattr(
        "controllers.api.UserService.get_by_id",
        lambda user_id: None,
    )

    response = client.put(
        "/api/admin/users/999",
        json={
            "username": "missing",
            "email": "missing@example.com",
        },
    )

    assert response.status_code == 404
    assert response.json == {"error": "User not found"}


def test_admin_cannot_delete_own_account(client):
    login(client, user_id=1, role="admin")

    response = client.delete("/api/admin/users/1")

    assert response.status_code == 400
    assert response.json["error"] == "Cannot delete your own account"


def test_admin_can_delete_user(client, monkeypatch):
    login(client, user_id=1, role="admin")

    deleted = {}

    def fake_delete(user_id, actor_id):
        deleted["user_id"] = user_id
        deleted["actor_id"] = actor_id

    monkeypatch.setattr(
        "controllers.api.UserService.delete",
        fake_delete,
    )

    response = client.delete("/api/admin/users/2")

    assert response.status_code == 204
    assert deleted == {
        "user_id": 2,
        "actor_id": 1,
    }


def test_rooms_are_public(client, monkeypatch):
    monkeypatch.setattr(
        "controllers.api.RoomService.get_all",
        lambda active_only: [
            {
                "id": 1,
                "name": "Room A",
                "capacity": 4,
                "active": True,
            }
        ],
    )

    response = client.get("/api/rooms")

    assert response.status_code == 200
    assert response.json[0]["name"] == "Room A"


def test_room_lookup_returns_404(client, monkeypatch):
    monkeypatch.setattr(
        "controllers.api.RoomService.get_by_id",
        lambda room_id: None,
    )

    response = client.get("/api/rooms/999")

    assert response.status_code == 404
    assert response.json == {"error": "Room not found"}


def test_room_schedule_returns_rooms_for_date(client, monkeypatch):
    monkeypatch.setattr(
        "controllers.api.RoomService.get_daily_schedule",
        lambda selected_date: [
            {
                "id": 1,
                "name": "Room A",
                "reservations": [],
            }
        ],
    )

    response = client.get("/api/rooms/schedule?date=2026-09-01")

    assert response.status_code == 200
    assert response.json[0]["name"] == "Room A"


def test_room_schedule_requires_date(client):
    response = client.get("/api/rooms/schedule")

    assert response.status_code == 400
    assert response.json == {"error": "date is required"}


def test_normal_user_cannot_create_room(client):
    login(client, role="user")

    response = client.post(
        "/api/rooms",
        json={
            "name": "Room E",
            "capacity": 10,
        },
    )

    assert response.status_code == 403


def test_admin_can_create_room(client, monkeypatch):
    login(client, role="admin")

    monkeypatch.setattr(
        "controllers.api.RoomService.create",
        lambda **kwargs: {
            "id": 5,
            "name": kwargs["name"],
            "capacity": kwargs["capacity"],
            "active": True,
        },
    )

    response = client.post(
        "/api/rooms",
        json={
            "name": "Room E",
            "capacity": 10,
        },
    )

    assert response.status_code == 201
    assert response.json["name"] == "Room E"


def test_admin_can_update_room(client, monkeypatch):
    login(client, role="admin")

    monkeypatch.setattr(
        "controllers.api.RoomService.update",
        lambda **kwargs: {
            "id": kwargs["room_id"],
            "name": kwargs["name"],
            "capacity": kwargs["capacity"],
            "active": kwargs["active"],
        },
    )

    response = client.put(
        "/api/rooms/1",
        json={
            "name": "Updated Room",
            "capacity": 8,
            "active": True,
        },
    )

    assert response.status_code == 200
    assert response.json["name"] == "Updated Room"


def test_admin_can_delete_room(client, monkeypatch):
    login(client, role="admin")

    monkeypatch.setattr(
        "controllers.api.RoomService.delete",
        lambda room_id, actor_id: None,
    )

    response = client.delete("/api/rooms/1")

    assert response.status_code == 204


def test_available_rooms_validates_datetime(client):
    response = client.get("/api/rooms/available?start=bad&end=bad")

    assert response.status_code == 400
    assert response.json["error"] == "Invalid datetime format"


def test_reservation_validation_requires_authentication(client):
    response = client.post(
        "/api/reservations/validate",
        json={
            "room_id": 1,
            "start_time": "2026-09-01T10:00:00",
            "end_time": "2026-09-01T11:00:00",
        },
    )

    assert response.status_code == 401


def test_reservation_validation_accepts_valid_request(
    client,
    monkeypatch,
):
    login(client, user_id=1, role="user")

    monkeypatch.setattr(
        "controllers.api.ReservationService.validate_request",
        lambda **kwargs: None,
    )

    response = client.post(
        "/api/reservations/validate",
        json={
            "room_id": 1,
            "start_time": "2026-09-01T10:00:00",
            "end_time": "2026-09-01T11:00:00",
        },
    )

    assert response.status_code == 200
    assert response.json == {"valid": True}


def test_reservation_validation_returns_business_rule_error(
    client,
    monkeypatch,
):
    login(client, user_id=1, role="user")

    def fake_validate(**kwargs):
        raise ValueError("You can reserve a maximum of 5 hours per day")

    monkeypatch.setattr(
        "controllers.api.ReservationService.validate_request",
        fake_validate,
    )

    response = client.post(
        "/api/reservations/validate",
        json={
            "room_id": 1,
            "start_time": "2026-09-01T10:00:00",
            "end_time": "2026-09-01T11:00:00",
        },
    )

    assert response.status_code == 400
    assert response.json == {
        "valid": False,
        "error": "You can reserve a maximum of 5 hours per day",
    }


def test_user_can_create_reservation(client, monkeypatch):
    login(client, user_id=1, role="user")

    monkeypatch.setattr(
        "controllers.api.ReservationService.create",
        lambda **kwargs: {
            "id": 10,
            "user_id": kwargs["user_id"],
            "room_id": kwargs["room_id"],
            "title": kwargs["title"],
            "status": "confirmed",
        },
    )

    response = client.post(
        "/api/reservations",
        json={
            "room_id": 1,
            "title": "Meeting",
            "start_time": "2026-09-01T10:00:00",
            "end_time": "2026-09-01T11:00:00",
        },
    )

    assert response.status_code == 201
    assert response.json["user_id"] == 1


def test_user_cannot_update_another_users_reservation(
    client,
    monkeypatch,
):
    login(client, user_id=1, role="user")

    monkeypatch.setattr(
        "controllers.api.ReservationService.get_by_id",
        lambda reservation_id: {
            "id": reservation_id,
            "user_id": 2,
        },
    )

    response = client.put(
        "/api/reservations/10",
        json={
            "room_id": 1,
            "title": "Updated",
            "start_time": "2026-09-01T10:00:00",
            "end_time": "2026-09-01T11:00:00",
            "status": "confirmed",
        },
    )

    assert response.status_code == 403


def test_user_can_delete_own_reservation(client, monkeypatch):
    login(client, user_id=1, role="user")

    monkeypatch.setattr(
        "controllers.api.ReservationService.get_by_id",
        lambda reservation_id: {
            "id": reservation_id,
            "user_id": 1,
        },
    )

    deleted = {}

    def fake_delete(
        reservation_id,
        actor_id,
        actor_role,
    ):
        deleted["reservation_id"] = reservation_id
        deleted["actor_id"] = actor_id
        deleted["actor_role"] = actor_role

    monkeypatch.setattr(
        "controllers.api.ReservationService.delete",
        fake_delete,
    )

    response = client.delete("/api/reservations/10")

    assert response.status_code == 204
    assert deleted == {
        "reservation_id": 10,
        "actor_id": 1,
        "actor_role": "user",
    }


def test_admin_can_delete_another_users_reservation(
    client,
    monkeypatch,
):
    login(client, user_id=1, role="admin")

    monkeypatch.setattr(
        "controllers.api.ReservationService.get_by_id",
        lambda reservation_id: {
            "id": reservation_id,
            "user_id": 2,
        },
    )

    deleted = {}

    def fake_delete(
        reservation_id,
        actor_id,
        actor_role,
    ):
        deleted["reservation_id"] = reservation_id
        deleted["actor_id"] = actor_id
        deleted["actor_role"] = actor_role

    monkeypatch.setattr(
        "controllers.api.ReservationService.delete",
        fake_delete,
    )

    response = client.delete("/api/reservations/10")

    assert response.status_code == 204
    assert deleted == {
        "reservation_id": 10,
        "actor_id": 1,
        "actor_role": "admin",
    }
