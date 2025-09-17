import boto3
from typing import Optional, Dict, Any
from .settings import settings
import logging

log = logging.getLogger(__name__)

# -------------------------
# Singleton metaclass
# -------------------------
class SingletonMeta(type):
    """Thread-safe Singleton metaclass."""
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]

# -------------------------
# S3 Service
# -------------------------
class S3Service(metaclass=SingletonMeta):
    def __init__(self):
        session = boto3.session.Session(region_name=settings.aws_region)
        kwargs = {
            "aws_access_key_id": settings.aws_access_key_id,
            "aws_secret_access_key": settings.aws_secret_access_key,
        }
        if settings.aws_endpoint_url:
            kwargs["endpoint_url"] = settings.aws_endpoint_url

        self.client = session.client("s3", **kwargs)
        log.info("Initialized S3 client")

    def upload(self, fileobj, key: str, content_type: str):
        self.client.upload_fileobj(
            Fileobj=fileobj,
            Bucket=settings.s3_bucket,
            Key=key,
            ExtraArgs={"ContentType": content_type},
        )
        log.debug("Uploaded %s to s3://%s/%s", key, settings.s3_bucket, key)

    def generate_presigned_url(self, key: str, expires_in: Optional[int] = None) -> str:
        expires = expires_in or settings.presign_expire_seconds
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket, "Key": key},
            ExpiresIn=expires,
        )

    def delete(self, key: str):
        self.client.delete_object(Bucket=settings.s3_bucket, Key=key)
        log.debug("Deleted s3://%s/%s", settings.s3_bucket, key)

# -------------------------
# DynamoDB Service
# -------------------------
class DynamoDBService(metaclass=SingletonMeta):
    def __init__(self):
        session = boto3.session.Session(region_name=settings.aws_region)
        kwargs = {
            "aws_access_key_id": settings.aws_access_key_id,
            "aws_secret_access_key": settings.aws_secret_access_key,
        }
        if settings.aws_endpoint_url:
            kwargs["endpoint_url"] = settings.aws_endpoint_url

        self.resource = session.resource("dynamodb", **kwargs)
        log.info("Initialized DynamoDB resource")

    def put_metadata(self, item: Dict[str, Any]):
        table = self.resource.Table(settings.dynamodb_table)
        table.put_item(Item=item)
        log.debug("Inserted metadata %s", item.get("image_id"))

    def get_metadata(self, image_id: str) -> Optional[Dict[str, Any]]:
        table = self.resource.Table(settings.dynamodb_table)
        resp = table.get_item(Key={"image_id": image_id})
        return resp.get("Item")

    def delete_metadata(self, image_id: str):
        table = self.resource.Table(settings.dynamodb_table)
        table.delete_item(Key={"image_id": image_id})
        log.debug("Deleted metadata %s", image_id)