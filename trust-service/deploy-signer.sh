#!/bin/bash

set -e

REGION="us-east-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
FUNCTION_NAME="salsag-signer"
REPO_NAME="salsag-signer"
BUCKET="mics295-pipeline-artifacts-bucket"
TABLE="trust-ledger"

echo "🚀 Deploying Lambda Signing Service"
echo "Account: $ACCOUNT_ID"
echo "Region: $REGION"

# Step 1: Create KMS key
echo ""
echo "📝 Step 1: Creating KMS key..."
KMS_KEY_ID=$(aws kms create-key \
  --key-usage SIGN_VERIFY \
  --key-spec ECC_NIST_P256 \
  --description "SalsaG artifact signing key" \
  --region $REGION \
  --query 'KeyMetadata.KeyId' \
  --output text 2>/dev/null || aws kms list-keys --region $REGION --query 'Keys[0].KeyId' --output text)

echo "✅ KMS Key: $KMS_KEY_ID"

# Step 2: Create ECR repository
echo ""
echo "📦 Step 2: Creating ECR repository..."
aws ecr create-repository --repository-name $REPO_NAME --region $REGION 2>/dev/null || echo "Repository already exists"

# Step 3: Build and push Docker image
echo ""
echo "🐳 Step 3: Building Docker image..."
docker build --platform linux/amd64 -t $REPO_NAME:latest -f Dockerfile.signer .

echo "🔐 Logging into ECR..."
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com

echo "📤 Pushing image to ECR..."
docker tag $REPO_NAME:latest $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO_NAME:latest
docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO_NAME:latest

# Step 4: Create IAM role
echo ""
echo "👤 Step 4: Creating IAM role..."
ROLE_NAME="lambda-$FUNCTION_NAME-role"

cat > /tmp/trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "lambda.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
EOF

aws iam create-role \
  --role-name $ROLE_NAME \
  --assume-role-policy-document file:///tmp/trust-policy.json \
  2>/dev/null || echo "Role already exists"

# Attach policies
aws iam attach-role-policy \
  --role-name $ROLE_NAME \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

cat > /tmp/lambda-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
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
      "Action": ["dynamodb:PutItem", "dynamodb:UpdateItem"],
      "Resource": "arn:aws:dynamodb:$REGION:$ACCOUNT_ID:table/$TABLE"
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name $ROLE_NAME \
  --policy-name ${FUNCTION_NAME}-policy \
  --policy-document file:///tmp/lambda-policy.json

echo "✅ IAM role created"
sleep 10  # Wait for IAM propagation

# Step 5: Create/Update Lambda function
echo ""
echo "⚡ Step 5: Creating Lambda function..."
ROLE_ARN="arn:aws:iam::$ACCOUNT_ID:role/$ROLE_NAME"
IMAGE_URI="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO_NAME:latest"

aws lambda create-function \
  --function-name $FUNCTION_NAME \
  --package-type Image \
  --code ImageUri=$IMAGE_URI \
  --role $ROLE_ARN \
  --environment Variables="{KMS_KEY_ID=$KMS_KEY_ID,LEDGER_TABLE=$TABLE}" \
  --timeout 60 \
  --memory-size 512 \
  --region $REGION \
  2>/dev/null || \
aws lambda update-function-code \
  --function-name $FUNCTION_NAME \
  --image-uri $IMAGE_URI \
  --region $REGION

aws lambda update-function-configuration \
  --function-name $FUNCTION_NAME \
  --environment Variables="{KMS_KEY_ID=$KMS_KEY_ID,LEDGER_TABLE=$TABLE}" \
  --region $REGION

echo "✅ Lambda function deployed"

# Step 6: Configure S3 trigger
echo ""
echo "🪣 Step 6: Configuring S3 trigger..."

# Add Lambda permission
aws lambda add-permission \
  --function-name $FUNCTION_NAME \
  --statement-id s3-trigger \
  --action lambda:InvokeFunction \
  --principal s3.amazonaws.com \
  --source-arn arn:aws:s3:::$BUCKET \
  --region $REGION \
  2>/dev/null || echo "Permission already exists"

# Create S3 notification config
cat > /tmp/s3-notification.json <<EOF
{
  "LambdaFunctionConfigurations": [{
    "LambdaFunctionArn": "arn:aws:lambda:$REGION:$ACCOUNT_ID:function:$FUNCTION_NAME",
    "Events": ["s3:ObjectCreated:*"],
    "Filter": {
      "Key": {
        "FilterRules": [{
          "Name": "suffix",
          "Value": ".tgz"
        }]
      }
    }
  }]
}
EOF

aws s3api put-bucket-notification-configuration \
  --bucket $BUCKET \
  --notification-configuration file:///tmp/s3-notification.json

echo "✅ S3 trigger configured"

echo ""
echo "🎉 Deployment complete!"
echo ""
echo "📋 Summary:"
echo "  Function: $FUNCTION_NAME"
echo "  KMS Key: $KMS_KEY_ID"
echo "  Trigger: s3://$BUCKET/*.tgz"
echo ""
echo "🧪 Test by uploading a .tgz file to S3:"
echo "  aws s3 cp test.tgz s3://$BUCKET/"
