"""
    Centralized exception handling for the FastAPI application.
"""
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import logging

log = logging.getLogger(__name__)

class APIException(Exception):
    """Base class for API exceptions."""
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(self.detail)

class ImageNotFoundException(APIException):
    """Exception for when an image is not found."""
    def __init__(self, image_id: str):
        super().__init__(status_code=404, detail=f"Image with ID '{image_id}' not found.")

class InvalidImageException(APIException):
    """Exception for invalid image files."""
    def __init__(self, detail: str):
        super().__init__(status_code=400, detail=detail)

class S3UploadException(APIException):
    """Exception for S3 upload failures."""
    def __init__(self, detail: str):
        super().__init__(status_code=500, detail=detail)

class DynamoDBException(APIException):
    """Exception for DynamoDB failures."""
    def __init__(self, detail: str):
        super().__init__(status_code=500, detail=detail)

async def api_exception_handler(request: Request, exc: APIException):
    """Handles API exceptions."""
    log.error(f"API Exception: {exc.detail}", exc_info=exc)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

async def http_exception_handler(request: Request, exc: HTTPException):
    """Handles FastAPI HTTP exceptions."""
    log.error(f"HTTP Exception: {exc.detail}", exc_info=exc)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

async def generic_exception_handler(request: Request, exc: Exception):
    """Handles all other exceptions."""
    log.error(f"Unhandled Exception: {str(exc)}", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred."},
    )

def add_exception_handlers(app):
    """Adds exception handlers to the FastAPI app."""
    app.add_exception_handler(APIException, api_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
