from typing import Literal

from helpshift.monitoring import sensu

from peekguard.utils.logger import get_logger

logger = get_logger(__name__)

TEAM_KEY = "mle"


def send_alert(
    status: Literal["warning", "critical"],
    message: str,
    name: str = "peekguard",
) -> None:
    """Send sensu alert with given message and status

    Args:
        status (str): should be one of [warning, critical]
        message (str): "alert message string"
        name (str, optional):
            - Name should represent the component for which alter needs to be triggered. Defaults to "peekguard".
            - This will be used as the name of the alert in sensu and all the alerts for this will be combined under this name.
            - Examples:
              * yugabyte_query_failed
              * elastic_search_query_failed
    """
    sensu_status = {
        "warning": sensu.WARNING,
        "critical": sensu.CRITICAL,
    }
    try:
        sensu.send_alert(
            status=sensu_status[status],
            message=f"{message}\n",
            name=name,
            team_key=TEAM_KEY,
        )
    except Exception:
        logger.exception("[peekguard] Unable to send sensu alert", exc_info=True)
