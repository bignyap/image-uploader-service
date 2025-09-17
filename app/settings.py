from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional

class Settings(BaseSettings):
    aws_region: str = Field("us-east-1", env="AWS_REGION")
    s3_bucket: str = Field("image-service-bucket", env="S3_BUCKET")
    dynamodb_table: str = Field("Images", env="DYNAMODB_TABLE")
    aws_endpoint_url: Optional[str] = Field(None, env="AWS_ENDPOINT_URL")
    presign_expire_seconds: int = Field(900, env="PRESIGN_EXPIRE_SECONDS")

    aws_access_key_id: str = Field("test", env="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field("test", env="AWS_SECRET_ACCESS_KEY")

    # 👇 this was missing
    app_title: str = Field("Image Service", env="APP_TITLE")

    class Config:
        env_file = ".env"
        extra = "allow"  # tolerate unknown vars if needed

settings = Settings()