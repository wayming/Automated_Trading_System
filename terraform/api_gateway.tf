
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
# API Gateway v2 integrations & routes for WebSocket
#####################
resource "aws_apigatewayv2_integration" "ws_connect_integration" {
  api_id                 = aws_apigatewayv2_api.websocket_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.lambda_functions["handle_connect"].invoke_arn
  integration_method     = "POST"
  payload_format_version = "1.0"
}

resource "aws_apigatewayv2_integration" "ws_disconnect_integration" {
  api_id                 = aws_apigatewayv2_api.websocket_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.lambda_functions["handle_disconnect"].invoke_arn
  integration_method     = "POST"
  payload_format_version = "1.0"
}

resource "aws_apigatewayv2_integration" "ws_send_integration" {
  api_id                 = aws_apigatewayv2_api.websocket_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.lambda_functions["handle_send_message"].invoke_arn
  integration_method     = "POST"
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
    throttling_burst_limit = 5000
    throttling_rate_limit  = 10000
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
  integration_uri        = "arn:aws:apigateway:${var.region}:lambda:path/2015-03-31/functions/${aws_lambda_function.lambda_functions["handle_send_message"].arn}/invocations"
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

  default_route_settings {
    data_trace_enabled = true
    logging_level      = "INFO"
    throttling_burst_limit = 5000
    throttling_rate_limit  = 10000
  }

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.http_api_logs.arn
    format = jsonencode({
      requestId = "$context.requestId",
      routeKey  = "$context.routeKey",
      status    = "$context.status"
    })
  }
}