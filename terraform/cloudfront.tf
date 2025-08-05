# OAC
resource "aws_cloudfront_origin_access_control" "oac" {
  name        = "${var.bucket_name}-oac"
  description = "OAC for ${var.bucket_name}"
  signing_behavior = "always"
  signing_protocol = "sigv4"
  origin_access_control_origin_type = "s3"
}

# CloudFront distribution
resource "aws_cloudfront_distribution" "cdn" {
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"
  price_class         = "PriceClass_100"

  origin {
    domain_name = aws_s3_bucket.frontend_bucket.bucket_regional_domain_name
    origin_id   = "s3-${var.bucket_name}"

    # 使用 OAC
    origin_access_control_id = aws_cloudfront_origin_access_control.oac.id

    s3_origin_config {}
  }

  default_cache_behavior {
    target_origin_id       = "s3-${var.bucket_name}"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    compress = true
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  # 为保证 Terraform 不会因为 distribution 尚未完全"Deployed"就报错，
  # 我们将在 bucket policy 里使用 depends_on，或分步 apply（见说明）。
}
