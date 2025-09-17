from fastapi import Request
from app.storage.dynamodb import DynamoDBService
from app.storage.s3 import S3Service

def get_s3_service(request: Request) -> S3Service:
    """Dependency provider for S3Service"""
    return request.app.state.s3

def get_dynamodb_service(request: Request) -> DynamoDBService:
    """Dependency provider for DynamoDBService"""
    return request.app.state.db
