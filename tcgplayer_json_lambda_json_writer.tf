variable "TCGPLAYER_PUBLIC_KEY" {
    type = string
}

variable "TCGPLAYER_PRIVATE_KEY" {
    type = string
}

resource "aws_lambda_layer_version" "lambda_support_layer" {
  filename   = "lambda_support_layer/layer.zip"
  source_code_hash = filebase64sha256("lambda_support_layer/layer.zip")
  layer_name = "lambda_support_layer"

  compatible_runtimes = ["python3.9"]
}

resource "aws_lambda_function" "tcgplayer_json_lambda_csv_writer" {
  filename      = "lambda_csv_writer/bundle.zip"
  function_name = "tcgplayer_csv_writer"
  role          = aws_iam_role.lambda-s3-executor-role.arn
  handler       = "csv_writer.main.lambda_handler"
  timeout       = 900

  source_code_hash = filebase64sha256("lambda_csv_writer/bundle.zip")
  memory_size = 1024
  layers = [aws_lambda_layer_version.lambda_support_layer.arn]

  runtime = "python3.9"

  environment {
    variables = {
      BUCKET_NAME = aws_s3_bucket.tcgplayer_json_csv_vault.bucket
      TCGPLAYER_PUBLIC_KEY = var.TCGPLAYER_PUBLIC_KEY
      TCGPLAYER_PRIVATE_KEY = var.TCGPLAYER_PRIVATE_KEY
      SHORTEN_URL = "https://${aws_apigatewayv2_domain_name.cpt.domain_name}"
    }
  }
}

resource "aws_cloudwatch_event_rule" "csv_writer_lambda_event_rule" {
  name = "csv_writer_lambda_event_rule"
  schedule_expression = "cron(0 0 * * ? *)"
}

resource "aws_cloudwatch_event_target" "csv_writer_lambda_target" {
  arn = aws_lambda_function.tcgplayer_json_lambda_csv_writer.arn
  rule = aws_cloudwatch_event_rule.csv_writer_lambda_event_rule.name
}

resource "aws_lambda_permission" "allow_cloudwatch" {
  statement_id = "AllowExecutionFromCloudWatch"
  action = "lambda:InvokeFunction"
  function_name = aws_lambda_function.tcgplayer_json_lambda_csv_writer.function_name
  principal = "events.amazonaws.com"
  source_arn = aws_cloudwatch_event_rule.csv_writer_lambda_event_rule.arn
}

resource "aws_cloudwatch_log_group" "function_log_group" {
  name = "/aws/lambda/${aws_lambda_function.tcgplayer_json_lambda_csv_writer.function_name}"
  retention_in_days = 1
}