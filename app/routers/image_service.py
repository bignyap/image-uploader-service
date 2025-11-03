from fastapi import APIRouter, Depends, UploadFile, File, Form, Query, Response
from fastapi.responses import JSONResponse
from datetime import datetime
from typing import Optional
from io import BytesIO
import logging
from PIL import Image
import xml.etree.ElementTree as ET
from botocore.exceptions import BotoCoreError, ClientError

from app.storage.dynamodb import DynamoDBService
from app.storage.s3 import S3Service
from app.dependencies.dependencies import get_s3_service, get_dynamodb_service
from app.image_service.service import save_image_and_meta, fetch_images, get_image_meta, remove_image
from app.image_service.models import ImageItem, UploadResponse, ListImagesResponse
from app.exceptions import InvalidImageException, ImageNotFoundException, S3UploadException
from app.settings import settings

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/images",
    tags=["image-uploader-service"]
)

# Allowed content types
ALLOWED_IMAGE_TYPES = {
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/svg+xml",
    "image/webp"
}

def validate_image_bytes(file_bytes: bytes, content_type: str) -> str:
    """Validate that the uploaded file is a real image."""
    if content_type in {"image/png", "image/jpeg", "image/gif", "image/webp"}:
        try:
            img = Image.open(BytesIO(file_bytes))
            img.load()
            MIME_MAP = {
                "JPEG": "image/jpeg",
                "PNG": "image/png",
                "GIF": "image/gif",
                "WEBP": "image/webp",
            }
            mime_type = MIME_MAP.get(img.format.upper())
            if mime_type not in ALLOWED_IMAGE_TYPES:
                raise InvalidImageException(f"Unsupported image type: {mime_type}")
            return mime_type
        except Exception:
            raise InvalidImageException("Invalid image file")
    elif content_type == "image/svg+xml":
        try:
            root = ET.fromstring(file_bytes.decode("utf-8"))
            # Check if root tag is svg (with or without namespace)
            tag_name = root.tag.split("}")[-1].lower() if "}" in root.tag else root.tag.lower()
            if tag_name == "svg":
                return "image/svg+xml"
            raise InvalidImageException("Invalid SVG root element")
        except InvalidImageException:
            raise
        except Exception:
            raise InvalidImageException("Invalid SVG file")
    else:
        raise InvalidImageException(f"Unsupported content type: {content_type}")

@router.post("", response_model=UploadResponse, status_code=201)
async def upload_image(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),  # Comma Separated Values
    response: Response = None,
    db: DynamoDBService = Depends(get_dynamodb_service),
    s3: S3Service = Depends(get_s3_service)
):
    """Uploads an image and its metadata with content-type verification."""
    # Add security header
    if response:
        response.headers["X-Content-Type-Options"] = "nosniff"

    # Pre-check content-type
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise InvalidImageException(f"Unsupported content type: {file.content_type}")

    tags_list = [t.strip() for t in tags.split(",")] if tags else []

    contents = await file.read()
    fileobj = BytesIO(contents)

    # Validate actual file content
    content_type = validate_image_bytes(contents, file.content_type)

    image = save_image_and_meta(
        db=db,
        s3=s3,
        fileobj=fileobj,
        filename=file.filename,
        content_type=content_type,
        size=len(contents),
        user_id=user_id,
        title=title,
        description=description,
        tags=tags_list
    )
    return UploadResponse(
        image_id=image.image_id,
        user_id=image.user_id,
        s3_key=image.s3_key,
        filename=image.filename,
        uploaded_at=image.uploaded_at,
    )

@router.get("", response_model=ListImagesResponse)
def list_images_handler(
    user_id: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    exclusive_start_key: Optional[str] = Query(None),
    db: DynamoDBService = Depends(get_dynamodb_service)
):
    """Lists images with optional filters."""
    eks = None
    if exclusive_start_key:
        import json
        try:
            eks = json.loads(exclusive_start_key)
        except Exception:
            raise InvalidImageException("invalid exclusive_start_key")

    resp = fetch_images(db=db, user_id=user_id, tag=tag, limit=limit, exclusive_start_key=eks)
    items = resp.get("Items", [])

    def to_item(it):
        return ImageItem(
            image_id=it["image_id"],
            user_id=it["user_id"],
            title=it.get("title"),
            description=it.get("description"),
            tags=it.get("tags", []),
            filename=it.get("filename"),
            content_type=it.get("content_type"),
            size=int(it.get("size", 0)),
            s3_key=it["s3_key"],
            uploaded_at=datetime.fromisoformat(it["uploaded_at"]),
        )

    images = [to_item(it) for it in items]
    next_token = resp.get("LastEvaluatedKey")

    import json
    return ListImagesResponse(images=images, next_token=json.dumps(next_token) if next_token else None)

@router.get("/{image_id}", response_model=ImageItem)
def get_image(
    image_id: str,
    db: DynamoDBService = Depends(get_dynamodb_service),
    s3: S3Service = Depends(get_s3_service)
):
    """Gets image metadata."""
    meta = get_image_meta(db, image_id)
    if not meta:
        raise ImageNotFoundException(image_id)

    return ImageItem(
        image_id=meta["image_id"],
        user_id=meta["user_id"],
        title=meta.get("title"),
        description=meta.get("description"),
        tags=meta.get("tags", []),
        filename=meta["filename"],
        content_type=meta["content_type"],
        size=int(meta.get("size", 0)),
        s3_key=meta["s3_key"],
        uploaded_at=datetime.fromisoformat(meta["uploaded_at"]),
    )

@router.get("/{image_id}/download", response_model=dict)
def get_presigned_url(
    image_id: str,
    expires_in: Optional[int] = Query(None, ge=60, le=86400, description="Expiration time in seconds (60-86400)"),
    db: DynamoDBService = Depends(get_dynamodb_service),
    s3: S3Service = Depends(get_s3_service)
):
    """
    Generates a presigned URL for downloading an image.

    The URL is valid for a limited time (default 15 minutes, max 24 hours).
    Users can download the image directly from S3 using this URL without AWS credentials.
    """
    # Verify image exists
    meta = get_image_meta(db, image_id)
    if not meta:
        raise ImageNotFoundException(image_id)

    s3_key = meta.get("s3_key")
    if not s3_key:
        raise InvalidImageException("Image S3 key not found")

    try:
        presigned_url = s3.generate_presigned_url(s3_key, expires_in=expires_in)
        return {
            "image_id": image_id,
            "download_url": presigned_url,
            "expires_in": expires_in or settings.presign_expire_seconds
        }
    except (BotoCoreError, ClientError) as e:
        log.error(f"Failed to generate presigned URL: {e}")
        raise S3UploadException(f"Failed to generate download URL: {e}")

@router.delete("/{image_id}", status_code=204)
def delete_image(
    image_id: str,
    db: DynamoDBService = Depends(get_dynamodb_service),
    s3: S3Service = Depends(get_s3_service)
):
    """Deletes an image and its metadata."""
    remove_image(db, s3, image_id)
    return JSONResponse(status_code=204, content=None)
