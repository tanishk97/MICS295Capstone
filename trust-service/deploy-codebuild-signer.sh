#!/bin/bash
set -e

REGION="us-east-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
PROJECT_NAME="salsag-artifact-signer"
BUCKET="mics295-pipeline-artifacts-bucket"

echo "🔐 Deploying SalsaG Keyless Signing Service..."

# Create IAM role for CodeBuild
echo "📝 Creating IAM role..."
ROLE_NAME="codebuild-$PROJECT_NAME-role"

cat > /tmp/trust-policy.json <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "codebuild.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
POLICY

aws iam create-role \
  --role-name $ROLE_NAME \
  --assume-role-policy-document file:///tmp/trust-policy.json \
  2>/dev/null || echo "Role already exists"

# Attach policies
cat > /tmp/codebuild-policy.json <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "arn:aws:logs:$REGION:$ACCOUNT_ID:log-group:/aws/codebuild/$PROJECT_NAME:*"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::$BUCKET/*"
    },
    {
      "Effect": "Allow",
      "Action": ["dynamodb:PutItem"],
      "Resource": "arn:aws:dynamodb:$REGION:$ACCOUNT_ID:table/trust-ledger"
    }
  ]
}
POLICY

aws iam put-role-policy \
  --role-name $ROLE_NAME \
  --policy-name ${PROJECT_NAME}-policy \
  --policy-document file:///tmp/codebuild-policy.json

echo "✅ IAM role created"
sleep 5

# Update CodeBuild project
echo "🔨 Updating CodeBuild project..."
aws codebuild update-project \
  --name $PROJECT_NAME \
  --source type=NO_SOURCE,buildspec="$(cat buildspec-signer.yml)" \
  --environment type=LINUX_CONTAINER,image=aws/codebuild/standard:7.0,computeType=BUILD_GENERAL1_SMALL,environmentVariables="[{name=BUCKET_NAME,value=$BUCKET}]" \
  --region $REGION \
  2>/dev/null || echo "Project doesn't exist, will be created by salsaG CLI"

echo ""
echo "✅ Keyless signing service deployed!"
echo "📋 No keys to manage - uses Sigstore keyless signing"
echo ""
echo "To sign an artifact:"
echo "  aws codebuild start-build --project-name $PROJECT_NAME --environment-variables-override name=ARTIFACT_KEY,value=index.tgz"
