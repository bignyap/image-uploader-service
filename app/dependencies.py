from fastapi import Request, Depends
from .storage import S3Service, DynamoDBService

def get_s3_service(request: Request) -> S3Service:
    """Dependency provider for S3Service"""
    return request.app.state.s3

def get_dynamodb_service(request: Request) -> DynamoDBService:
    """Dependency provider for DynamoDBService"""
    return request.app.state.db
