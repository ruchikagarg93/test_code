from pr_flyers_metrics_worker.worker.worker import request
from pr_flyers_metrics_worker.worker.worker import worker
from pr_flyers_metrics_worker.worker.worker.config_loader import ConfigLoader
import os

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
    
    cfg = ConfigLoader.get_instance()
    req = request.CisRequestUp(**request_data)

    # 2) Compute feedback_container & output_path from cfg + request
    feedback_container = cfg.storage.promoflyer_container_name  # e.g. "pflyers-data-rnd"
    
    asset = req.input.assets[0]
    base = cfg.storage.dmle_output_home_path  # "dmle"
    output_path = os.path.join(
        base,
        req.application,
        req.consumer,
        str(asset.iso_week),
        f"{asset.name}_response.csv"
    )
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # 3) Instantiate worker
    worker_instance = Worker(
    # -- Azure Blob Storage
    promoflyer_storage_account=cfg.storage.promoflyer_storage_account,
    promoflyer_container_name=cfg.storage.promoflyer_container_name,
    token_cis=cfg.storage.token_cis,

    # -- Redis cache
    redis_cache_host=cfg.redis.cache_host,
    redis_cache_port=cfg.redis.cache_port,
    redis_cache_password=cfg.redis.cache_password,

    # -- Redis queue
    redis_queue_host=cfg.redis.queue_host,
    redis_queue_port=cfg.redis.queue_port,
    redis_queue_password=cfg.redis.queue_password,

    # -- Database
    db_server=cfg.database.server,
    db_port=cfg.database.port,
    db_name=cfg.database.name,
    db_user=cfg.database.user,
    db_pass=cfg.database.password,

    # -- Azure ML
    azureml_subscription_id=cfg.azureml.subscription_id,
    azureml_resource_group=cfg.azureml.resource_group,
    azureml_workspace_name=cfg.azureml.workspace_name,
    azureml_tenant_id=cfg.azureml.tenant_id,
    azureml_client_id=cfg.azureml.client_id,
    azureml_client_secret=cfg.azureml.client_secret,
    )
    
    worker_instance.run(req, output_path, feedback_container)
    print(f"Test run complete. Output CSV at: {output_path}")

if __name__ == "__main__":
    main()
