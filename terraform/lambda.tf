locals {
  lambdas = {
    handle_connect      = "lambda/handle_connect"
    handle_disconnect   = "lambda/handle_disconnect"
    handle_send_message = "lambda/handle_send_message"
    post_connect_worker = "lambda/post_connect_worker"
  }
  async_connect_worker = "post_connect_worker"
}

# # Execution role for Lambda functions
# resource "aws_iam_role" "lambda_execution" {
#   name = "lambda_execution_role"
#   assume_role_policy = jsonencode({
#     Version = "2012-10-17",
#     Statement = [{
#       Effect = "Allow",
#       Principal = {
#         Service = "lambda.amazonaws.com"
#       },
#       Action = "sts:AssumeRole"
#     }]
#   })
# }
# resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
#   role       = aws_iam_role.lambda_execution.name
#   policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
# }

# # Allow Lambda to invoke other Lambda functions
# data "aws_iam_policy_document" "allow_invoke_worker" {
#   statement {
#     actions   = ["lambda:InvokeFunction"]
#     resources = [aws_lambda_function.lambda_functions["post_connect_worker"].arn]
#     effect    = "Allow"
#   }
# }
# resource "aws_iam_policy" "allow_async_invoke_worker_policy" {
#   name   = "AllowAsyncInvokeWorker"
#   policy = data.aws_iam_policy_document.allow_invoke_worker.json
# }
# resource "aws_iam_role_policy_attachment" "attach_invoke_worker_policy" {
#   role       = aws_iam_role.lambda_execution.name
#   policy_arn = aws_iam_policy.allow_async_invoke_worker_policy.arn
# }


# Lambda functions
data "archive_file" "lambda_zips" {
  for_each = local.lambdas

  type        = "zip"
  source_dir  = each.value
  output_path = "${path.module}/build/${each.key}.zip"
}

resource "aws_lambda_function" "lambda_functions" {
  for_each = local.lambdas

  function_name = each.key
  filename = data.archive_file.lambda_zips[each.key].output_path
  source_code_hash = data.archive_file.lambda_zips[each.key].output_base64sha256

  handler = "index.lambda_handler"
  runtime = "python3.11"
  role    = aws_iam_role.lambda_execution.arn

  environment {
    variables = merge({
      CONNECTIONS_TABLE     = aws_dynamodb_table.websocket_connections.name,
      MESSAGES_TABLE        = aws_dynamodb_table.analysis_messages.name,
      API_GATEWAY_ID        = aws_apigatewayv2_api.websocket_api.id,
      CURR_AWS_REGION       = var.region,
      STAGE                 = var.stage_name,
      ASYNC_CONNECT_WORKER  = local.async_connect_worker,
    },
    each.key == "handle_disconnect" ? {
      TABLE_NAME = aws_dynamodb_table.websocket_connections.name
    } : {})
  }
}

# WebSocket permissions
resource "aws_lambda_permission" "allow_apigw_invoke" {
  for_each = {
    connect            = "$connect"
    disconnect         = "$disconnect"
  }

  statement_id  = "AllowAPIGWInvoke_${each.key}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.lambda_functions["handle_${each.key}"].function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "arn:aws:execute-api:${var.region}:${data.aws_caller_identity.current.account_id}:${aws_apigatewayv2_api.websocket_api.id}/*/${each.value}"
}

# HTTP API permission for send_message
resource "aws_lambda_permission" "allow_apigw_invoke_http_send" {
  statement_id  = "AllowAPIGWInvoke_send_message"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.lambda_functions["handle_send_message"].function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "arn:aws:execute-api:${var.region}:${data.aws_caller_identity.current.account_id}:${aws_apigatewayv2_api.http_api.id}/*/POST/send"
}

data "aws_caller_identity" "current" {}

