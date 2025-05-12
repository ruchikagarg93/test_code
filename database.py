import os
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

class DatabaseClient:
    def __init__(self):
        self.conn = psycopg2.connect(os.getenv("DB_CONNECTION_STRING"))
        self.cursor = self.conn.cursor()

    def insert_feedback(self, records):
        query = """
        INSERT INTO feedback_table (request_id, asset_name, iso_week, prediction_path)
        VALUES %s
        """
        execute_values(self.cursor, query, records)
        self.conn.commit()

    def close(self):
        self.cursor.close()
        self.conn.close()
