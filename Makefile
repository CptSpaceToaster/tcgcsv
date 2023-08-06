.PHONY: bundles
bundles: lambda_expander/bundle.zip lambda_csv_writer/bundle.zip lambda_website_writer/bundle.zip
	terraform apply

.PHONY: csv
csv: bundles
	AWS_SHARED_CREDENTIALS_FILE='~/.aws/personal_credentials' aws lambda invoke --region=us-east-1 --function-name=tcgplayer_csv_writer --cli-read-timeout 0 output.txt
	cat output.txt
	
.PHONY: web
web: bundles
	AWS_SHARED_CREDENTIALS_FILE='~/.aws/personal_credentials' aws lambda invoke --region=us-east-1 --function-name=tcgcsv_website_writer --cli-read-timeout 0 output.txt
	cat output.txt

.SECONDEXPANSION:
%/bundle.zip: $$(wildcard %/*.py) $$(wildcard %/*/*.py)
	cd $(dir $@) && zip bundle.zip $(patsubst $(dir $@)%,%,$^)

.PHONY: clean
clean: 
	rm lambda_expander/bundle.zip
	rm lambda_csv_writer/bundle.zip
	rm lambda_website_writer/bundle.zip