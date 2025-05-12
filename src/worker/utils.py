"""
util module is used for all the helper functions for CDAR PanelModernization.
"""
import os
import json
import pandas
import re
import traceback
import csv

from pathlib import Path
from cerberus import Validator
from .metrics_paths import MetricsPaths
from wrapper_worker.core.redis_utils import RedisUtils
from .config import Config
from .message import Message
from .storage_utils import HttpsDownloader, get_storage_obj
from .globals import Globals

HTTP_REGEX = re.compile(
                r'^(?:http)s?://' # http:// or https://
                r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' #domain...
                r'localhost|' #localhost...
                r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
                r'(?::\d+)?' # optional port
                r'(?:/?|[/?]\S+)$', re.IGNORECASE)


def format_err_msg(err, val):
    """Helper function of generate error message used to formate error message"""
    val = str(val)
    if "required" in val:
        err += f"is a {val}"
    elif "empty" in val:
        err = f"{val} for {err}"
    elif "type" in val:
        err += f" {val}"
    elif "unallowed" in val:
        err += f"contains the {val}"
    return err

def check_for(err, val):
    """Helper function of generate error message which is used to check for all errors"""
    if isinstance(val, list):
        for v in val:
            return check_for(err, v)
    elif isinstance(val, dict):
        for kk, vv in val.items():
            if not isinstance(kk, int):
                err = kk + " inside " + err
            return check_for(err, vv)
    return format_err_msg(err, val)

def generate_err_msg(error):
    """generate error message in verbal way"""
    err = ""
    for key, val in error.items():
        e = check_for(f"{key} ", val)
        if err != "":
            err += " and "
        err += e
    return err

def validate_input_json(request_json):
    """
    Validates all the input JSON received from the umbrella service

    :param request_json: input_json provided by the umbrella service
    :return : True if the json is correct or False with respective message.

    """
    methods = [validate_schema]

    msg = None

    # Run all the validator methods, return the message if validation fails
    for method in methods:
        msg = method(**request_json)
        if msg and msg is not None:
            break
        else:
            continue
    return msg

def validate_schema(**request_json) -> str:
    """
    Validates the input JSON against the expected schema

    :param request_json: request_json provided by the umbrella service
    :return : str validates and returns the respective message.
    """
    promoflyers_metrics_schema = {
        "application": {"type": "string", "required": True, "empty": False},
        "consumer": {"type": "string", "required": True, "empty": False},
        "country": {"type": "string", "required": True, "empty": False},
        "client": {"type": "string", "required": True, "empty": False},
        "characteristics": {
            "type": "list",
            "required": True,
            "items": [{"type": "string", "empty": False}],
        },
        "input":{
            "type": "dict",
            "required": False,
            "schema":{
                "assets": {
                    "type": "list",
                    "required": True,
                    "empty": False,
                    "schema": {
                        "type": "dict",
                        "required": True,
                        "empty": False,
                        "schema": {
                            "name": {
                                "type": "string",
                                "required": True,
                                "empty": False,
                            },
                            "path": {
                                "type": "string",
                                "required": True,
                                "empty": False,
                            },
                            "delimiter": {
                                "type": "string",
                                "required": False,
                                "empty": False,
                            },
                            "iso_week": {
                                "type": "integer",
                                "required": True,
                                "empty": False,
                            }
                        },
                    },
                },
            }
        }
    }
    validator = Validator(promoflyers_metrics_schema, allow_unknown=True)
    if not validator.validate(request_json, promoflyers_metrics_schema):
        return generate_err_msg(validator.errors)

def validate_metadata(input_json):
    """
    validate_metadata method is used to validate metadata.

    :param input_json: input_json give by the user
    :return : True if the metadata validated or False with respective message.

    """
    country_keys = RedisUtils.get_redis_metadata().get_matched_keys(
        f'*{input_json["application"].lower()}_{input_json["consumer"].lower()}_{input_json["country"].lower()}_{input_json["characteristics"][0].lower()}_*'
    )
    country_keys_for_any = RedisUtils.get_redis_metadata().get_matched_keys(
        f'*{input_json["application"].lower()}_{input_json["consumer"].lower()}_any_{input_json["characteristics"][0].lower()}_*'
    )

    if not (country_keys or country_keys_for_any):
        return False, Message.invalid_country

    service_keys = RedisUtils.get_redis_metadata().get_matched_keys(
        f'*{input_json["application"].lower()}_{input_json["consumer"].lower()}_{input_json["country"].lower()}_{input_json["characteristics"][0].lower()}_service*'
    )
    service_keys_any = RedisUtils.get_redis_metadata().get_matched_keys(
        f'*{input_json["application"].lower()}_{input_json["consumer"].lower()}_any_{input_json["characteristics"][0].lower()}_service*'
    )

    if not (service_keys or service_keys_any):
        return False, Message.check_model_services
  
    return True, Message.metadata_validated

def validate_iso_week(input_json):  
    if input_json.get("input", None) and input_json["input"].get("assets", None):
        for asset in input_json["input"]["assets"]:
            isoweek = asset.get("iso_week",None)
            if isoweek:
                if not (isoweek>=200001 and isoweek<=210000):
                    message = Message.invalid_iso_week + f' {isoweek}'
                    return False, message
                else: 
                    month = isoweek%100
                    if not (month>=1 and month<=53):
                        message = Message.invalid_iso_week + f' {isoweek}'
                        return False, message
    return True, Message.iso_week_validate

