"""
start is the module which is used to start the CDAR PanelModernization worker.
"""

import sys
import json
import traceback
from wrapper_worker.core.logger_utils import LoggerUtils
from wrapper_worker.receiver import start_process
from .worker import MetricsWorker


def begin_process():
    """
    begin_process method is used start the main process.
    It will call the wrapper start_process and it will pass the Sample worke class as a paramater.
    Sample Worker class has to extend Base Worker form the wrapper worker or else it will error out.
    """
    try:
        return start_process(MetricsWorker)
    except Exception:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        LoggerUtils.get_logger().log(
            level="Error",
            request_id="0000",
            event_type="NA_NA_RESPONSE",
            message=exc_value,
            extended_message=json.dumps(
                {
                    "trace_back": "The main program encountered a fatal error, please check the stack trace below :"
                    + f"{traceback.format_exception(exc_type, exc_value, exc_traceback, chain=True)}"
                }
            ),
        )
        return False
