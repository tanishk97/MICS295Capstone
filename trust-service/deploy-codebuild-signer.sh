#!/bin/bash

set -e

REGION="us-east-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
PROJECT_NAME="salsag-artifact-signer"
BUCKET="mics295-pipeline-artifacts-bucket"
KMS_KEY_ID="e05bdb66-eeaf-455d-9783-2187c351066c"

echo "🚀 Deploying CodeBuild Signing Service"

# Create IAM role for CodeBuild
echo "📝 Creating IAM role..."
ROLE_NAME="codebuild-$PROJECT_NAME-role"

cat > /tmp/trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "codebuild.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
EOF

aws iam create-role \
  --role-name $ROLE_NAME \
  --assume-role-policy-document file:///tmp/trust-policy.json \
  2>/dev/null || echo "Role already exists"

# Attach policies
cat > /tmp/codebuild-policy.json <<EOF
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
      "Action": ["kms:Sign", "kms:GetPublicKey"],
      "Resource": "arn:aws:kms:$REGION:$ACCOUNT_ID:key/$KMS_KEY_ID"
    },
    {
      "Effect": "Allow",
      "Action": ["dynamodb:PutItem"],
      "Resource": "arn:aws:dynamodb:$REGION:$ACCOUNT_ID:table/trust-ledger"
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name $ROLE_NAME \
  --policy-name ${PROJECT_NAME}-policy \
  --policy-document file:///tmp/codebuild-policy.json

echo "✅ IAM role created"
sleep 5

# Create CodeBuild project
echo "🔨 Creating CodeBuild project..."

cat > /tmp/codebuild-project.json <<EOF
{
  "name": "$PROJECT_NAME",
  "source": {
    "type": "NO_SOURCE",
    "buildspec": "$(cat buildspec-signer.yml | sed 's/"/\\"/g' | tr '\n' ' ')"
  },
  "artifacts": {
    "type": "NO_ARTIFACTS"
  },
  "environment": {
    "type": "LINUX_CONTAINER",
    "image": "aws/codebuild/standard:7.0",
    "computeType": "BUILD_GENERAL1_SMALL",
    "environmentVariables": [
      {"name": "BUCKET_NAME", "value": "$BUCKET"},
      {"name": "KMS_KEY_ID", "value": "$KMS_KEY_ID"}
    ]
  },
  "serviceRole": "arn:aws:iam::$ACCOUNT_ID:role/$ROLE_NAME",
  "timeoutInMinutes": 10
}
EOF

aws codebuild create-project \
  --cli-input-json file:///tmp/codebuild-project.json \
  --region $REGION \
  2>/dev/null || \
aws codebuild update-project \
  --name $PROJECT_NAME \
  --source type=NO_SOURCE,buildspec="$(cat buildspec-signer.yml)" \
  --region $REGION

echo "✅ CodeBuild project created"

# Create EventBridge rule
echo "📅 Creating EventBridge rule..."
RULE_NAME="salsag-s3-trigger-codebuild"

aws events put-rule \
  --name $RULE_NAME \
  --event-pattern "{
    \"source\": [\"aws.s3\"],
    \"detail-type\": [\"Object Created\"],
    \"detail\": {
      \"bucket\": {\"name\": [\"$BUCKET\"]},
      \"object\": {\"key\": [{\"suffix\": \".tgz\"}]}
    }
  }" \
  --state ENABLED \
  --region $REGION

# Add CodeBuild as target
aws events put-targets \
  --rule $RULE_NAME \
  --targets "Id=1,Arn=arn:aws:codebuild:$REGION:$ACCOUNT_ID:project/$PROJECT_NAME,RoleArn=arn:aws:iam::$ACCOUNT_ID:role/service-role/Amazon_EventBridge_Invoke_CodeBuild,Input={\\\"environmentVariablesOverride\\\":[{\\\"name\\\":\\\"ARTIFACT_KEY\\\",\\\"value\\\":\\\"$.detail.object.key\\\"}]}" \
  --region $REGION

echo "✅ EventBridge rule created"

# Enable S3 EventBridge notifications
echo "🪣 Enabling S3 EventBridge notifications..."
aws s3api put-bucket-notification-configuration \
  --bucket $BUCKET \
  --notification-configuration '{
    "EventBridgeConfiguration": {}
  }'

echo ""
echo "🎉 Deployment complete!"
echo ""
echo "📋 Summary:"
echo "  Project: $PROJECT_NAME"
echo "  KMS Key: $KMS_KEY_ID"
echo "  Trigger: S3 EventBridge → CodeBuild"
echo ""
echo "🧪 Test by uploading a .tgz file:"
echo "  aws s3 cp test.tgz s3://$BUCKET/"
