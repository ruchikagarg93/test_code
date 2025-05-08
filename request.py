from pydantic import BaseModel, PlainSerializer
from typing import Annotated, Optional, Union
from pathlib import Path

class CisAsset(BaseModel):
    """An asset in the request."""
    
    name: str
    path: Union[str, Path]  # This can be a string or Path
    delimiter: Optional[str] = None  # Optional delimiter for CSV files
    iso_week: Optional[int] = None  # ISO week (optional)

class CisRequestInput(BaseModel):
    """The input data of the request."""

    application: str
    consumer: str
    country: str
    characteristics: list[str]
    assets: Optional[list[CisAsset]] = None


class CisRequestUp(CisRequest):
    """A request received in CIS."""

    input: CisRequestInput
