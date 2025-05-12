"""
Worker module is used to process the Sirval us-ops sirval-training, and validates its files and parameters.
"""
import os
import pandas as pd
import sys
import traceback
import shutil

from pathlib import Path
from wrapper_worker.core.app_status import AppStatus
from wrapper_worker.worker import Worker
from wrapper_worker.core.logger_utils import LoggerUtils
from .blobContainerController import (container_client, upload_file, list_prediction_files, blob_exists)
from .storage_utils import HttpsDownloader
from .config import Config
from .globals import Globals
from .metrics_paths import MetricsPaths
from .message import Message
from .storage_utils import get_storage_obj
from .utils import (
    get_dataframe_from_file_data,
    validate_input_json,
    validate_metadata,
    validate_input_files,
    validate_iso_week, 
    download_assets_files,
    get_output_file_path,
    create_output_csv_file
)
from index.controller import IndexController
from index.schema import AnnotationSchema

class MetricsWorker(Worker):

    """
    MetricsWorker will extend all the abstract method form the base Worker Wrapper:
        - clean_up_environment(self, request_json: dict, logger: logging.Logger) -> None
        - validate_request(self, request_json: dict, logger: logging.Logger) -> [bool, str]
        - prepare_request_environment(self, request_json: dict, logger: logging.Logger) -> pandas.DataFrame
        - process_results(self, request_json: dict, output_data_frame: pandas.DataFrame, logger: logging.Logger)
        - ml_exec_request(self, request_json: dict, logger: logging.Logger, ml_property=None) -> [bool, str]
    """
    def validate_request(self, request_json: dict, logger):
        """
        validate_request method extend the base Worker validate_request method, validates: input JSON, metadata and files
        :param request_json: Input json got from the queue (umbrella input + requestId)
        :param logger: logger object
        :return: True if the validation is success else False with respective message.
        """
        LoggerUtils.save_log(
            request_id=request_json["requestId"],
            app_con=request_json["application"] + "_" + request_json["consumer"],
            message=Message.validation_started,
            extended_message=request_json
        )
        msg = validate_input_json(request_json)
        if msg is not None:
            return False, msg
        status, msg = validate_metadata(request_json)
        if not status:
            return False, msg        
        status, msg = validate_input_files(request_json)
        if not status:
            return False, msg
        status, msg = validate_iso_week(request_json)
        if not status:
            return False, msg       
        
        LoggerUtils.save_log(
            request_id=request_json["requestId"],
            app_con=request_json["application"] + "_" + request_json["consumer"],
            message=Message.validation_completed,
        )
        return True, Message.validation_completed
        
    def ml_exec_request(self, request_json: dict, logger, ml_property: list):
        """
        ml_exec_request method is used to prepare all the input files, model files and calliberation files.
        Once all the files are prepared it will invoke the predict method and save the output dataframe.
        :param request_json: Input json got from the user
        :param logger: logger object
        :param ml_property: list of ml property loaded from the metadata.
        :return: True if the process is success else False with the respective message.   
        """
        try:
            LoggerUtils.save_log(
                request_id=request_json["requestId"],
                app_con=request_json["application"] + "_" + request_json["consumer"],
                message=Message.metrics_worker_started,
                extended_message=request_json,
            )
            status = self.prepare_request_environment(
                request_json, LoggerUtils
            )
            if not status:
                LoggerUtils.save_log(
                    request_id=request_json["requestId"],
                    app_con=request_json["application"] + "_" + request_json["consumer"],
                    message=Message.prepare_req_env_error,
                    extended_message=request_json,
                )
                return status, f"{Message.prepare_req_env_error}: {request_json}"
            LoggerUtils.save_log(
                request_id=request_json["requestId"],
                app_con=request_json["application"] + "_" + request_json["consumer"],
                message=Message.preparation_completed,
                extended_message=Message.preparation_completed,
            )
            status, output_feedback_list = self.generate_data_for_output_csv_file(request_json)
            if status:
                return self.process_results(request_json, output_feedback_list, logger)
            return False, Message.generate_csv_output_data_error
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            LoggerUtils.save_log(
                level=Message.log_level_error,
                is_request=False,
                request_id=request_json["requestId"],
                app_con=f'{request_json["application"]}_{request_json["consumer"]}',
                message=f'ERROR - {e.args[0]}',
                extended_message={"traceback": traceback.format_exception(exc_type, exc_value, exc_traceback,
                                                                          chain=True)},
            )
            return False, str(e)
        finally:
            self.clean_up_environment(request_json, LoggerUtils)

    def prepare_request_environment(self, request_json: dict, LoggerUtils):
        """
        Downloads input CSV files from assets nodes in input request

        :param request_json: input json got from the user
        :param LoggerUtils: logger
        :return: True if the process is success else False with the respective message.
        """
        status = False
        try:
            file_paths = MetricsPaths(request_json)

            LoggerUtils.save_log(
                request_id=request_json["requestId"],
                app_con=request_json["application"] + "_" + request_json["consumer"],
                message=AppStatus.inprogress,
                extended_message=f"Downloading file to local {file_paths.local_dir}...",
            )        
            # Download files within request assets node
            status, message = download_assets_files(request_json)

            LoggerUtils.save_log(
                request_id=request_json["requestId"],
                app_con=request_json["application"] + "_" + request_json["consumer"],
                message=AppStatus.inprogress,
                extended_message=f"Downloaded file from remote path to local {file_paths.local_dir}",
            )
       
            return status
        except Exception as ex:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            LoggerUtils.save_log(
                request_id=request_json["requestId"],
                app_con=request_json["application"] + "_" + request_json["consumer"],
                message=f"Error preparing request environment: {str(ex)}",
                extended_message={"traceback": traceback.format_exception(exc_type, exc_value, exc_traceback,chain=True)},
                )
            return status

    def generate_data_for_output_csv_file(self, request_json):
        """
        Reads feedback CSV file and generates data for creating output JSON file

        :param request_json: Input request json
        :return: Result of the process and data from input feedback CSV file
        """
        path_metrics = MetricsPaths(request_json)
        req_id = request_json["requestId"]
        LoggerUtils.save_log(
            request_id= req_id ,
            app_con=request_json["application"] + "_" + request_json["consumer"],
            message=Message.metrics_calculate_started,
            extended_message={"msg": f"Processing request...{req_id}"},
        )

        status, input_df = self.get_dataframe_input_file(path_metrics.local_dir, request_json=request_json)
        output_feedback_list = []

        if not status:    
            LoggerUtils.save_log(
                request_id=req_id,
                app_con=request_json["application"] + "_" + request_json["consumer"],
                message=f"Error preparing request environment: {path_metrics.local_dir}",
                extended_message={"Error: Problem in input file"},
                )
            return status,'No data in input file'

        # Get prediction folders paths and their files numbers
        predictions_dict = {}
        predictions_dict = self.get_predictions_files_from_feedback_csv(request_json, input_df)
        for index, row in input_df.iterrows():
            LoggerUtils.save_log(
                request_id=request_json["requestId"],
                app_con=request_json["application"] + "_" + request_json["consumer"],
                message=Message.metrics_calculate_started,
                extended_message={"msg": f"Processing data row: {index} values {row}..."},
            )

            download_res: bool = True
            msg = ''
            status = 'OK'

            # Check if GLT feedback images match prediction images; if not, indicate it with an error in output CSV file
            predictions_dir_path = str(request_json["country"]).lower() + '/' + str(row["ISO_WEEK"]) + '/' + str(row["RETAILER"]).lower() + '/' + str(row["LEAFLET_NAME"]).lower() + '/' + str(row["DOC_ID"]).lower() + '/' + str(row["REQUEST_ID"]).lower() + '/' + Globals.PREDICTIONS_DIR_NAME
            feedback_image_number = row["IMAGE_NUMBER"]
            if (feedback_image_number in predictions_dict[predictions_dir_path]):
                # Get feedback_url value from CSV dataframe
                feedback_url = str(row["FEEDBACK_URL"])

                try:
                    # Download feedback JSON file from GLT container to local dir
                    local_file_path = Path(path_metrics.local_dir + '/' + Globals.CSV_FEEDBACK_TEMP_NAME).as_posix()
                    download_res, msg = HttpsDownloader.download_file(feedback_url, local_file_path)
                except Exception as ex:
                    download_res = False
                    msg = Message.glt_connection_error
                    status = 'NOK'

                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    LoggerUtils.save_log(
                        level=Message.log_level_error,
                        is_request=False,
                        request_id=request_json["requestId"],
                        app_con=f'{request_json["application"]}_{request_json["consumer"]}',
                        message=f'ERROR - {ex.args[0]}',
                        extended_message={"traceback": traceback.format_exception(exc_type, exc_value, exc_traceback, chain=True)},
                    )

                # Upload feedback file to AzureStorage (path pattern: <country_code>/<iso_week>/<retailer>/<leaflet_name>/<doc_id>/<request_id>/feedbacks)
                if (download_res):
                    try:
                        file_name = str(row["IMAGE_ID"]).rsplit('-',1)[1] + '.json'
                        file_path = str(request_json["country"]).lower() + '/' + str(row["ISO_WEEK"]) + '/' + str(row["RETAILER"]).lower() + '/' + str(row["LEAFLET_NAME"]).lower() + '/' + str(row["DOC_ID"]).lower() + '/' + str(row["REQUEST_ID"]).lower() + '/' + Globals.FEEDBACKS_DIR_NAME + '/' + file_name
                        upload_path = Path(file_path)
                        cc = container_client()
                        upload_file(cc, local_file_path, upload_path)
                    except Exception as ex:
                        msg = f'{Message.azure_storage_upload_error} {upload_path}'
                        status = 'NOK'

                        exc_type, exc_value, exc_traceback = sys.exc_info()
                        LoggerUtils.save_log(
                            level=Message.log_level_error,
                            is_request=False,
                            request_id=request_json["requestId"],
                            app_con=f'{request_json["application"]}_{request_json["consumer"]}',
                            message=f'ERROR - {ex.args[0]}',
                            extended_message={"traceback": traceback.format_exception(exc_type, exc_value, exc_traceback, chain=True)},
                        )
                    else:
                        # Index annotation in database
                        image_path = blob_exists(upload_path.parent.parent / Globals.IMAGES_DIR_NAME / upload_path.with_suffix(".jpg").name)
                        self.index_annotation(request_json, row, feedback_path=upload_path, image_path=image_path)
                else:
                    status = 'NOK'    
            else:
                status = 'NOK'
                msg = Message.unavailable_predcition

            # Generate rows for output CSV file
            feedback_data = list()
            feedback_data.append(str(row["DOC_ID"]))
            feedback_data.append(str(row["REQUEST_ID"]))
            feedback_data.append(int(row["IMAGE_NUMBER"]))
            feedback_data.append(status)
            feedback_data.append(msg)
            output_feedback_list.append(feedback_data)

        return True, output_feedback_list
    
    def index_annotation(self, request_json: dict, row: pd.Series, feedback_path: Path, image_path: Path) -> None:
        """
        Indexes the annotation in the database.

        :param request_json: The request JSON.
        :param row: The row from the feedback CSV.
        :param upload_path: The path to the uploaded feedback file.
        """
        annotation = AnnotationSchema(
            request_id=row["REQUEST_ID"],
            country_code=request_json["country"],
            retailer=row["RETAILER"],
            isoweek=row["ISO_WEEK"],
            annotation_path=feedback_path.as_posix(),
            image_path=image_path.as_posix(),
        )
        try:
            IndexController().add_annotation(annotation)
            LoggerUtils.save_log(
                request_id=request_json["requestId"],
                app_con=request_json["application"] + "_" + request_json["consumer"],
                message=f"Annotation indexed: {annotation.to_dict()}",
            )
        except Exception as ex:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            LoggerUtils.save_log(
                level=Message.log_level_error,
                is_request=False,
                request_id=request_json["requestId"],
                app_con=f'{request_json["application"]}_{request_json["consumer"]}',
                message=f'ERROR - {ex.args[0]}',
                extended_message={"traceback": traceback.format_exception(exc_type, exc_value, exc_traceback, chain=True)},
            )

    def process_results(self, request_json: dict, output_feedback_list, logger):
        """
        Generates output CSV file and uploads to datalake

        :param request_json: input request json
        :param output_feedback_list: data of output CSV file
        :param logger: logger object
        :return: result of the process and respective message
        """
        path_metrics = MetricsPaths(request_json)
        try:
            if not os.path.exists(path_metrics.local_dir_output):
                os.makedirs(path_metrics.local_dir_output)

            # Generate output CSV file
            create_output_csv_file(path_metrics.local_dir_output, output_feedback_list)
            # Upload to datalake
            status, storage_obj = get_storage_obj(Config.output_storage_type())
            output_path = get_output_file_path(request_json)
            input_path = Path(path_metrics.local_dir_output,  Globals.CSV_FEEDBACK_RESPONSE_NAME).as_posix()
            storage_obj.upload_file(f'{output_path}', f'{input_path}')
            return True, Message.csv_output_file_uploaded
        except Exception as err:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            LoggerUtils.save_log(
                request_id=request_json["requestId"],
                app_con=request_json["application"] + "_" + request_json["consumer"],
                message=f"{Message.csv_output_file_uploaded_error}: {str(err)}",
                extended_message={"traceback": traceback.format_exception(exc_type, exc_value, exc_traceback,chain=True)},
                )
            return False, repr(err)

    def clean_up_environment(self, request_json: dict, logger):
        """
        Cleans up all the files after whole process

        :param request_json: Input json got from the user
        :param logger: logger object
        :return: True if the clean up environment is success else False with the respective message.
        """
        try:
            LoggerUtils.save_log(
                request_id=request_json["requestId"],
                app_con=request_json["application"] + "_" + request_json["consumer"],
                message="CLEANING THE ENVIRONMENT",
            )
            path = MetricsPaths(request_json)
            #cleaning input and output files
            input_dir = path.local_dir
            if os.path.exists(input_dir):
                shutil.rmtree(input_dir)
                LoggerUtils.save_log(
                    request_id=request_json["requestId"],
                    app_con=request_json["application"] + "_" + request_json["consumer"],
                    is_request=False,
                    level=Message.log_level_info,
                    message=f"Files under {input_dir} removed",
                )
            return True,Message.cleanup_completed
        except Exception as file_clean_error:
            LoggerUtils.save_log(
                request_id=request_json["requestId"],
                app_con=request_json["application"] + "_" + request_json["consumer"],
                is_request=False,
                level=Message.log_level_error,
                message=f"Exception cleaning env - {str(file_clean_error)}",
            )
        return False, str(Message.cleanup_error)

    def get_dataframe_input_file(self, path_input_file, request_json):
        """
        Converts input CSV file to dataframe

        :param path_input_file: path to the downloaded input CSV file
        :param request_json: input request data
        :return: dataframe with input CSV file data
        """
        try:
            input_df = pd.DataFrame()
            all_input_df = pd.DataFrame()
            for file_data in request_json["input"]["assets"]:
                file = Path(path_input_file, file_data["name"]).as_posix()
                delimiter = file_data["delimiter"]

                input_df, message = get_dataframe_from_file_data(file, delimiter)
                all_input_df = pd.concat([all_input_df, input_df], axis=0)

            if (all_input_df.empty):
                return False, "No data in input file"
            return True , all_input_df
        except Exception as ex:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            LoggerUtils.save_log(
                request_id=request_json["requestId"],
                app_con=request_json["application"] + "_" + request_json["consumer"],
                message=f"Error converting input CSV file to dataframe: {str(ex)}",
                extended_message={"traceback": traceback.format_exception(exc_type, exc_value, exc_traceback,chain=True)},
                )
            return False , all_input_df
    
    def get_predictions_files_from_feedback_csv(self, request_json, input_df):
        """
        Reads feedback CSV dataframe and get for each prediction folder its files number

        :param country: country for building predictions path
        :param input_df: dataframe with data from feedback CSV
        :return: dictionary with prediction folder paths and its image numbers
        """
        # Get from feedback CSV dataframe all different paths to prediction folders
        predictions_paths_list = []

        try:
            for index, row in input_df.iterrows():
                predict_dir_path = str(request_json["country"]).lower() + '/' + str(row["ISO_WEEK"]) + '/' + str(row["RETAILER"]).lower() + '/' + str(row["LEAFLET_NAME"]).lower() + '/' + str(row["DOC_ID"]).lower() + '/' + str(row["REQUEST_ID"]).lower() + '/' + Globals.PREDICTIONS_DIR_NAME
                if predict_dir_path not in predictions_paths_list:
                    predictions_paths_list.append(predict_dir_path)

            # List and get files from AzureStorage from prediction folders paths
            predictions_dict = {}
            con_cli = container_client()
            for predict_path in predictions_paths_list:
                predict_numbers = []
                predict_numbers = list_prediction_files(con_cli, predict_path)
                predictions_dict[predict_path] = predict_numbers

            return predictions_dict
        except Exception as ex:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            LoggerUtils.save_log(
                level=Message.log_level_error,
                is_request=False,
                request_id=request_json["requestId"],
                app_con=f'{request_json["application"]}_{request_json["consumer"]}',
                message=f'ERROR - {ex.args[0]}',
                extended_message={"traceback": traceback.format_exception(exc_type, exc_value, exc_traceback, chain=True)},
            )
            return False, f"{str(ex)} {traceback.format_exc()}"
