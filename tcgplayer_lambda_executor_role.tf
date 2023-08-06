data aws_iam_policy_document lambda_assume_role {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

data aws_iam_policy_document lambda_s3 {
  statement {
    actions = [
      "s3:PutObject",
      "s3:PutObjectAcl"
    ]

    resources = [
      "${aws_s3_bucket.tcgplayer_json_csv_vault.arn}/*"
    ]
  }
}

data aws_iam_policy_document lambda_logs {
  statement {
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]

    resources = [
      "arn:aws:logs:*:*:*"
    ]
  }
}


# Vanilla AWS IAM role (default)
resource aws_iam_role lambda-executor-role {
  name = "lambda-executor-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

# AWS IAM role with s3 write privlages... useful for writing into one s3 bucket in particular :P
resource aws_iam_role lambda-s3-executor-role {
  name = "lambda-s3-executor-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource aws_iam_policy lambda_s3 {
  name  = "lambda-s3-permissions"
  description = "Contains S3 put permission for lambda"
  policy = data.aws_iam_policy_document.lambda_s3.json
}

resource aws_iam_role_policy_attachment lambda_s3 {
  role = aws_iam_role.lambda-s3-executor-role.name
  policy_arn = aws_iam_policy.lambda_s3.arn
}

resource aws_iam_policy lambda_can_log {
  name  = "lambda-logger-permissions"
  policy = data.aws_iam_policy_document.lambda_logs.json
}

resource "aws_iam_role_policy_attachment" "function_logging_policy_attachment" {
  role = aws_iam_role.lambda-s3-executor-role.name
  policy_arn = aws_iam_policy.lambda_can_log.arn
}



# Bucket level policies
data "aws_iam_policy_document" "bucket_policy" {
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

# Applying the bucket level policies
resource "aws_s3_bucket_policy" "allow_access_from_cloudfront" {
  bucket = aws_s3_bucket.tcgplayer_json_csv_vault.id
  policy = data.aws_iam_policy_document.bucket_policy.json
}