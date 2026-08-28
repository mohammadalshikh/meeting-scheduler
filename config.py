import os


class Config:
    MYSQL_HOST = os.environ["MYSQL_HOST"]
    MYSQL_PORT = int(os.environ["MYSQL_PORT"])
    MYSQL_USER = os.environ["MYSQL_USER"]
    MYSQL_PASSWORD = os.environ["MYSQL_PASSWORD"]
    MYSQL_DATABASE = os.environ["MYSQL_DATABASE"]
    SECRET_KEY = os.environ["SECRET_KEY"]
