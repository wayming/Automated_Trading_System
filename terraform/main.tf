

#####################
# DynamoDB tables
#####################
resource "aws_dynamodb_table" "websocket_connections" {
  name         = "WebSocketConnections"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "connectionId"

  attribute {
    name = "connectionId"
    type = "S"
  }

  tags = {
    Name = "WebSocketConnections"
  }
}

resource "aws_dynamodb_table" "analysis_messages" {
  name         = "AnalysisMessages"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "partitionKey"
  range_key    = "timestamp"

  attribute {
    name = "partitionKey"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "N"
  }

  tags = {
    Name = "AnalysisMessages"
  }
}

#####################
# IAM role for Lambdas (execution)
#####################
data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      identifiers = ["lambda.amazonaws.com"]
      type        = "Service"
    }
  }
}

resource "aws_iam_role" "lambda_execution" {
  name               = "WebSocketLambdaExecutionRole"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

# Attach AWSLambdaBasicExecutionRole managed policy
resource "aws_iam_role_policy_attachment" "lambda_basic_exec" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Inline policy allowing DynamoDB ops, ManageConnections and message table ops
data "aws_iam_policy_document" "lambda_policy_doc" {
  statement {
    sid     = "DynamoPermissionsConnections"
    actions = ["dynamodb:PutItem", "dynamodb:DeleteItem", "dynamodb:Scan"]
    resources = [
      aws_dynamodb_table.websocket_connections.arn
    ]
    effect = "Allow"
  }

  statement {
    sid     = "ManageConnections"
    actions = ["execute-api:ManageConnections"]
    resources = [
      # wildcard: will be interpolated via AWS api id later through a separate policy resource because api id unknown yet
      "*"
    ]
    effect = "Allow"
  }

  statement {
    sid     = "MessagesTable"
    actions = ["dynamodb:PutItem", "dynamodb:Query", "dynamodb:DeleteItem"]
    resources = [
      aws_dynamodb_table.analysis_messages.arn
    ]
    effect = "Allow"
  }
}

resource "aws_iam_role_policy" "lambda_inline_policy" {
  name   = "WebSocketLambdaPolicy"
  role   = aws_iam_role.lambda_execution.id
  policy = data.aws_iam_policy_document.lambda_policy_doc.json
}

#####################
# API Gateway v2 - WebSocket
#####################
resource "aws_apigatewayv2_api" "websocket_api" {
  name                      = "WebSocketChatApi"
  protocol_type             = "WEBSOCKET"
  route_selection_expression = "$request.body.action"
}

#####################
# Api Gateway v2 - HTTP (for POST /send)
#####################
resource "aws_apigatewayv2_api" "http_api" {
  name          = "HttpPushApi"
  protocol_type = "HTTP"
}

#####################
# Lambda functions (pack inline code into zip using archive_file)
#####################

# HandleConnectFunction code (inline from CloudFormation)
data "archive_file" "handle_connect_zip" {
  type        = "zip"
  output_path = "${path.module}/handle_connect.zip"
  source {
    content  = <<PY
import boto3, os, json
from boto3.dynamodb.conditions import Key

ddb = boto3.resource('dynamodb')
lambda_client = boto3.client('lambda')
connections_table = ddb.Table(os.environ['CONNECTIONS_TABLE'])

def lambda_handler(event, context):
    connection_id = event['requestContext']['connectionId']
    print(f"New connection: {connection_id}")
    try:
        connections_table.put_item(Item={'connectionId': connection_id})
    except Exception as e:
        print(f"Failed to save connection: {e}")
        return {'statusCode': 500, 'body': 'DB Error'}

    try:
        lambda_client.invoke(
            FunctionName=os.environ['ASYNC_CONNECT_WORKER'],
            InvocationType='Event',
            Payload=json.dumps({'connectionId': connection_id})
        )
    except Exception as e:
        print(f"Failed to invoke async worker: {e}")
    return {'statusCode': 200}
PY
    filename = "index.py"
  }
}

resource "aws_lambda_function" "handle_connect" {
  function_name = "HandleConnectFunction"
  filename      = data.archive_file.handle_connect_zip.output_path
  source_code_hash = data.archive_file.handle_connect_zip.output_base64sha256
  handler       = "index.lambda_handler"
  runtime       = "python3.9"
  role          = aws_iam_role.lambda_execution.arn

  environment {
    variables = {
      CONNECTIONS_TABLE     = aws_dynamodb_table.websocket_connections.name
      MESSAGES_TABLE        = aws_dynamodb_table.analysis_messages.name
      API_GATEWAY_ID        = aws_apigatewayv2_api.websocket_api.id
      CURR_AWS_REGION       = var.region
      STAGE                 = var.stage_name
      ASYNC_CONNECT_WORKER  = aws_lambda_function.post_connect_worker.function_name
    }
  }
}

# HandleDisconnectFunction
data "archive_file" "handle_disconnect_zip" {
  type        = "zip"
  output_path = "${path.module}/handle_disconnect.zip"
  source {
    content  = <<PY
import boto3
import os
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])
def lambda_handler(event, context):
    connectionId = event['requestContext']['connectionId']
    table.delete_item(Key={'connectionId': connectionId})
    return {'statusCode': 200}
PY
    filename = "index.py"
  }
}

