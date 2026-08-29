from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from services.audit_service import AuditService
from services.db_service import DbService
from services.reservation_service import ReservationService
from services.room_service import RoomService
from services.user_service import UserService


def make_connection(fetchone_values=None, lastrowid=1):
    connection = MagicMock()
    cursor = MagicMock()

    cursor.__enter__.return_value = cursor
    cursor.__exit__.return_value = None
    cursor.lastrowid = lastrowid

    if fetchone_values is not None:
        cursor.fetchone.side_effect = fetchone_values

    connection.cursor.return_value = cursor

    return connection, cursor


def test_validate_rejects_invalid_time():
    with pytest.raises(ValueError, match="End time must be after start time"):
        ReservationService.validate_request(
            user_id=1,
            room_id=1,
            start_time=datetime(2026, 9, 1, 11, 0),
            end_time=datetime(2026, 9, 1, 10, 0),
        )


def test_validate_rejects_cross_day_reservation():
    with pytest.raises(ValueError, match="Reservation must be on one day"):
        ReservationService.validate_request(
            user_id=1,
            room_id=1,
            start_time=datetime(2026, 9, 1, 20, 0),
            end_time=datetime(2026, 9, 2, 10, 0),
        )


def test_validate_rejects_outside_booking_hours():
    with pytest.raises(
        ValueError,
        match="Rooms can only be reserved between 9:00 AM and 9:00 PM",
    ):
        ReservationService.validate_request(
            user_id=1,
            room_id=1,
            start_time=datetime(2026, 9, 1, 8, 0),
            end_time=datetime(2026, 9, 1, 10, 0),
        )


def test_validate_rejects_non_30_minute_increment():
    with pytest.raises(
        ValueError,
        match="Reservations must use 30-minute increments",
    ):
        ReservationService.validate_request(
            user_id=1,
            room_id=1,
            start_time=datetime(2026, 9, 1, 10, 15),
            end_time=datetime(2026, 9, 1, 11, 0),
        )


def test_validate_rejects_more_than_7_days_ahead(monkeypatch):
    class FixedDateTime(datetime):
        @classmethod
        def now(cls):
            return cls(2026, 9, 1, 10, 0)

    monkeypatch.setattr(
        "services.reservation_service.datetime",
        FixedDateTime,
    )

    with pytest.raises(
        ValueError,
        match="Reservations can only be made up to 7 days ahead",
    ):
        ReservationService.validate_request(
            user_id=1,
            room_id=1,
            start_time=datetime(2026, 9, 9, 10, 0),
            end_time=datetime(2026, 9, 9, 11, 0),
        )


def test_validate_rejects_inactive_room(monkeypatch):
    connection, _ = make_connection(
        fetchone_values=[
            {"id": 1, "active": False},
        ]
    )

    monkeypatch.setattr(
        DbService,
        "get_connection",
        lambda: connection,
    )

    with pytest.raises(ValueError, match="Room is inactive"):
        ReservationService.validate_request(
            user_id=1,
            room_id=1,
            start_time=datetime(2026, 9, 1, 10, 0),
            end_time=datetime(2026, 9, 1, 11, 0),
        )

    connection.close.assert_called_once()


def test_validate_rejects_same_room_twice_same_day(monkeypatch):
    connection, _ = make_connection(
        fetchone_values=[
            {"id": 1, "active": True},
            {"id": 20},
        ]
    )

    monkeypatch.setattr(
        DbService,
        "get_connection",
        lambda: connection,
    )

    with pytest.raises(
        ValueError,
        match="You can only reserve the same room once per day",
    ):
        ReservationService.validate_request(
            user_id=1,
            room_id=1,
            start_time=datetime(2026, 9, 1, 10, 0),
            end_time=datetime(2026, 9, 1, 11, 0),
        )


def test_validate_rejects_more_than_5_hours_per_day(monkeypatch):
    connection = MagicMock()

    room_cursor = MagicMock()
    room_cursor.__enter__.return_value = room_cursor
    room_cursor.__exit__.return_value = None
    room_cursor.fetchone.return_value = {
        "id": 1,
        "active": True,
    }

    connection.cursor.return_value = room_cursor

    monkeypatch.setattr(
        DbService,
        "get_connection",
        lambda: connection,
    )

    monkeypatch.setattr(
        ReservationService,
        "_has_user_room_reservation",
        lambda *args, **kwargs: False,
    )

    monkeypatch.setattr(
        ReservationService,
        "_get_user_daily_minutes",
        lambda *args, **kwargs: 241,
    )

    monkeypatch.setattr(
        ReservationService,
        "_has_overlap",
        lambda *args, **kwargs: False,
    )

    with pytest.raises(
        ValueError,
        match="You can reserve a maximum of 5 hours per day",
    ):
        ReservationService.validate_request(
            user_id=1,
            room_id=1,
            start_time=datetime(2026, 9, 1, 10, 0),
            end_time=datetime(2026, 9, 1, 11, 0),
        )

    connection.close.assert_called_once()


