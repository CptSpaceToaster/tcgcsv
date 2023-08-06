# https://tcgcsv.com

⚠️ It's a mess in here... please be kind ⚠️

### Project setup

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

To bundle the lambda into a zip: (it's just one file for now):

```
zip bundle.zip main.py
```

To deploy all terraform infrastructure (including the lambda bundles)
```
terraform apply
```

To test the lambda directly:

```
# expander
AWS_SHARED_CREDENTIALS_FILE='~/.aws/personal_credentials' aws lambda invoke --region=us-east-1 --function-name=   output.txt

# csv_writer
AWS_SHARED_CREDENTIALS_FILE='~/.aws/personal_credentials' aws lambda invoke --region=us-east-1 --function-name=tcgplayer_csv_writer output.txt
```

https://cpt.tcgcsv.com/JC63 should redirect to "Bingo" https://www.tcgplayer.com/product/261484

We can store files in S3 and serve them through cloudfront now! 
  - https://d2k043kz2pm3nn.cloudfront.net/categories