import logging
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import requests
from fsspec import AbstractFileSystem
from typing_extensions import override

from cis.runtime.caching.caching import Caching
from cis.runtime.core import CisChildRequest, CisRequest
from cis.runtime.exceptions import ValidationException
from cis.runtime.infra.cis.monitor import RequestStatusMonitor
from cis.runtime.messaging import AuditQueue, MessageQueue

from .execution_flow import ExecutionFlow
from .execution_status import ExecutionStatus
from .worker import Worker

ALLOWED_CHILD_STATUSES = [
    ExecutionStatus.INPROGRESS.name,
    ExecutionStatus.COMPLETED.name,
]

logger = logging.getLogger(__name__)


class CisWorker(Worker, AuditQueue):
    """The basic worker to use on any deployment in CIS.

    Args:
        filesystem: The storage filesystem to access the files in CIS.
        audit_queue: The message queue to send the audit messages.
        cache: The cache to use in the worker.
        metadata_client: The metadata client for accessing metadata to use in the worker.
    """

    execution_flow = ExecutionFlow()

    def __init__(
        self,
        filesystem: AbstractFileSystem,
        cache: Optional[Caching] = None,
        metadata_client: Caching = None,
        audit_queue: Optional[MessageQueue] = None,
    ) -> None:
        self.filesystem = filesystem
        self._cache = cache
        self._metadata_client = metadata_client
        self.audit_queue = audit_queue
        self.start_time: Optional[datetime] = None
        self._status_monitor: Optional[RequestStatusMonitor] = None
        self._child_request: Optional[CisChildRequest] = None

    def get_child_request(self, request: CisRequest) -> Optional[CisChildRequest]:
        """Gets the request that is being managed by the main request.

        Returns:
            The child request to manage in the worker execution flow or None if no child request is needed.
        """
        if self._child_request is None:
            self._child_request = self._build_child_request(request)
        return self._child_request

    def _build_child_request(self, request: CisRequest) -> CisChildRequest:  # noqa: PLR6301
        """Builds the child request to manage in the worker execution flow.

        This is a hook to be implemented by the worker when a child request is needed.
        """
        return None

    def get_statuses_for_request(self, is_child: bool = False) -> list[str]:
        """Gets the allowed statuses for the parent or child request.

        Args:
            is_child: Whether the request is a child request or the parent (original) request.

        Returns:
            The list of statuses allowed for the request.
        """
        return ALLOWED_CHILD_STATUSES if is_child else self.execution_flow.all_statuses

    @property
    def cache(self) -> Caching:
        """The cache client to use in the worker."""
        if not self._cache:
            raise ValueError(
                "A cache implementation is required for this worker. "
                "Please, set the `cache` argument in the worker constructor or set the `cache` property on the worker instance."
            )
        return self._cache

    @cache.setter
    def cache(self, cache: Caching):
        self._cache = cache

    @property
    def metadata_client(self) -> Caching:
        """The metadata client to use in the worker."""
        if not self._metadata_client:
            raise ValueError(
                "A Metadata implementation is required for this worker. "
                "Please, set the `metadata_client` argument in the worker constructor."
            )
        return self._metadata_client

    @metadata_client.setter
    def metadata_client(self, metadata_client: Caching):
        self._metadata_client = metadata_client

    @property
    def status_monitor(self) -> Optional[RequestStatusMonitor]:
        """The object to monitor status of requests in the Umbrella API."""
        return self._status_monitor

    @status_monitor.setter
    def status_monitor(self, status_monitor: RequestStatusMonitor):
        self._status_monitor = status_monitor

    @override
    def validate_request(self, request: CisRequest):
        """Validates the input files.

        Args:
            request: The request to get the assets to validate.

        Raises:
            ValidationException if one of the files is not found.
        """
        super().validate_request(request)
        bad_filenames = (" ", "  ", "", ".", '""')
        assets = request.input.assets if "assets" in request.input.model_fields else []
        if not assets:
            return

        bad_files = any(asset.path in bad_filenames for asset in assets)
        if bad_files or not assets:
            raise ValidationException(f"Wrong paths in input assets: {assets}")

        try:
            for file_data in assets:
                final_path = file_data.path
                if not self.filesystem.exists(final_path):
                    raise ValidationException()
        except Exception as e:
            raise ValidationException(
                f"File {file_data.path} not found. Check the path in input.assets"
            ) from e

    @execution_flow.register_step(
        name="validate",
        status=ExecutionStatus.VALIDATED,
        message="Request validated successfully",
    )
    def _validate_request(self, request: CisRequest):
        self.validate_request(request)

    @execution_flow.register_step(
        name="start",
        status=ExecutionStatus.INPROGRESS,
        message="Worker started processing request",
        depends_on=["validate"],
    )
    def _start_processing(self, request: CisRequest):
        logger.info("Worker started processing the request")
        self.start_time = datetime.now()

    @execution_flow.register_step(
        name="run",
        status=ExecutionStatus.COMPLETED,
        message="Worker process completed",
        depends_on=["start"],
    )
    def _run_worker(self, request: CisRequest) -> None:
        self.run(request=request)

    @execution_flow.register_step(
        name="report",
        status=ExecutionStatus.DELIVERED,
        message="Request notification delivered successfully",
        depends_on=["run"],
    )
    def _report_callback(self, request: CisRequest):
        """Calls back the client using the URL to notify job completion."""
        if not request.callback_url:
            return

        result = urlparse(request.callback_url)
        if not result.scheme:
            raise ValueError(f"Invalid URL: {request.callback_url}")

        job_info_status = ExecutionStatus.DELIVERED.name
        end_time = datetime.now()
        if self.status_monitor:
            try:
                end_time = self.status_monitor.wait_for_child_requests(
                    request, end_time
                )
            except Exception as error:
                logger.exception("Error waiting for child requests: %s", error)
                end_time = datetime.now()
                job_info_status = ExecutionStatus.ERROR.name

        logger.info("Sending callback to URL %s", request.callback_url)
        job_info = self._build_callback_json_payload(
            request=request,
            start_time=self.start_time or datetime.now(),
            end_time=end_time,
            job_status=job_info_status,
        )
        result = requests.post(request.callback_url, json=job_info, timeout=300)
        logger.info(
            "Callback reported successfully",
            extra={"status_code": result.status_code, "result": result.text},
        )
        result.raise_for_status()

    @staticmethod
    def _build_callback_json_payload(
        request: CisRequest,
        start_time: datetime,
        end_time: datetime,
        job_status: str,
    ) -> dict:
        job_info = request.model_dump()
        job_info["jobInformation"] = {
            "id": request.requestId,
            "requestId": request.requestId,
            "jobStatus": job_status,
            "startTime": start_time.strftime("%m/%d/%Y %H:%M:%S"),
            "endTime": end_time.strftime("%m/%d/%Y %H:%M:%S"),
            "output": {
                "path": request.output_csv_path.as_posix(),
                "delimiter": ",",
            },
        }
        return job_info
