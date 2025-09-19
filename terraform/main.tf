provider "aws" {
  region                      = "us-east-1"
  access_key                  = "test"
  secret_key                  = "test"
  s3_use_path_style           = true
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true

  endpoints {
    apigateway     = "http://localhost:4566"
    apigatewayv2   = "http://localhost:4566"
    lambda         = "http://localhost:4566"
    iam            = "http://localhost:4566"
    s3             = "http://localhost:4566"
  }
}

# -----------------------------
# IAM Role for Lambda
# -----------------------------
resource "aws_iam_role" "lambda_exec" {
  name = "fastapi-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
  role       = aws_iam_role.lambda_exec.name
}

# -----------------------------
# S3 bucket to store Lambda zip
# -----------------------------
resource "aws_s3_bucket" "lambda_bucket" {
  bucket = "lambda-code-bucket"
}

# -----------------------------
# Upload Lambda zip to S3
# -----------------------------
resource "aws_s3_object" "lambda_zip" {
  
  bucket = aws_s3_bucket.lambda_bucket.bucket
  key    = "image-uploader.zip"
  source = "${path.module}/../image-uploader.zip"
  etag   = filemd5("${path.module}/../image-uploader.zip")
}

# -----------------------------
# Lambda function (from S3)
# -----------------------------
resource "aws_lambda_function" "fastapi" {
  depends_on = [
    aws_s3_object.lambda_zip,
    aws_s3_bucket.lambda_bucket
  ]

  function_name = "fastapi-lambda"
  role          = aws_iam_role.lambda_exec.arn
  runtime       = "python3.12"
  handler       = "app.lambda_handler.handler"
  timeout       = 30
  memory_size   = 512

  s3_bucket = aws_s3_bucket.lambda_bucket.bucket
  s3_key    = "image-uploader.zip"
  
  # Force update when zip changes
  source_code_hash = filebase64sha256("${path.module}/../image-uploader.zip")
}

# -----------------------------
# Lambda permission for API Gateway
# -----------------------------
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.fastapi.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.fastapi.execution_arn}/*/*"
}

# -----------------------------
# API Gateway setup
# -----------------------------
resource "aws_api_gateway_rest_api" "fastapi" {
  name        = "fastapi-rest-api"
  description = "FastAPI running in Lambda on LocalStack"
}

resource "aws_api_gateway_resource" "proxy" {
  rest_api_id = aws_api_gateway_rest_api.fastapi.id
  parent_id   = aws_api_gateway_rest_api.fastapi.root_resource_id
  path_part   = "{proxy+}"
}

resource "aws_api_gateway_method" "proxy" {
  rest_api_id   = aws_api_gateway_rest_api.fastapi.id
  resource_id   = aws_api_gateway_resource.proxy.id
  http_method   = "ANY"
  authorization = "NONE"
}

resource "aws_api_gateway_method" "proxy_root" {
  rest_api_id   = aws_api_gateway_rest_api.fastapi.id
  resource_id   = aws_api_gateway_rest_api.fastapi.root_resource_id
  http_method   = "ANY"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "lambda" {
  rest_api_id             = aws_api_gateway_rest_api.fastapi.id
  resource_id             = aws_api_gateway_method.proxy.resource_id
  http_method             = aws_api_gateway_method.proxy.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.fastapi.invoke_arn
}

resource "aws_api_gateway_integration" "lambda_root" {
  rest_api_id             = aws_api_gateway_rest_api.fastapi.id
  resource_id             = aws_api_gateway_method.proxy_root.resource_id
  http_method             = aws_api_gateway_method.proxy_root.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.fastapi.invoke_arn
}

resource "aws_api_gateway_deployment" "fastapi" {
  depends_on = [
    aws_api_gateway_integration.lambda,
    aws_api_gateway_integration.lambda_root,
  ]

  rest_api_id = aws_api_gateway_rest_api.fastapi.id

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.proxy.id,
      aws_api_gateway_method.proxy.id,
      aws_api_gateway_method.proxy_root.id,
      aws_api_gateway_integration.lambda.id,
      aws_api_gateway_integration.lambda_root.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "fastapi" {
  deployment_id = aws_api_gateway_deployment.fastapi.id
  rest_api_id   = aws_api_gateway_rest_api.fastapi.id
  stage_name    = "local"
}

# -----------------------------
# Outputs
# -----------------------------
output "api_id" {
  value = aws_api_gateway_rest_api.fastapi.id
}

output "invoke_url" {
  value = "http://localhost:4566/_aws/execute-api/${aws_api_gateway_rest_api.fastapi.id}/local/api/v1/images"
}

output "lambda_function_name" {
  value = aws_lambda_function.fastapi.function_name
}

output "s3_bucket" {
  value = aws_s3_bucket.lambda_bucket.bucket
}