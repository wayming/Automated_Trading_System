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

ROLE_NAME="ApiGatewayCloudWatchLogsRole"

# 获取 account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# 检查 CloudWatch 日志角色是否存在
ROLE_EXISTS=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text 2>/dev/null || echo "none")

if [ "$ROLE_EXISTS" = "none" ]; then
  echo "🔧 创建 CloudWatch 日志角色: $ROLE_NAME"

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

  echo "⏳ 等待 IAM 角色生效..."
  sleep 10
fi

# 获取 Role ARN
ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text)

# 设置 API Gateway 账户日志角色
echo "🔧 设置 API Gateway CloudWatch 日志角色..."
aws apigateway update-account \
  --patch-operations op=replace,path=/cloudwatchRoleArn,value="$ROLE_ARN"


STACK_NAME="WebSocketChatStack"
TEMPLATE_FILE="gateway_cloud_formation.yaml"
STAGE_NAME="prod"

# echo "Checking if stack $STACK_NAME exists..."

# if aws cloudformation describe-stacks --stack-name $STACK_NAME >/dev/null 2>&1; then
#   echo "Stack $STACK_NAME exists, deleting..."
#   aws cloudformation delete-stack --stack-name $STACK_NAME
#   echo "Waiting for stack deletion to complete..."
#   aws cloudformation wait stack-delete-complete --stack-name $STACK_NAME
#   echo "Previous stack deleted."
# else
#   echo "Stack $STACK_NAME does not exist, no deletion needed."
# fi

# echo "Deploying CloudFormation stack..."

# aws cloudformation deploy \
#   --stack-name $STACK_NAME \
#   --template-file $TEMPLATE_FILE \
#   --capabilities CAPABILITY_NAMED_IAM \
#   --parameter-overrides StageName=$STAGE_NAME

# echo "Deployment complete!"

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

# 获取 CloudFront 分发 ID
S3_ORIGIN="$BUCKET_NAME.s3.amazonaws.com"
DISTRIBUTION_ID=$(aws cloudfront list-distributions \
  --query "DistributionList.Items[?Origins.Items[0].DomainName=='${S3_ORIGIN}'].Id" \
  --output text)

if [ -z "$DISTRIBUTION_ID" ]; then
  echo "❌ No CloudFront Distribution found for ${S3_ORIGIN} "
  exit 1
fi

# 执行失效请求
INVALIDATION_ID=$(aws cloudfront create-invalidation \
  --distribution-id "$DISTRIBUTION_ID" \
  --paths "/*" \
  --query "Invalidation.Id" \
  --output text)


# 生成前端网站访问URL
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
export HTTP_API_ENDPOINT=$HTTP_API_ENDPOINT
