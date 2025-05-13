from typing import Optional
import logging
from sqlalchemy import Column, Integer, String, create_engine, MetaData
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base
from src.pr_flyers_metrics_worker.worker.worker.config import Config

# Setting up the base for SQLAlchemy
Base = declarative_base()

# Logging setup
logger = logging.getLogger(__name__)

def get_database_uri():
    """
    Get the database URI from the environment variables.
    """
    logger.info("No DB URI provided. Using environment variables.")
    db_server = Config.get_db_server()
    db_name = Config.get_db_name()
    db_user = Config.get_db_user()
    db_password = Config.get_db_pass()
    db_port = Config.get_db_port()
    return f"postgresql://{db_user}:{db_password}@{db_server}:{db_port}/{db_name}"

class AnnotationSchema(Base):
    """
    AnnotationSchema class is used to interact with the database.
    """

    __tablename__ = "annotations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(200), nullable=False)
    country_code = Column(String(2), nullable=False)
    retailer = Column(String(200), nullable=False)
    isoweek = Column(Integer, nullable=False)
    annotation_path = Column(String(1000), unique=True, nullable=False)
    image_path = Column(String(1000), unique=True, nullable=False)

def get_session(db_uri: str) -> scoped_session:
    """
    Get a session to interact with the database.
    """
    session_factory = sessionmaker(bind=create_engine(db_uri), expire_on_commit=False)
    Session = scoped_session(session_factory)
    return Session()

class IndexController:
    """
    IndexController class is used to interact with the database.
    """

    def __init__(
        self,
        db_uri: Optional[str] = None,
    ):
        """
        Constructor for the IndexController class.
        """
        self.db_uri = db_uri or get_database_uri()
        self.metadata = MetaData()
        self.table = AnnotationSchema.__table__
        self.session = get_session(self.db_uri)

    def add_annotation(self, annotation: AnnotationSchema) -> None:
        """
        Add an annotation to the database.

        :param annotation: The annotation to add.
        """
        with self.session as session:
            session.add(annotation)
            session.commit()
