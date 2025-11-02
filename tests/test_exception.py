import pytest
import json
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from app import exceptions


@pytest.mark.asyncio
async def test_api_exception_handler():
    exc = exceptions.ImageNotFoundException("123")
    request = Request(scope={"type": "http"})
    response: JSONResponse = await exceptions.api_exception_handler(request, exc)

    assert response.status_code == 404
    # JSONResponse body is bytes, need to decode and parse
    body = json.loads(response.body.decode())
    assert body == {"detail": "Image with ID '123' not found."}


@pytest.mark.asyncio
async def test_http_exception_handler():
    exc = HTTPException(status_code=403, detail="Forbidden")
    request = Request(scope={"type": "http"})
    response: JSONResponse = await exceptions.http_exception_handler(request, exc)

    assert response.status_code == 403
    body = json.loads(response.body.decode())
    assert body == {"detail": "Forbidden"}


@pytest.mark.asyncio
async def test_generic_exception_handler():
    exc = ValueError("Something went wrong")
    request = Request(scope={"type": "http"})
    response: JSONResponse = await exceptions.generic_exception_handler(request, exc)

    assert response.status_code == 500
    body = json.loads(response.body.decode())
    assert body == {"detail": "An unexpected error occurred."}


def test_custom_exceptions_inherit_api_exception():
    exc = exceptions.InvalidImageException("Bad format")
    assert isinstance(exc, exceptions.APIException)
    assert exc.status_code == 400
    assert "Bad format" in str(exc)
