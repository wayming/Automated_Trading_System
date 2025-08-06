resource "aws_cloudfront_distribution" "frontend_cf" {
  enabled             = true
  default_root_object = "index.html"

  origin {
    domain_name = aws_s3_bucket.frontend_bucket.bucket_regional_domain_name
    origin_id   = "QtsS3Origin"
    s3_origin_config {
      origin_access_identity = "" # 若使用 OAC/OAI，这里需替换
    }
  }

  default_cache_behavior {
    target_origin_id       = "QtsS3Origin"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }
  }

  price_class = "PriceClass_100"

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  # 必须加的块
  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }
}
