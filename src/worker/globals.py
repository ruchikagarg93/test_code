import re
class Globals:
    """This module defines project-level constants."""

    INPUT_DIR_NAME = "input"
    OUTPUT_DIR_NAME = "output"
    INPUT_ASSETS_DIR_NAME = "input_assets"
    INFERENCE_RESULTS_DIR_NAME = "inference_results"
    PIPELINE_STATUS_COMPLETED = "Completed"
    DELIMITER= ";"
    CLIENT = 'cis'
    PREDICTIONS_DIR_NAME = "predictions"
    FEEDBACKS_DIR_NAME = "feedbacks"
    IMAGES_DIR_NAME = "input/images"
    CSV_FEEDBACK_TEMP_NAME = "csv_feedback.json"
    CSV_FEEDBACK_RESPONSE_NAME = "feedback_output.csv"

    # Fields of CSV files
    DOC_ID = 'DOC_ID'
    REQUEST_ID = 'REQUEST_ID'
    IMAGE_NUMBER = 'IMAGE_NUMBER'
    IMAGE_ID = 'IMAGE_ID'
    ISO_WEEK = 'ISO_WEEK'
    RETAILER = 'RETAILER'
    LEAFLET_NAME = 'LEAFLET_NAME'
    FEEDBACK_URL = 'FEEDBACK_URL'
    STATUS = 'STATUS'
    ERROR_DESCRIPTION = 'ERROR_DESCRIPTION'

