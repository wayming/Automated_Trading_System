#!/bin/bash

set -e

STACK_NAME="WebSocketChatStack"
TEMPLATE_FILE="gateway_cloud_formation.yaml"
STAGE_NAME="prod"

echo "Deploying CloudFormation stack..."

aws cloudformation deploy \
  --stack-name $STACK_NAME \
  --template-file $TEMPLATE_FILE \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides StageName=$STAGE_NAME

echo "Deployment complete!"

API_ENDPOINT=$(aws cloudformation describe-stacks --stack-name $STACK_NAME \
  --query "Stacks[0].Outputs[?OutputKey=='WebSocketApiEndpoint'].OutputValue" --output text)

echo "WebSocket API Endpoint: $API_ENDPOINT"
