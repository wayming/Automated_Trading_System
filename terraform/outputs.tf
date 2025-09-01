#####################
# Outputs
#####################
output "http_api_endpoint" {
  description = "HTTP API Endpoint URL for POST /send"
  value       = local.http_api_endpoint
}

output "websocket_api_endpoint" {
  description = "WebSocket API Endpoint URL"
  value       = "wss://${aws_apigatewayv2_api.websocket_api.id}.execute-api.${var.region}.amazonaws.com/${var.stage_name}"
}

output "cloudfront_domain_name" {
  description = "CloudFront distribution domain"
  value       = aws_cloudfront_distribution.frontend_cf.domain_name
}
