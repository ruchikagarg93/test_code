import os
import csv
import tempfile
import logging
from azure.storage.blob import BlobServiceClient
from request import CisRequestInput

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class Worker:
    def __init__(self, azure_connection_string: str):
        # Initialize Azure Blob service client
        self.blob_service_client = BlobServiceClient.from_connection_string(
            azure_connection_string
        )

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
            data = blob_client.download_blob().readall()
            f.write(data)
        return local_file

    def check_prediction_files(self, local_input_csv: str) -> list:
        """
        Checks if the corresponding prediction file exists for each feedback URL file
        in the input CSV.
        Returns a list of valid entries (dicts).
        """
        valid_entries = []
        with open(local_input_csv, 'r', newline='') as f:
            reader = csv.DictReader(f, delimiter=',')
            for row in reader:
                feedback_file = row.get('filename') or row.get('name')
                if not feedback_file:
                    logger.warning("Missing filename in CSV row. Skipping.")
                    continue

                prediction_file = feedback_file.replace('.csv', '_prediction.json')
                if not os.path.exists(prediction_file):
                    logger.warning(f"Prediction file not found: {prediction_file}. Skipping.")
                    continue

                valid_entries.append({'feedback_file': feedback_file, 'prediction_file': prediction_file})
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
        Indexes annotation in the database.
        Placeholder for actual DB logic.
        """
        logger.info("Indexing feedback entries in database...")
        # TODO: implement real DB insertion logic here
        for e in entries:
            logger.debug(f"Indexed entry: {e}")

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
        logger.info("Starting worker run...")
        # Validate the incoming request
        self.validate_request(request)

        local_input = self.download_input(request)
        preds = self.check_prediction_files(local_input)
        local_feedbacks = self.download_feedback(preds)
        self.upload_feedback(local_feedbacks, feedback_container)
        self.index_feedback(preds)
        self.process_results(preds, output_path)
        logger.info("Worker run completed.")
                        
