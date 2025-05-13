from cis.common.aml_conventions import AmlConventions
from cis.runtime.workers import PipelineWorker
from typing_extensions import override
from cis.runtime.infra.fs import AdlsFileSystem
import logging
import os
from pathlib import Path
from .metrics_path import MetricsPaths
from azureml.data.azure_storage_datastore import AzureBlobDatastore
from cis.runtime.infra.azure.azure_ml import AzureMlClient
from azureml.core import Workspace, Datastore, Dataset, Model
from .get_file_from_database import RequestStatus
from concurrent.futures import ThreadPoolExecutor
from os.path import isfile, isdir
from datetime import datetime
from .globals import Globals
import json

class AdlsFilesystem(AdlsFileSystem):

    @override
    def get_file(self, rpath, lpath, callback=None, outfile=None, **kwargs):
        """Download the file from ADLS filesystem."""

        rpath = Path(rpath)
        file_name = rpath.name
        rpath_dir = rpath.parent.as_posix()
        file_client = self.fs_client.get_directory_client(rpath_dir).get_file_client(
            file_name
        )

        lpath = Path(lpath)
        lpath.parent.mkdir(exist_ok=True, parents=True)
        with lpath.open(mode="wb") as local_file:
            for data in file_client.download_file().chunks():
                local_file.write(data)


logger = logging.getLogger(__name__)




