from typing import Optional

from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker, scoped_session

from index.schema import AnnotationSchema
from index.utils import get_database_uri


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
