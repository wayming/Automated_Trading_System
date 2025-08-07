

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