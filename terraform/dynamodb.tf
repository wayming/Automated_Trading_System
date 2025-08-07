

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
