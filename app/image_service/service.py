from datetime import datetime, timezone
from typing import List, Dict, Optional
import logging
from datetime import datetime, timezone
import uuid
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import BotoCoreError, ClientError

from app.storage.dynamodb import DynamoDBService
from app.storage.s3 import S3Service
from app.image_service.models import ImageMeta
from app.settings import settings
from app.exceptions import S3UploadException, DynamoDBException, ImageNotFoundException

log = logging.getLogger(__name__)

def save_image_and_meta(
    db: DynamoDBService,
    s3: S3Service,
    fileobj,
    filename: str,
    content_type: str,
    size: int,
    user_id: str,
    title: Optional[str],
    description: Optional[str],
    tags: List[str]
) -> ImageMeta:
    """Saves image to S3 and metadata to DynamoDB."""
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
    try:
        s3.upload(fileobj=fileobj, key=image.s3_key, content_type=content_type)
    except (BotoCoreError, ClientError) as e:
        log.error(f"S3 upload failed: {e}")
        raise S3UploadException(f"Failed to upload image to S3: {e}")

    # persist metadata in dynamodb
    item = image.model_dump()
    # Dynamo needs uploaded_at as ISO string
    item["uploaded_at"] = item["uploaded_at"].isoformat()
    try:
        db.put_metadata(item)
    except (BotoCoreError, ClientError) as e:
        log.error(f"DynamoDB put_metadata failed: {e}")
        raise DynamoDBException(f"Failed to save image metadata: {e}")

    log.info("Saved image metadata %s", image.image_id)
    return image

def image_id_key() -> str:
    """Generates a new unique image ID key."""
    return str(uuid.uuid4())


def fetch_images(
    db: DynamoDBService,
    user_id: Optional[str] = None, 
    tag: Optional[str] = None, 
    limit:int = 50, 
    exclusive_start_key: Optional[Dict[str,str]] = None
):
    """Fetches images from DynamoDB with optional filters."""
    try:
        filters = {}
        if user_id:
            filters["user_id"] = user_id
        if tag:
            table = db.resource.Table(settings.dynamodb_table)
            scan_kwargs = {"Limit": limit}
            if exclusive_start_key:
                scan_kwargs["ExclusiveStartKey"] = exclusive_start_key
            scan_kwargs["FilterExpression"] = Attr("tags").contains(tag)
            if user_id:
                scan_kwargs["FilterExpression"] = scan_kwargs["FilterExpression"] & Attr("user_id").eq(user_id)
            resp = table.scan(**scan_kwargs)
            items = resp.get("Items", [])
            return {"Items": items, "LastEvaluatedKey": resp.get("LastEvaluatedKey")}
        else:
            resp = db.scan_metadata(filter_expression=filters if filters else None, limit=limit, exclusive_start_key=exclusive_start_key)
            return resp
    except (BotoCoreError, ClientError) as e:
        log.error(f"DynamoDB fetch_images failed: {e}")
        raise DynamoDBException(f"Failed to fetch images: {e}")
    
def get_image_meta(db: DynamoDBService, image_id: str):
    """Gets image metadata from DynamoDB."""
    try:
        item = db.get_metadata(image_id)
        if not item:
            raise ImageNotFoundException(image_id)
        return item
    except (BotoCoreError, ClientError) as e:
        log.error(f"DynamoDB get_image_meta failed: {e}")
        raise DynamoDBException(f"Failed to get image metadata: {e}")

def remove_image( 
    db: DynamoDBService,
    s3: S3Service,
    image_id: str
):
    """Removes image from S3 and metadata from DynamoDB."""
    item = get_image_meta(db, image_id)
    if not item:
        raise ImageNotFoundException(image_id)
    
    s3_key = item.get("s3_key")
    if s3_key:
        try:
            s3.delete_from_s3(s3_key)
        except (BotoCoreError, ClientError) as e:
            log.error(f"S3 delete_from_s3 failed: {e}")
            raise S3UploadException(f"Failed to delete image from S3: {e}")
    try:
        db.delete_metadata(image_id)
    except (BotoCoreError, ClientError) as e:
        log.error(f"DynamoDB delete_metadata failed: {e}")
        raise DynamoDBException(f"Failed to delete image metadata: {e}")
    return True