def test_validate_rejects_overlapping_reservation(monkeypatch):
    connection, _ = make_connection(
        fetchone_values=[
            {"id": 1, "active": True},
            None,
            {"minutes": 0},
            {"id": 20},
        ]
    )

    monkeypatch.setattr(
        DbService,
        "get_connection",
        lambda: connection,
    )

    with pytest.raises(
        ValueError,
        match="Room is already reserved during that time",
    ):
        ReservationService.validate_request(
            user_id=1,
            room_id=1,
            start_time=datetime(2026, 9, 1, 10, 0),
            end_time=datetime(2026, 9, 1, 11, 0),
        )


def test_create_calls_validation_and_writes_audit(monkeypatch):
    connection, cursor = make_connection(lastrowid=25)

    reservation = MagicMock()
    reservation.to_dict.return_value = {
        "id": 25,
        "user_id": 1,
        "room_id": 1,
        "title": "Meeting",
    }

    monkeypatch.setattr(
        DbService,
        "get_connection",
        lambda: connection,
    )

    validate_mock = MagicMock()
    monkeypatch.setattr(
        ReservationService,
        "validate_request",
        validate_mock,
    )

    monkeypatch.setattr(
        ReservationService,
        "_get_by_id",
        lambda connection, reservation_id: reservation,
    )

    audit_mock = MagicMock()
    monkeypatch.setattr(
        AuditService,
        "log",
        audit_mock,
    )

    result = ReservationService.create(
        user_id=1,
        room_id=1,
        title="Meeting",
        start_time=datetime(2026, 9, 1, 10, 0),
        end_time=datetime(2026, 9, 1, 11, 0),
    )

    validate_mock.assert_called_once_with(
        1,
        1,
        datetime(2026, 9, 1, 10, 0),
        datetime(2026, 9, 1, 11, 0),
    )

    assert result["id"] == 25

    audit_mock.assert_called_once_with(
        connection,
        user_id=1,
        table_name="reservations",
        record_id=25,
        action="INSERT",
        new_data=result,
    )

    connection.commit.assert_called_once()
    connection.close.assert_called_once()


def test_create_propagates_validation_error(monkeypatch):
    connection, _ = make_connection()

    monkeypatch.setattr(
        DbService,
        "get_connection",
        lambda: connection,
    )

    monkeypatch.setattr(
        ReservationService,
        "validate_request",
        MagicMock(
            side_effect=ValueError("You can reserve a maximum of 5 hours per day")
        ),
    )

    with pytest.raises(
        ValueError,
        match="You can reserve a maximum of 5 hours per day",
    ):
        ReservationService.create(
            user_id=1,
            room_id=1,
            title="Meeting",
            start_time=datetime(2026, 9, 1, 10, 0),
            end_time=datetime(2026, 9, 1, 11, 0),
        )

    connection.rollback.assert_called_once()
    connection.close.assert_called_once()


def test_update_rejects_invalid_status(monkeypatch):
    connection, _ = make_connection()

    existing = MagicMock()

    monkeypatch.setattr(
        DbService,
        "get_connection",
        lambda: connection,
    )

    monkeypatch.setattr(
        ReservationService,
        "_get_by_id",
        lambda connection, reservation_id: existing,
    )

    with pytest.raises(
        ValueError,
        match="Invalid reservation status",
    ):
        ReservationService.update(
            reservation_id=10,
            room_id=1,
            title="Meeting",
            start_time=datetime(2026, 9, 1, 10, 0),
            end_time=datetime(2026, 9, 1, 11, 0),
            status="invalid",
            actor_id=1,
        )

    connection.rollback.assert_called_once()
    connection.close.assert_called_once()


