import os
from pathlib import Path
from typing import Annotated, Optional, Union

import yaml
from loguru import logger
from pydantic import BaseModel, PlainSerializer, model_validator
from upath import UPath

from .cis_key import CisKey

SerializablePath = Annotated[os.PathLike, PlainSerializer(str)]


class CisModel(BaseModel):
    """A AI/ML model in CIS."""

    path: Union[str, os.PathLike]
    version: str = "latest"
    training_id: Optional[str] = None

    def model_post_init(self, __context):
        """Attempts to load the model metadata when available."""
        self.path = UPath(self.path)
        if not self.path.exists():
            raise FileNotFoundError(f"Model not found in path {self.path}")

        metadata_filename = self.path / "metadata.yml"
        if not metadata_filename.exists():
            logger.warning(f"Model metadata not found in {metadata_filename}")
        else:
            metadata = yaml.load(metadata_filename.read_text(), Loader=yaml.SafeLoader)
            self.version = str(metadata["model_version"])
            self.training_id = metadata.get("model_training_id")
            if self.training_id:
                self.training_id = str(self.training_id)


class CisAsset(BaseModel):
    """An asset in the request."""

    name: str
    path: Union[str, SerializablePath]
    delimiter: Optional[str] = None


class CisRequestInput(BaseModel):
    """The input data of the request.

    Args:
        assets: The request assets.
        training_id: The training id of the inference model.
        ml_model_version: The version of the inference model.
        model_path: The path (local or remote) to the inference model.
    """

    assets: Optional[list[CisAsset]] = None
    training_id: Optional[str] = None
    ml_model_version: Optional[str] = None
    model_path: Optional[str] = None


class CisInternalConfig(BaseModel):
    """CIS internal config data of the request.

    output_path: The path where the output file will be saved.
    delimiter: The delimiter used in the output file.
    child_request_data: Indicates if there are other requests associated with this one,
        triggered by A/B configuration in the Umbrella API.
    """

    output_path: SerializablePath
    delimiter: str = "\u0001"
    child_request_data: Optional[list[dict]] = None


class CisRequest(BaseModel):
    """A request received in CIS."""

    requestId: str
    application: str
    consumer: str
    country: str
    characteristics: list[str]
    input: CisRequestInput
    cis_internal_config: Optional[CisInternalConfig] = None
    client: Optional[Union[int, str]] = None
    language: Optional[str] = None
    callback_url: Optional[str] = None

    def __hash__(self) -> int:
        return hash(self.model_dump_json())

    @model_validator(mode="before")
    @classmethod
    def _check_field_types(cls, data):
        """Catch edge case where the raw data is not the expected type."""
        if not isinstance(data, dict):
            return data
        for field_name, field in cls.model_fields.items():
            if field.annotation in {str, Optional[str]}:
                field_value = data.get(field_name)
                if field_value is not None and type(field_value) is not str:
                    data[field_name] = str(field_value)
        return data

    def with_conventions(self) -> "CisRequest":
        """Return a copy of this object with CIS case conventions applied."""
        copy_request = self.model_copy(deep=True)
        copy_request.application = self.application.lower()
        copy_request.consumer = self.consumer.lower()
        copy_request.country = str(self.country).lower()
        copy_request.characteristics = [c.lower() for c in self.characteristics]
        return copy_request

    def model_post_init(self, context) -> None:
        """Perform model post initialization."""
        if not self.cis_internal_config:
            self.cis_internal_config = self._get_default_internal_config()

    def _get_default_internal_config(self) -> CisInternalConfig:
        """Returns the default CIS internal config."""
        return CisInternalConfig(output_path=self.output_csv_path)

    def to_key(self) -> CisKey:
        """Creates a key from the request."""
        request = self.with_conventions()
        return CisKey(
            request_id=request.requestId,
            application=request.application,
            consumer=request.consumer,
            country=request.country,
            characteristic=request.characteristic,
            status=None,
            time=None,
        )

    def get_metadata_matching_pattern(self, use_country: bool = True) -> str:
        """Returns the pattern for matching Metadata keys.

        Args:
            use_country: Uses the request country in the matching pattern, uses "any" country if False.

        Returns:
            Metadata matching pattern.
        """
        country = str(self.country).lower() if use_country else "any"
        pattern_parts = [self.application, self.consumer, country, self.characteristic]
        pattern = f"*{'_'.join(pattern_parts)}*"
        return pattern

    @property
    def characteristic(self) -> str:
        """The first characteristic of the request."""
        return self.characteristics[0]

    @property
    def app_con(self):
        """The application consumer key."""
        return f"{self.application}_{self.consumer}"

    @property
    def _default_parts(self) -> list[str]:
        return [
            self.application.lower(),
            self.consumer.lower(),
            self.characteristic.lower(),
            str(self.country).lower(),
            str(self.client).lower() if self.client else "",
        ]

    @property
    def model_path(self) -> Path:
        """The default local model path using the request."""
        request = self.with_conventions()
        local_model_path = Path(
            *request._default_parts,
            "models",
        )
        return local_model_path

    @property
    def input_path(self) -> Path:
        """The canonical path where input files are stored in CIS filesystem."""
        request = self.with_conventions()
        input_path = Path(
            *request._default_parts,
            "input",
            request.requestId,
        )
        return input_path

    @property
    def output_csv_path(self) -> Path:
        """The default output path to save artifacts for this request."""
        request = self.with_conventions()
        return Path(
            os.sep,
            os.getenv("OUTPUT_BASE_DIR", ""),
            *request._default_parts,
            "output",
            request.requestId,
            f"{request.requestId}_output.csv",
        )
