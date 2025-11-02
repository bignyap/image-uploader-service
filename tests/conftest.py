import os
import pytest
from moto import mock_aws
from fastapi.testclient import TestClient
import boto3
import importlib

# Set test environment variable BEFORE importing app modules
os.environ["TESTING"] = "true"

# Dummy AWS credentials for moto
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["S3_BUCKET"] = "image-service-bucket"
os.environ["DYNAMODB_TABLE"] = "Images"
# Clear the AWS_ENDPOINT_URL so moto mocks are used instead of localstack
os.environ.pop("AWS_ENDPOINT_URL", None)

# Import settings module and reload it to pick up the cleared AWS_ENDPOINT_URL
from app import settings as settings_module
importlib.reload(settings_module)

from app.main import app
from app.storage.s3 import S3Service
from app.storage.dynamodb import DynamoDBService


@pytest.fixture(scope="function")
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"


@pytest.fixture(scope="function")
def test_client(aws_credentials):
    # Reload settings to pick up the cleared AWS_ENDPOINT_URL
    import importlib
    from app import settings as settings_module
    importlib.reload(settings_module)

    with mock_aws():
        # Create S3 bucket
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="image-service-bucket")

        # Create DynamoDB table
        dynamodb = boto3.client("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName="Images",
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

        # Create services within the moto context
        s3_service = S3Service()
        db_service = DynamoDBService()

        # Replace the original services with mocked ones
        app.state.s3 = s3_service
        app.state.db = db_service

        with TestClient(app) as client:
            yield client