resource "aws_lambda_function" "handle_disconnect" {
  function_name = "HandleDisconnectFunction"
  filename      = data.archive_file.handle_disconnect_zip.output_path
  source_code_hash = data.archive_file.handle_disconnect_zip.output_base64sha256
  handler       = "index.lambda_handler"
  runtime       = "python3.9"
  role          = aws_iam_role.lambda_execution.arn

  environment {
    variables = {
      TABLE_NAME = aws_dynamodb_table.websocket_connections.name
    }
  }
}

# PostConnectWorkerFunction
data "archive_file" "post_connect_worker_zip" {
  type        = "zip"
  output_path = "${path.module}/post_connect_worker.zip"
  source {
    content  = <<PY
import boto3, os, json, time
from boto3.dynamodb.conditions import Key

def lambda_handler(event, context):
    connection_id = event.get('connectionId')
    print(f"Async PostConnectWorker: {connection_id}")

    ddb = boto3.resource('dynamodb')
    msg_table = ddb.Table(os.environ['MESSAGES_TABLE'])

    gateway_url = f"https://{os.environ['API_GATEWAY_ID']}.execute-api.{os.environ['CURR_AWS_REGION']}.amazonaws.com/{os.environ['STAGE']}"
    apigw = boto3.client('apigatewaymanagementapi', endpoint_url=gateway_url)

    try:
        response = msg_table.query(
            KeyConditionExpression=Key('partitionKey').eq('global'),
            ScanIndexForward=False,
            Limit=10
        )
        messages = response.get('Items', [])[::-1]
        for msg in messages:
            apigw.post_to_connection(
                ConnectionId=connection_id,
                Data=msg['message'].encode('utf-8')
            )
    except apigw.exceptions.GoneException:
        print(f"Connection {connection_id} is gone.")
    except Exception as e:
        print(f"Error sending: {e}")
PY
    filename = "index.py"
  }
}

resource "aws_lambda_function" "post_connect_worker" {
  function_name = "PostConnectWorkerFunction"
  filename      = data.archive_file.post_connect_worker_zip.output_path
  source_code_hash = data.archive_file.post_connect_worker_zip.output_base64sha256
  handler       = "index.lambda_handler"
  runtime       = "python3.9"
  role          = aws_iam_role.lambda_execution.arn

  environment {
    variables = {
      MESSAGES_TABLE  = aws_dynamodb_table.analysis_messages.name
      API_GATEWAY_ID  = aws_apigatewayv2_api.websocket_api.id
      CURR_AWS_REGION = var.region
      STAGE           = var.stage_name
    }
  }
}

# HandleSendMessageFunction
data "archive_file" "handle_send_message_zip" {
  type        = "zip"
  output_path = "${path.module}/handle_send_message.zip"
  source {
    content  = <<PY
import boto3
import os
import json
import time
from boto3.dynamodb.conditions import Key

ddb = boto3.resource('dynamodb')
conn_table = ddb.Table(os.environ['CONNECTIONS_TABLE'])
msg_table = ddb.Table(os.environ['MESSAGES_TABLE'])

gateway_url = f"https://{os.environ['API_GATEWAY_ID']}.execute-api.{os.environ['CURR_AWS_REGION']}.amazonaws.com/{os.environ['STAGE']}"
apigw_client = boto3.client('apigatewaymanagementapi', endpoint_url=gateway_url)
print(f"API Gateway endpoint URL: {gateway_url}")

def lambda_handler(event, context):
    try:
        # Read body as raw string
        message = event.get('body', '')
        if not message:
            return {'statusCode': 400, 'body': 'Empty message body'}
    except Exception as e:
        return {'statusCode': 400, 'body': f"Error reading message: {str(e)}"}

    timestamp = int(time.time() * 1000)
    msg_item = {
        'partitionKey': 'global',
        'timestamp': timestamp,
        'message': message  # Store as-is
    }

    print("Storing message:", msg_item)

    try:
        msg_table.put_item(Item=msg_item)
    except Exception as e:
        print("Error writing to DynamoDB:", str(e))
        return {'statusCode': 500, 'body': 'Failed to write message'}

    # Trim to latest 10 messages
    messages = msg_table.query(
        KeyConditionExpression=Key('partitionKey').eq('global'),
        ScanIndexForward=True  # oldest first
    )['Items']

    if len(messages) > 10:
        for old in messages[:-10]:
            msg_table.delete_item(
                Key={
                    'partitionKey': 'global',
                    'timestamp': old['timestamp']
                }
            )

    # Send to all connections
    connections = conn_table.scan(ProjectionExpression='connectionId')['Items']
    for connection in connections:
        try:
            print(f"Send message to {connection['connectionId']}")
            apigw_client.post_to_connection(
                ConnectionId=connection['connectionId'],
                Data=message.encode('utf-8')
            )
        except apigw_client.exceptions.GoneException:
            conn_table.delete_item(Key={'connectionId': connection['connectionId']})

    return {'statusCode': 200}
PY
    filename = "index.py"
  }
}

