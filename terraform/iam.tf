
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
