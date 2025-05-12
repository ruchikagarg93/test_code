"""
config module is used to get all the config related to the CDAR PanelModernization worker.
"""

from os import environ
from wrapper_worker.config import Config as BasicConfig


class Config(BasicConfig):
    """
    Config class is used to get all the config values related to the Consumer worker.
    """

    @staticmethod
    def adls_gen2_account_name():
        """
        adls_gen2_account_name method is used to get the
             adls gen2 account name from the configuration.

        :return: adls gen2 account name
        """
        return Config.config[Config.get_env()]["adls_gen2_account_name"]

    @staticmethod
    def adls_gen2_container_name():
        """
        adls_gen2_container_name method is used to
            get the adls gen2 container name from the configuration.

        :return: adls gen2 container name
        """
        return Config.config[Config.get_env()]["adls_gen2_container_name"]

    @staticmethod
    def adls_gen2_tenant_id():
        """
        adls_gen2_tenant_id method is used to get the adls gen2 tenant id from the configuration.

        :return: adls gen2 tenant id
        """
        return Config.config[Config.get_env()]["adls_gen2_tenant_id"]

    @staticmethod
    def adls_gen2_client_id():
        """
        adls_gen2_client_id method is used to get the adls gen2 client id from the configuration.

        :return: adls gen2 client id
        """
        return Config.config[Config.get_env()]["adls_gen2_client_id"]

    @staticmethod
    def adls_gen2_client_secret():
        """
        adls_gen2_client_secret method is used to
            get the adls gen2 client secret from the configuration.

        :return: adls gen2 client secret
        """
        return Config.config[Config.get_env()]["adls_gen2_client_secret"]

    @staticmethod
    def input_storage_type():
        """
        input_storage_type method is used to get the input storage type from the configuration.

        :return: input stoarage type
        """
        return Config.config[Config.get_env()]["input_storage_type"]

    @staticmethod
    def output_storage_type():
        """
        output_storage_type method is used to get the output storage type from the configuration.

        :return: output stoarage type
        """
        return Config.config[Config.get_env()]["output_storage_type"]

    @staticmethod
    def get_dmle_output_home_path():
        """
        get_dmle_output_home_path method is used to get the output home path.

        :return: output home
        """
        return Config.config[Config.get_env()]["dmle_output_home_path"]

    @staticmethod
    def get_azureml_subscription_id():
        """
        azureml_subscription_id method is used to get the output home path.

        :return: output home
        """
        return Config.config[Config.get_env()]["azureml_subscription_id"]

    @staticmethod
    def get_azureml_resource_group():
        """
        azureml_resource_group method is used to get the output home path.

        :return: output home
        """
        return Config.config[Config.get_env()]["azureml_resource_group"]

    @staticmethod
    def get_azureml_workspace_name():
        """
        azureml_workspace_name method is used to get the output home path.

        :return: output home
        """
        return Config.config[Config.get_env()]["azureml_workspace_name"]

    @staticmethod
    def get_azureml_tenant_id():
        """
        azureml_workspace_name method is used to get the output home path.

        :return: output home
        """
        return Config.config[Config.get_env()]["azureml_tenant_id"]

    @staticmethod
    def get_azureml_service_principal_id():
        """
        azureml_workspace_name method is used to get the output home path.

        :return: output home
        """
        return Config.config[Config.get_env()]["azureml_client_id"]

    @staticmethod
    def get_azureml_service_principal_secret():
        """
        azureml_workspace_name method is used to get the output home path.

        :return: output home
        """
        return Config.config[Config.get_env()]["azureml_client_secret"]

    @staticmethod
    def get_default_model_id():
        """
        Gets azureml_pipeline_name value from the config
        :return: Azure ML sirval training pipeline
        """
        env_var = environ.get("default_model_id")
        if env_var is None:
            return Config.config[Config.get_env()]["default_model_id"]
        return env_var

    @staticmethod
    def get_storage_account():
        """
        get_storage_account method is used to get the save the promoflyer files..

        :return: output stoarage type
        """
        return Config.config[Config.get_env()]["promoflyer_storage_account"]

    @staticmethod
    def get_container_name():
        """
        get_container_name method is used to get the save the promoflyer files.

        :return: output stoarage type
        """
        return Config.config[Config.get_env()]["promoflyer_container_name"]

    @staticmethod
    def get_token_cis():
        return Config.config[Config.get_env()]["token_cis"]

    @staticmethod
    def get_db_server():
        return Config.config[Config.get_env()]["db_server"]
    
    @staticmethod
    def get_db_port():
        return Config.config[Config.get_env()]["db_port"]
    
    @staticmethod
    def get_db_user():
        return Config.config[Config.get_env()]["db_user"]
    
    @staticmethod
    def get_db_name():
        return Config.config[Config.get_env()]["db_name"]
    
    @staticmethod
    def get_db_pass():
        return Config.config[Config.get_env()]["db_pass"]
