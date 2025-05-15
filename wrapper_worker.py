"""Config module is to read all the config value(s)."""
from os import path, getcwd, environ
import os
import sys
import yaml
import glob


def find_resource(relative_path) -> str:
    """
    find_resource is used to find a resource file
    :param relative_path: name of the file
    :return: file location if found
    """
    dirs = [
        f"{environ.get('CONFIG_PATH','')}",
        sys.prefix,
        "src/**/resources",
        "../**/../**/resources",
        "../../**/resources",
        f"{getcwd()}/../resources",
        f"{getcwd()}/../../resources",
        f"{getcwd()}/../../src/**/resources",
        f"{getcwd()}/resources",
        f"{getcwd()}/../src/**/resources",
        f"{getcwd()}/src/**/resources",
    ]
    found_in = [
        glob.glob(path.join(d, relative_path))[0]
        for d in dirs
        if glob.glob(path.join(d, relative_path))
    ]
    if found_in:
        return found_in[0]
    raise FileNotFoundError(f"Resource not found - {relative_path}")


class Config:
    """Config class is to read all the config values."""

    with open(find_resource("config.yaml")) as f:
        config = yaml.load(f, Loader=yaml.FullLoader)

    @staticmethod
    def get_env():
        """
        get_env method is to read the env values in the app is running.
        :return: current env
        """
        return Config.config["ENV"]

    @staticmethod
    def get_redis_cache_host():
        """get_redis_cache_host method is to read the redis host.

        :return: redis host
        """
        return Config.config[Config.get_env()]["redis_cache_host"]

    @staticmethod
    def get_redis_cache_port():
        """get_redis_cache_port method is to read the redis port.

        :return: redis port
        """
        return Config.config[Config.get_env()]["redis_cache_port"]

    @staticmethod
    def get_redis_cache_password():
        """get_redis_cache_password method is to read the redis password.

        :return: redis password
        """
        return Config.config[Config.get_env()]["redis_cache_password"]

    @staticmethod
    def get_redis_queue_host():
        """get_redis_queue_host method is to read the redis host.

        :return: redis host
        """
        return Config.config[Config.get_env()]["redis_queue_host"]

    @staticmethod
    def get_redis_queue_port():
        """get_redis_queue_port method is to read the redis port.

        :return: redis port
        """
        return Config.config[Config.get_env()]["redis_queue_port"]

    @staticmethod
    def get_redis_queue_password():
        """get_redis_queue_password method is to read the redis password.

        :return: redis password
        """
        return Config.config[Config.get_env()]["redis_queue_password"]

    @staticmethod
    def get_redis_metadata_host():
        """get_redis_metadata_host method is to read the redis host.

        :return: redis host
        """
        return Config.config[Config.get_env()]["redis_metadata_host"]

    @staticmethod
    def get_redis_metadata_port():
        """get_redis_metadata_port method is to read the redis port.

        :return: redis port
        """
        return Config.config[Config.get_env()]["redis_metadata_port"]

    @staticmethod
    def get_redis_metadata_password():
        """get_redis_queue_password method is to read the redis password.

        :return: redis password
        """
        return Config.config[Config.get_env()]["redis_metadata_password"]

    @staticmethod
    def get_redis_queue_name():
        """
        get_redis_queue_name method is used to get redis queue name.
        :return: reis queue
        """
        return Config.config[Config.get_env()]["redis_queue_name"]

    @staticmethod
    def get_redis_queue_visible_time():
        """
        get_redis_queue_time_out method is used to get redis queue timeout
        :return:
        """
        return Config.config[Config.get_env()]["redis_queue_time_out"]

    @staticmethod
    def get_component_name():
        """
        get_component_name method is to read the component name
        :return: component name
        """
        return Config.config[Config.get_env()]["component_name"]

    @staticmethod
    def get_log_to_console():
        """
        get_log_to_console method is indicate do we need to log to console
        :return: True if need to log to console else False
        """
        value = Config.config[Config.get_env()]["log_to_console"]
        return value == "True"

    @staticmethod
    def get_log_to_file():
        """
        get_log_to_file method is indicate do we need to log to file
        :return: True if need to log to file else False
        """
        value = Config.config[Config.get_env()]["log_to_file"]
        return value == "True"

    @staticmethod
    def get_characteristics():
        """get_characteristics is used to get the current
        characteristics that the worker should work on.

        :return: characteristics name
        """
        return Config.config[Config.get_env()]["characteristics"]

    @staticmethod
    def get_log_file_path():
        """get_registry_password method is to read the redis host.

        :return: redis host
        """
        return Config.config[Config.get_env()]["log_file_path"]

    @staticmethod
    def get_queue_component():
        """
        get the queue component name which is currently implemented.
        :return: queue component name
        """
        return Config.config[Config.get_env()]["queue_component"]

    @staticmethod
    def is_continuous():
        """
        to check do we need to listen the queue always or not
        : return : True or False
        """
        return Config.config[Config.get_env()]["is_continuous"]

    @staticmethod
    def client():
        """
        to check do we need to listen the queue always or not
        : return : True or False
        """
        return Config.config[Config.get_env()]["client"]

    @staticmethod
    def get_log_file_name():
        """
        Log file name to write logs
        : return : log file name
        """
        return Config.config[Config.get_env()]["get_log_file_name"]

    @staticmethod
    def get_redis_queue_wait() -> float:
        """
        get the wait time before retry to read message form queue by default 0.5 seconds
        : return : wait time in float
        """
        try:
            return float(Config.config[Config.get_env()]["redis_queue_wait_time"])
        except:
            return 1

    @staticmethod
    def get_redis_cache_timeout() -> int:
        """
        get the wait time before retry to read message form queue by default 0.5 seconds
        : return : wait time in float
        """
        try:
            return int(Config.config[Config.get_env()]["redis_cache_timeout"])
        except:
            return 3024000
