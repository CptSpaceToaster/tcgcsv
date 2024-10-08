.PHONY: bundles
bundles: lambda_url_expander/bundle.zip lambda_tcgplayer_etl/bundle.zip lambda_support_layer/layer.zip
	terraform apply

.PHONY: csv
csv: bundles
	AWS_SHARED_CREDENTIALS_FILE='~/.aws/personal_credentials' aws lambda invoke --region=us-east-1 --function-name=tcgcsv_etl --cli-read-timeout 0 output.txt
	cat output.txt

.PHONY: local
local:
	poetry run python lambda_tcgplayer_etl/tcgplayer_etl/main.py

# TODO: Instructions use docker and are in README...
# lambda_support_layer/layer.zip: lambda_support_layer/requirements.txt
# 	rm lambda_support_layer/layer.zip
# 	rm -rf lambda_support_layer/python
# 	pip install --target lambda_support_layer/python -r lambda_support_layer/requirements.txt
# 	cd lambda_support_layer && zip layer.zip -r python

.SECONDEXPANSION:
%/bundle.zip: $$(wildcard %/*.py) $$(wildcard %/*/*.py)
	cd $(dir $@) && zip bundle.zip $(patsubst $(dir $@)%,%,$^)

.PHONY: clean
clean:
	rm lambda_url_expander/bundle.zip
	rm lambda_tcgplayer_etl/bundle.zip
