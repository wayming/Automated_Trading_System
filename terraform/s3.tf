data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "frontend_bucket" {
  bucket = var.bucket_name
  acl    = "private"

  versioning {
    enabled = false
  }

  tags = {
    Name = var.bucket_name
    Env  = var.env
  }
}

resource "aws_s3_bucket_public_access_block" "block" {
  bucket = aws_s3_bucket.frontend_bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
