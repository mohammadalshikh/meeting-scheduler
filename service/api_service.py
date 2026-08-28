import os
import pymysql


class ApiService:

    @staticmethod
    def get_connection():
        return pymysql.connect(
            host=os.environ["MYSQL_HOST"],
            port=int(os.environ.get("MYSQL_PORT", 3306)),
            user=os.environ["MYSQL_USER"],
            password=os.environ["MYSQL_PASSWORD"],
            database=os.environ["MYSQL_DATABASE"],
            cursorclass=pymysql.cursors.DictCursor,
        )

    @staticmethod
    def create_game(answer):
        connection = ApiService.get_connection()

        try:
            with connection.cursor() as cursor:
                cursor.execute("INSERT INTO games (answer) VALUES (%s)", (answer,))
                game_id = cursor.lastrowid

            connection.commit()
            return game_id

        finally:
            connection.close()
