import pytest
from unittest.mock import MagicMock, patch
from worker import Worker  # assuming your worker class is in worker.py
from cis.runtime.core import CisRequestInput, CisAsset
from azure.storage.blob import BlobServiceClient
from pathlib import Path
import logging

# Disable logging for the test run
logging.disable(logging.CRITICAL)

@pytest.fixture
def fake_config():
    return {
        'azure_connection_string': 'fake_connection_string',
        'feedback_container': 'fake_feedback_container',
        'output_path': '/fake/output/path'
    }

@pytest.fixture
def fake_cis_request():
    # Creating a fake CisRequestInput for testing
    return CisRequestInput(
        application='test_application',
        consumer='test_consumer',
        country='US',
        characteristics=['test_characteristic'],
        assets=[CisAsset(
            name='test_asset.csv',
            path='/fake/path/to/asset.csv',
            iso_week=202152
        )]
    )

@pytest.fixture
def fake_worker(fake_config):
    # Mocking the BlobServiceClient and creating a Worker instance
    with patch.object(BlobServiceClient, 'from_connection_string', return_value=MagicMock()):
        worker = Worker(fake_config['azure_connection_string'])
    return worker

def test_validate_request(fake_worker, fake_cis_request):
    # Testing validation logic
    fake_worker.validate_request(fake_cis_request)  # Should not raise any exceptions

def test_validate_request_missing_assets(fake_worker, fake_cis_request):
    fake_cis_request.assets = []  # No assets
    with pytest.raises(ValueError, match="Request must contain at least one asset"):
        fake_worker.validate_request(fake_cis_request)

def test_validate_request_missing_asset_name(fake_worker, fake_cis_request):
    fake_cis_request.assets[0].name = None  # Missing name
    with pytest.raises(ValueError, match="Asset missing name or path"):
        fake_worker.validate_request(fake_cis_request)

def test_download_input(fake_worker, fake_cis_request):
    # Mocking the blob download method to simulate file download
    with patch.object(fake_worker.blob_service_client, 'get_blob_client', return_value=MagicMock(download_blob=MagicMock(readall=MagicMock(return_value=b"test_data")))):
        local_file = fake_worker.download_input(fake_cis_request)
        assert local_file == '/tmp/test_asset.csv', f"Expected '/tmp/test_asset.csv' but got {local_file}"

def test_check_prediction_files(fake_worker, fake_cis_request):
    # Mocking the os.path.exists method to simulate file existence check
    with patch('os.path.exists', return_value=True):
        valid_entries = fake_worker.check_prediction_files('/fake/path/to/test_asset.csv')
        assert isinstance(valid_entries, list), "Expected valid entries to be a list."

def test_download_feedback(fake_worker):
    # Mocking feedback file download
    with patch.object(fake_worker.blob_service_client, 'get_blob_client', return_value=MagicMock(download_blob=MagicMock(readall=MagicMock(return_value=b"feedback_data")))):
        local_feedback_files = fake_worker.download_feedback([{
            'feedback_file': 'feedback1.csv'
        }])
        assert isinstance(local_feedback_files, list), "Expected feedback files to be a list."

def test_upload_feedback(fake_worker):
    # Mocking the blob upload method
    with patch.object(fake_worker.blob_service_client, 'get_blob_client', return_value=MagicMock(upload_blob=MagicMock())):
        fake_worker.upload_feedback(['/fake/path/to/feedback.csv'], 'fake_container')
        # Check if the upload was called with the correct parameters
        fake_worker.blob_service_client.get_blob_client.return_value.upload_blob.assert_called_with(open('/fake/path/to/feedback.csv', 'rb'), overwrite=True)

def test_index_feedback(fake_worker):
    # Mocking the indexer function
    with patch('indexer.IndexController') as MockIndexer:
        mock_index_controller = MagicMock()
        MockIndexer.return_value = mock_index_controller
        fake_worker.index_feedback([{
            'request_id': '12345',
            'country_code': 'US',
            'retailer': 'test_retailer',
            'isoweek': 202152,
            'annotation_path': '/fake/path/to/annotation.json',
            'image_path': '/fake/path/to/image.csv'
        }])
        mock_index_controller.add_annotation.assert_called_once()

def test_process_results(fake_worker):
    # Mocking file write operation
    with patch('builtins.open', mock_open()):
        fake_worker.process_results([{
            'feedback_file': 'feedback.csv',
            'prediction_file': 'prediction.json'
        }], '/fake/output/path/result.csv')
        # Ensure that the file is being opened for writing
        open.assert_called_with('/fake/output/path/result.csv', 'w', newline='')

def test_run(fake_worker, fake_cis_request, fake_config):
    with patch.object(fake_worker, 'validate_request', return_value=None), \
         patch.object(fake_worker, 'download_input', return_value='/fake/path/input.csv'), \
         patch.object(fake_worker, 'check_prediction_files', return_value=[{
            'feedback_file': 'feedback.csv',
            'prediction_file': 'prediction.json'
         }]), \
         patch.object(fake_worker, 'download_feedback', return_value=['/fake/path/to/feedback.csv']), \
         patch.object(fake_worker, 'upload_feedback'), \
         patch.object(fake_worker, 'index_feedback'), \
         patch.object(fake_worker, 'process_results'):
        
        fake_worker.run(fake_cis_request, fake_config['output_path'], fake_config['feedback_container'])

        # Verify that the correct methods were called in sequence
        fake_worker.validate_request.assert_called_once_with(fake_cis_request)
        fake_worker.download_input.assert_called_once_with(fake_cis_request)
        fake_worker.check_prediction_files.assert_called_once_with('/fake/path/input.csv')
        fake_worker.download_feedback.assert_called_once_with([{
            'feedback_file': 'feedback.csv',
            'prediction_file': 'prediction.json'
        }])
        fake_worker.upload_feedback.assert_called_once_with(['/fake/path/to/feedback.csv'], fake_config['feedback_container'])
        fake_worker.index_feedback.assert_called_once_with([{
            'feedback_file': 'feedback.csv',
            'prediction_file': 'prediction.json'
        }])
        fake_worker.process_results.assert_called_once_with([{
            'feedback_file': 'feedback.csv',
            'prediction_file': 'prediction.json'
        }], fake_config['output_path'])
