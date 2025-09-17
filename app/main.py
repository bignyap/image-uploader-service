from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException
from typing import Optional
from contextlib import asynccontextmanager
import uvicorn
from io import BytesIO
import logging

from .storage import S3Service, DynamoDBService
from .dependencies import get_s3_service, get_dynamodb_service
from .settings import settings
from .repository import save_image_and_meta
from .models import UploadResponse

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("image-service")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize resources
    app.state.s3 = S3Service()
    app.state.db = DynamoDBService()
    yield
    # Cleanup resources
    app.state.s3.close()
    app.state.db.close()

app = FastAPI(title=settings.app_title, lifespan=lifespan)

@app.post("/images")
async def upload_image(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    db: DynamoDBService = Depends(get_dynamodb_service),
    s3: S3Service = Depends(get_s3_service) # Comma Separated Values
):
    # Split the tags
    tags_list = []
    if tags:
        tags_list = [t.strip() for t in tags.split(",") if t.strip()]
     # Read file into bytes stream
    try:
        contents = await file.read()
        fileobj = BytesIO(contents)
        image = save_image_and_meta(
            fileobj=fileobj,
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream",
            size=len(contents),
            user_id=user_id,
            title=title,
            description=description,
            tags=tags_list,
        )
        return UploadResponse(
            image_id=image.image_id,
            s3_key=image.s3_key,
            filename=image.filename,
            uploaded_at=image.uploaded_at,
        )
    except Exception as exc:
        log.exception("Upload failed")
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/images")
async def list_images(db: DynamoDBService = Depends(get_dynamodb_service)):
    return {"images": []}

@app.delete("/images/{image_id}")
async def delete_image(db: DynamoDBService = Depends(get_dynamodb_service)):
    return {"message": "Deleted"}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
