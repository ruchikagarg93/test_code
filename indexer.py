import logging
import psycopg2
from typing import Optional
from config_loader import ConfigLoader

logger = logging.getLogger(__name__)

class AnnotationSchema:
    def __init__(self, request_id: str, country_code: str, retailer: str,
                 isoweek: int, annotation_path: str, image_path: str):
        self.request_id = request_id
        self.country_code = country_code
        self.retailer = retailer
        self.isoweek = isoweek
        self.annotation_path = annotation_path
        self.image_path = image_path

class IndexController:
    def __init__(self, db_uri: Optional[str] = None):
        cfg = ConfigLoader.get_instance()
        db = cfg.database

        self.db_uri = db_uri or (
            f"dbname={db.name} user={db.user} password={db.password} "
            f"host={db.server} port={db.port}"
        )
        self.conn = psycopg2.connect(self.db_uri)
        self.conn.autocommit = True
        logger.info("IndexController initialized and DB connection established.")

    def index_annotation(self, annotation: AnnotationSchema) -> None:
        insert_sql = """
        INSERT INTO annotations
        (request_id, country_code, retailer, isoweek, annotation_path, image_path)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (annotation_path) DO NOTHING
        """
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(insert_sql, (
                    annotation.request_id,
                    annotation.country_code,
                    annotation.retailer,
                    annotation.isoweek,
                    annotation.annotation_path,
                    annotation.image_path,
                ))
            logger.info(f"Inserted annotation: {annotation.annotation_path}")
        except Exception as e:
            logger.error(f"Failed to insert annotation {annotation.annotation_path}: {e}")
            raise

    def close(self):
        self.conn.close()
        logger.info("DB connection closed.")
        
