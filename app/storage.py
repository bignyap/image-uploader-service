import boto3
from typing import Optional, Dict, Any
from botocore.exceptions import ClientError
from .settings import settings
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
class DynamoDBService:
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

        # Ensure table exists at initialization
        self.ensure_table()

    # Refer here: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/dynamodb/client/create_table.html
    def ensure_table(self):
        try:
            table = self.resource.Table(settings.dynamodb_table)
            table.load()
        except ClientError:
            table = self.resource.create_table(
                TableName=settings.dynamodb_table,
                KeySchema=[{"AttributeName": "image_id", "KeyType": "HASH"}],
                AttributeDefinitions=[
                    {"AttributeName": "image_id", "AttributeType": "S"},
                    {"AttributeName": "user_id", "AttributeType": "S"},
                ],
                GlobalSecondaryIndexes=[
                    {
                        "IndexName": "UserIndex",
                        "KeySchema": [{"AttributeName": "user_id", "KeyType": "HASH"}],
                        "Projection": {"ProjectionType": "ALL"},
                        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
                    }
                ],
                ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
            )
            table.wait_until_exists()
            log.info("Created table %s", settings.dynamodb_table)

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