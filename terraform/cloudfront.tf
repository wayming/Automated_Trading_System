resource "aws_cloudfront_distribution" "frontend_cf" {
  enabled = true

  origin {
    domain_name = aws_s3_bucket.frontend_bucket.bucket_regional_domain_name
    origin_id   = "public-s3-origin"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "public-s3-origin"
    viewer_protocol_policy = "redirect-to-https"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }
  }

  default_root_object = "index.html"

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  price_class = "PriceClass_100"

  tags = {
    Environment = "prod"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }
}


resource "aws_cloudfront_origin_access_identity" "oai" {
  comment = "OAI for S3 access"
}
