resource "aws_s3_bucket_policy" "bucket_policy" {
  bucket = aws_s3_bucket.frontend_bucket.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "PublicReadGetObject"
      Effect    = "Allow"
      Principal = "*"
      Action    = "s3:GetObject"
      Resource  = "arn:aws:s3:::${aws_s3_bucket.frontend_bucket.id}/*"
    }]
  })

  depends_on = [aws_cloudfront_distribution.frontend_cf]
}