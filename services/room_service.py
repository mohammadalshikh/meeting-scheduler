from models.room import Room
from services.audit_service import AuditService
from services.db_service import DbService


class RoomService:

    @staticmethod
    def _get_by_id(connection, room_id):
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM rooms WHERE id = %s", (room_id,))
            row = cursor.fetchone()

        return Room.from_row(row)

    @staticmethod
    def get_by_id(room_id):
        connection = DbService.get_connection()

        try:
            room = RoomService._get_by_id(connection, room_id)
            return room.to_dict() if room else None
        finally:
            connection.close()

    @staticmethod
    def get_all(active_only=False):
        connection = DbService.get_connection()

        try:
            query = """
                SELECT *
                FROM rooms
            """

            if active_only:
                query += " WHERE active = TRUE"

            query += " ORDER BY name"

            with connection.cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()

            return [Room.from_row(row).to_dict() for row in rows]

        finally:
            connection.close()

    @staticmethod
    def get_available(start_time, end_time):
        connection = DbService.get_connection()

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT r.*
                    FROM rooms r
                    WHERE r.active = TRUE
                      AND NOT EXISTS (
                          SELECT 1
                          FROM reservations res
                          WHERE res.room_id = r.id
                            AND res.status = 'confirmed'
                            AND res.start_time < %s
                            AND res.end_time > %s
                      )
                    ORDER BY r.name
                    """,
                    (end_time, start_time),
                )

                rows = cursor.fetchall()

            return [Room.from_row(row).to_dict() for row in rows]
        finally:
            connection.close()

    @staticmethod
    def create(name, capacity, location, description, actor_id):
        connection = DbService.get_connection()

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO rooms
                        (name, capacity, location, description)
                    VALUES
                        (%s, %s, %s, %s)
                    """,
                    (name, capacity, location, description),
                )

                room_id = cursor.lastrowid

            room = RoomService._get_by_id(connection, room_id)

            room_dict = room.to_dict()

            AuditService.log(
                connection,
                user_id=actor_id,
                table_name="rooms",
                record_id=room_id,
                action="INSERT",
                new_data=room_dict,
            )

            connection.commit()
            return room_dict

        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def update(room_id, name, capacity, location, description, active, actor_id):
        connection = DbService.get_connection()

        try:
            old_room = RoomService._get_by_id(connection, room_id)

            if old_room is None:
                raise ValueError("Room not found")

            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE rooms
                    SET name = %s,
                        capacity = %s,
                        location = %s,
                        description = %s,
                        active = %s
                    WHERE id = %s
                    """,
                    (name, capacity, location, description, active, room_id),
                )

            new_room = RoomService._get_by_id(connection, room_id)

            AuditService.log(
                connection,
                user_id=actor_id,
                table_name="rooms",
                record_id=room_id,
                action="UPDATE",
                old_data=old_room.to_dict(),
                new_data=new_room.to_dict(),
            )

            connection.commit()
            return new_room.to_dict()

        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def delete(room_id, actor_id):
        connection = DbService.get_connection()

        try:
            old_room = RoomService._get_by_id(
                connection,
                room_id,
            )

            if old_room is None:
                raise ValueError("Room not found")

            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM rooms WHERE id = %s",
                    (room_id,),
                )

            AuditService.log(
                connection,
                user_id=actor_id,
                table_name="rooms",
                record_id=room_id,
                action="DELETE",
                old_data=old_room.to_dict(),
            )

            connection.commit()

        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
