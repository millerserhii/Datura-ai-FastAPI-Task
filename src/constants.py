"""
Global constants for the application.
"""


class CacheKeys:
    """
    Cache key prefixes
    """

    TAO_DIVIDENDS = "tao_dividends:{netuid}:{hotkey}"
    SENTIMENT_ANALYSIS = "sentiment_analysis:{netuid}"


class ErrorCode:
    """
    Error codes
    """

    AUTHENTICATION_ERROR = "authentication_error"
    BLOCKCHAIN_ERROR = "blockchain_error"
    NOT_FOUND = "not_found"
    EXTERNAL_API_ERROR = "external_api_error"
    VALIDATION_ERROR = "validation_error"
