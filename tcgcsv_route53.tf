resource "aws_route53_zone" "primary" {
  name = "tcgcsv.com"
}

import {
  to = aws_route53_zone.primary
  id = "Z00309973CD4FK0ZEQEP3"
}



resource "aws_acm_certificate" "primary_cert" {
  domain_name = aws_route53_zone.primary.name
  subject_alternative_names = ["cpt.${aws_route53_zone.primary.name}"]
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.primary_cert.domain_validation_options: dvo.domain_name => {
      name = dvo.resource_record_name
      record = dvo.resource_record_value
      type = dvo.resource_record_type
    }
  }
  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = aws_route53_zone.primary.zone_id
}

resource "aws_acm_certificate_validation" "cert" {
  certificate_arn         = "${aws_acm_certificate.primary_cert.arn}"
  validation_record_fqdns = [for record in aws_route53_record.cert_validation: record.fqdn]
}



resource "aws_route53_record" "root_A" {
  zone_id = aws_route53_zone.primary.zone_id
  name = aws_route53_zone.primary.name
  type = "A"

  alias {
    name = aws_cloudfront_distribution.s3_distribution.domain_name
    zone_id = aws_cloudfront_distribution.s3_distribution.hosted_zone_id
    evaluate_target_health = false
  }
}

resource "aws_route53_record" "root_AAAA" {
  zone_id = aws_route53_zone.primary.zone_id
  name = aws_route53_zone.primary.name
  type = "AAAA"

  alias {
    name = aws_cloudfront_distribution.s3_distribution.domain_name
    zone_id = aws_cloudfront_distribution.s3_distribution.hosted_zone_id
    evaluate_target_health = false
  }
}



resource "aws_apigatewayv2_domain_name" "cpt" {
  domain_name = "cpt.${aws_route53_zone.primary.name}"

  domain_name_configuration {
    certificate_arn = aws_acm_certificate_validation.cert.certificate_arn
    endpoint_type = "REGIONAL"
    security_policy = "TLS_1_2"
  }
}

resource "aws_route53_record" "cpt_A" {
  zone_id = aws_route53_zone.primary.zone_id
  name = aws_apigatewayv2_domain_name.cpt.domain_name
  type = "A"

  alias {
    name = aws_apigatewayv2_domain_name.cpt.domain_name_configuration[0].target_domain_name
    zone_id = aws_apigatewayv2_domain_name.cpt.domain_name_configuration[0].hosted_zone_id
    evaluate_target_health = false
  }
}