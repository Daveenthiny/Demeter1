# portfolio_project
AWS ReStart Portfolio Project

URL: https://main.dgchwyhaw9222.amplifyapp.com

AWS Deployment Instructions (Using AWS CDK)
These instructions are based on the DemeterAutomation/README.md and the CDK code structure.

Prerequisites:

AWS Account & Credentials: Configured AWS CLI or environment variables with credentials that have permissions to create the necessary resources (ECR, App Runner, Lambda, S3, IAM, Secrets Manager, CloudFormation, etc.). An IAM role with AdministratorAccess or a more fine-grained set of permissions is required for the GitHub Actions deployment role mentioned in the README, and similar permissions are needed for manual CDK deployment.
Node.js & npm: Required for AWS CDK installation.
Python & pip: Required for CDK application code and dependencies.
Docker: Required to build the backend application container image.
Git: Required for cloning the repository (if applicable) and potentially for GitHub Actions.
AWS CDK Toolkit: Install globally: npm install -g aws-cdk

Existing Resources:
An S3 Bucket: You need an existing S3 bucket to store data (CSVs) and embeddings (JSON). The name of this bucket will be passed during deployment.
An AWS Secrets Manager Secret: You need an existing secret containing the admin token used to authenticate the /rebuild-embeddings endpoint. The name of this secret will be passed during deployment.
An ECR Repository: The CDK code attempts to look up an existing ECR repository named demeter-backend. Ensure this repository exists in your target AWS account and region, or modify the CDK code (demeter_stack.py) to create one if it doesn't exist.
A Bedrock Agent: You need an existing Bedrock Agent and an Alias for that agent. Their IDs will be passed during deployment.
Deployment Steps:

Install Python Dependencies:

Navigate to the CDK directory: cd DemeterAutomation/cdk
Install required Python packages for the CDK app: python -m pip install -r requirements.txt 
Build and Push Docker Image:

Navigate to the backend code directory: cd ../../DemeterConsolidated (from the cdk directory)
Build the Docker image (replace <aws_account_id> and <region>):
Bash

docker build -t <aws_account_id>.dkr.ecr.<region>.amazonaws.com/demeter-backend:latest .
Log in to ECR (replace <region>):
Bash

aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <aws_account_id>.dkr.ecr.<region>.amazonaws.com
Push the image to ECR (replace <aws_account_id> and <region>):
Bash

docker push <aws_account_id>.dkr.ecr.<region>.amazonaws.com/demeter-backend:latest
(Note: Using latest tag works but immutable tags like commit hashes are recommended for production deployments).
Bootstrap CDK (If first time using CDK in this account/region):

Navigate back to the CDK directory: cd ../DemeterAutomation/cdk
Run bootstrap (replace <aws_account_id> and <region> if needed, or rely on configured AWS profile):
Bash

cdk bootstrap aws://<aws_account_id>/<region>
(Or simply cdk bootstrap if your AWS CLI profile is set correctly)
Deploy the CDK Stack:

From the DemeterAutomation/cdk directory, run the deploy command.
Replace the placeholder values (<your-s3-bucket-name>, <your-secret-name>, <your-bedrock-agent-id>, <your-bedrock-agent-alias-id>) with your actual resource names/IDs.
Bash

cdk deploy -c dataBucket=<your-s3-bucket-name> \
           -c adminTokenSecretName=<your-secret-name> \
           -c bedrockAgentId=<your-bedrock-agent-id> \
           -c bedrockAgentAliasId=<your-bedrock-agent-alias-id>
           # Optional: -c queryLambdaDataset=YourDatasetName (defaults to FoodItems)
CDK will synthesize a CloudFormation template and deploy the resources defined in demeter_stack.py. Review the changes and confirm the deployment.
Post-Deployment:

The App Runner service URL will be an output of the CDK deployment. This URL is automatically configured as the APP_RUNNER_URL environment variable for the Lambda functions.
The S3 upload triggers the demeter_rebuild_embeddings_lambda, which calls the /rebuild-embeddings endpoint on the App Runner service to generate the initial _bedrock_embedded.json files in the same bucket.
User interacts with the deployed application via the /ask-agent endpoint using the configured Bedrock Agent.
