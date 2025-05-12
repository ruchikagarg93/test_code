from typing import Dict

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base


Base = declarative_base()


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

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "request_id": self.request_id,
            "country_code": self.country_code,
            "retailer": self.retailer,
            "isoweek": self.isoweek,
            "annotation_path": self.annotation_path,
            "image_path": self.image_path,
        }

    @staticmethod
    def from_dict(annotation) -> "AnnotationSchema":
        return AnnotationSchema(
            id=annotation["id"],
            request_id=annotation["request_id"],
            country_code=annotation["country_code"],
            retailer=annotation["retailer"],
            isoweek=annotation["isoweek"],
            annotation_path=annotation["annotation_path"],
            image_path=annotation["image_path"],
        )
