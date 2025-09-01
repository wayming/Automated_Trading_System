resource "kubernetes_config_map" "aws_gateway_env" {
  metadata {
    name      = "aws-gateway-env"
    namespace = "default"
  }

  data = {
    HTTP_API_ENDPOINT = local.http_api_endpoint
  }
}