class Worker(PipelineWorker):
    """A worker to invoke an AzureML pipeline.

    Only a few hooks (methods) have to be implemented to make this worker work.
    Feel free to override other methods in the parent class to customize the behavior.
    """

    def __init__(
        self,
        home_path: str,
        datastore_name: str,
        filesystem: AdlsFilesystem,
        environment: str,
        AzureMlClient: AzureMlClient,
        gpub_path: str,
        host: str,
        port: str,
        username: str,
        password: str,
        databasename: str,
        number_of_process: int,
        tenant_id: str,
        service_principal_id: str ,
        service_principal_password: str ,
        subscription_id: str,
        resource_group: str,
        workspace_name : str,
        # workspace : Workspace,
        **kwargs,
    ) -> None:
        self.home_path = home_path
        self.filesystem = filesystem
        self.datastore_name = datastore_name
        self.environment = environment
        self.AzureMlClient = AzureMlClient
        self.gpub_path = gpub_path
        self.host = host
        self.password = password
        self.username = username
        self.port = port
        self.databasename = databasename
        self.number_of_process = number_of_process
        self.tenant_id = tenant_id
        self.service_principal_id  = service_principal_id
        self.service_principal_password = service_principal_password
        self.subscription_id = subscription_id
        self.resource_group = resource_group
        self.workspace_name =  workspace_name 


        super().__init__(
            filesystem=filesystem,
            pipeline_client=AzureMlClient,
            environment=environment,
            **kwargs,
        )

    def get_files(self, request_json, start_date_obj, end_date_obj):
        request = RequestStatus(
            self.host, self.port, self.username, self.password, self.databasename
        )

        list_of_request = request.get_reqids(
            #application= "projectrun", #request_json["application"],
            application= request_json["application"],
            consumer= request_json["consumer"],
            country=request_json["country"],
            characteristics=  "prediction", #request_json["input"].predict_characteristics,
            start_time=start_date_obj,
            end_time=end_date_obj,
        )
        return list_of_request

        # Datastore

    def get_datastore(self, ws, datastore_name=None):
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

    def upload_file(self, file, path_model, client, datastore):
        try:
            datastore.upload_files(
                [path_model.local_dir + "/" + file],
                target_path=f"{path_model.ml_base_dir}/{client.lower()}/{Globals.INFERENCE_RESULTS_DIR_NAME}",
            )
        except Exception as e:
            print(f"Error uploading {file}: {e}")

    def upload_local_dir(
        self, ws, path_model: MetricsPaths, client, datastore_name=None
    ):
        """Uploads a local directory to an Azure ML datastore location
        :param ws: Workspace where the datastore is located
        :param path_model: TrainingPaths object containing the paths involved in the process
        :param datastore_name: Name of the datastore, if None, the default one will be used
        :returns: Datastore object
        """
        try:
            # The storage system credentials are obtained from the AzureBlobDatastore object
            # TODO: Implement the logic for the rest of storages supported by datastores (currently only works for blobstorage)
            datastore = self.get_datastore(ws, datastore_name)
            if type(datastore) is AzureBlobDatastore:

                if isdir(path_model.local_dir):
                    files_to_upload = [
                        file for file in os.listdir(path_model.local_dir)
                    ]
                    print(f"total files to be uploaded {len(files_to_upload)}")
                    with ThreadPoolExecutor(max_workers=self.number_of_process) as executor:
                        executor.map(
                            lambda file: self.upload_file(
                                file, path_model, client, datastore
                            ),
                            files_to_upload,
                        )


            else:
                raise NotImplementedError("Only AzureBlobDatastore type is implemented")
        except Exception as e:
            raise e

    def output_path(self, request_json, request_id, client):
        output_file_path = f'dmle/{request_json["application"]}/{request_json["consumer"]}/{request_json["input"].predict_characteristics}/{request_json["country"].lower()}/{client.lower()}/output/{request_id}/{request_id}_output.csv'
       
    
        return output_file_path

    def download_inference_files(self, request_json):
        """Get inference files from Redis taking into account dates range from request
        :param request_json: input json got from the user
        :param LoggerUtils: logger
        :return: True if the process is success else False with the respective message.
        """
        input = request_json.get("input")
        # index_file = input.assets[0].path
        country = request_json.get("country")
        start_date = input.start_date
        end_date = input.end_date
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
        path_model = MetricsPaths(request_json)

        count = 0
        request_file = self.get_files(
            request_json, start_date_obj, end_date_obj
        )  ##########

        requests = [request for request in request_file]
        client = requests[0][2]

        with ThreadPoolExecutor(max_workers=self.number_of_process) as executor:
            print("Starting file retrieval...")

            # This assumes requests is a list of tuples, where:
            executor.map(
                lambda request: self.filesystem.get_file(
                    request[1], path_model.local_dir + "/" + request[0] + "_input.csv"
                ),
                requests,
            )
        with ThreadPoolExecutor(max_workers=self.number_of_process) as executor:
            print("Starting file retrieval...")

            executor.map(
                    lambda request: self.filesystem.get_file(
                        self.output_path(request_json, request[0], request[2]),
                        path_model.local_dir + "/" + request[0] + "_output.csv",
                    ),
                    requests,
                )
            
        print("File retrieval completed.")
            
       
        downloaded = True
        message = "file downloaded successfully"
        logger.info(f"count ={count}")
        logger.info(f"length of request_file  ={len(request_file)}")
        print(count)

        return downloaded, message, client

    @override
    def _build_cis_aml_conventions(self, request_json: dict) -> AmlConventions:
        """The conventions to be used to call the AzureML pipeline."""
        request_json = request_json.__dict__
        return AmlConventions(
            cis_env=self.environment,
            input_json=request_json,
            pipeline_country="any",
            pipeline_suffix="metrics",
        )

    @override
    def _build_pipeline_display_name(self, request_json: dict) -> str:
        """The custom name of the pipeline to show in the AzureML WebUI."""
        try:
            pipeline_name = (
                self.environment
                + "_"
                + request_json.application
                + "_"
                + request_json.consumer
                + "_"
                + "any"
                + "_metrics"
            )
            return pipeline_name
        except Exception as e:
            print(e)

    @override
    def _build_pipeline_parameters(self, request_json: dict) -> dict:
        try:
            request_json = request_json.__dict__
            ws = self.AzureMlClient.workspace

            status, message, client = self.download_inference_files(request_json)
            if status:
                self.upload_local_dir(
                    ws, MetricsPaths(request_json), client, self.datastore_name
                )

            """The parameters to invoke the pipeline endpoint."""
            path_model = MetricsPaths(request_json)

            datastore = self.get_datastore(ws, self.datastore_name)
            status, msg = True, None

            count = 0

            model_status = "ACTIVE"
            model_name = client

            inference_path = (
                f"{path_model.ml_base_dir}/{client.lower()}/inference_results"
            )

            assets_path = f"{path_model.ml_base_dir}/{client.lower()}/input_assets"
            country = request_json["country"]
            logger.info(
                f"datastore value is {datastore} path value is {inference_path}  assets value {assets_path}"
            )
            dataset = Dataset.File.from_files((datastore, inference_path))
            
            inference_dataset_reg = dataset.register(workspace=ws, name=inference_path)
            
            index_path = request_json['input'].index_file

            index_dataset = Dataset.File.from_files((datastore, index_path))

            index_dataset_reg = index_dataset.register(workspace=ws, name=index_path)
           
            gpub_path = f"{self.gpub_path}/{country}"
            # pg_id_file = self.pg_id_path

            dataset = Dataset.File.from_files((datastore, gpub_path))
            gpub_dataset_reg = dataset.register(
                workspace=ws, name=gpub_path, create_new_version=True
            )

            pipeline_parameters = {
                "request_id": request_json["requestId"],
                "input_data": inference_dataset_reg,
                "index_data": index_dataset_reg,
                "gpub_data": gpub_dataset_reg,
                "start_date": request_json["input"].start_date,
                "end_date": request_json["input"].end_date,
                "model_artifact_id": request_json["requestId"],
                "model_version": "1",
                "model_status": model_status,
                "model_name": model_name,
                "country": request_json["country"],
                "initiative_name": request_json["consumer"],
                "tenant_id" : self.tenant_id,
                "service_principal_id"  : self.service_principal_id ,
                "service_principal_password" : self.service_principal_password ,
                "subscription_id" : self.subscription_id,
                "resource_group" : self.resource_group ,
                "workspace_name" : self.workspace_name 

            }

            logger.info(f"Pipeline parameters are {pipeline_parameters}")
            return pipeline_parameters
        except Exception as e:
            
            print(e)
