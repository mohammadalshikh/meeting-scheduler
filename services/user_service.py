from models.user import User
from services.audit_service import AuditService
from services.db_service import DbService


class UserService:

    @staticmethod
    def _get_by_id(connection, user_id):
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            row = cursor.fetchone()

        return User.from_row(row)

    @staticmethod
    def get_by_id(user_id):
        connection = DbService.get_connection()

        try:
            user = UserService._get_by_id(connection, user_id)
            return user.to_dict() if user else None
        finally:
            connection.close()

    @staticmethod
    def get_by_username(username):
        connection = DbService.get_connection()

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
                row = cursor.fetchone()

            user = User.from_row(row)
            return user.to_dict() if user else None
        finally:
            connection.close()

    @staticmethod
    def get_by_email(email):
        connection = DbService.get_connection()

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
                row = cursor.fetchone()

            user = User.from_row(row)
            return user.to_dict() if user else None
        finally:
            connection.close()


    @staticmethod
    def get_all():
        connection = DbService.get_connection()

        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT id, username, email, role, created_at
                    FROM users
                    ORDER BY id
                """)
                rows = cursor.fetchall()

            return [dict(row) for row in rows]
        finally:
            connection.close()


    @staticmethod
    def create(username, email, password_hash, role="user"):
        connection = DbService.get_connection()

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO users
                        (username, email, password_hash, role)
                    VALUES
                        (%s, %s, %s, %s)
                """,
                    (username, email, password_hash, role),
                )

                user_id = cursor.lastrowid

            user = UserService._get_by_id(connection, user_id)
            user_dict = user.to_dict()

            AuditService.log(
                connection,
                user_id=user_id,
                table_name="users",
                record_id=user_id,
                action="INSERT",
                new_data=user_dict,
            )

            connection.commit()
            return user_dict

        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def update(user_id, username, email, role, actor_id):
        connection = DbService.get_connection()

        try:
            old_user = UserService._get_by_id(connection, user_id)

            if old_user is None:
                raise ValueError("User not found")

            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE users
                    SET username = %s,
                        email = %s,
                        role = %s
                    WHERE id = %s
                """,
                    (username, email, role, user_id),
                )

            new_user = UserService._get_by_id(connection, user_id)

            AuditService.log(
                connection,
                user_id=actor_id,
                table_name="users",
                record_id=user_id,
                action="UPDATE",
                old_data=old_user.to_dict(),
                new_data=new_user.to_dict(),
            )

            connection.commit()
            return new_user.to_dict()

        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def delete(user_id, actor_id):
        connection = DbService.get_connection()

        try:
            old_user = UserService._get_by_id(connection, user_id)

            if old_user is None:
                raise ValueError("User not found")

            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))

            AuditService.log(
                connection,
                user_id=actor_id,
                table_name="users",
                record_id=user_id,
                action="DELETE",
                old_data=old_user.to_dict(),
            )

            connection.commit()

        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
