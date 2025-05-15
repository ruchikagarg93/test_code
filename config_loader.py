from wrapper_worker.config import Config as BaseConfig


class ConfigLoader(BaseConfig):
    """
    Custom Config Loader extending wrapper_worker.config.Config
    with project-specific config accessors.
    """

    @staticmethod
    def get_redis_cache_host():
        return ConfigLoader.config[ConfigLoader.get_env()]["redis_cache_host"]

    @staticmethod
    def get_redis_cache_port():
        return int(ConfigLoader.config[ConfigLoader.get_env()]["redis_cache_port"])

    @staticmethod
    def get_redis_cache_password():
        return ConfigLoader.config[ConfigLoader.get_env()]["redis_cache_password"]

    @staticmethod
    def get_redis_queue_host():
        return ConfigLoader.config[ConfigLoader.get_env()]["redis_queue_host"]

    @staticmethod
    def get_redis_queue_port():
        return int(ConfigLoader.config[ConfigLoader.get_env()]["redis_queue_port"])

    @staticmethod
    def get_redis_queue_password():
        return ConfigLoader.config[ConfigLoader.get_env()]["redis_queue_password"]

    @staticmethod
    def get_redis_metadata_host():
        return ConfigLoader.config[ConfigLoader.get_env()]["redis_metadata_host"]

    @staticmethod
    def get_redis_metadata_port():
        return int(ConfigLoader.config[ConfigLoader.get_env()]["redis_metadata_port"])

    @staticmethod
    def get_redis_metadata_password():
        return ConfigLoader.config[ConfigLoader.get_env()]["redis_metadata_password"]

    @staticmethod
    def get_redis_queue_timeout():
        return int(ConfigLoader.config[ConfigLoader.get_env()]["redis_queue_time_out"])

    @staticmethod
    def get_queue_name():
        return ConfigLoader.config[ConfigLoader.get_env()]["redis_queue_name"]

    @staticmethod
    def get_component_name():
        return ConfigLoader.config[ConfigLoader.get_env()]["component_name"]

    @staticmethod
    def log_to_console():
        return str(ConfigLoader.config[ConfigLoader.get_env()].get("log_to_console", "False")).lower() == "true"

    @staticmethod
    def log_to_file():
        return str(ConfigLoader.config[ConfigLoader.get_env()].get("log_to_file", "False")).lower() == "true"

    @staticmethod
    def get_log_file_name():
        return ConfigLoader.config[ConfigLoader.get_env()]["get_log_file_name"]

    @staticmethod
    def get_log_file_path():
        return ConfigLoader.config[ConfigLoader.get_env()]["log_file_path"]

    @staticmethod
    def is_continuous():
        return str(ConfigLoader.config[ConfigLoader.get_env()].get("is_continuous", "False")).lower() == "true"

    @staticmethod
    def get_adls_config():
        env_config = ConfigLoader.config[ConfigLoader.get_env()]
        return {
            "account_name": env_config["adls_gen2_account_name"],
            "container_name": env_config["adls_gen2_container_name"],
            "tenant_id": env_config["adls_gen2_tenant_id"],
            "client_id": env_config["adls_gen2_client_id"],
            "client_secret": env_config["adls_gen2_client_secret"]
        }

    @staticmethod
    def get_promoflyer_storage():
        env_config = ConfigLoader.config[ConfigLoader.get_env()]
        return {
            "container": env_config["promoflyer_container_name"],
            "account": env_config["promoflyer_storage_account"]
        }

    @staticmethod
    def get_storage_types():
        env_config = ConfigLoader.config[ConfigLoader.get_env()]
        return {
            "input": env_config["input_storage_type"],
            "output": env_config["output_storage_type"]
        }

    @staticmethod
    def get_output_path():
        return ConfigLoader.config[ConfigLoader.get_env()]["dmle_output_home_path"]

    @staticmethod
    def get_azureml_config():
        env_config = ConfigLoader.config[ConfigLoader.get_env()]
        return {
            "subscription_id": env_config["azureml_subscription_id"],
            "resource_group": env_config["azureml_resource_group"],
            "workspace_name": env_config["azureml_workspace_name"],
            "tenant_id": env_config["azureml_tenant_id"],
            "client_id": env_config["azureml_client_id"],
            "client_secret": env_config["azureml_client_secret"]
        }

    @staticmethod
    def get_token_cis():
        return ConfigLoader.config[ConfigLoader.get_env()]["token_cis"]

    @staticmethod
    def get_db_config():
        env_config = ConfigLoader.config[ConfigLoader.get_env()]
        return {
            "server": env_config["db_server"],
            "port": int(env_config["db_port"]),
            "name": env_config["db_name"],
            "user": env_config["db_user"],
            "password": env_config["db_pass"]
        }
        
