import os
import tempfile
import shutil
import pytest
import pandas as pd

from azure.storage.blob import BlobServiceClient
from src.pr_flyers_metrics_worker.worker.worker import Worker
from src.pr_flyers_metrics_worker.request import CisAsset, CisRequestInput

# These constants should match your test Azure Blob config
AZURE_CONN_STR = os.getenv("AZURE_TEST_CONN_STRING")  # set in .env or CI
CONTAINER_NAME = "test-container"

@pytest.fixture(scope="module")
def setup_blob_container():
    blob_service = BlobServiceClient.from_connection_string(AZURE_CONN_STR)
    try:
        container_client = blob_service.create_container(CONTAINER_NAME)
    except Exception:
        container_client = blob_service.get_container_client(CONTAINER_NAME)

    # Upload files
    base_dir = os.path.join(os.path.dirname(__file__), "test_files")
    for fname in os.listdir(base_dir):
        path = os.path.join(base_dir, fname)
        with open(path, "rb") as data:
            container_client.upload_blob(name=fname, data=data, overwrite=True)

    yield container_client

    # Teardown: delete container
    blob_service.delete_container(CONTAINER_NAME)

@pytest.fixture
def integration_request():
    return CisRequestInput(
        application="test-app",
        consumer="test-team",
        country="US",
        characteristics=["test"],
        assets=[
            CisAsset(
                name="input_files.csv",
                path=f"{CONTAINER_NAME}/input_files.csv",
                iso_week=23
            )
        ]
    )

def test_worker_integration_run(setup_blob_container, integration_request):
    tmp_output = tempfile.mktemp(suffix=".csv")
    worker = Worker(azure_connection_string=AZURE_CONN_STR)

    worker.run(
        request=integration_request,
        output_path=tmp_output,
        feedback_container=CONTAINER_NAME
    )

    assert os.path.exists(tmp_output)
    df = pd.read_csv(tmp_output)
    assert not df.empty
    assert "feedback_file" in df.columns
