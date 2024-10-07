resource "aws_cloudfront_cache_policy" "vault_cache" {
  name = "vault-cache"
  default_ttl = 57600 # 16 hours
  max_ttl = 86400 # 24 hours
  min_ttl = 57600 # 16 hours

  parameters_in_cache_key_and_forwarded_to_origin {
    cookies_config {
      cookie_behavior = "none"
    }
    headers_config {
      header_behavior = "none"
    }
    query_strings_config {
      query_string_behavior = "none"
    }
  }
}

resource "aws_cloudfront_response_headers_policy" "allow_cors" {
  name    = "allow-cors"

  cors_config {
    access_control_allow_credentials = true

    access_control_allow_headers {
      items = ["content-type"]
    }

    access_control_allow_methods {
      items = ["GET", "OPTIONS"]
    }

    access_control_allow_origins {
      items = ["*"]
    }

    origin_override = true
  }
}

resource "aws_cloudfront_origin_access_control" "S3_OA" {
  name                              = "S3_OA"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "s3_distribution" {
  origin {
    domain_name = aws_s3_bucket.tcgplayer_json_csv_vault.bucket_regional_domain_name
    origin_id = local.s3_origin_id
    origin_access_control_id = aws_cloudfront_origin_access_control.S3_OA.id
  }

  enabled = true
  is_ipv6_enabled = true
  http_version = "http2and3"
  default_root_object = "index.html"

  aliases = [aws_route53_zone.primary.name]

  default_cache_behavior {
    cache_policy_id = aws_cloudfront_cache_policy.vault_cache.id
    response_headers_policy_id = aws_cloudfront_response_headers_policy.allow_cors.id
    allowed_methods = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = local.s3_origin_id
    viewer_protocol_policy = "redirect-to-https"
  }

  price_class = "PriceClass_100"

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn = aws_acm_certificate.primary_cert.arn
    ssl_support_method = "sni-only"
  }
}
