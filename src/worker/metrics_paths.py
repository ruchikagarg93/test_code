import html
from pathlib import Path
from datetime import datetime
from .config import Config
from .globals import Globals 

class MetricsPaths:
    local_dir: str
    local_dir_output: str
    local_dir_output_file: str
    ml_base_dir: str
    ml_base_trainig: str
    ml_base_prediction: str
    ml_input_dir: str
    ml_output_dir: str
    ml_input_assets_dir: str
    ml_inference_results_dir: str
    adl_base_dir:str
    output_csv_name: str

    def __init__(self, input_json):
        self.output_csv_name = f"{input_json.get('requestId')}_output.csv"

        self.local_dir = str(Path(
            "/",
            Config.get_dmle_output_home_path(),
            f'{input_json.get("application").lower()}/'
            f'{input_json.get("consumer").lower()}/'
            f'{input_json.get("characteristics")[0].lower()}/'
            f'{input_json.get("country").lower()}/'
            f'{input_json.get("client").lower()}/'
            f"input/"
            f'{input_json.get("requestId")}/'
        ).as_posix())

        self.local_dir_output = str(Path(
            self.local_dir,
            Globals.OUTPUT_DIR_NAME
        ).as_posix())

        self.local_dir_output_file = str(Path(
            self.local_dir_output,
            self.output_csv_name
        ).as_posix()) 
        
        self.ml_base_dir = Path(
            input_json.get("application").lower(),
            input_json.get("consumer").lower(),
            input_json.get("characteristics")[0].lower(),
            input_json.get("country").lower(),
            datetime.utcnow().strftime("%Y"),
            datetime.utcnow().strftime("%m"),
            datetime.utcnow().strftime("%d"),
            input_json.get("requestId")
        ).as_posix()

        self.ml_input_dir = Path(
            self.ml_base_dir,
            Globals.INPUT_DIR_NAME
        ).as_posix()

        self.ml_output_dir = Path(
            self.ml_base_dir,
            Globals.OUTPUT_DIR_NAME
        ).as_posix()

        self.ml_input_assets_dir = Path(
            self.ml_base_dir,
            Globals.INPUT_ASSETS_DIR_NAME
        ).as_posix()

        self.ml_inference_results_dir = Path(
            self.ml_base_dir,
            Globals.INFERENCE_RESULTS_DIR_NAME
        ).as_posix()

        self.adl_base_dir = Path(
            Config.adls_gen2_container_name(),
            input_json.get("application").lower(),
            input_json.get("consumer").lower(),
            input_json.get("characteristics")[0].lower(),
            input_json.get("country").lower(),
            input_json.get("client").lower(),
            Globals.OUTPUT_DIR_NAME,
            input_json.get("requestId")
        ).as_posix()

        self.adl_output_csv = Path(
            self.adl_base_dir,
            self.output_csv_name
        ).as_posix()