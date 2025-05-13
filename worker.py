import os
import csv
import tempfile
import logging
import pandas as pd

from typing_extensions import override
from fsspec import AbstractFileSystem
from cis.runtime.caching.caching import Caching
from cis.runtime.messaging import MessageQueue
from cis.runtime.workers import CisWorker
from cis.runtime.core import CisRequestInput

from azure.storage.blob import BlobServiceClient
from redis import Redis
from azureml.core import Workspace

from src.pr_flyers_metrics_worker.worker.worker.indexer import IndexController, AnnotationSchema

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class Worker(CisWorker):
    def __init__(
        self,
        # Core CISWorker dependencies
        filesystem: AbstractFileSystem,
        cache: Caching,
        metadata_client: Caching,
        audit_queue: MessageQueue,

        # Azure Blob Storage
        promoflyer_storage_account: str,
        promoflyer_container_name: str,
        token_cis: str,

        # Redis cache config
        redis_cache_host: str,
        redis_cache_port: int,
        redis_cache_password: str,

        # Redis queue config
        redis_queue_host: str,
        redis_queue_port: int,
        redis_queue_password: str,

        # Database config
        db_server: str,
        db_port: int,
        db_name: str,
        db_user: str,
        db_pass: str,

        # Azure ML workspace config
        azureml_subscription_id: str,
        azureml_resource_group: str,
        azureml_workspace_name: str,
        azureml_tenant_id: str,
        azureml_client_id: str,
        azureml_client_secret: str,
    ) -> None:
        """
        Initializes the Worker, injecting:
         - filesystem, cache, metadata_client, audit_queue (CisWorker)
         - Redis cache & queue clients
         - BlobServiceClient using SAS token
         - Database connection config
         - Azure ML Workspace
        """
        # 1) initialize base class
        super().__init__(
            filesystem=filesystem,
            cache=cache,
            metadata_client=metadata_client,
            audit_queue=audit_queue,
        )

        # 2) Redis clients
        self.redis_cache = Redis(
            host=redis_cache_host,
            port=redis_cache_port,
            password=redis_cache_password,
        )
        self.redis_queue = Redis(
            host=redis_queue_host,
            port=redis_queue_port,
            password=redis_queue_password,
        )

        # 3) BlobServiceClient with SAS token
        account_url = f"https://{promoflyer_storage_account}.blob.core.windows.net"
        self.blob_service_client = BlobServiceClient(
            account_url=account_url,
            credential=token_cis
        )
        self.container_name = promoflyer_container_name

        # 4) Database config for indexer
        self.db_config = {
            "server": db_server,
            "port": db_port,
            "name": db_name,
            "user": db_user,
            "pass": db_pass,
        }

        # 5) Azure ML Workspace
        self.workspace = Workspace(
            subscription_id=azureml_subscription_id,
            resource_group=azureml_resource_group,
            workspace_name=azureml_workspace_name,
            tenant_id=azureml_tenant_id,
            auth=azureml_client_id + ":" + azureml_client_secret
        )

        logger.info("Worker initialized with Redis, BlobServiceClient, DB config, and AzureML workspace.")

    def validate_request(self, request: CisRequestInput):
        """
        Validates the incoming request for required fields.
        """
        if not request.input.assets:
            raise ValueError("Request must contain at least one asset.")
        for asset in request.input.assets:
            if not asset.name or not asset.path:
                raise ValueError(f"Asset missing name or path: {asset}")
            if asset.iso_week is None:
                raise ValueError(f"Asset {asset.name} is missing 'iso_week'.")

    def download_input(self, request: CisRequestInput) -> str:
        """
        Downloads the input CSV file locally to a temporary folder.
        Returns the local file path.
        """
        asset = request.input.assets[0]
        path = asset.path
        if not path:
            logger.error("No path specified for input asset.")
            return ""

        parts = str(path).lstrip("/").split('/', 1)
        container_name, blob_name = parts[0], parts[1]

        tmp_dir = tempfile.mkdtemp()
        local_file = os.path.join(tmp_dir, asset.name)

        logger.info(f"Downloading input CSV from {container_name}/{blob_name} to {local_file}")
        blob_client = self.blob_service_client.get_blob_client(
            container=container_name, blob=blob_name
        )
        with open(local_file, "wb") as f:
            f.write(blob_client.download_blob().readall())
        return local_file

    def check_prediction_files(self, local_input_csv: str) -> list:
        """
        Checks if the corresponding prediction file exists for each feedback URL file
        in the input CSV. Returns a list of valid entries with metadata.
        """
        valid_entries = []
        with open(local_input_csv, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                feedback_file = row.get('filename') or row.get('name')
                if not feedback_file:
                    logger.warning("Missing filename in CSV row. Skipping.")
                    continue

                prediction_file = feedback_file.replace('.csv', '_prediction.json')
                if not os.path.exists(prediction_file):
                    logger.warning(f"Prediction file not found: {prediction_file}. Skipping.")
                    continue

                valid_entries.append({
                    'feedback_file': feedback_file,
                    'prediction_file': prediction_file,
                    'request_id': row.get('request_id'),
                    'country_code': row.get('country_code'),
                    'retailer': row.get('retailer'),
                    'isoweek': row.get('iso_week') or row.get('isoweek'),
                    'annotation_path': prediction_file,
                    'image_path': feedback_file
                })
        return valid_entries

    def download_feedback(self, entries: list) -> list:
        """
        Downloads each feedback file listed in entries to a temporary folder.
        Returns a list of local feedback file paths.
        """
        local_feedback_files = []
        for e in entries:
            feedback_path = e['feedback_file']
            parts = feedback_path.lstrip('/').split('/', 1)
            container, blob = parts[0], parts[1]
            tmp_dir = tempfile.mkdtemp()
            local_file = os.path.join(tmp_dir, os.path.basename(blob))
            logger.info(f"Downloading feedback file from {container}/{blob} to {local_file}")
            blob_client = self.blob_service_client.get_blob_client(
                container=container, blob=blob
            )
            with open(local_file, 'wb') as f:
                f.write(blob_client.download_blob().readall())
            local_feedback_files.append(local_file)
        return local_feedback_files

    def upload_feedback(self, local_feedback_files: list, container_name: str):
        """
        Uploads each local feedback file to Azure Storage in the specified container.
        """
        for filepath in local_feedback_files:
            blob_name = os.path.basename(filepath)
            logger.info(f"Uploading feedback file {filepath} to {container_name}/{blob_name}")
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name, blob=blob_name
            )
            with open(filepath, 'rb') as data:
                blob_client.upload_blob(data, overwrite=True)

    def index_feedback(self, entries: list):
        """
        Indexes feedback entries in the database.
        """
        logger.info("Indexing feedback entries in database...")
        controller = IndexController(db_config=self.db_config)
        for entry in entries:
            try:
                ann = AnnotationSchema(
                    request_id=entry['request_id'],
                    country_code=entry['country_code'],
                    retailer=entry['retailer'],
                    isoweek=int(entry['isoweek']),
                    annotation_path=entry['annotation_path'],
                    image_path=entry['image_path']
                )
                controller.add_annotation(ann)
                logger.info(f"Indexed annotation for request_id={entry['request_id']}")
            except Exception as e:
                logger.error(f"Failed to index entry {entry}: {e}")

    def process_results(self, entries: list, output_path: str):
        """
        Generates output CSV file for the worker response.
        """
        logger.info(f"Generating output CSV at {output_path}")
        if not entries:
            logger.warning("No entries to write to output CSV.")
            return
        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=entries[0].keys())
            writer.writeheader()
            writer.writerows(entries)

    def run(self, request: CisRequestInput, output_path: str, feedback_container: str):
        """
        Orchestrates the full worker process.
        """
        logger.info("Starting worker run...")
        self.validate_request(request)

        local_csv = self.download_input(request)
        preds = self.check_prediction_files(local_csv)
        local_feedbacks = self.download_feedback(preds)
        self.upload_feedback(local_feedbacks, feedback_container)
        self.index_feedback(preds)
        self.process_results(preds, output_path)

        logger.info("Worker run completed.")
