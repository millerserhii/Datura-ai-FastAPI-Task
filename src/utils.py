import logging
from typing import Any, Optional


logger = logging.getLogger(__name__)


def format_error_response(
    status_code: int,
    message: str,
    code: str = "error",
    details: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Format error response."""
    response = {
        "status_code": status_code,
        "message": message,
        "code": code,
    }

    if details:
        response["details"] = details

    return response
