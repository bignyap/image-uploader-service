import io
import pytest
from PIL import Image

from app.image_service import service
from app.exceptions import InvalidImageException, ImageNotFoundException


def make_png_bytes():
    """Generate a simple valid PNG in-memory."""
    img = Image.new("RGB", (10, 10), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ------------------------------
# validate_image_bytes
# ------------------------------

def test_validate_png_bytes_ok():
    data = make_png_bytes()
    result = service.validate_image_bytes(data, "image/png")
    assert result == "image/png"


def test_validate_invalid_bytes_raises():
    with pytest.raises(InvalidImageException):
        service.validate_image_bytes(b"notanimage", "image/png")


def test_validate_svg_ok():
    svg_data = b'<svg xmlns="http://www.w3.org/2000/svg"></svg>'
    result = service.validate_image_bytes(svg_data, "image/svg+xml")
    assert result == "image/svg+xml"


def test_validate_svg_invalid_root():
    bad_svg = b'<not_svg></not_svg>'
    with pytest.raises(InvalidImageException):
        service.validate_image_bytes(bad_svg, "image/svg+xml")


def test_validate_unsupported_type():
    with pytest.raises(InvalidImageException):
        service.validate_image_bytes(b"fake", "application/pdf")


# ------------------------------
# save_image_and_meta
# ------------------------------

def test_save_image_and_meta_success(mocker):
    mock_db = mocker.Mock()
    mock_s3 = mocker.Mock()
    mock_db.put_metadata.return_value = {}
    mock_s3.upload.return_value = True

    fileobj = io.BytesIO(b"12345")
    image = service.save_image_and_meta(
        db=mock_db,
        s3=mock_s3,
        fileobj=fileobj,
        filename="test.png",
        content_type="image/png",
        size=5,
        user_id="user1",
        title="Test",
        description="Desc",
        tags=["tag1"]
    )

    assert image.user_id == "user1"
    assert image.s3_key.endswith("test.png")
    mock_s3.upload.assert_called_once()
    mock_db.put_metadata.assert_called_once()


def test_save_image_and_meta_s3_error(mocker):
    mock_db = mocker.Mock()
    mock_s3 = mocker.Mock()
    mock_s3.upload.side_effect = Exception("upload fail")

    with pytest.raises(Exception):
        service.save_image_and_meta(
            db=mock_db,
            s3=mock_s3,
            fileobj=io.BytesIO(b"x"),
            filename="f.png",
            content_type="image/png",
            size=1,
            user_id="u",
            title=None,
            description=None,
            tags=[]
        )


# ------------------------------
# fetch_images
# ------------------------------

def test_fetch_images_with_tag(mocker):
    mock_db = mocker.Mock()
    table_mock = mocker.Mock()
    table_mock.scan.return_value = {"Items": [{"image_id": "1"}]}
    mock_db.resource.Table.return_value = table_mock

    resp = service.fetch_images(mock_db, user_id="u1", tag="tag1", limit=10)
    assert resp["Items"][0]["image_id"] == "1"


def test_fetch_images_without_tag(mocker):
    mock_db = mocker.Mock()
    mock_db.scan_metadata.return_value = {"Items": [{"image_id": "2"}]}
    resp = service.fetch_images(mock_db, user_id="u2", limit=5)
    assert resp["Items"][0]["image_id"] == "2"


# ------------------------------
# get_image_meta
# ------------------------------

def test_get_image_meta_found(mocker):
    mock_db = mocker.Mock()
    mock_db.get_metadata.return_value = {"image_id": "abc"}
    result = service.get_image_meta(mock_db, "abc")
    assert result["image_id"] == "abc"


def test_get_image_meta_not_found(mocker):
    mock_db = mocker.Mock()
    mock_db.get_metadata.return_value = None
    with pytest.raises(ImageNotFoundException):
        service.get_image_meta(mock_db, "nope")


# ------------------------------
# remove_image
# ------------------------------

def test_remove_image_success(mocker):
    mock_db = mocker.Mock()
    mock_s3 = mocker.Mock()
    mock_db.get_metadata.return_value = {"image_id": "1", "s3_key": "k"}
    result = service.remove_image(mock_db, mock_s3, "1")
    assert result is True
    mock_s3.delete_from_s3.assert_called_once()
    mock_db.delete_metadata.assert_called_once()


def test_remove_image_not_found(mocker):
    mock_db = mocker.Mock()
    mock_s3 = mocker.Mock()
    mock_db.get_metadata.return_value = None
    with pytest.raises(ImageNotFoundException):
        service.remove_image(mock_db, mock_s3, "doesnotexist")