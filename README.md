# https://tcgcsv.com

Thanks for taking a look!

### Project setup

The current development environment relies on pyenv & poetry, and some setup instructions I haven't written yet. Please message me on discord if you're looking to get things running, and I can prioritize writing additional instructions to help answer any questions.

To install the AWS CLI
```
brew install awscli - https://formulae.brew.sh/formula/awscli
```

To install terraform
```
brew install terraform - https://formulae.brew.sh/formula/terraform
```

To get AWS credentials on file:
1. Login to https://us-east-1.console.aws.amazon.com/iamv2/home?region=us-east-1#/users
2. Select the account you would like to create credentials for (you may need to create a whole account and add admin permissions to it)
3. Select the "Security credentials" tab
4. Create an Access Key. If an access key has already been created, you may want to either re-use that one (if you can still find it) or regenerate it to prevent extra keys from piling up here
5. I selected that this was an "Application running outside of AWS" but there may be better options here now... like there were for gitlab
6. Keep the page open that allows you to copy & paste the `aws_access_key_id` and `aws_secret_access_key`.
7. verify that the local `~/.aws` directory is empty: `ls -al ~/.aws/` as we don't want to lose or muck up existing credentials
8. in a terminal, run `aws configure`
9. paste in the `aws_access_key_id` and `aws_secret_access_key` when prompted
10. leave the region blank
11. verify that a new file was created: `cat ~/.aws/credentials`
12. for this project, I renamed this file to `mv ~/.aws/credentials ~/.aws/personal_credentials`

Verify that the AWS cli works:
```
AWS_SHARED_CREDENTIALS_FILE='~/.aws/personal_credentials' aws sts get-caller-identity
```

Verify that terraform works with a:
```
terraform plan
```

To deploy all terraform infrastructure (including the lambda bundles)
```
terraform apply
```

To test the lambda directly:

```
AWS_SHARED_CREDENTIALS_FILE='~/.aws/personal_credentials' aws lambda invoke --region=us-east-1 --function-name=tcgcsv_etl --cli-read-timeout 0 output.txt
```

Python dependencies used by the lambda ETL scripts are managed by a `requirements.txt` file. Installing dependencies locally and freezing the results is an easy way to update `requirements.txt`.

```
cd lambda_support_layer
pip install merkle-json -t ./python
pip freeze --path ./python > requirements.txt
```

To update the lambda support layer's archive:

```
# Drop into a docker shell
docker run -v lambda_support_layer:/working -it --rm --entrypoint /bin/bash public.ecr.aws/lambda/python:3.11-arm64

cd /working

# install gcc and python-devel
yum -y install gcc python-devel
rm layer.zip
rm -rf python
pip install --target python -r requirements.txt
exit
cd lambda_support_layer && zip layer.zip -r python
```
