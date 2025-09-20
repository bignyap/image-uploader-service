from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query, Response
from fastapi.responses import RedirectResponse, JSONResponse
from datetime import datetime
from typing import Optional
from io import BytesIO
import logging
from PIL import Image
import xml.etree.ElementTree as ET

from app.storage.dynamodb import DynamoDBService
from app.storage.s3 import S3Service
from app.dependencies.dependencies import get_s3_service, get_dynamodb_service
from app.image_service.service import save_image_and_meta, fetch_images, get_image_meta, remove_image
from app.image_service.models import ImageItem, UploadResponse, ListImagesResponse

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
    """
    Validate that the uploaded file is a real image.
    - For raster images: Pillow verify()
    - For SVG: simple XML parse
    """
    if content_type in {"image/png", "image/jpeg", "image/gif", "image/webp"}:
        try:
            img = Image.open(BytesIO(file_bytes))
            img.verify()
            # Map to proper MIME type
            mime_type = Image.MIME.get(img.format)
            if mime_type not in ALLOWED_IMAGE_TYPES:
                raise HTTPException(status_code=400, detail=f"Unsupported image type: {mime_type}")
            return mime_type
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid image file")
    elif content_type == "image/svg+xml":
        try:
            ET.fromstring(file_bytes.decode("utf-8"))
            return "image/svg+xml"
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid SVG file")
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported content type: {content_type}")

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
        raise HTTPException(status_code=400, detail=f"Unsupported content type: {file.content_type}")

    tags_list = [t.strip() for t in tags.split(",")] if tags else []

    try:
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
            s3_key=image.s3_key,
            filename=image.filename,
            uploaded_at=image.uploaded_at,
        )
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Upload failed")
        raise HTTPException(status_code=500, detail=str(exc))

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
            raise HTTPException(status_code=400, detail="invalid exclusive_start_key")

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

@router.get("/{image_id}")
def get_image(
    image_id: str,
    db: DynamoDBService = Depends(get_dynamodb_service),
    s3: S3Service = Depends(get_s3_service)
):
    """Gets a presigned URL for an image."""
    meta = get_image_meta(db, image_id)
    if not meta:
        raise HTTPException(status_code=404, detail="image not found")

    url = s3.generate_presigned_url(meta["s3_key"])
    return RedirectResponse(url)

@router.delete("/{image_id}", status_code=204)
def delete_image(
    image_id: str,
    db: DynamoDBService = Depends(get_dynamodb_service),
    s3: S3Service = Depends(get_s3_service)
):
    """Deletes an image and its metadata."""
    ok = remove_image(db, s3, image_id)
    if not ok:
        raise HTTPException(status_code=404, detail="image not found")
    return JSONResponse(status_code=204, content=None)