resource "aws_apigatewayv2_api" "tcgplayer_json_api" {
  name = "tcgplayer_json"
  protocol_type = "HTTP"
  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "OPTIONS"]
    allow_headers = ["content-type"]
    max_age = 300
  }
}

resource "aws_apigatewayv2_stage" "default" {
  api_id = aws_apigatewayv2_api.tcgplayer_json_api.id
  name   = "$default"
}

resource "aws_apigatewayv2_api_mapping" "mapping" {
  api_id      = aws_apigatewayv2_api.tcgplayer_json_api.id
  domain_name = aws_apigatewayv2_domain_name.cpt.id
  stage       = aws_apigatewayv2_stage.default.id
}

resource "aws_apigatewayv2_integration" "integration" {
  api_id = aws_apigatewayv2_api.tcgplayer_json_api.id
  integration_type = "AWS_PROXY"
  connection_type = "INTERNET"

  integration_method = "POST"
  integration_uri = aws_lambda_function.tcgplayer_json_lambda_expander.invoke_arn
  passthrough_behavior = "WHEN_NO_MATCH"

}

resource "aws_apigatewayv2_route" "route" {
  api_id = aws_apigatewayv2_api.tcgplayer_json_api.id
  route_key = "GET /{shortCode}"

  target = "integrations/${aws_apigatewayv2_integration.integration.id}"
}