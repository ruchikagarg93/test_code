"""
message module is used to store all the message for logs.
"""
from wrapper_worker.message import Message as BasicMessage


class Message(BasicMessage):
    """
    Message class extends base Message from wrapper and it contains all the message for logs.
    """

    validation_started = "Promoflyers promoflyers-metrics worker Validation started"

    json_schema_validated = "Json schema validated successfully"

    check_model_services = "Metadata is not validated, Kindly check for the model or service metadata available in Redis metadata cache"

    check_model_attributes = "Model attributes are not available in the Metadata kinldy check it!!"

    validation_completed = "Validation completed from Promoflyers promoflyers-metrics worker"

    no_input_files = "No input files found in the asserts, Kindly provide proper input files in the asserts"
    
    input_file_read_ok = "OK"

    adls_gen_1 = "ADLS_GEN1"

    adls_gen_2 = "ADLS_GEN2"

    hdfs = "HDFS"

    invalid_storage_type = "Storage type is not valid, Kindly check the storage type in configuration"

    input_file_not_found = "Input files not found in the given path, kindly check the paths in input assets array"
    
    input_files_available = "Input files are available"

    input_files_downloaded = "Input files downloaded"

    input_files_ml_published = "Input files succesfully published in Azure ML"

    input_files_prepared = "Input files prepared successfully!"

    model_files_downloaded = "Model files downloaded successfully!"

    metrics_worker_started = "Promoflyers promoflyer-metrics worker started processing"

    metrics_calculate_started = "Promoflyers calculate metrics started"

    metrics_calculate_completed = "Promoflyers calculate metrics successfully!"

    dataprep_pipeline_started = "Azure ML Pipeline for data preparation will start"

    dataprep_pipeline_ended = "Azure ML Pipeline has ended succesfully"

    Promoflyers_completed = "Promoflyers promoflyer-metrics worker Completed Successfully!"

    preparation_completed = "Environment preparation completed"

    prepare_req_env_error = "Error preparing request environment"

    uploaded_successfully = "Uploaded successfully"

    downloaded_successfully = "Downloaded successfully"

    file_exists = "File exists"

    file_not_exists = "File not exists"

    no_model_files = "There is no model files available in the container"

    no_output_service_response = "There is no 'output_service_response' attribute the metrics service reponse!"

    model_files_available = "Model files available in the container"

    invalid_country = "Country is invalid, Kindly check the country once!"

    cleanup_completed = "Environment cleanup completed!"

    cleanup_error = "Error cleaning up environment!"

    results_processed = "metrics results processed succesfully"

    ml_upload_completed = "Assests directory succesfully uploaded"

    job_not_found = "Job not found"

    date_format_error = "Incorrect format of Date"

    dates_error = "Start date after End date"

    input_validate = "Input data validate"

    training_file_not_found = "Training file not found"

    training_file_downloaded = "Training file downloaded"
    
    prediction_file_not_found = "Prediction file not found"

    prediction_file_downloaded = "Prediction file downloaded"

    iso_week_validate = "Iso week data validate"
    
    invalid_iso_week ="Iso week is invalid, check it "

    glt_connection_issue = "Failed to establish a new connection"

    glt_connection_error = "FEEDBACK ACCESS: remote file in GLT container cannot be accessed"

    azure_storage_upload_error = "AZURE STORAGE: Error uploading file to "

    unavailable_predcition = "UNAVAILABLE PREDICTION: there is no data for the indicated document and prediction"

    generate_csv_output_data_error = "Error generating data for output CSV file"

    csv_output_file_uploaded = "Output CSV file uploaded successfully to datalake"

    csv_output_file_uploaded_error = "Error uploading output CSV file to datalake"
