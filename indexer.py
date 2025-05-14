import logging
from typing import Optional

from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base

from config_loader import ConfigLoader

# SQLAlchemy base & logger
Base = declarative_base()
logger = logging.getLogger(__name__)

class AnnotationSchema(Base):
    __tablename__ = "annotations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(200), nullable=False)
    country_code = Column(String(2), nullable=False)
    retailer = Column(String(200), nullable=False)
    isoweek = Column(Integer, nullable=False)
    annotation_path = Column(String(1000), unique=True, nullable=False)
    image_path = Column(String(1000), unique=True, nullable=False)

class IndexController:
    def __init__(self, db_uri: Optional[str] = None):
        """
        Initializes the IndexController by loading DB URI from ConfigLoader
        and setting up the SQLAlchemy engine and session.
        """
        # Load centralized config
        cfg = ConfigLoader.get_instance()
        db = cfg.database

        # Build URI if not passed explicitly
        self.db_uri = db_uri or (
            f"postgresql://{db.user}:{db.password}"
            f"@{db.server}:{db.port}/{db.name}"
        )

        # Set up engine and session
        self.engine = create_engine(self.db_uri)
        self.Session = scoped_session(
            sessionmaker(bind=self.engine, expire_on_commit=False)
        )

        # Create table if it doesn't exist
        Base.metadata.create_all(self.engine)
        logger.info("IndexController initialized and DB schema ensured.")

    def index_annotation(self, annotation: AnnotationSchema) -> None:
        """
        Inserts a single AnnotationSchema instance into the DB.
        """
        session = self.Session()
        try:
            session.add(annotation)
            session.commit()
            logger.info(f"Inserted annotation: {annotation.annotation_path}")
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to insert annotation {annotation}: {e}")
            raise
        finally:
            session.close()
