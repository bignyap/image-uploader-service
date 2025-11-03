import io
from PIL import Image


def make_png_bytes():
    img = Image.new("RGB", (10, 10), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ------------------------------
# /images [POST]
# ------------------------------

def test_upload_image_success(test_client):
    data = make_png_bytes()
    files = {"file": ("f.png", data, "image/png")}
    resp = test_client.post(
        "/images",
        data={"user_id": "u1", "title": "MyPic"},
        files=files,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "image_id" in body
    assert body["user_id"] == "u1"


def test_upload_invalid_file_type(test_client):
    files = {"file": ("f.txt", b"notimg", "text/plain")}
    resp = test_client.post("/images", data={"user_id": "u1"}, files=files)
    assert resp.status_code == 400


# ------------------------------
# /images/{id} [GET + DELETE]
# ------------------------------

def test_get_and_delete_image(test_client):
    # upload first
    data = make_png_bytes()
    files = {"file": ("g.png", data, "image/png")}
    upload = test_client.post("/images", data={"user_id": "u2"}, files=files)
    img_id = upload.json()["image_id"]

    # fetch
    resp = test_client.get(f"/images/{img_id}")
    assert resp.status_code == 200
    assert resp.json()["image_id"] == img_id

    # delete
    delete = test_client.delete(f"/images/{img_id}")
    assert delete.status_code == 204


def test_get_nonexistent_image(test_client):
    resp = test_client.get("/images/nope")
    assert resp.status_code == 404


def test_delete_nonexistent_image(test_client):
    resp = test_client.delete("/images/nope")
    assert resp.status_code == 404


# ------------------------------
# /images [GET list]
# ------------------------------

def test_list_images(test_client):
    # upload 2 images
    data = make_png_bytes()
    files = {"file": ("a.png", data, "image/png")}
    test_client.post("/images", data={"user_id": "list1"}, files=files)
    test_client.post("/images", data={"user_id": "list1"}, files=files)

    resp = test_client.get("/images", params={"user_id": "list1"})
    assert resp.status_code == 200
    body = resp.json()
    assert "images" in body
    assert len(body["images"]) >= 2


# ------------------------------
# /images/{id}/download [GET presigned URL]
# ------------------------------

def test_get_presigned_url(test_client):
    # upload an image first
    data = make_png_bytes()
    files = {"file": ("download.png", data, "image/png")}
    upload = test_client.post("/images", data={"user_id": "u3"}, files=files)
    img_id = upload.json()["image_id"]

    # get presigned URL
    resp = test_client.get(f"/images/{img_id}/download")
    assert resp.status_code == 200
    body = resp.json()
    assert "download_url" in body
    assert "image_id" in body
    assert body["image_id"] == img_id
    assert "expires_in" in body
    # Presigned URL should contain S3 bucket and key
    assert "image-service-bucket" in body["download_url"]


def test_get_presigned_url_with_custom_expiry(test_client):
    # upload an image first
    data = make_png_bytes()
    files = {"file": ("download.png", data, "image/png")}
    upload = test_client.post("/images", data={"user_id": "u4"}, files=files)
    img_id = upload.json()["image_id"]

    # get presigned URL with custom expiry (3600 seconds = 1 hour)
    resp = test_client.get(f"/images/{img_id}/download", params={"expires_in": 3600})
    assert resp.status_code == 200
    body = resp.json()
    assert body["expires_in"] == 3600


def test_get_presigned_url_nonexistent_image(test_client):
    resp = test_client.get("/images/nonexistent/download")
    assert resp.status_code == 404


def test_get_presigned_url_invalid_expiry(test_client):
    # upload an image first
    data = make_png_bytes()
    files = {"file": ("download.png", data, "image/png")}
    upload = test_client.post("/images", data={"user_id": "u5"}, files=files)
    img_id = upload.json()["image_id"]

    # try with expiry too short (less than 60 seconds)
    resp = test_client.get(f"/images/{img_id}/download", params={"expires_in": 30})
    assert resp.status_code == 422  # Validation error

    # try with expiry too long (more than 86400 seconds)
    resp = test_client.get(f"/images/{img_id}/download", params={"expires_in": 100000})
    assert resp.status_code == 422  # Validation error
