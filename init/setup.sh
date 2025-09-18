#!/bin/bash
set -e

# --------------------------
# Detect Python version
# --------------------------
PYTHON_VERSION=$(python3 --version | awk '{print $2}')
PYTHON_MAJOR_MINOR=$(echo $PYTHON_VERSION | cut -d. -f1,2)
echo "🐍 Detected Python version: $PYTHON_VERSION"

# --------------------------
# Cleanup old artifacts
# --------------------------
echo "🧹 Cleaning up old build artifacts..."
rm -rf /tmp/layer /tmp/image_layer.zip /tmp/app /tmp/image_service.zip /tmp/venv-lambda

# --------------------------
# Create virtual environment
# --------------------------
echo "🛠️ Creating Python virtual environment..."
python3 -m venv /tmp/venv-lambda
source /tmp/venv-lambda/bin/activate
pip install --upgrade pip >/dev/null

# --------------------------
# Build Lambda layer
# --------------------------
echo "🚀 Building Lambda layer (FastAPI + dependencies)..."
mkdir -p /tmp/layer/python/lib/python$PYTHON_MAJOR_MINOR/site-packages

# Install dependencies into the layer
echo "Installing dependencies from requirements.txt..."
pip install -r /project/requirements.txt -t /tmp/layer/python/lib/python$PYTHON_MAJOR_MINOR/site-packages

echo "Listing installed packages in the layer:"
ls -l /tmp/layer/python/lib/python$PYTHON_MAJOR_MINOR/site-packages

# Zip the layer
echo "Zipping the layer..."
cd /tmp/layer
zip -r9 /tmp/image_layer.zip python

# Publish the layer
LAYER_ARN=$(awslocal lambda publish-layer-version \
  --layer-name image-deps \
  --zip-file fileb:///tmp/image_layer.zip \
  --compatible-runtimes python$PYTHON_MAJOR_MINOR \
  --query 'LayerVersionArn' --output text)
echo "✅ Layer published: $LAYER_ARN"

# --------------------------
# Package Lambda function (app code)
# --------------------------
echo "📦 Packaging Lambda function..."
cd /project
zip -r9 /tmp/image_service.zip app -x "app/**/__pycache__/*" >/dev/null

# --------------------------
# Create Lambda function
# --------------------------
echo "📝 Creating Lambda function..."
awslocal lambda delete-function --function-name image-service 2>/dev/null || true
awslocal lambda create-function \
  --function-name image-service \
  --runtime python$PYTHON_MAJOR_MINOR \
  --role arn:aws:iam::000000000000:role/lambda-role \
  --handler app.lambda_handler.handler \
  --zip-file fileb:///tmp/image_service.zip \
  --layers "$LAYER_ARN" \
  --timeout 30

echo "⏳ Waiting for Lambda to become Active..."
awslocal lambda wait function-active-v2 --function-name image-service

# --------------------------
# API Gateway integration
# --------------------------
echo "🔗 Adding invoke permission for API Gateway..."
awslocal lambda add-permission \
  --function-name image-service \
  --statement-id apigateway-invoke \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com || true

echo "🌐 Creating API Gateway..."
API_ID=$(awslocal apigateway create-rest-api --name "ImageAPI" --query 'id' --output text)
PARENT_ID=$(awslocal apigateway get-resources --rest-api-id $API_ID --query 'items[0].id' --output text)
RESOURCE_ID=$(awslocal apigateway create-resource --rest-api-id $API_ID --parent-id $PARENT_ID --path-part "{proxy+}" --query 'id' --output text)

awslocal apigateway put-method \
  --rest-api-id $API_ID \
  --resource-id $RESOURCE_ID \
  --http-method ANY \
  --authorization-type NONE

awslocal apigateway put-integration \
  --rest-api-id $API_ID \
  --resource-id $RESOURCE_ID \
  --http-method ANY \
  --type AWS_PROXY \
  --integration-http-method POST \
  --uri arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:000000000000:function:image-service/invocations

awslocal apigateway create-deployment --rest-api-id $API_ID --stage-name dev

# --------------------------
# Test the API
# --------------------------
echo "✅ Setup complete!"
echo "👉 Test your API with:"
echo "curl http://localhost:4566/_aws/execute-api/$API_ID/dev/api/v1/"