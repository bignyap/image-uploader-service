from fastapi import FastAPI
import uvicorn

app = FastAPI(title="image-uploader-service")

@app.post("/images")
async def upload_image():
    return "Uploaded"

@app.get("/images")
async def list_images():
    return {
        "images": []
    }

@app.delete("/images/{image_id}")
async def delete_image():
    return "Deleted"

if __name__ == "__main__":
     uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

