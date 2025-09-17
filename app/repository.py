from datetime import datetime, timezone
from typing import List, Dict, Optional
import logging
from . import storage
from .models import ImageMeta
from datetime import datetime, timezone
import uuid

from .storage import S3Service, DynamoDBService
from .settings import settings

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
    s3.upload(fileobj=fileobj, key=image.s3_key, content_type=content_type)

    # persist metadata in dynamodb
    item = image.model_dump()
    # Dynamo needs uploaded_at as ISO string
    item["uploaded_at"] = item["uploaded_at"].isoformat()
    db.put_metadata(item)
    log.info("Saved image metadata %s", image.image_id)
    return image

def image_id_key() -> str:
    return str(uuid.uuid4())


def list_images(
    db: DynamoDBService,
    user_id: Optional[str] = None, 
    tag: Optional[str] = None, 
    limit:int = 50, 
    exclusive_start_key: Optional[Dict[str,str]] = None
):
    filters = {}
    if user_id:
        filters["user_id"] = user_id
    if tag:
        # Dynamo doesn't support searching inside list easily without GSI; scan with filter expression on tags contains
        # We'll do a scan with condition contains(tags, tag)
        from boto3.dynamodb.conditions import Attr
        table = storage.dynamodb_resource().Table(settings.dynamodb_table)
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
    
def get_image_meta(db: DynamoDBService, image_id: str):
    item = db.get_metadata(image_id)
    return item

def delete_image( 
    db: DynamoDBService,
    s3: S3Service,
    image_id: str
):
    item = get_image_meta(image_id)
    if not item:
        return False
    s3_key = item.get("s3_key")
    if s3_key:
        s3.delete_from_s3(s3_key)
    db.delete_metadata(image_id)
    return True
