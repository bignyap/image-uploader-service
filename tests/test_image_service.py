from fastapi.testclient import TestClient
from moto import mock_aws
import pytest
from app.main import app
import os
from io import BytesIO

# Test for successful image upload
def test_upload_image_success(test_client: TestClient):
    # Given
    user_id = "test-user"
    title = "Test Title"
    description = "Test Description"
    tags = "tag1,tag2"
    file_content = b"test image data"
    file = ("test.jpg", BytesIO(file_content), "image/jpeg")

    # When
    response = test_client.post(
        "/images",
        data={"user_id": user_id, "title": title, "description": description, "tags": tags},
        files={"file": file},
    )

    # Then
    assert response.status_code == 201
    data = response.json()
    assert "image_id" in data
    assert "s3_key" in data
    assert data["filename"] == "test.jpg"

# Test for uploading a file with no tags
def test_upload_image_no_tags(test_client: TestClient):
    # Given
    user_id = "test-user"
    file_content = b"test image data"
    file = ("test.jpg", BytesIO(file_content), "image/jpeg")

    # When
    response = test_client.post(
        "/images",
        data={"user_id": user_id},
        files={"file": file},
    )

    # Then
    assert response.status_code == 201
    data = response.json()
    assert "image_id" in data

# Test for uploading a file with empty tags
def test_upload_image_empty_tags(test_client: TestClient):
    # Given
    user_id = "test-user"
    tags = ""
    file_content = b"test image data"
    file = ("test.jpg", BytesIO(file_content), "image/jpeg")

    # When
    response = test_client.post(
        "/images",
        data={"user_id": user_id, "tags": tags},
        files={"file": file},
    )

    # Then
    assert response.status_code == 201
    data = response.json()
    assert "image_id" in data

# Test for missing user_id
def test_upload_image_missing_user_id(test_client: TestClient):
    # Given
    file_content = b"test image data"
    file = ("test.jpg", BytesIO(file_content), "image/jpeg")

    # When
    response = test_client.post(
        "/images",
        files={"file": file},
    )

    # Then
    assert response.status_code == 422  # Unprocessable Entity

# Test for listing images
def test_list_images(test_client: TestClient):
    # Given
    # Upload a couple of images first
    test_client.post("/images", data={"user_id": "user1"}, files={"file": ("test1.jpg", b"content1", "image/jpeg")})
    test_client.post("/images", data={"user_id": "user2"}, files={"file": ("test2.jpg", b"content2", "image/jpeg")})

    # When
    response = test_client.get("/images")

    # Then
    assert response.status_code == 200
    data = response.json()
    assert "images" in data
    assert len(data["images"]) == 2

# Test for listing images with user_id filter
def test_list_images_by_user(test_client: TestClient):
    # Given
    test_client.post("/images", data={"user_id": "user1"}, files={"file": ("test1.jpg", b"content1", "image/jpeg")})
    test_client.post("/images", data={"user_id": "user2"}, files={"file": ("test2.jpg", b"content2", "image/jpeg")})

    # When
    response = test_client.get("/images?user_id=user1")

    # Then
    assert response.status_code == 200
    data = response.json()
    assert len(data["images"]) == 1
    assert data["images"][0]["user_id"] == "user1"

# Test for listing images with tag filter
def test_list_images_by_tag(test_client: TestClient):
    # Given
    test_client.post("/images", data={"user_id": "user1", "tags": "cat,cute"}, files={"file": ("cat.jpg", b"content", "image/jpeg")})
    test_client.post("/images", data={"user_id": "user2", "tags": "dog,cute"}, files={"file": ("dog.jpg", b"content", "image/jpeg")})

    # When
    response = test_client.get("/images?tag=cat")

    # Then
    assert response.status_code == 200
    data = response.json()
    assert len(data["images"]) == 1
    assert "cat" in data["images"][0]["tags"]

# Test for getting an image
def test_get_image(test_client: TestClient):
    # Given
    response = test_client.post("/images", data={"user_id": "user1"}, files={"file": ("test.jpg", b"content", "image/jpeg")})
    image_id = response.json()["image_id"]

    # When
    response = test_client.get(f"/images/{image_id}", allow_redirects=False)

    # Then
    assert response.status_code == 307  # Temporary Redirect
    assert "Location" in response.headers

# Test for getting a non-existent image
def test_get_non_existent_image(test_client: TestClient):
    # When
    response = test_client.get("/images/non-existent-id")

    # Then
    assert response.status_code == 404
    assert response.json() == {"detail": "Image with ID 'non-existent-id' not found."}

# Test for deleting an image
def test_delete_image(test_client: TestClient):
    # Given
    response = test_client.post("/images", data={"user_id": "user1"}, files={"file": ("test.jpg", b"content", "image/jpeg")})
    image_id = response.json()["image_id"]

    # When
    response = test_client.delete(f"/images/{image_id}")

    # Then
    assert response.status_code == 204

    # Verify that the image is gone
    response = test_client.get(f"/images/{image_id}")
    assert response.status_code == 404

# Test for deleting a non-existent image
def test_delete_non_existent_image(test_client: TestClient):
    # When
    response = test_client.delete("/images/non-existent-id")

    # Then
    assert response.status_code == 404
    assert response.json() == {"detail": "Image with ID 'non-existent-id' not found."}

# Test for uploading an invalid image file
def test_upload_invalid_image(test_client: TestClient):
    # Given
    user_id = "test-user"
    file_content = b"this is not an image"
    file = ("test.jpg", BytesIO(file_content), "image/jpeg")

    # When
    response = test_client.post(
        "/images",
        data={"user_id": user_id},
        files={"file": file},
    )

    # Then
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid image file"}

# Test for uploading a file with an unsupported content type
def test_upload_unsupported_content_type(test_client: TestClient):
    # Given
    user_id = "test-user"
    file_content = b"test image data"
    file = ("test.txt", BytesIO(file_content), "text/plain")

    # When
    response = test_client.post(
        "/images",
        data={"user_id": user_id},
        files={"file": file},
    )

    # Then
    assert response.status_code == 400
    assert response.json() == {"detail": "Unsupported content type: text/plain"}

# Test for invalid exclusive_start_key
def test_list_images_invalid_exclusive_start_key(test_client: TestClient):
    # When
    response = test_client.get("/images?exclusive_start_key=invalid-json")

    # Then
    assert response.status_code == 400
    assert response.json() == {"detail": "invalid exclusive_start_key"}