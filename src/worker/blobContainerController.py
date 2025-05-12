from azure.storage.blob import BlobServiceClient, ContainerClient
from .config import Config
from wrapper_worker.core.logger_utils import LoggerUtils
from .worker_errors import WorkspaceAuthenticationError

import os
from pathlib import Path
from os.path import isfile

def container_client() -> ContainerClient:
    """Conect with a container. Need a sas token to connect 
    :returns: Container client object
    """
    storage_account = Config.get_storage_account()   # storage account to connect
    credential = Config.get_token_cis()    # token with all permision
    container_name = Config.get_container_name()      # container to work

    LoggerUtils.save_log(
        message=f"storage_account: {storage_account}"
                f"container_name: {container_name}"
    )

    try:
        # Access to blob storage
        blob_service_client = BlobServiceClient(
            account_url=f"https://{storage_account}.blob.core.windows.net",
            credential=credential)

        # Access to specific container
        container_client = blob_service_client.get_container_client(container_name)

        return container_client
    except Exception as e:
        raise WorkspaceAuthenticationError(
                f"Error to connect to "
                f"storage_account: {storage_account}"
                f"container_name: {container_name}"                
            ) from e
    
def list_prediction_files(container_client, predictions_dir_path):
    """
    Lists and returns images of prediction folder

    :param container_client: client for calling to Azure file operations
    :param predictions_dir_path: path where prediction files are stored
    :return: list of prediction files
    """
    try:
        blobs_list = container_client.list_blobs(predictions_dir_path)

        predictions_image_numbers = []
        for blob in blobs_list:
            # Format numbers (from '01' to 1, '02', to 2...) for comparing with IMAGE_NUMBER field in feedback CSV file
            num_image = int(blob.name.rsplit('/',1)[1].split('.')[0])
            predictions_image_numbers.append(num_image)
        
        return predictions_image_numbers
    except Exception as ex:
        raise ex

def upload_local_dir(container_client, path_origin, target_remote_path):
    try:
        for file in os.listdir(path_origin):
            if isfile(path_origin + "/" + file):
                file_origin = Path(path_origin,file).as_posix()
                remote_file = Path(target_remote_path, file).as_posix()

                with open(file=file_origin, mode="rb") as data:
                    blob_client = container_client.upload_blob(name=remote_file, data=data, overwrite=True)

        return blob_client
    except Exception as e:
        raise e

def upload_file(container_client, local_file, target_remote_path):
    try:
        with open(file=local_file, mode="rb") as data:
            blob_client = container_client.upload_blob(name=target_remote_path.as_posix(), data=data, overwrite=True)
        return blob_client
    except Exception as e:
        raise e

def download_file(container_client, container_name, target_local_path, remote_file):
    try:        
        blob_client = container_client.get_blob_client(container=container_name, blob=remote_file)

        with open(file=target_local_path, mode="wb") as sample_blob:
            download_stream = blob_client.download_blob()
            sample_blob.write(download_stream.readall())
    except Exception as e:
        raise e

def delete_file (container_client,container_name,removal_path):
    try:
        blob_client = container_client.get_blob_client(container=container_name, blob=removal_path)
        blob_client.delete_blob()
    except Exception as e:
        raise e
            
def blob_exists(blob_name: Path) -> str:
    """
    Checks if a blob exists in the container
    
    :param blob_name: name of the blob to get the URL
    :return: URL of the blob
    :raises FileNotFoundError: if the blob does not exist in the container
    """
    blob_client = container_client().get_blob_client(blob=blob_name.as_posix())
    if blob_client.exists():
        return blob_name
    raise FileNotFoundError(f"Blob {blob_name} not found in container")