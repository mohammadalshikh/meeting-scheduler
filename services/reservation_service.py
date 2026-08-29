from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from models.reservation import Reservation
from services.audit_service import AuditService
from services.db_service import DbService

tz = ZoneInfo("America/Toronto")

class ReservationService:

    @staticmethod
    def _get_by_id(connection, reservation_id):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM reservations WHERE id = %s", (reservation_id,)
            )
            row = cursor.fetchone()

        return Reservation.from_row(row)

    @staticmethod
    def _has_overlap(connection, room_id, start_time, end_time, reservation_id=None):
        query = """
            SELECT id
            FROM reservations
            WHERE room_id = %s
              AND status = 'confirmed'
              AND start_time < %s
              AND end_time > %s
        """

        params = [room_id, end_time, start_time]

        if reservation_id is not None:
            query += " AND id != %s"
            params.append(reservation_id)

        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone() is not None

    @staticmethod
    def _get_user_daily_minutes(
        connection,
        user_id,
        reservation_date,
        reservation_id=None,
    ):
        query = """
            SELECT COALESCE(
                SUM(TIMESTAMPDIFF(MINUTE, start_time, end_time)),
                0
            ) AS minutes
            FROM reservations
            WHERE user_id = %s
              AND DATE(start_time) = %s
              AND status = 'confirmed'
        """

        params = [user_id, reservation_date]

        if reservation_id is not None:
            query += " AND id != %s"
            params.append(reservation_id)

        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()["minutes"]

    @staticmethod
    def _has_user_room_reservation(
        connection,
        user_id,
        room_id,
        reservation_date,
        reservation_id=None,
    ):
        query = """
            SELECT id
            FROM reservations
            WHERE user_id = %s
              AND room_id = %s
              AND DATE(start_time) = %s
              AND status = 'confirmed'
        """

        params = [user_id, room_id, reservation_date]

        if reservation_id is not None:
            query += " AND id != %s"
            params.append(reservation_id)

        query += " LIMIT 1"

        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone() is not None

    @staticmethod
    def validate_request(
        user_id,
        room_id,
        start_time,
        end_time,
        reservation_id=None,
    ):
        if end_time <= start_time:
            raise ValueError("End time must be after start time")

        if start_time.date() != end_time.date():
            raise ValueError("Reservation must be on one day")

        if start_time.hour < 9:
            raise ValueError("Rooms can only be reserved between 9:00 AM and 9:00 PM")

        if end_time.hour > 21 or (end_time.hour == 21 and end_time.minute != 0):
            raise ValueError("Rooms can only be reserved between 9:00 AM and 9:00 PM")

        if start_time.minute not in (0, 30) or end_time.minute not in (0, 30):
            raise ValueError("Reservations must use 30-minute increments")

        now = datetime.now(tz)

        earliest = now.replace(
            minute=0,
            second=0,
            microsecond=0,
        )

        if now.minute > 0 or now.second > 0 or now.microsecond > 0:
            earliest += timedelta(hours=1)

        latest = now + timedelta(days=7)

        if start_time < earliest:
            raise ValueError(
                "Reservations must start no earlier than the next full hour"
            )

        if end_time > latest:
            raise ValueError("Reservations can only be made up to 7 days ahead")

        connection = DbService.get_connection()

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id, active FROM rooms WHERE id = %s",
                    (room_id,),
                )
                room = cursor.fetchone()

            if room is None:
                raise ValueError("Room not found")

            if not room["active"]:
                raise ValueError("Room is inactive")

            if ReservationService._has_user_room_reservation(
                connection,
                user_id,
                room_id,
                start_time.date(),
                reservation_id,
            ):
                raise ValueError("You can only reserve the same room once per day")

            requested_minutes = int((end_time - start_time).total_seconds() / 60)

            existing_minutes = ReservationService._get_user_daily_minutes(
                connection,
                user_id,
                start_time.date(),
                reservation_id,
            )

            if existing_minutes + requested_minutes > 300:
                raise ValueError("You can reserve a maximum of 5 hours per day")

            if ReservationService._has_overlap(
                connection,
                room_id,
                start_time,
                end_time,
                reservation_id,
            ):
                raise ValueError("Room is already reserved during that time")

        finally:
            connection.close()

    @staticmethod
    def get_by_id(reservation_id):
        connection = DbService.get_connection()

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        r.*,
                        u.username,
                        rm.name AS room_name
                    FROM reservations r
                    JOIN users u ON u.id = r.user_id
                    JOIN rooms rm ON rm.id = r.room_id
                    WHERE r.id = %s
                """,
                    (reservation_id,),
                )

                row = cursor.fetchone()

            if row is None:
                return None

            result = Reservation.from_row(row).to_dict()
            result["username"] = row["username"]
            result["room_name"] = row["room_name"]

            return result

        finally:
            connection.close()

    @staticmethod
    def get_all():
        connection = DbService.get_connection()

        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT
                        r.*,
                        u.username,
                        rm.name AS room_name
                    FROM reservations r
                    JOIN users u ON u.id = r.user_id
                    JOIN rooms rm ON rm.id = r.room_id
                    ORDER BY r.start_time
                """)

                rows = cursor.fetchall()

            results = []

            for row in rows:
                result = Reservation.from_row(row).to_dict()
                result["username"] = row["username"]
                result["room_name"] = row["room_name"]
                results.append(result)

            return results

        finally:
            connection.close()

    @staticmethod
    def get_for_user(user_id):
        connection = DbService.get_connection()

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        r.*,
                        rm.name AS room_name
                    FROM reservations r
                    JOIN rooms rm ON rm.id = r.room_id
                    WHERE r.user_id = %s
                    ORDER BY r.start_time
                """,
                    (user_id,),
                )

                rows = cursor.fetchall()

            results = []

            for row in rows:
                result = Reservation.from_row(row).to_dict()
                result["room_name"] = row["room_name"]
                results.append(result)

            return results

        finally:
            connection.close()

    @staticmethod
    def create(user_id, room_id, title, start_time, end_time):
        connection = DbService.get_connection()

        try:
            ReservationService.validate_request(
                user_id,
                room_id,
                start_time,
                end_time,
            )

            start_time_db = start_time.replace(tzinfo=None)
            end_time_db = end_time.replace(tzinfo=None)

            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO reservations
                        (user_id, room_id, title, start_time, end_time)
                    VALUES
                        (%s, %s, %s, %s, %s)
                """,
                    (
                        user_id,
                        room_id,
                        title,
                        start_time_db,
                        end_time_db,
                    ),
                )

                reservation_id = cursor.lastrowid

            reservation = ReservationService._get_by_id(connection, reservation_id)
            reservation_dict = reservation.to_dict()

            AuditService.log(
                connection,
                user_id=user_id,
                table_name="reservations",
                record_id=reservation_id,
                action="INSERT",
                new_data=reservation_dict,
            )

            connection.commit()
            return reservation_dict

        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def update(reservation_id, room_id, title, start_time, end_time, status, actor_id):
        connection = DbService.get_connection()

        try:
            old_reservation = ReservationService._get_by_id(connection, reservation_id)

            if old_reservation is None:
                raise ValueError("Reservation not found")

            if status not in ("confirmed", "cancelled"):
                raise ValueError("Invalid reservation status")

            if status == "confirmed":
                ReservationService.validate_request(
                    old_reservation.user_id,
                    room_id,
                    start_time,
                    end_time,
                    reservation_id,
                )

            start_time_db = start_time.replace(tzinfo=None)
            end_time_db = end_time.replace(tzinfo=None)

            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE reservations
                    SET room_id = %s,
                        title = %s,
                        start_time = %s,
                        end_time = %s,
                        status = %s
                    WHERE id = %s
                """,
                    (
                        room_id,
                        title,
                        start_time_db,
                        end_time_db,
                        status,
                        reservation_id,
                    ),
                )

            new_reservation = ReservationService._get_by_id(connection, reservation_id)

            AuditService.log(
                connection,
                user_id=actor_id,
                table_name="reservations",
                record_id=reservation_id,
                action="UPDATE",
                old_data=old_reservation.to_dict(),
                new_data=new_reservation.to_dict(),
            )

            connection.commit()
            return new_reservation.to_dict()

        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def delete(reservation_id, actor_id, actor_role="user"):
        connection = DbService.get_connection()

        try:
            reservation = ReservationService._get_by_id(
                connection,
                reservation_id,
            )

            if reservation is None:
                raise ValueError("Reservation not found")

            if (actor_role != "admin"
                and reservation.start_time.replace(tzinfo=tz) - datetime.now(tz) <= timedelta(hours=24)
            ):
                raise ValueError("Reservations cannot be deleted within 24 hours of their start time")

            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM reservations
                    WHERE id = %s
                    """,
                    (reservation_id,),
                )

            AuditService.log(
                connection,
                user_id=actor_id,
                table_name="reservations",
                record_id=reservation_id,
                action="DELETE",
                old_data=reservation.to_dict(),
            )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()