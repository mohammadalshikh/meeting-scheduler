from datetime import datetime
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


def test_create_rejects_invalid_time():
    with pytest.raises(ValueError, match="End time must be after start time"):
        ReservationService.create(
            user_id=1,
            room_id=1,
            title="Meeting",
            start_time=datetime(2026, 9, 1, 11, 0),
            end_time=datetime(2026, 9, 1, 10, 0),
        )


def test_create_rejects_inactive_room(monkeypatch):
    connection, cursor = make_connection(
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
        ReservationService.create(
            user_id=1,
            room_id=1,
            title="Meeting",
            start_time=datetime(2026, 9, 1, 10, 0),
            end_time=datetime(2026, 9, 1, 11, 0),
        )

    connection.rollback.assert_called_once()
    connection.close.assert_called_once()


def test_create_rejects_overlapping_reservation(monkeypatch):
    connection, cursor = make_connection(
        fetchone_values=[
            {"id": 1, "active": True},
            {"id": 10},  # overlap found
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
        ReservationService.create(
            user_id=1,
            room_id=1,
            title="Meeting",
            start_time=datetime(2026, 9, 1, 10, 0),
            end_time=datetime(2026, 9, 1, 11, 0),
        )

    connection.rollback.assert_called_once()
    connection.close.assert_called_once()


def test_create_writes_audit_and_commits(monkeypatch):
    connection, cursor = make_connection(
        fetchone_values=[
            {"id": 1, "active": True},
            None,  # no overlap
        ],
        lastrowid=25,
    )

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
    monkeypatch.setattr(
        ReservationService,
        "_get_by_id",
        lambda connection, reservation_id: reservation,
    )

    audit_mock = MagicMock()
    monkeypatch.setattr(AuditService, "log", audit_mock)

    result = ReservationService.create(
        user_id=1,
        room_id=1,
        title="Meeting",
        start_time=datetime(2026, 9, 1, 10, 0),
        end_time=datetime(2026, 9, 1, 11, 0),
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


def test_update_rejects_invalid_status(monkeypatch):
    connection, _ = make_connection()

    existing = MagicMock()
    existing.to_dict.return_value = {"id": 10}

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

    with pytest.raises(ValueError, match="Invalid reservation status"):
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


def test_update_writes_audit_and_commits(monkeypatch):
    connection, cursor = make_connection(
        fetchone_values=[
            {"id": 1, "active": True},
            None,  # no overlapping reservation
        ]
    )

    old_reservation = MagicMock()
    old_reservation.to_dict.return_value = {
        "id": 10,
        "title": "Old meeting",
    }

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

    get_by_id = MagicMock(side_effect=[old_reservation, new_reservation])
    monkeypatch.setattr(
        ReservationService,
        "_get_by_id",
        get_by_id,
    )

    audit_mock = MagicMock()
    monkeypatch.setattr(AuditService, "log", audit_mock)

    result = ReservationService.update(
        reservation_id=10,
        room_id=1,
        title="New meeting",
        start_time=datetime(2026, 9, 1, 10, 0),
        end_time=datetime(2026, 9, 1, 11, 0),
        status="confirmed",
        actor_id=2,
    )

    assert result["title"] == "New meeting"

    audit_mock.assert_called_once_with(
        connection,
        user_id=2,
        table_name="reservations",
        record_id=10,
        action="UPDATE",
        old_data=old_reservation.to_dict(),
        new_data=new_reservation.to_dict(),
    )

    connection.commit.assert_called_once()


def test_delete_writes_audit_and_commits(monkeypatch):
    connection, _ = make_connection()

    old_reservation = MagicMock()
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
    monkeypatch.setattr(AuditService, "log", audit_mock)

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
    connection, cursor = make_connection(lastrowid=5)

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
    monkeypatch.setattr(AuditService, "log", audit_mock)

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
