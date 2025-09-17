import boto3
from typing import Optional
from botocore.exceptions import ClientError
from app.settings import settings
import logging

log = logging.getLogger(__name__)

# -------------------------
# S3 Service
# -------------------------
class S3Service:
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
    
        # Ensure bucket exists at initialization
        self.ensure_bucket()

    def ensure_bucket(self):
        try:
            self.client.head_bucket(Bucket=settings.s3_bucket)
            log.debug("Bucket %s already exists", settings.s3_bucket)
        except ClientError as e:
            error_code = int(e.response["Error"]["Code"])
            if error_code == 404:
                self.client.create_bucket(Bucket=settings.s3_bucket)
                log.info("Created bucket %s", settings.s3_bucket)
            else:
                log.error("Failed to check/create bucket: %s", e)
                raise

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
        url = self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket, "Key": key},
            ExpiresIn=expires,
        )
        if settings.external_endpoint and settings.aws_endpoint_url:
                url = url.replace(settings.aws_endpoint_url, settings.external_endpoint)
        return url

    def delete(self, key: str):
        self.client.delete_object(Bucket=settings.s3_bucket, Key=key)
        log.debug("Deleted s3://%s/%s", settings.s3_bucket, key)
    
    def close(self):
        log.info("Closed S3 client")