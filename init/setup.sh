#!/bin/bash
set -e

echo "🚀 Packaging Lambda layer (dependencies)..."
mkdir -p /tmp/layer/python/lib/python3.11/site-packages
pip install -r /project/requirements.txt -t /tmp/layer/python/lib/python3.11/site-packages >/dev/null

cd /tmp/layer && zip -r9 /tmp/image_layer.zip .
LAYER_ARN=$(awslocal lambda publish-layer-version \
  --layer-name image-deps \
  --zip-file fileb:///tmp/image_layer.zip \
  --compatible-runtimes python3.11 \
  --query 'LayerVersionArn' --output text)

echo "✅ Layer published: $LAYER_ARN"

echo "📦 Packaging Lambda function (app code only)..."
mkdir -p /tmp/app
cp -r /project/app /tmp/app/
cd /tmp/app && zip -r9 /tmp/image_service.zip . -x "**/__pycache__/*"

echo "📝 Creating Lambda function..."
awslocal lambda create-function \
  --function-name image-service \
  --runtime python3.11 \
  --role arn:aws:iam::000000000000:role/lambda-role \
  --handler app.lambda_handler.handler \
  --zip-file fileb:///tmp/image_service.zip \
  --layers "$LAYER_ARN"

echo "🔗 Adding invoke permission for API Gateway..."
awslocal lambda add-permission \
  --function-name image-service \
  --statement-id apigateway-invoke \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com

echo "🌐 Creating API Gateway..."
API_ID=$(awslocal apigateway create-rest-api \
  --name "ImageAPI" \
  --query 'id' --output text)

PARENT_ID=$(awslocal apigateway get-resources \
  --rest-api-id $API_ID \
  --query 'items[0].id' --output text)

RESOURCE_ID=$(awslocal apigateway create-resource \
  --rest-api-id $API_ID \
  --parent-id $PARENT_ID \
  --path-part "{proxy+}" \
  --query 'id' --output text)

awslocal apigateway put-method \
  --rest-api-id $API_ID \
  --resource-id $RESOURCE_ID \
  --http-method ANY \
  --authorization-type "NONE"

awslocal apigateway put-integration \
  --rest-api-id $API_ID \
  --resource-id $RESOURCE_ID \
  --http-method ANY \
  --type AWS_PROXY \
  --integration-http-method POST \
  --uri arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:000000000000:function:image-service/invocations

awslocal apigateway create-deployment \
  --rest-api-id $API_ID \
  --stage-name dev

echo "✅ Setup complete!"
echo "👉 Test your API with:"
echo "curl http://localhost:4566/_aws/execute-api/$API_ID/dev/api/v1/"