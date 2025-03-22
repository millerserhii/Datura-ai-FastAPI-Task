from fastapi import HTTPException, status


class CustomException(HTTPException):
    """Base class for custom exceptions."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        code: str = "error",
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.code = code


class AuthenticationError(CustomException):
    """Raised when authentication fails."""

    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            code="authentication_error",
        )


class NotFoundError(CustomException):
    """Raised when a resource is not found."""

    def __init__(self, detail: str = "Resource not found"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
            code="not_found",
        )


class BlockchainError(CustomException):
    """Raised when there's an error with blockchain operations."""

    def __init__(self, detail: str = "Blockchain operation failed"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
            code="blockchain_error",
        )


class ExternalAPIError(CustomException):
    """Raised when there's an error with external API calls."""

    def __init__(self, detail: str = "External API call failed"):
        super().__init__(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail,
            code="external_api_error",
        )
