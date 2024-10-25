resource "aws_s3_bucket" "tcgplayer_json_csv_vault" {
  bucket = "csv-vault"
}

resource "aws_s3_bucket" "tcgcsv_tcgplayer_vault" {
  bucket = "tcgcsv-tcgplayer-vault"
}

resource "aws_s3_bucket" "tcgcsv_frontend" {
  bucket = "tcgcsv-frontend"
}

resource "aws_s3_bucket" "tcgcsv_archive" {
  bucket = "tcgcsv-archive"
}

# Bucket level policies
# TODO: This is copy-pasted and I should generate this with some sort of terraform function
data "aws_iam_policy_document" "vault_bucket_policy" {
  statement {
    sid       = "AllowCloudFrontServicePrincipalReadOnly"
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.tcgplayer_json_csv_vault.arn}/*"]

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = ["${aws_cloudfront_distribution.s3_distribution.arn}"]
    }
  }
}

data "aws_iam_policy_document" "tcgplayer_vault_bucket_policy" {
  statement {
    sid       = "AllowCloudFrontServicePrincipalReadOnly"
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.tcgcsv_tcgplayer_vault.arn}/*"]

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = ["${aws_cloudfront_distribution.s3_distribution.arn}"]
    }
  }
}

data "aws_iam_policy_document" "frontend_bucket_policy" {
  statement {
    sid       = "AllowCloudFrontServicePrincipalReadOnly"
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.tcgcsv_frontend.arn}/*"]

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = ["${aws_cloudfront_distribution.s3_distribution.arn}"]
    }
  }
}

data "aws_iam_policy_document" "archive_bucket_policy" {
  statement {
    sid       = "AllowCloudFrontServicePrincipalReadOnly"
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.tcgcsv_archive.arn}/*"]

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = ["${aws_cloudfront_distribution.s3_distribution.arn}"]
    }
  }
}

# Applying the bucket level policies
resource "aws_s3_bucket_policy" "allow_access_to_vault_from_cloudfront" {
  bucket = aws_s3_bucket.tcgplayer_json_csv_vault.id
  policy = data.aws_iam_policy_document.vault_bucket_policy.json
}

resource "aws_s3_bucket_policy" "allow_access_to_tcgplayer_vault_from_cloudfront" {
  bucket = aws_s3_bucket.tcgcsv_tcgplayer_vault.id
  policy = data.aws_iam_policy_document.tcgplayer_vault_bucket_policy.json
}

resource "aws_s3_bucket_policy" "allow_access_to_frontend_from_cloudfront" {
  bucket = aws_s3_bucket.tcgcsv_frontend.id
  policy = data.aws_iam_policy_document.frontend_bucket_policy.json
}

resource "aws_s3_bucket_policy" "allow_access_to_archive_from_cloudfront" {
  bucket = aws_s3_bucket.tcgcsv_archive.id
  policy = data.aws_iam_policy_document.archive_bucket_policy.json
}