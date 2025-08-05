# 严格限制 CloudFront 访问，仅允许当前账户下该 distribution 的请求
resource "aws_s3_bucket_policy" "bucket_policy" {
  bucket = aws_s3_bucket.frontend_bucket.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid = "AllowCloudFrontServicePrincipalReadOnly"
        Effect = "Allow"
        Principal = { Service = "cloudfront.amazonaws.com" }
        Action   = "s3:GetObject"
        Resource = "arn:aws:s3:::${aws_s3_bucket.frontend_bucket.id}/*"
        Condition = {
          StringEquals = { "AWS:SourceAccount" = data.aws_caller_identity.current.account_id }
          ArnLike = { "AWS:SourceArn" = "arn:aws:cloudfront::${data.aws_caller_identity.current.account_id}:distribution/${aws_cloudfront_distribution.cdn.id}" }
        }
      }
    ]
  })

  # 强制 Terraform 在创建 bucket policy 时等待 distribution 资源完成创建
  depends_on = [aws_cloudfront_distribution.cdn]
}