def test_update_calls_validation_for_confirmed_reservation(monkeypatch):
    connection, _ = make_connection()

    old_reservation = MagicMock()
    old_reservation.user_id = 1

    new_reservation = MagicMock()
    new_reservation.to_dict.return_value = {
        "id": 10,
        "title": "New meeting",
    }

    monkeypatch.setattr(
        DbService,
        "get_connection",
        lambda: connection,
    )

    monkeypatch.setattr(
        ReservationService,
        "_get_by_id",
        MagicMock(
            side_effect=[
                old_reservation,
                new_reservation,
            ]
        ),
    )

    validate_mock = MagicMock()
    monkeypatch.setattr(
        ReservationService,
        "validate_request",
        validate_mock,
    )

    audit_mock = MagicMock()
    monkeypatch.setattr(
        AuditService,
        "log",
        audit_mock,
    )

    result = ReservationService.update(
        reservation_id=10,
        room_id=2,
        title="New meeting",
        start_time=datetime(2026, 9, 1, 10, 0),
        end_time=datetime(2026, 9, 1, 11, 0),
        status="confirmed",
        actor_id=2,
    )

    validate_mock.assert_called_once_with(
        1,
        2,
        datetime(2026, 9, 1, 10, 0),
        datetime(2026, 9, 1, 11, 0),
        10,
    )

    assert result["title"] == "New meeting"
    connection.commit.assert_called_once()


def test_delete_rejects_reservation_within_24_hours(monkeypatch):
    connection, _ = make_connection()

    old_reservation = MagicMock()
    old_reservation.start_time = datetime.now() + timedelta(hours=1)

    monkeypatch.setattr(
        DbService,
        "get_connection",
        lambda: connection,
    )

    monkeypatch.setattr(
        ReservationService,
        "_get_by_id",
        lambda connection, reservation_id: old_reservation,
    )

    with pytest.raises(
        ValueError,
        match="cannot be deleted within 24 hours",
    ):
        ReservationService.delete(
            reservation_id=10,
            actor_id=1,
        )

    connection.rollback.assert_called_once()
    connection.close.assert_called_once()


def test_delete_writes_audit_and_commits(monkeypatch):
    connection, _ = make_connection()

    old_reservation = MagicMock()
    old_reservation.start_time = datetime.now() + timedelta(days=2)
    old_reservation.to_dict.return_value = {
        "id": 10,
        "title": "Meeting",
    }

    monkeypatch.setattr(
        DbService,
        "get_connection",
        lambda: connection,
    )

    monkeypatch.setattr(
        ReservationService,
        "_get_by_id",
        lambda connection, reservation_id: old_reservation,
    )

    audit_mock = MagicMock()

    monkeypatch.setattr(
        AuditService,
        "log",
        audit_mock,
    )

    ReservationService.delete(
        reservation_id=10,
        actor_id=2,
    )

    audit_mock.assert_called_once_with(
        connection,
        user_id=2,
        table_name="reservations",
        record_id=10,
        action="DELETE",
        old_data=old_reservation.to_dict(),
    )

    connection.commit.assert_called_once()
    connection.close.assert_called_once()


def test_room_create_writes_audit_and_commits(monkeypatch):
    connection, _ = make_connection(lastrowid=5)

    room = MagicMock()
    room.to_dict.return_value = {
        "id": 5,
        "name": "Room E",
    }

    monkeypatch.setattr(
        DbService,
        "get_connection",
        lambda: connection,
    )

    monkeypatch.setattr(
        RoomService,
        "_get_by_id",
        lambda connection, room_id: room,
    )

    audit_mock = MagicMock()

    monkeypatch.setattr(
        AuditService,
        "log",
        audit_mock,
    )

    result = RoomService.create(
        name="Room E",
        capacity=10,
        location="3rd Floor",
        description="Training room",
        actor_id=1,
    )

    assert result["id"] == 5

    audit_mock.assert_called_once_with(
        connection,
        user_id=1,
        table_name="rooms",
        record_id=5,
        action="INSERT",
        new_data=result,
    )

    connection.commit.assert_called_once()


def test_user_update_rejects_missing_user(monkeypatch):
    connection, _ = make_connection()

    monkeypatch.setattr(
        DbService,
        "get_connection",
        lambda: connection,
    )

    monkeypatch.setattr(
        UserService,
        "_get_by_id",
        lambda connection, user_id: None,
    )

    with pytest.raises(ValueError, match="User not found"):
        UserService.update(
            user_id=999,
            username="missing",
            email="missing@example.com",
            role="user",
            actor_id=1,
        )

    connection.rollback.assert_called_once()
    connection.close.assert_called_once()
