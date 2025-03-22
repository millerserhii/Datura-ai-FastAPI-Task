import json
import logging
import time
import uuid
from typing import Any, Callable, List, Optional

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


logger = logging.getLogger("api.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging request and response details in a single log entry."""

    def __init__(
        self,
        app: Any,
        exclude_paths: Optional[List[str]] = None,
    ):
        super().__init__(app)
        self.exclude_paths = exclude_paths or [
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
        ]

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """Process request and log details in a single entry after completion."""
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
        user_agent = request.headers.get("user-agent", "")

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
            except Exception:
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

            # Log a single entry with all the information
            logger.log(
                log_level,
                f"{method} {path} | "
                f"Status: {response.status_code} | "
                f"Time: {process_time_ms}ms | "
                f"Client: {client_ip} | "
                f"ID: {request_id}{body_info}",
            )

            return response

        except Exception as e:
            # Calculate processing time for failed requests
            process_time = time.time() - start_time
            process_time_ms = round(process_time * 1000, 2)

            # Log exception as a single entry
            logger.exception(
                f"{method} {path} | "
                f"Error: {str(e)} | "
                f"Time: {process_time_ms}ms | "
                f"Client: {client_ip} | "
                f"ID: {request_id}{body_info}"
            )

            # Re-raise to let FastAPI handle the exception
            raise


def setup_request_logging_middleware(
    app: FastAPI,
    exclude_paths: Optional[List[str]] = None,
) -> None:
    """Add request logging middleware to FastAPI app."""
    app.add_middleware(
        RequestLoggingMiddleware,
        exclude_paths=exclude_paths,
    )
