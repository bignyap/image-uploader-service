from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import logging

from app.storage.dynamodb import DynamoDBService
from app.storage.s3 import S3Service
from app.settings import settings
from app.routers.image_service import router as image_router

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

# Initialize App
app = FastAPI(
    title=settings.app_title, 
    lifespan=lifespan,
    description="Image Uploader Service",
    root_path = "/api/v1"
)

# CORS - Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    # allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add the routers
app.include_router(image_router)

# Check Health
@app.get("/")
def read_root():
    """
        Default end point
    
    """
    return "Image Uploader Service is running."

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
