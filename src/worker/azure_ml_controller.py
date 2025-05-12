from azureml.core import Workspace, Datastore
from azureml.data.azure_storage_datastore import AzureBlobDatastore
from azureml.core.authentication import ServicePrincipalAuthentication
from azureml.pipeline.core import PipelineEndpoint

from .globals import Globals

from .metrics_paths import MetricsPaths
from .worker_errors import WorkspaceAuthenticationError
from .config import Config
from wrapper_worker.core.logger_utils import LoggerUtils
from azure.storage.blob import BlobServiceClient,StorageStreamDownloader
from azure.core.credentials import AzureNamedKeyCredential
from pathlib import Path
from os.path import isfile
import os

def get_workspace() -> Workspace:
    """Gets the Azure ML workspace object where the datasets will be registered to.
    Uses the values stored in the config file
    :returns: Workspace object
    """

    service_principal_id = Config.get_azureml_service_principal_id()            #  client / service principal ID
    service_principal_secret = Config.get_azureml_service_principal_secret()    # client / service principal secret
    tenant_id = Config.get_azureml_tenant_id()                                  # tenantID
    subscription_id = Config.get_azureml_subscription_id()                      # subscriptionId
    resource_group = Config.get_azureml_resource_group()                        # resource group
    workspace_name = Config.get_azureml_workspace_name()                        # Workspace name
    
    LoggerUtils.save_log(
        message=f"service_principal_id: {service_principal_id}"
                f"service_principal_secret: {service_principal_secret}"
                f"tenant_id: {tenant_id}"
                f"subscription_id: {subscription_id}"
                f"resource_group: {resource_group}"
                f"workspace_name: {workspace_name}"
    )

    auth = ServicePrincipalAuthentication(
        tenant_id=tenant_id,
        service_principal_id=service_principal_id,
        service_principal_password=service_principal_secret
    )

    try:
        ws = Workspace(
            subscription_id=subscription_id,
            resource_group=resource_group,
            workspace_name=workspace_name,
            auth=auth
        )
        return ws
    except Exception as e:
        raise WorkspaceAuthenticationError(
                f"An error occurred while getting the workspace - {workspace_name}."
                f"subscription id: {subscription_id},"
                f"resource group: {resource_group},"
                f"tenant_id: {tenant_id},"
                f"please check the service principal's credentials"
                f"service_principal_id:{service_principal_id},"
                f" and the workspace details specified"
            ) from e

def get_datastore(ws, datastore_name = None):
    """Gets an Azure ML datastore
    :param ws: Workspace where the datastore is located
    :param datastore_name: Name of the datastore, if None, the default one will be returned
    :returns: Datastore object
    """
    try:
        datastore = None
        if datastore_name is None:
            datastore = Datastore.get_default(ws)
        else:
            datastore = Datastore.get(ws, datastore_name)
        print(f"Datastore attrs: {vars(datastore)}")
        return datastore
    except Exception as e:
        raise e

def upload_local_dir(ws, path_model: MetricsPaths, datastore_name = None):
    """Uploads a local directory to an Azure ML datastore location
    :param ws: Workspace where the datastore is located
    :param path_model: TrainingPaths object containing the paths involved in the process
    :param datastore_name: Name of the datastore, if None, the default one will be used
    :returns: Datastore object
    """
    try:
        # The storage system credentials are obtained from the AzureBlobDatastore object
        # TODO: Implement the logic for the rest of storages supported by datastores (currently only works for blobstorage)
        datastore = get_datastore(ws, datastore_name)
        if type(datastore) is AzureBlobDatastore:

            # Upload request assets files
            for file in os.listdir(path_model.local_dir):
                if isfile(path_model.local_dir + "/" + file):
                    file = path_model.local_dir + "/" + file
                    datastore.upload_files([file], target_path=path_model.ml_input_assets_dir)

            # TODO: Why the Dataset creatin fails in the kubernetes DMLE cluster?
            ####################################################################################################################################################
            # Create non registered dataset from parent dir. Ex: 'sirval/sirval-training/us/2022/11/16/REQ-bb78aa81-c4a0-4cf2-84b5-1ad687e18dde'
            #dataset = Dataset.File.from_files((datastore, path_model.ml_base_dir))

            # Register dataset in ws
            #dataset = dataset.register(workspace=ws, name=path_model.ml_base_dir)
            ####################################################################################################################################################
            
        else:
            raise NotImplementedError("Only AzureBlobDatastore type is implemented")
    except Exception as e:
        raise e

def run_pipeline(ws: Workspace, experiment_name: str, pipeline_name: str, input_params: dict):
    """
    Runs an AzureML pipeline endpoint given its name
    By default, the latest published pipeline will be ran (this process is defined in the CI/CD flow)
    :param ws Workspace where the pipeline is located
    :param pipeline_name Name of the AzureML Pipeline
    :param input_params List of arguments to be passed to the pipeline
    """
    pipeline_endpoint = PipelineEndpoint.get(workspace=ws, name=pipeline_name)
    
    pipeline_run = pipeline_endpoint.submit(
        experiment_name=experiment_name,
        pipeline_parameters=input_params,
    )
    pipeline_run.set_tags({"client":Globals.CLIENT,"environment":Config.get_env(),"pipeline":"metrics"})
    pipeline_run.wait_for_completion(show_output=False)
    return pipeline_run.status


def download_file(ws, remote_path, local_path,file_name):
    datastore = get_datastore(ws)
    count = 0
    if type(datastore) is AzureBlobDatastore:
        count = datastore.download(local_path,prefix=remote_path)
    if(count==1):
        Path(local_path,remote_path).rename(str(Path(local_path,file_name)))
        #os.remove(Path(local_path, remote_path.split('/')[0]))
    return count==1