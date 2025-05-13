from pydantic import BaseModel
from typing import List, Union, Optional
from pathlib import Path
from cis.runtime.core import CisRequest  # the runtime’s base request


class CisAsset(BaseModel):
    """An asset in the request."""
    name: str
    path: Union[str, Path]
    delimiter: Optional[str] = None
    iso_week: Optional[int] = None


class CisInput(BaseModel):
    """The nested `input` block."""
    assets: List[CisAsset]


class CisRequestUp(CisRequest):
    """
    A CIS request that adds our `input.assets` structure on top 
    of the runtime’s CisRequest base.
    """
    application: str
    consumer: str
    country: str
    characteristics: List[str]
    client: Optional[str]
    input: CisInput
