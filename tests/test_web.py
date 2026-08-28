from unittest.mock import Mock

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


def login(client, user_id=1, username="alice", role="user"):
    with client.session_transaction() as session:
        session["user_id"] = user_id
        session["username"] = username
        session["role"] = role


def test_index_is_public(client):
    response = client.get("/")
    assert response.status_code == 200


def test_register_rejects_missing_fields(client):
    response = client.post(
        "/register",
        data={"username": "", "email": "", "password": ""},
    )

    assert response.status_code == 302
    assert "/register" in response.headers["Location"]


def test_register_rejects_short_password(client):
    response = client.post(
        "/register",
        data={
            "username": "alice",
            "email": "alice@example.com",
            "password": "123",
        },
    )

    assert response.status_code == 302


def test_login_rejects_invalid_credentials(client, monkeypatch):
    monkeypatch.setattr(
        "controllers.web.UserService.get_by_username",
        lambda username: None,
    )

    response = client.post(
        "/login",
        data={"username": "alice", "password": "wrong"},
    )

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_login_creates_session(client, monkeypatch):
    monkeypatch.setattr(
        "controllers.web.UserService.get_by_username",
        lambda username: {
            "id": 1,
            "username": "alice",
            "role": "user",
            "password_hash": "hashed",
        },
    )
    monkeypatch.setattr(
        "controllers.web.check_password_hash",
        lambda stored, supplied: supplied == "correct",
    )

    response = client.post(
        "/login",
        data={"username": "alice", "password": "correct"},
    )

    assert response.status_code == 302

    with client.session_transaction() as session:
        assert session["user_id"] == 1
        assert session["username"] == "alice"
        assert session["role"] == "user"


def test_logout_clears_session(client):
    login(client)

    response = client.get("/logout")

    assert response.status_code == 302

    with client.session_transaction() as session:
        assert "user_id" not in session
        assert "role" not in session


def test_reservations_requires_login(client):
    response = client.get("/reservations")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_normal_user_cannot_access_admin_users(client):
    login(client, role="user")

    response = client.get("/admin/users")

    assert response.status_code == 403


def test_admin_can_access_admin_users(client, monkeypatch):
    login(client, role="admin")

    monkeypatch.setattr(
        "controllers.web.UserService.get_all",
        lambda: [],
    )

    response = client.get("/admin/users")

    assert response.status_code == 200


def test_available_rooms_rejects_invalid_time(client):
    response = client.get("/available_rooms" "?date=2026-09-01&start=12:00&end=11:00")

    assert response.status_code == 302
    assert "/schedule" in response.headers["Location"]


def test_delete_reservation_forbids_other_user(client, monkeypatch):
    login(client, user_id=1, role="user")

    monkeypatch.setattr(
        "controllers.web.ReservationService.get_by_id",
        lambda reservation_id: {"id": 10, "user_id": 2},
    )

    response = client.post("/reservations/10/delete")

    assert response.status_code == 403


def test_delete_reservation_allows_owner(client, monkeypatch):
    login(client, user_id=1, role="user")

    monkeypatch.setattr(
        "controllers.web.ReservationService.get_by_id",
        lambda reservation_id: {"id": 10, "user_id": 1},
    )

    delete_mock = Mock()
    monkeypatch.setattr(
        "controllers.web.ReservationService.delete",
        delete_mock,
    )

    response = client.post("/reservations/10/delete")

    assert response.status_code == 302
    delete_mock.assert_called_once_with(10, 1)
