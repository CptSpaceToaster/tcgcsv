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
        "s3:ListBucket"
    ]

    resources = [
      "${aws_s3_bucket.tcgplayer_json_csv_vault.arn}"
    ]
  }

  statement {
    actions = [
      "s3:PutObject",
      "s3:PutObjectAcl",
      "s3:GetObject",
      "s3:GetObjectAcl",
      "s3:DeleteObject",
    ]

    resources = [
      "${aws_s3_bucket.tcgplayer_json_csv_vault.arn}/*"
    ]
  }

  statement {
    actions = [
      "cloudfront:CreateInvalidation"
    ]

    resources = [
      "${aws_cloudfront_distribution.s3_distribution.arn}"
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
