resource "aws_lambda_function" "tcgplayer_json_lambda_expander" {
  # If the file is not in the current working directory you will need to include a
  # path.module in the filename.
  filename      = "lambda_expander/bundle.zip"
  function_name = "tcgplayer_json_expander"
  role          = aws_iam_role.lambda-executor-role.arn
  handler       = "main.lambda_handler"

  # The filebase64sha256() function is available in Terraform 0.11.12 and later
  # For Terraform 0.11.11 and earlier, use the base64sha256() function and the file() function:
  # source_code_hash = "${base64sha256(file("lambda_function_payload.zip"))}"
  source_code_hash = filebase64sha256("lambda_expander/bundle.zip")

  runtime = "python3.10"

  environment {
    variables = {
      TCGCSV_AFFILIATE_CODE = "pkmntcgdecklist"
    }
  }
}

# Allow lambda to talk to API-Gateway
resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = "${aws_lambda_function.tcgplayer_json_lambda_expander.function_name}"
  principal     = "apigateway.amazonaws.com"

  # The /*/* portion grants access from any method on any resource within the API Gateway "REST API".
  source_arn = "${aws_apigatewayv2_api.tcgplayer_json_api.execution_arn}/*/*"
}
