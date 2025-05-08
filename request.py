from pydantic import BaseModel, PlainSerializer
from typing import Annotated, Optional, Union

from cis.runtime.core.cis_request import CisRequest
from cis.runtime.core.cis_request import CisAsset

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
