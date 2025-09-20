import pytest
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from app import exceptions


@pytest.mark.asyncio
async def test_api_exception_handler(monkeypatch):
    exc = exceptions.ImageNotFoundException("123")
    request = Request(scope={"type": "http"})
    response: JSONResponse = await exceptions.api_exception_handler(request, exc)

    assert response.status_code == 404
    assert response.json() == {"detail": "Image with ID '123' not found."}


@pytest.mark.asyncio
async def test_http_exception_handler():
    exc = HTTPException(status_code=403, detail="Forbidden")
    request = Request(scope={"type": "http"})
    response: JSONResponse = await exceptions.http_exception_handler(request, exc)

    assert response.status_code == 403
    assert response.json() == {"detail": "Forbidden"}


@pytest.mark.asyncio
async def test_generic_exception_handler():
    exc = ValueError("Something went wrong")
    request = Request(scope={"type": "http"})
    response: JSONResponse = await exceptions.generic_exception_handler(request, exc)

    assert response.status_code == 500
    assert response.json() == {"detail": "An unexpected error occurred."}


def test_custom_exceptions_inherit_api_exception():
    exc = exceptions.InvalidImageException("Bad format")
    assert isinstance(exc, exceptions.APIException)
    assert exc.status_code == 400
    assert "Bad format" in str(exc)
