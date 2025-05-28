#!/bin/bash

set -e

# 自动获取 AWS 区域
if [ -n "$AWS_REGION" ]; then
  REGION=$AWS_REGION
else
  REGION=$(aws configure get region)
fi

if [ -z "$REGION" ]; then
  echo "Error: AWS region not set. Please set AWS_REGION environment variable or configure default region via 'aws configure'."
  exit 1
fi

STACK_NAME="WebSocketChatStack"
TEMPLATE_FILE="gateway_cloud_formation.yaml"
STAGE_NAME="prod"

echo "Checking if stack $STACK_NAME exists..."

if aws cloudformation describe-stacks --stack-name $STACK_NAME >/dev/null 2>&1; then
  echo "Stack $STACK_NAME exists, deleting..."
  aws cloudformation delete-stack --stack-name $STACK_NAME
  echo "Waiting for stack deletion to complete..."
  aws cloudformation wait stack-delete-complete --stack-name $STACK_NAME
  echo "Previous stack deleted."
else
  echo "Stack $STACK_NAME does not exist, no deletion needed."
fi

echo "Deploying CloudFormation stack..."

aws cloudformation deploy \
  --stack-name $STACK_NAME \
  --template-file $TEMPLATE_FILE \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides StageName=$STAGE_NAME

echo "Deployment complete!"

WEB_SOCKET_API_ENDPOINT=$(aws cloudformation describe-stacks --stack-name $STACK_NAME \
  --query "Stacks[0].Outputs[?OutputKey=='WebSocketApiEndpoint'].OutputValue" --output text)

echo "WebSocket API Endpoint: $WEB_SOCKET_API_ENDPOINT"

BUCKET_NAME="qts-front"

# 检查bucket是否存在
if aws s3api head-bucket --bucket $BUCKET_NAME 2>/dev/null; then
  echo "Bucket $BUCKET_NAME already exists."
else
  echo "Creating bucket $BUCKET_NAME..."
  aws s3 mb s3://$BUCKET_NAME
fi

# 设置静态网站托管
aws s3 website s3://$BUCKET_NAME/ --index-document index.html

# 设置公共访问策略，注意你需要确认是否允许公开访问
aws s3api put-public-access-block \
  --bucket $BUCKET_NAME \
  --public-access-block-configuration \
  "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"

aws s3api put-bucket-policy --bucket $BUCKET_NAME --policy file://bucket_policy.json

# 替换 index.html 中 <WEB_SOCKET_API_ENDPOINT> 为实际的 WEB_SOCKET_API_ENDPOINT
TMP_INDEX="index.tmp.html"
sed "s|<WEB_SOCKET_API_ENDPOINT>|$WEB_SOCKET_API_ENDPOINT|g" index.html > $TMP_INDEX

aws s3 cp $TMP_INDEX s3://$BUCKET_NAME/index.html

rm $TMP_INDEX

echo "Frontend deployed to bucket $BUCKET_NAME"

# 生成前端网站访问URL
if [[ "$REGION" == "us-east-1" ]]; then
  WEBSITE_URL="http://${BUCKET_NAME}.s3-website.amazonaws.com"
else
  WEBSITE_URL="http://${BUCKET_NAME}.s3-website-${REGION}.amazonaws.com"
fi

echo "Frontend website URL: $WEBSITE_URL"

HTTP_API_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name WebSocketChatStack \
  --query "Stacks[0].Outputs[?OutputKey=='HttpApiEndpoint'].OutputValue" \
  --output text)
echo "HTTP Push API: $HTTP_API_ENDPOINT"
