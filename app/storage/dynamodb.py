import boto3
from typing import Optional, Dict, Any
from botocore.exceptions import ClientError
from app.settings import settings
import logging

log = logging.getLogger(__name__)

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

    def scan_metadata(
        self,
        filter_expression: Optional[Dict[str, Any]] = None,
        limit: int = 50,
        exclusive_start_key: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        table = self.resource.Table(settings.dynamodb_table)
        scan_kwargs = {"Limit": limit}
        if exclusive_start_key:
            scan_kwargs["ExclusiveStartKey"] = exclusive_start_key
        if filter_expression:
            from boto3.dynamodb.conditions import Attr

            filters = None
            for k, v in filter_expression.items():
                cond = Attr(k).eq(v)
                filters = cond if filters is None else filters & cond
            if filters is not None:
                scan_kwargs["FilterExpression"] = filters
        return table.scan(**scan_kwargs)
    
    def close(self):
        log.info("Closed DynamoDB resource")