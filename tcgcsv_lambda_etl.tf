variable "TCGPLAYER_PUBLIC_KEY" {
    type = string
}

variable "TCGPLAYER_PRIVATE_KEY" {
    type = string
}

variable "TCGCSV_DISCORD_WEBHOOK" {
    type = string
}

resource "aws_lambda_layer_version" "lambda_support_layer" {
  filename   = "lambda_support_layer/layer.zip"
  source_code_hash = filebase64sha256("lambda_support_layer/layer.zip")
  layer_name = "lambda_support_layer"

  compatible_runtimes = ["python3.11"]
}

resource "aws_lambda_function" "tcgcsv_lambda_etl" {
  filename      = "lambda_tcgplayer_etl/bundle.zip"
  function_name = "tcgcsv_etl"
  role          = aws_iam_role.lambda-s3-executor-role.arn
  handler       = "tcgplayer_etl.main.lambda_handler"
  timeout       = 900
  memory_size   = 1024
  architectures = ["arm64"]
  layers        = [aws_lambda_layer_version.lambda_support_layer.arn]

  source_code_hash = filebase64sha256("lambda_tcgplayer_etl/bundle.zip")

  runtime = "python3.11"

  environment {
    variables = {
      TCGCSV_TCGPLAYER_VAULT_BUCKET_NAME = aws_s3_bucket.tcgcsv_tcgplayer_vault.bucket
      TCGCSV_FRONTEND_BUCKET_NAME = aws_s3_bucket.tcgcsv_frontend.bucket
      TCGCSV_ARCHIVE_BUCKET_NAME = aws_s3_bucket.tcgcsv_archive.bucket
      TCGPLAYER_PUBLIC_KEY = var.TCGPLAYER_PUBLIC_KEY
      TCGPLAYER_PRIVATE_KEY = var.TCGPLAYER_PRIVATE_KEY
      TCGCSV_SHORTEN_DOMAIN = "https://${aws_apigatewayv2_domain_name.cpt.domain_name}"
      TCGCSV_DISTRIBUTION_ID = aws_cloudfront_distribution.s3_distribution.id
      TCGCSV_DISCORD_WEBHOOK = var.TCGCSV_DISCORD_WEBHOOK
    }
  }
}

resource "aws_cloudwatch_event_rule" "tcgcsv_etl_lambda_event_rule" {
  name = "tcgcsv_etl_lambda_event_rule"
  schedule_expression = "cron(0 20 * * ? *)" // Every day at 20:00 UTC which is 4:00 PM EST
}

resource "aws_cloudwatch_event_target" "tcgcsv_etl_lambda_target" {
  arn = aws_lambda_function.tcgcsv_lambda_etl.arn
  rule = aws_cloudwatch_event_rule.tcgcsv_etl_lambda_event_rule.name
}

resource "aws_lambda_permission" "allow_cloudwatch" {
  statement_id = "AllowExecutionFromCloudWatch"
  action = "lambda:InvokeFunction"
  function_name = aws_lambda_function.tcgcsv_lambda_etl.function_name
  principal = "events.amazonaws.com"
  source_arn = aws_cloudwatch_event_rule.tcgcsv_etl_lambda_event_rule.arn
}

resource "aws_cloudwatch_log_group" "function_log_group" {
  name = "/aws/lambda/${aws_lambda_function.tcgcsv_lambda_etl.function_name}"
  retention_in_days = 1
}
