from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from uuid import uuid4

def new_image_id() -> str:
    """Generates a new unique image ID."""
    return str(uuid4())

class ImageMeta(BaseModel):
    image_id: str = Field(default_factory=new_image_id)
    user_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = []
    s3_key: str
    filename: str
    content_type: str
    size: int
    uploaded_at: datetime

class ImageItem(BaseModel):
    image_id: str
    user_id: str
    title: Optional[str]
    description: Optional[str]
    tags: List[str]
    filename: str
    content_type: str
    size: int
    s3_key: str
    uploaded_at: datetime

class UploadResponse(BaseModel):
    image_id: str
    user_id: str
    s3_key: str
    filename: str
    uploaded_at: datetime

class ListImagesResponse(BaseModel):
    images: List[ImageItem]
    next_token: Optional[str] = None