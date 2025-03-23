import json
import logging
import time
import uuid
from collections.abc import Callable
from typing import Any, Optional

from fastapi import FastAPI, Request, Response
from rich.console import Console
from rich.logging import RichHandler
from starlette.middleware.base import BaseHTTPMiddleware


# Set up rich console
console = Console()

# Configure logger with rich handler
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True, console=console)],
)

logger = logging.getLogger("api.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for logging request and
    response details in a single log entry.
    """

    def __init__(
        self,
        app: Any,
        exclude_paths: Optional[list[str]] = None,
    ):
        super().__init__(app)
        self.exclude_paths = exclude_paths or [
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
        ]

    async def dispatch(
        self, request: Request, call_next: Callable[..., Any]
    ) -> Response:
        """
        Process request and log details in
        a single entry after completion.
        """
        # Skip excluded paths
        if any(
            request.url.path.startswith(path) for path in self.exclude_paths
        ):
            return await call_next(request)

        # Generate a unique request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Record start time
        start_time = time.time()

        # Prepare request info
        method = request.method
        path = request.url.path
        client_ip = request.client.host if request.client else None
        request.headers.get("user-agent", "")

        # Process the request and capture body info if needed
        body_info = ""
        if method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                try:
                    # Try to parse as JSON
                    json.loads(body)
                    body_info = " | Body: JSON"
                except json.JSONDecodeError:
                    # If not JSON, log the size only
                    body_info = f" | Body: {len(body)} bytes"

                # Reset the request body
                await request.body()
            except Exception:  # pylint: disable=broad-exception-caught
                body_info = " | Body: [Error reading]"

        try:
            # Process the request
            response = await call_next(request)

            # Calculate processing time
            process_time = time.time() - start_time
            process_time_ms = round(process_time * 1000, 2)

            # Set response headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = str(process_time)

            # Determine log level based on status code
            log_level = (
                logging.ERROR
                if response.status_code >= 500
                else (
                    logging.WARNING
                    if response.status_code >= 400
                    else logging.INFO
                )
            )

            # Define method color
            method_color = (
                "green"
                if method == "GET"
                else (
                    "blue"
                    if method == "POST"
                    else (
                        "yellow"
                        if method in ["PUT", "PATCH"]
                        else "red" if method == "DELETE" else "white"
                    )
                )
            )

            # Define status color
            status_color = (
                "green"
                if response.status_code < 300
                else (
                    "blue"
                    if response.status_code < 400
                    else "yellow" if response.status_code < 500 else "red"
                )
            )

            # Create a more readable message with rich formatting
            message = (
                f"[{method_color}]{method}[/] {path} | "
                f"Status: [{status_color}]{response.status_code}[/] | "
                f"Time: [cyan]{process_time_ms}ms[/] | "
                f"Client: {client_ip} | "
                f"ID: [dim]{request_id}[/]{body_info}"
            )

            # Log with rich formatting
            logger.log(log_level, message)

            return response

        except Exception as e:  # pylint: disable=broad-exception-caught
            # Calculate processing time for failed requests
            process_time = time.time() - start_time
            process_time_ms = round(process_time * 1000, 2)

            # Define method color
            method_color = (
                "green"
                if method == "GET"
                else (
                    "blue"
                    if method == "POST"
                    else (
                        "yellow"
                        if method in ["PUT", "PATCH"]
                        else "red" if method == "DELETE" else "white"
                    )
                )
            )

            # Create error message with rich formatting
            error_message = (
                f"[{method_color}]{method}[/] {path} | "
                f"Error: [red]{str(e)}[/] | "
                f"Time: [cyan]{process_time_ms}ms[/] | "
                f"Client: {client_ip} | "
                f"ID: [dim]{request_id}[/]{body_info}"
            )

            # Log exception with rich formatting
            logger.error(error_message, exc_info=True)

            # Re-raise to let FastAPI handle the exception
            raise


def setup_request_logging_middleware(
    app: FastAPI,
    exclude_paths: Optional[list[str]] = None,
) -> None:
    """Add request logging middleware to FastAPI app."""
    app.add_middleware(
        RequestLoggingMiddleware,
        exclude_paths=exclude_paths,
    )
