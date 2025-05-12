import os
import logging
from dmle_promoflyers_metrics_worker.config import Config

logger = logging.getLogger(__name__)

def get_database_uri():
    """
    Get the database URI from the environment variables.
    """
    logger.info("No DB URI provided. Using environment variables.")
    db_server = Config.get_db_server()
    db_name = Config.get_db_name()
    db_user = Config.get_db_user()
    db_password = Config.get_db_pass()
    db_port = Config.get_db_port()
    return f"postgresql://{db_user}:{db_password}@{db_server}:{db_port}/{db_name}"
