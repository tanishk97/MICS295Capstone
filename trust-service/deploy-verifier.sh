#!/bin/bash
set -e

REGION="us-east-1"
PROJECT_NAME="salsag-artifact-verifier"
ROLE_NAME="CodeBuildVerifierRole"

echo "🔍 Deploying SalsaG Verifier Service..."

# Create IAM role if it doesn't exist
if ! aws iam get-role --role-name $ROLE_NAME 2>/dev/null; then
  echo "Creating IAM role..."
  aws iam create-role --role-name $ROLE_NAME \
    --assume-role-policy-document '{
      "Version": "2012-10-17",
      "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "codebuild.amazonaws.com"},
        "Action": "sts:AssumeRole"
      }]
    }'
  
  aws iam attach-role-policy --role-name $ROLE_NAME \
    --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess
  
  aws iam attach-role-policy --role-name $ROLE_NAME \
    --policy-arn arn:aws:iam::aws:policy/CloudWatchLogsFullAccess
  
  aws iam put-role-policy --role-name $ROLE_NAME \
    --policy-name DynamoDBReadAccess \
    --policy-document '{
      "Version": "2012-10-17",
      "Statement": [{
        "Effect": "Allow",
        "Action": ["dynamodb:GetItem", "dynamodb:Query"],
        "Resource": "*"
      }]
    }'
  
  sleep 10
fi

ROLE_ARN=$(aws iam get-role --role-name $ROLE_NAME --query 'Role.Arn' --output text)

# Create or update CodeBuild project
if aws codebuild batch-get-projects --names $PROJECT_NAME --query 'projects[0].name' --output text 2>/dev/null | grep -q $PROJECT_NAME; then
  echo "Updating existing CodeBuild project..."
  aws codebuild update-project \
    --name $PROJECT_NAME \
    --source type=NO_SOURCE,buildspec=trust-service/buildspec-verifier.yml \
    --artifacts type=NO_ARTIFACTS \
    --environment type=LINUX_CONTAINER,image=aws/codebuild/standard:5.0,computeType=BUILD_GENERAL1_SMALL \
    --service-role $ROLE_ARN
else
  echo "Creating CodeBuild project..."
  aws codebuild create-project \
    --name $PROJECT_NAME \
    --source type=NO_SOURCE \
    --source-version buildspec-verifier.yml \
    --artifacts type=NO_ARTIFACTS \
    --environment type=LINUX_CONTAINER,image=aws/codebuild/standard:5.0,computeType=BUILD_GENERAL1_SMALL \
    --service-role $ROLE_ARN \
    --cli-input-json file://verifier-project.json
fi

echo "✅ Verifier service deployed!"
echo "📋 To verify an artifact, run:"
echo "   aws codebuild start-build --project-name $PROJECT_NAME --environment-variables-override name=ARTIFACT_KEY,value=index.tgz"