resource "aws_lambda_function" "handle_send_message" {
  function_name = "HandleSendMessageFunction"
  filename      = data.archive_file.handle_send_message_zip.output_path
  source_code_hash = data.archive_file.handle_send_message_zip.output_base64sha256
  handler       = "index.lambda_handler"
  runtime       = "python3.9"
  role          = aws_iam_role.lambda_execution.arn

  environment {
    variables = {
      CONNECTIONS_TABLE = aws_dynamodb_table.websocket_connections.name
      MESSAGES_TABLE    = aws_dynamodb_table.analysis_messages.name
      API_GATEWAY_ID    = aws_apigatewayv2_api.websocket_api.id
      CURR_AWS_REGION   = var.region
      STAGE             = var.stage_name
    }
  }
}

#####################
# Grant Lambda invocation permissions from API Gateway
#####################
resource "aws_lambda_permission" "allow_apigw_invoke_connect" {
  statement_id  = "AllowAPIGWInvokeConnect"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.handle_connect.function_name
  principal     = "apigateway.amazonaws.com"
  # SourceArn should reference execute-api ARN pattern for the websocket API
  source_arn = "arn:aws:execute-api:${var.region}:${data.aws_caller_identity.current.account_id}:${aws_apigatewayv2_api.websocket_api.id}/*/$connect"
}

resource "aws_lambda_permission" "allow_apigw_invoke_disconnect" {
  statement_id  = "AllowAPIGWInvokeDisconnect"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.handle_disconnect.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn = "arn:aws:execute-api:${var.region}:${data.aws_caller_identity.current.account_id}:${aws_apigatewayv2_api.websocket_api.id}/*/$disconnect"
}

resource "aws_lambda_permission" "allow_apigw_invoke_send" {
  statement_id  = "AllowAPIGWInvokeSend"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.handle_send_message.function_name
  principal     = "apigateway.amazonaws.com"
  # NOTE: CF original used ${HttpApi} in SourceArn for POST send; for HTTP api use execute-api ARN wildcard
  source_arn = "arn:aws:execute-api:${var.region}:${data.aws_caller_identity.current.account_id}:${aws_apigatewayv2_api.http_api.id}/*/POST/send"
}

data "aws_caller_identity" "current" {}

#####################
# Grant the LambdaExecutionRole permission to invoke PostConnectWorkerFunction (PostConnectWorkerInvokePermission)
#####################
data "aws_iam_policy_document" "allow_invoke_worker" {
  statement {
    actions = ["lambda:InvokeFunction"]
    resources = [aws_lambda_function.post_connect_worker.arn]
    effect = "Allow"
  }
}

resource "aws_iam_policy" "allow_async_invoke_worker_policy" {
  name   = "AllowAsyncInvokeWorker"
  policy = data.aws_iam_policy_document.allow_invoke_worker.json
}

resource "aws_iam_role_policy_attachment" "attach_invoke_worker_policy" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = aws_iam_policy.allow_async_invoke_worker_policy.arn
}

#####################
# API Gateway v2 integrations & routes for WebSocket
#####################
resource "aws_apigatewayv2_integration" "ws_connect_integration" {
  api_id                 = aws_apigatewayv2_api.websocket_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = "arn:aws:apigateway:${var.region}:lambda:path/2015-03-31/functions/${aws_lambda_function.handle_connect.arn}/invocations"
  payload_format_version = "1.0"
}

resource "aws_apigatewayv2_integration" "ws_disconnect_integration" {
  api_id                 = aws_apigatewayv2_api.websocket_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = "arn:aws:apigateway:${var.region}:lambda:path/2015-03-31/functions/${aws_lambda_function.handle_disconnect.arn}/invocations"
  payload_format_version = "1.0"
}

resource "aws_apigatewayv2_integration" "ws_send_integration" {
  api_id                 = aws_apigatewayv2_api.websocket_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = "arn:aws:apigateway:${var.region}:lambda:path/2015-03-31/functions/${aws_lambda_function.handle_send_message.arn}/invocations"
  payload_format_version = "1.0"
}

