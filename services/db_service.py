import pymysql

from config import Config


class DbService:

    @staticmethod
    def get_connection():
        return pymysql.connect(
            host=Config.MYSQL_HOST,
            port=Config.MYSQL_PORT,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DATABASE,
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )

    @staticmethod
    def test_connection():
        connection = DbService.get_connection()

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 AS result")
                return cursor.fetchone()
        finally:
            connection.close()
