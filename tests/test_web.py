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


def test_register_page_is_public(client):
    response = client.get("/register")

    assert response.status_code == 200


def test_login_page_is_public(client):
    response = client.get("/login")

    assert response.status_code == 200


def test_logout_clears_session(client):
    login(client)

    response = client.get("/logout")

    assert response.status_code == 302

    with client.session_transaction() as session:
        assert "user_id" not in session
        assert "username" not in session
        assert "role" not in session


def test_schedule_page_is_public(client, monkeypatch):
    monkeypatch.setattr(
        "controllers.web.RoomService.get_daily_schedule",
        lambda selected_date: [],
    )

    response = client.get("/schedule")

    assert response.status_code == 200


def test_schedule_rejects_date_before_today(client, monkeypatch):
    monkeypatch.setattr(
        "controllers.web.RoomService.get_daily_schedule",
        lambda selected_date: [],
    )

    response = client.get("/schedule?date=2020-01-01")

    assert response.status_code == 200


def test_schedule_rejects_date_beyond_booking_window(client, monkeypatch):
    monkeypatch.setattr(
        "controllers.web.RoomService.get_daily_schedule",
        lambda selected_date: [],
    )

    response = client.get("/schedule?date=2099-01-01")

    assert response.status_code == 200


def test_reservations_requires_login(client):
    response = client.get("/reservations")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_reservations_page_loads_for_logged_in_user(client, monkeypatch):
    login(client)

    monkeypatch.setattr(
        "controllers.web.ReservationService.get_for_user",
        lambda user_id: [],
    )

    response = client.get("/reservations")

    assert response.status_code == 200


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


def test_normal_user_cannot_access_admin_reservations(client):
    login(client, role="user")

    response = client.get("/admin/reservations")

    assert response.status_code == 403


def test_admin_can_access_admin_reservations(client, monkeypatch):
    login(client, role="admin")

    monkeypatch.setattr(
        "controllers.web.ReservationService.get_all",
        lambda: [],
    )

    response = client.get("/admin/reservations")

    assert response.status_code == 200
