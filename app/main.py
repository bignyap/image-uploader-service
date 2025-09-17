from fastapi import FastAPI, Depends
from contextlib import asynccontextmanager
import uvicorn

from .storage import S3Service, DynamoDBService
from .dependencies import get_s3_service, get_dynamodb_service
from .settings import settings

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
async def upload_image(s3: S3Service = Depends(get_s3_service)):
    # Example usage
    return {"message": "Uploaded"}

@app.get("/images")
async def list_images(db: DynamoDBService = Depends(get_dynamodb_service)):
    return {"images": []}

@app.delete("/images/{image_id}")
async def delete_image(db: DynamoDBService = Depends(get_dynamodb_service)):
    return {"message": "Deleted"}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
