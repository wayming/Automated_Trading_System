#!/bin/bash

set -e

if [ -n "$AWS_REGION" ]; then
  REGION=$AWS_REGION
else
  REGION=$(aws configure get region)
fi

if [ -z "$REGION" ]; then
  echo "Error: AWS region not set. Please set AWS_REGION environment variable or configure default region via 'aws configure'."
  exit 1
fi

ROLE_NAME="ApiGatewayCloudWatchLogsRole"

# Account global setting which can not be configured via CloudFormation
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ROLE_EXISTS=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text 2>/dev/null || echo "none")
if [ "$ROLE_EXISTS" = "none" ]; then
  echo "🔧 Create CloudWatch Role for API Gateway: $ROLE_NAME"

  aws iam create-role --role-name "$ROLE_NAME" \
    --assume-role-policy-document '{
      "Version": "2012-10-17",
      "Statement": [{
        "Effect": "Allow",
        "Principal": { "Service": "apigateway.amazonaws.com" },
        "Action": "sts:AssumeRole"
      }]
    }'

  aws iam attach-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-arn arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs

  echo "⏳ Wait IAM Role To Be Effective..."
  sleep 10
fi

# Attatch CloudWatch Role
ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text)
echo "🔧 Set API Gateway CloudWatch Role..."
aws apigateway update-account \
  --patch-operations op=replace,path=/cloudwatchRoleArn,value="$ROLE_ARN"


STACK_NAME="WebSocketChatStack"
TEMPLATE_FILE="gateway_cloud_formation.yaml"
STAGE_NAME="prod"
BUCKET_NAME="qts-front"

terraform apply -var="bucket_name=$BUCKET"

WEB_SOCKET_API_ENDPOINT=$(aws cloudformation describe-stacks --stack-name $STACK_NAME \
  --query "Stacks[0].Outputs[?OutputKey=='WebSocketApiEndpoint'].OutputValue" --output text)

echo "WebSocket API Endpoint: $WEB_SOCKET_API_ENDPOINT"

# If S3 bucket already exists
if aws s3api head-bucket --bucket $BUCKET_NAME 2>/dev/null; then
  echo "Bucket $BUCKET_NAME already exists."
else
  echo "Creating bucket $BUCKET_NAME..."
  aws s3 mb s3://$BUCKET_NAME
fi

# Static Web Pages
aws s3 website s3://$BUCKET_NAME/ --index-document index.html

# S3 public access
aws s3api put-public-access-block \
  --bucket $BUCKET_NAME \
  --public-access-block-configuration \
  "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"

aws s3api put-bucket-policy --bucket $BUCKET_NAME --policy file://bucket_policy.json

# Replace <WEB_SOCKET_API_ENDPOINT> with WEB_SOCKET_API_ENDPOINT
TMP_INDEX="index.tmp.html"
sed "s|<WEB_SOCKET_API_ENDPOINT>|$WEB_SOCKET_API_ENDPOINT|g" index.html > $TMP_INDEX

aws s3 cp $TMP_INDEX s3://$BUCKET_NAME/index.html

rm $TMP_INDEX

echo "Frontend deployed to bucket $BUCKET_NAME"

# Distribution ID
S3_ORIGIN="$BUCKET_NAME.s3.amazonaws.com"
DISTRIBUTION_ID=$(aws cloudfront list-distributions \
  --query "DistributionList.Items[?Origins.Items[0].DomainName=='${S3_ORIGIN}'].Id" \
  --output text)

if [ -z "$DISTRIBUTION_ID" ]; then
  echo "❌ No CloudFront Distribution found for ${S3_ORIGIN} "
  exit 1
fi

# Invalidate static html pages
INVALIDATION_ID=$(aws cloudfront create-invalidation \
  --distribution-id "$DISTRIBUTION_ID" \
  --paths "/*" \
  --query "Invalidation.Id" \
  --output text)

# S3 frontend URL
if [[ "$REGION" == "us-east-1" ]]; then
  WEBSITE_URL="https://${BUCKET_NAME}.s3-website.amazonaws.com"
else
  WEBSITE_URL="https://${BUCKET_NAME}.s3-website-${REGION}.amazonaws.com"
fi

FRONT_URL=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query "Stacks[0].Outputs[?OutputKey=='CloudFrontDistributionDomainName'].OutputValue" \
  --output text)
echo "Frontend website URL: $FRONT_URL"

HTTP_API_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query "Stacks[0].Outputs[?OutputKey=='HttpApiEndpoint'].OutputValue" \
  --output text)
echo "HTTP Push API: $HTTP_API_ENDPOINT"
DOCKER_ENV="../docker/.env"
cat $DOCKER_ENV | sed "s|HTTP_API_ENDPOINT=.*|HTTP_API_ENDPOINT=$HTTP_API_ENDPOINT|g" > $DOCKER_ENV.tmp
mv $DOCKER_ENV.tmp $DOCKER_ENV
export HTTP_API_ENDPOINT=$HTTP_API_ENDPOINT
