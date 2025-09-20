# Image Uploader Service (S3 + DynamoDB) — LocalStack-ready

This project implements a small image upload service using FastAPI, S3, and DynamoDB. It is designed to run against LocalStack for local development and testing.

## Requirements
- Python 3.13+
- Docker and Docker Compose

## Deployment Options

### Option 1: Local Docker Deployment

This runs the service as a FastAPI application in Docker containers.

#### Setup
```bash
# Build the image-uploader docker image
docker build -t bignya/image-uploader .

# Copy environment configuration
cp .env.sample .env
```

#### Running
```bash
# Start the services
docker compose down; docker compose up -d
```

#### API Docs
```bash
localhost:8000/docs
```

#### Testing the API

**Upload Image:**
```bash
curl -X POST "http://localhost:8000/api/v1/images" \
  -H "accept: application/json" \
  -F "file=@./gif.gif;type=image/gif" \
  -F "user_id=user123" \
  -F "title=My Holiday Photo" \
  -F "description=Taken at the beach" \
  -F "tags=beach,holiday,sunset"
```

**List Images:**
```bash
curl -X GET "http://localhost:8000/api/v1/images" \
  -H "accept: application/json"
```

**Get Specific Image:**
```bash
curl -X GET "http://localhost:8000/api/v1/images/{image_id}" \
  -H "accept: application/json"
```

### Option 2: LocalStack Lambda Deployment

This deploys the service as AWS Lambda functions running on LocalStack for a more production-like environment.

#### Setup
```bash
# Build the Lambda deployment package
docker build -t bignya/image-uploader-builder -f Dockerfile-lambda .

# Extract the deployment package
docker run --rm -v ${PWD}:/out bignya/image-uploader-builder sh -c "cp /app/image-uploader.zip /out/"

# Run the localstack service
docker compose -f lambda-compose.yaml down; docker compose -f lambda-compose.yaml up -d
```

#### Deploy with Terraform
```bash
# Initialize and apply Terraform configuration
cd terraform
terraform init
terraform plan
terraform apply -auto-approve
```

#### Testing
After deployment, the API endpoints will be available through LocalStack's API Gateway. Check the Terraform output for the specific endpoint URLs.

## Architecture

- **FastAPI**: Web framework for the REST API
- **S3**: Object storage for image files
- **DynamoDB**: NoSQL database for image metadata
- **LocalStack**: Local AWS cloud stack for development
- **Docker**: Containerization for consistent environments

## Development Notes

- The service automatically creates the required S3 buckets and DynamoDB tables
- Image files are stored in S3 with generated UUIDs
- Metadata including user_id, title, description, and tags are stored in DynamoDB
- Both deployment options use the same codebase with different packaging strategies