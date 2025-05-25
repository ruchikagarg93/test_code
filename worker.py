import os
import csv
import tempfile
import logging

from azure.storage.blob import BlobServiceClient
from azureml.core import Workspace
from azureml.core.authentication import ServicePrincipalAuthentication
from pr_flyers_metrics_worker.worker.worker.indexer import AnnotationSchema, IndexController

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class Worker:
    def __init__(
        self,
        promoflyer_storage_account: str,
        promoflyer_container_name: str,
        token_cis: str,
        # Database config for indexer
        db_server: str,
        db_port: int,
        db_name: str,
        db_user: str,
        db_pass: str,
        # Azure ML
        azureml_subscription_id: str,
        azureml_resource_group: str,
        azureml_workspace_name: str,
        azureml_tenant_id: str,
        azureml_client_id: str,
        azureml_client_secret: str,
    ) -> None:
        # Blob client
        account_url = f"https://{promoflyer_storage_account}.blob.core.windows.net"
        self.blob_service_client = BlobServiceClient(
            account_url=account_url,
            credential=token_cis
        )
        self.container_name = promoflyer_container_name

        # DB indexer
        db_uri = f"postgresql://{db_user}:{db_pass}@{db_server}:{db_port}/{db_name}"
        self.index_controller = IndexController(db_uri=db_uri)

        # Azure ML workspace
        sp_auth = ServicePrincipalAuthentication(
            tenant_id=azureml_tenant_id,
            service_principal_id=azureml_client_id,
            service_principal_password=azureml_client_secret,
        )
        self.workspace = Workspace(
            subscription_id=azureml_subscription_id,
            resource_group=azureml_resource_group,
            workspace_name=azureml_workspace_name,
            auth=sp_auth,
        )

        logger.info("Worker initialized with BlobServiceClient, DB indexer, and AzureML workspace.")

    def validate_request(self, request):
        if not request.input.assets:
            raise ValueError("Request must contain at least one asset.")
        for asset in request.input.assets:
            if not asset.name or not asset.path:
                raise ValueError(f"Asset missing name or path: {asset}")
            if asset.iso_week is None:
                raise ValueError(f"Asset {asset.name} is missing 'iso_week'.")

    def download_input(self, request) -> str:
        asset = request.input.assets[0]
        path = asset.path
        if not path:
            raise ValueError("No path specified for input asset.")

        # path like "/projectrun/promoflyers/input/REQ-xxx/metric_example.csv"
        parts = str(path).lstrip("/").split("/", 1)
        container_name, blob_name = parts[0], parts[1]

        tmp_dir = tempfile.mkdtemp()
        local_file = os.path.join(tmp_dir, asset.name)

        logger.info(f"Downloading input CSV from {container_name}/{blob_name} to {local_file}")
        blob_client = self.blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        with open(local_file, "wb") as f:
            f.write(blob_client.download_blob().readall())

        return local_file

    def check_prediction_files(self, local_input_csv: str) -> list:
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
        local_feedback_files = []
        for e in entries:
            parts = e['feedback_file'].lstrip('/').split('/', 1)
            container, blob = parts[0], parts[1]
            tmp_dir = tempfile.mkdtemp()
            local_file = os.path.join(tmp_dir, os.path.basename(blob))
            logger.info(f"Downloading feedback file from {container}/{blob} to {local_file}")
            blob_client = self.blob_service_client.get_blob_client(container=container, blob=blob)
            with open(local_file, 'wb') as f:
                f.write(blob_client.download_blob().readall())
            local_feedback_files.append(local_file)
        return local_feedback_files

    def upload_feedback(self, local_feedback_files: list, container_name: str):
        for filepath in local_feedback_files:
            blob_name = os.path.basename(filepath)
            logger.info(f"Uploading feedback file {filepath} to {container_name}/{blob_name}")
            blob_client = self.blob_service_client.get_blob_client(container=container_name, blob=blob_name)
            with open(filepath, 'rb') as data:
                blob_client.upload_blob(data, overwrite=True)

    def index_feedback(self, entries: list):
        logger.info("Indexing feedback entries in database...")
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
                self.index_controller.index_annotation(ann)
                logger.info(f"Indexed annotation for request_id={entry['request_id']}")
            except Exception as e:
                logger.error(f"Failed to index entry {entry}: {e}")

    def process_results(self, entries: list, output_path: str):
        logger.info(f"Generating output CSV at {output_path}")
        if not entries:
            logger.warning("No entries to write to output CSV.")
            return
        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=entries[0].keys())
            writer.writeheader()
            writer.writerows(entries)

    def run(self, request, output_path: str, feedback_container: str):
        logger.info("Starting worker run...")
        self.validate_request(request)

        local_csv = self.download_input(request)
        preds = self.check_prediction_files(local_csv)
        local_feedbacks = self.download_feedback(preds)
        self.upload_feedback(local_feedbacks, feedback_container)
        self.index_feedback(preds)
        self.process_results(preds, output_path)

        logger.info("Worker run completed.")
