from src.pr_flyers_metrics_worker.worker.worker.request import CisRequestUp
from src.pr_flyers_metrics_worker.worker import worker
from src.pr_flyers_metrics_worker.worker.worker import config
 def main():
    # Sample request input
    request_data = {
        "application": "projectrun",
        "consumer": "promoflyers",
        "country": "us",
        "characteristics": [
            "promoflyers-metrics"
        ],
        "client": "GLT",
        "input": {
            "assets": [
                {
                    "name": "test_name",
                    "path":"/projectrun/promoflyers/input/REQ-db0b6564-fe43-408b-9c9c-9391d1d64a4e/metic_example.csv",
                    "delimiter": ",",
                    "iso_week": 202501
                }
            ]
        }
    }
    
    req = CisRequestUp(**request_data)
    worker.run(req, output_path, feedback_container)

    # 2) Compute feedback_container & output_path from Config + request
    feedback_container = Config.get_promoflyer_container_name()  # e.g. "pflyers-data-rnd"
    
    asset = req.input.assets[0]
    base = Config.get_dmle_output_home_path()  # "dmle"
    output_path = os.path.join(
        base,
        req.application,
        req.consumer,
        str(asset.iso_week),
        f"{asset.name}_response.csv"
    )
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # 3) Instantiate Worker
    worker = Worker(
        # -- CisWorker core dependencies:
        filesystem=LocalFileSystem(),     # local fs for now
        cache=None,                       # not used by your business logic
        metadata_client=None,             # likewise
        audit_queue=None,                 # OK for local test

        # -- Azure Blob Storage
        promoflyer_storage_account=Config.get_promoflyer_storage_account(),
        promoflyer_container_name=Config.get_promoflyer_container_name(),
        token_cis=Config.get_token_cis(),

        # -- Redis cache
        redis_cache_host=Config.get_redis_cache_host(),
        redis_cache_port=Config.get_redis_cache_port(),
        redis_cache_password=Config.get_redis_cache_password(),

        # -- Redis queue
        redis_queue_host=Config.get_redis_queue_host(),
        redis_queue_port=Config.get_redis_queue_port(),
        redis_queue_password=Config.get_redis_queue_password(),

        # -- Database
        db_server=Config.get_db_server(),
        db_port=Config.get_db_port(),
        db_name=Config.get_db_name(),
        db_user=Config.get_db_user(),
        db_pass=Config.get_db_pass(),

        # -- Azure ML
        azureml_subscription_id=Config.get_azureml_subscription_id(),
        azureml_resource_group=Config.get_azureml_resource_group(),
        azureml_workspace_name=Config.get_azureml_workspace_name(),
        azureml_tenant_id=Config.get_azureml_tenant_id(),
        azureml_client_id=Config.get_azureml_client_id(),
        azureml_client_secret=Config.get_azureml_client_secret(),
    )

    # 4) Run the worker
    worker.run(req, output_path, feedback_container)
    print(f"Test run complete. Output CSV at: {output_path}")

if __name__ == "__main__":
    main()
