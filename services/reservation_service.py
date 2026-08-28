from models.reservation import Reservation
from services.audit_service import AuditService
from services.db_service import DbService


class ReservationService:

    @staticmethod
    def _get_by_id(connection, reservation_id):
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM reservations WHERE id = %s", (reservation_id,))
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
    def get_by_id(reservation_id):
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
                    WHERE r.id = %s
                """, (reservation_id,))

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
                cursor.execute("""
                    SELECT
                        r.*,
                        rm.name AS room_name
                    FROM reservations r
                    JOIN rooms rm ON rm.id = r.room_id
                    WHERE r.user_id = %s
                    ORDER BY r.start_time
                """, (user_id,))

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
            if end_time <= start_time:
                raise ValueError("End time must be after start time")

            with connection.cursor() as cursor:
                cursor.execute("SELECT id, active FROM rooms WHERE id = %s", (room_id,))
                room = cursor.fetchone()

            if room is None:
                raise ValueError("Room not found")

            if not room["active"]:
                raise ValueError("Room is inactive")

            if ReservationService._has_overlap(connection, room_id, start_time, end_time):
                raise ValueError("Room is already reserved during that time")

            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO reservations
                        (user_id, room_id, title, start_time, end_time)
                    VALUES
                        (%s, %s, %s, %s, %s)
                """, (user_id, room_id, title, start_time, end_time))

                reservation_id = cursor.lastrowid

            reservation = ReservationService._get_by_id(connection, reservation_id)
            reservation_dict = reservation.to_dict()

            AuditService.log(
                connection,
                user_id=user_id,
                table_name="reservations",
                record_id=reservation_id,
                action="INSERT",
                new_data=reservation_dict
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

            if end_time <= start_time:
                raise ValueError("End time must be after start time")

            with connection.cursor() as cursor:
                cursor.execute("SELECT id, active FROM rooms WHERE id = %s", (room_id,))
                room = cursor.fetchone()

            if room is None:
                raise ValueError("Room not found")

            if status == "confirmed":
                if not room["active"]:
                    raise ValueError("Room is inactive")

                if ReservationService._has_overlap(
                    connection,
                    room_id,
                    start_time,
                    end_time,
                    reservation_id
                ):
                    raise ValueError("Room is already reserved during that time")

            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE reservations
                    SET room_id = %s,
                        title = %s,
                        start_time = %s,
                        end_time = %s,
                        status = %s
                    WHERE id = %s
                """, (room_id, title, start_time, end_time, status, reservation_id))

            new_reservation = ReservationService._get_by_id(connection, reservation_id)

            AuditService.log(
                connection,
                user_id=actor_id,
                table_name="reservations",
                record_id=reservation_id,
                action="UPDATE",
                old_data=old_reservation.to_dict(),
                new_data=new_reservation.to_dict()
            )

            connection.commit()
            return new_reservation.to_dict()

        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def delete(reservation_id, actor_id):
        connection = DbService.get_connection()

        try:
            old_reservation = ReservationService._get_by_id(connection, reservation_id)

            if old_reservation is None:
                raise ValueError("Reservation not found")

            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM reservations WHERE id = %s", (reservation_id,))

            AuditService.log(
                connection,
                user_id=actor_id,
                table_name="reservations",
                record_id=reservation_id,
                action="DELETE",
                old_data=old_reservation.to_dict()
            )

            connection.commit()

        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
