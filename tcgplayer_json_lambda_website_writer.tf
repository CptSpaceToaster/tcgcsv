resource "aws_lambda_function" "tcgplayer_json_lambda_website_writer" {
  filename      = "lambda_website_writer/bundle.zip"
  function_name = "tcgcsv_website_writer"
  role          = aws_iam_role.lambda-s3-executor-role.arn
  handler       = "main.lambda_handler"
  timeout       = 60
  layers = [aws_lambda_layer_version.lambda_support_layer.arn]

  source_code_hash = filebase64sha256("lambda_website_writer/bundle.zip")

  runtime = "python3.9"

  environment {
    variables = {
      BUCKET_NAME = aws_s3_bucket.tcgplayer_json_csv_vault.bucket
      SHORTEN_DOMAIN = "https://${aws_apigatewayv2_domain_name.cpt.domain_name}"
      DISTRIBUTION_ID = aws_cloudfront_distribution.s3_distribution.id
    }
  }
}