resource "aws_apigatewayv2_route" "ws_connect_route" {
  api_id    = aws_apigatewayv2_api.websocket_api.id
  route_key = "$connect"
  authorization_type = "NONE"
  target = "integrations/${aws_apigatewayv2_integration.ws_connect_integration.id}"
}

resource "aws_apigatewayv2_route" "ws_disconnect_route" {
  api_id    = aws_apigatewayv2_api.websocket_api.id
  route_key = "$disconnect"
  authorization_type = "NONE"
  target = "integrations/${aws_apigatewayv2_integration.ws_disconnect_integration.id}"
}

resource "aws_apigatewayv2_route" "ws_send_route" {
  api_id    = aws_apigatewayv2_api.websocket_api.id
  route_key = "sendmessage"
  authorization_type = "NONE"
  target = "integrations/${aws_apigatewayv2_integration.ws_send_integration.id}"
}

# Deployment & Stage for WebSocket (AutoDeploy true set by stage auto_deploy)
resource "aws_apigatewayv2_deployment" "ws_deployment" {
  api_id = aws_apigatewayv2_api.websocket_api.id

  # redeploy if any of these change:
  triggers = {
    routes_hash = sha1(join("", [
      aws_apigatewayv2_route.ws_connect_route.id,
      aws_apigatewayv2_route.ws_disconnect_route.id,
      aws_apigatewayv2_route.ws_send_route.id,
    ]))
  }

  depends_on = [
    aws_apigatewayv2_route.ws_connect_route,
    aws_apigatewayv2_route.ws_disconnect_route,
    aws_apigatewayv2_route.ws_send_route
  ]
}

resource "aws_apigatewayv2_stage" "ws_stage" {
  api_id = aws_apigatewayv2_api.websocket_api.id
  name   = var.stage_name
  deployment_id = aws_apigatewayv2_deployment.ws_deployment.id
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.websocket_api_logs.arn
    format = jsonencode({
      requestId = "$context.requestId",
      routeKey  = "$context.routeKey",
      status    = "$context.status"
    })
  }

  default_route_settings {
    data_trace_enabled = true
    logging_level      = "INFO"
  }

  tags = {
    Environment = var.stage_name
  }
}

#####################
# HTTP API integration & route (POST /send)
#####################
resource "aws_apigatewayv2_integration" "http_send_integration" {
  api_id                 = aws_apigatewayv2_api.http_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = "arn:aws:apigateway:${var.region}:lambda:path/2015-03-31/functions/${aws_lambda_function.handle_send_message.arn}/invocations"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "http_send_route" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "POST /send"
  target    = "integrations/${aws_apigatewayv2_integration.http_send_integration.id}"
}

resource "aws_apigatewayv2_stage" "http_stage" {
  api_id = aws_apigatewayv2_api.http_api.id
  name   = var.stage_name
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.http_api_logs.arn
    format = jsonencode({
      requestId = "$context.requestId",
      routeKey  = "$context.routeKey",
      status    = "$context.status"
    })
  }
}

#####################
# CloudWatch Log Groups
#####################
resource "aws_cloudwatch_log_group" "connect_log_group" {
  name              = "/aws/lambda/HandleConnectFunction"
  retention_in_days = 14
  lifecycle {
    prevent_destroy = false
  }
}

resource "aws_cloudwatch_log_group" "disconnect_log_group" {
  name              = "/aws/lambda/HandleDisconnectFunction"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "send_log_group" {
  name              = "/aws/lambda/HandleSendMessageFunction"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "post_connect_worker_log_group" {
  name              = "/aws/lambda/PostConnectWorkerFunction"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "websocket_api_logs" {
  name              = "/aws/apigateway/${aws_apigatewayv2_api.websocket_api.id}"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "http_api_logs" {
  name              = "/aws/apigateway/HttpPushApi-${var.stage_name}"
  retention_in_days = 14
}

#####################
# Api Gateway CloudWatch Role for logging (like ApiGatewayCloudWatchRole in CF)
#####################
data "aws_iam_policy_document" "apigw_logs_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type = "Service"
      identifiers = ["apigateway.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "apigw_cloudwatch_role" {
  name               = "ApiGatewayWebSocketLoggingRole"
  assume_role_policy = data.aws_iam_policy_document.apigw_logs_assume.json
}

data "aws_iam_policy_document" "apigw_log_policy" {
  statement {
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "apigw_log_policy_attach" {
  name = "ApiGatewayLoggingPolicy"
  role = aws_iam_role.apigw_cloudwatch_role.id
  policy = data.aws_iam_policy_document.apigw_log_policy.json
}