def validate_input_files(input_json):
    """
    validate_input_files method is used to validate input files.

    :param input_json: input_json give by the user
    :return : True if the input files are validated or False with respective message.
    """

    if input_json.get("input", None) and input_json["input"].get("assets", None):
        files = [
            False
            for file_data in input_json["input"]["assets"]
            if file_data["path"] in [" ", "  ", "", ".", '""']
        ]
        if len(files) > 0:
            return False, Message.no_input_files

        status, storage_obj = get_storage_obj(storage_type=Config.input_storage_type())

        if not status:
            return False, storage_obj

        try:
            for file_data in input_json["input"]["assets"]:
                if is_http(file_data["path"]):
                    status,_ = HttpsDownloader.check_file(file_data["path"])
                else:
                    status,_ = storage_obj.check_file(file_data["path"])
                if not status:
                    return False, Message.input_file_not_found
            return True, Message.input_files_available
        except Exception as err:
            return False, f"{str(err)} {traceback.format_exc()}"


def download_assets_files(request_json: dict):
    """
    Downloads input file from asset node

    :param request_json: input request data
    :return : True if the input CSV file is downloaded correctly; False otherwise
    """
    if request_json.get("input", None) and request_json["input"].get("assets", None):
        files = [
            False
            for file_data in request_json["input"]["assets"]
            if file_data["path"] in [" ", "  ", "", ".", '""']
        ]
        if len(files) > 0:
            return False, Message.no_input_files

        status, storage_obj = get_storage_obj(storage_type=Config.input_storage_type())

        if not status:
            return False, storage_obj

        try:
            path_model = MetricsPaths(request_json)
            for file_data in request_json["input"]["assets"]:
                folder = path_model.local_dir
                if not os.path.exists(folder):
                    os.makedirs(folder)
                
                local_path = Path(path_model.local_dir + '/' + file_data["name"]).as_posix()
                if is_http(file_data["path"]):    
                    status, msg = HttpsDownloader.download_file(file_data["path"],local_path,)
                else:
                    status, msg = storage_obj.download_file(file_data["path"],local_path,)
                if not status:
                    return False, msg
            return True, Message.input_files_available
        except Exception as err:
            return False, f"{str(err)} {traceback.format_exc()}"

def is_http(url):
    """
    Check if url is an URI or a relative path to the storage

    :param url: path of the file to be checked
    :return : True if url is a URI; False otherwise
    """
    return re.match(HTTP_REGEX, url)

def get_dataframe_from_file_data(local_input_path: str, delimiter: str):
    """
    reads input csv file and convert data into a dataframe

    :param local_input_path: path in local disk of the downloaded input file
    :param delimiter: delimiter used in the input csv
    :return: dataframe with input file data
    """
    try:
        input_df = pandas.DataFrame()
        # Read CSV input file
        import numpy as np
        input_df = pandas.read_csv(Path(local_input_path).as_posix(),
                    encoding='utf-8',
                    sep = delimiter,
                    usecols = [Globals.DOC_ID, Globals.REQUEST_ID, Globals.IMAGE_NUMBER, Globals.IMAGE_ID, Globals.ISO_WEEK, Globals.RETAILER, Globals.LEAFLET_NAME, Globals.FEEDBACK_URL],
                    dtype = {
                        Globals.DOC_ID: str,
                        Globals.REQUEST_ID: str,
                        Globals.IMAGE_NUMBER: np.int64,
                        Globals.IMAGE_ID: str,
                        Globals.ISO_WEEK: np.int64,
                        Globals.RETAILER: str,
                        Globals.LEAFLET_NAME: str,
                        Globals.FEEDBACK_URL: str
                        }
                    )
        df_without_duplicates = remove_duplicates(input_df)
        return df_without_duplicates, Message.input_file_read_ok
    except Exception as err:
        return input_df, str(err)

def remove_duplicates(df: pandas.DataFrame) -> pandas.DataFrame:
    """
    Remove duplicates from dataset 

    Args:
        df (pd.DataFrame): 

    Returns:
        pd.DataFrame: dataframe after removing duplicates
    """
    features = list(df.columns)
    features.remove('DOC_ID')

    df = df.drop_duplicates(subset=features).reset_index(drop=True)

    return df

def get_output_file_path(request_json):
    """
        Generates datalake path to store CSV feedback file

        :param request_json: input request data
        :return: datalake path
    """
    return (f'/dmle/'
        f'{request_json.get("application").lower()}/'
        f'{request_json.get("consumer").lower()}/'
        f'{request_json.get("characteristics")[0].lower()}/'
        f'{request_json.get("country").lower()}/'
        f'{request_json.get("client").lower()}/'
        f"output/"
        f'{request_json.get("requestId")}/'
        f'{request_json.get("requestId")}_output.csv')

def create_output_csv_file(local_dir_output: str, output_feedback_list: list) -> bool:
    """
        Creates output CSV file in local disk for being upload to datalake later

        :param local_dir_output: path in local disk to store output CSV file
        :param output_feedback_list: output CSV file ros data
        :return: result of the creation of output CSV file in local disk
    """
    # Field names  
    fields = [Globals.DOC_ID, Globals.REQUEST_ID, Globals.IMAGE_NUMBER, Globals.STATUS, Globals.ERROR_DESCRIPTION]
    # Data rows of csv file  
    rows = output_feedback_list

    try:
        # Writing to csv file  
        with open(os.path.join(local_dir_output, Globals.CSV_FEEDBACK_RESPONSE_NAME), 'w', newline ='') as csvfile:  
            # Creating a csv writer object  
            csvwriter = csv.writer(csvfile)  
            # Writing the fields  
            csvwriter.writerow(fields)  
            # Writing the data rows  
            csvwriter.writerows(rows)
    except Exception as ex:
        return False

    return True
