
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