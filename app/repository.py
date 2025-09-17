from datetime import datetime, timezone
from typing import List, Dict, Optional
import logging
from . import storage
from .models import ImageMeta
# from .settings import settings
from datetime import datetime, timezone

log = logging.getLogger(__name__)

def save_image_and_meta(
    fileobj,
    filename: str,
    content_type: str,
    size: int,
    user_id: str,
    title: Optional[str],
    description: Optional[str],
    tags: List[str],
) -> ImageMeta:
    # generate s3 key and metadata
    image = ImageMeta(
        user_id = user_id,
        title = title,
        description = description,
        tags = tags,
        s3_key = f"{user_id}/{datetime.now(timezone.utc).strftime('%Y%m%d')}/{image_id_key()}_{filename}",
        filename = filename,
        content_type = content_type,
        size = size,
        uploaded_at = datetime.now(timezone.utc),
    )
    # upload to s3
    storage.upload_to_s3(fileobj=fileobj, key=image.s3_key, content_type=content_type)

    # persist metadata in dynamodb
    item = image.model_dump()
    # Dynamo needs uploaded_at as ISO string
    item["uploaded_at"] = item["uploaded_at"].isoformat()
    storage.put_metadata(item)
    log.info("Saved image metadata %s", image.image_id)
    return image

def image_id_key() -> str:
    # simple short id for key part
    import uuid
    return str(uuid.uuid4())
