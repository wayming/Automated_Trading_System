#!/bin/bash

set -e

if [ -n "$AWS_REGION" ]; then
  REGION=$AWS_REGION
else
  REGION=$(aws configure get region)
fi
BUCKET_NAME="qts-front-5222753b"

if [ -z "$REGION" ]; then
  echo "Error: AWS region not set. Please set AWS_REGION environment variable or configure default region via 'aws configure'."
  exit 1
fi

# if aws s3api head-bucket --bucket "$BUCKET_NAME" 2>/dev/null; then
#   echo "Bucket exists, deleting index.html..."
#   aws s3 rm s3://$BUCKET_NAME/index.html
# else
#   echo "Bucket does not exist."
# fi

# terraform destroy -auto-approve

# terraform apply -auto-approve -var bucket_name="$BUCKET_NAME" -var region="$REGION"

# Replace <WEBSOCKET_API_ENDPOINT> with WEBSOCKET_API_ENDPOINT
WEBSOCKET_API_ENDPOINT=$(terraform output -raw websocket_api_endpoint)
sed -i "s|wss://[^\"']*|$WEBSOCKET_API_ENDPOINT|" index.html
aws s3 cp index.html s3://$BUCKET_NAME/index.html 
echo "index.html with websocket endpoint $WEBSOCKET_API_ENDPOINT deployed to bucket $BUCKET_NAME"

CLOUDFRONT_DOMAIN=$(terraform output -raw cloudfront_domain_name)
echo "Frontend domain: $CLOUDFRONT_DOMAIN"

HTTP_API_ENDPOINT=$(terraform output -raw http_api_endpoint)
echo "HTTP Push API: $HTTP_API_ENDPOINT"
DOCKER_ENV="../docker/.env"
sed -i '/^HTTP_API_ENDPOINT=/d' "$DOCKER_ENV"
echo "HTTP_API_ENDPOINT=$HTTP_API_ENDPOINT" >> "$DOCKER_ENV"
export HTTP_API_ENDPOINT=$HTTP_API_ENDPOINT
