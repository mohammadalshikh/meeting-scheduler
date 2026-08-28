import json


class AuditService:

    @staticmethod
    def log(
        connection,
        user_id,
        table_name,
        record_id,
        action,
        old_data=None,
        new_data=None,
    ):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO audit_log
                    (user_id, table_name, record_id, action, old_data, new_data)
                VALUES
                    (%s, %s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    table_name,
                    record_id,
                    action,
                    json.dumps(old_data, default=str) if old_data is not None else None,
                    json.dumps(new_data, default=str) if new_data is not None else None,
                ),
            )
