# Image Uploader Service (S3 + DynamoDB) — LocalStack-ready

This project implements a small image upload service using FastAPI, S3, and DynamoDB. It is designed to run against LocalStack for local development.

## Requirements
- Python 3.13+
- Docker (for LocalStack)

## Local Deployment

### Build the image-uploader docker image
```bash
docker build -t bignya/image-uploader .
cp .env.sample .env
```

### Running image-uploader
```bash
docker compose down; docker compose up -d
```

### Make curl requests

- Upload Image

```bash
curl -X POST "http://localhost:8000/api/v1/images" -H "accept: application/json" -F "file=@./gif.gif;type=image/gif" -F "user_id=user123" -F "title=My Holiday Photo" -F "description=Taken at the beach" -F "tags=beach,holiday,sunset"
```

- List Images

```bash
curl -X GET "http://localhost:8000/api/v1/images" -H "accept: application/json"
```

- Get Images

```bash
http://localhost:8000/api/v1/images/{image_id}
```

## Localstack API Gateway Deployment


### Build the image-uploader docker image
```bash
docker compose -f lambda-compose.yaml down; docker compose -f lambda-compose.yaml up -d --build
cp .env.sample .env
```