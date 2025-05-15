import yaml
import os
from dataclasses import dataclass
from typing import Optional
 
 
@dataclass
class RedisConfig:
    cache_host: str
    cache_port: int
    cache_password: str
    queue_host: str
    queue_port: int
    queue_password: str
    metadata_host: str
    metadata_port: int
    metadata_password: str
    queue_time_out: int
    queue_name: str
 
 
@dataclass
class LoggingConfig:
    component_name: str
    log_to_console: bool
    log_to_file: bool
    get_log_file_name: str
    log_file_path: str
 
 
@dataclass
class AzureMLConfig:
    subscription_id: str
    resource_group: str
    workspace_name: str
    tenant_id: str
    client_id: str
    client_secret: str
 
 
@dataclass
class StorageConfig:
    adls_account_name: str
    adls_container_name: str
    adls_tenant_id: str
    adls_client_id: str
    adls_client_secret: str
    promoflyer_container_name: str
    promoflyer_storage_account: str
    input_storage_type: str
    output_storage_type: str
    dmle_output_home_path: str
    token_cis: str
 
 
@dataclass
class DatabaseConfig:
    server: str
    port: int
    name: str
    user: str
    password: str
 
 
@dataclass
class AppConfig:
    redis: RedisConfig
    logging: LoggingConfig
    azureml: AzureMLConfig
    storage: StorageConfig
    database: DatabaseConfig
    is_continuous: bool
 
 
class ConfigLoader:
    _instance = None
 
    def __init__(self, config_path: str = "./config.yaml"):
        with open(config_path, "r") as f:
            full_config = yaml.safe_load(f)
        env = full_config.get("ENV", "rnd")
        cfg = full_config.get(env, {})
 
        self.redis = RedisConfig(
            cache_host=cfg["redis_cache_host"],
            cache_port=int(cfg["redis_cache_port"]),
            cache_password=cfg["redis_cache_password"],
            queue_host=cfg["redis_queue_host"],
            queue_port=int(cfg["redis_queue_port"]),
            queue_password=cfg["redis_queue_password"],
            metadata_host=cfg["redis_metadata_host"],
            metadata_port=int(cfg["redis_metadata_port"]),
            metadata_password=cfg["redis_metadata_password"],
            queue_time_out=int(cfg["redis_queue_time_out"]),
            queue_name=cfg["redis_queue_name"],
        )
 
        self.logging = LoggingConfig(
            component_name=cfg["component_name"],
            log_to_console=cfg["log_to_console"].lower() == "true",
            log_to_file=cfg["log_to_file"].lower() == "true",
            get_log_file_name=cfg["get_log_file_name"],
            log_file_path=cfg["log_file_path"],
        )
 
        self.azureml = AzureMLConfig(
            subscription_id=cfg["azureml_subscription_id"],
            resource_group=cfg["azureml_resource_group"],
            workspace_name=cfg["azureml_workspace_name"],
            tenant_id=cfg["azureml_tenant_id"],
            client_id=cfg["azureml_client_id"],
            client_secret=cfg["azureml_client_secret"],
        )
 
        self.storage = StorageConfig(
            adls_account_name=cfg["adls_gen2_account_name"],
            adls_container_name=cfg["adls_gen2_container_name"],
            adls_tenant_id=cfg["adls_gen2_tenant_id"],
            adls_client_id=cfg["adls_gen2_client_id"],
            adls_client_secret=cfg["adls_gen2_client_secret"],
            promoflyer_container_name=cfg["promoflyer_container_name"],
            promoflyer_storage_account=cfg["promoflyer_storage_account"],
            input_storage_type=cfg["input_storage_type"],
            output_storage_type=cfg["output_storage_type"],
            dmle_output_home_path=cfg["dmle_output_home_path"],
            token_cis=cfg["token_cis"],
        )
 
        self.database = DatabaseConfig(
            server=cfg["db_server"],
            port=int(cfg["db_port"]),
            name=cfg["db_name"],
            user=cfg["db_user"],
            password=cfg["db_pass"],
        )
 
        self.is_continuous = cfg.get("is_continuous", False)
 
    @classmethod
    def get_instance(cls, config_path: str = "config.yaml"):
        if cls._instance is None:
            cls._instance = cls(config_path)
        return cls._instance
