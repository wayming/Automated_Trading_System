resource "aws_s3_bucket" "frontend_bucket" {
  bucket = "qts-front-${random_id.suffix.hex}"
  force_destroy = true
}

# ACL 现在单独定义
resource "aws_s3_bucket_acl" "frontend_bucket_acl" {
  bucket = aws_s3_bucket.frontend_bucket.id
  acl    = "public-read" # 测试用，生产请改为 private + OAC
}

# 可选：测试时允许 public 访问
resource "aws_s3_bucket_public_access_block" "public_block" {
  bucket                  = aws_s3_bucket.frontend_bucket.id
  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "random_id" "suffix" {
  byte_length = 4
}