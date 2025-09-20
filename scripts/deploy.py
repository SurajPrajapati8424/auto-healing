#!/bin/bash
set -e

# Configuration
STACK_NAME="s3-bucket-management-system"
REGION="us-east-1"
ENVIRONMENT="dev"

echo "=== S3 Bucket Management System Deployment ==="
echo "Environment: $ENVIRONMENT"
echo "Region: $REGION"

# Validate AWS CLI configuration
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "❌ Error: AWS CLI not configured. Please run 'aws configure'"
    exit 1
fi

# Check if parameters file exists
if [ ! -f "infrastructure/parameters.json" ]; then
    echo "❌ Error: parameters.json not found. Please create it with your email."
    exit 1
fi

# Validate CloudFormation template
echo "🔍 Validating CloudFormation template..."
aws cloudformation validate-template \
    --template-body file://infrastructure/cloudformation-template.yaml > /dev/null

echo "✅ Template validation successful!"

# Deploy CloudFormation stack
echo "🚀 Deploying CloudFormation stack..."
aws cloudformation deploy \
    --template-file infrastructure/cloudformation-template.yaml \
    --stack-name "${STACK_NAME}-${ENVIRONMENT}" \
    --region $REGION \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameter-overrides file://infrastructure/parameters.json \
    --tags Environment=$ENVIRONMENT Project=BucketManagement

# Get outputs
echo "📊 Getting stack outputs..."
API_ENDPOINT=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}-${ENVIRONMENT}" \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`APIEndpoint`].OutputValue' \
    --output text)

USER_POOL_ID=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}-${ENVIRONMENT}" \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' \
    --output text)

USER_POOL_CLIENT_ID=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}-${ENVIRONMENT}" \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`UserPoolClientId`].OutputValue' \
    --output text)

IDENTITY_POOL_ID=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}-${ENVIRONMENT}" \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`IdentityPoolId`].OutputValue' \
    --output text)

# Create config file for web interface
echo "📝 Creating configuration file..."
cat > web-interface/config.js << EOF
const CONFIG = {
    apiEndpoint: '$API_ENDPOINT',
    region: '$REGION',
    userPoolId: '$USER_POOL_ID',
    userPoolClientId: '$USER_POOL_CLIENT_ID',
    identityPoolId: '$IDENTITY_POOL_ID',
    environment: '$ENVIRONMENT'
};
EOF

echo ""
echo "🎉 Deployment Complete!"
echo "=============================="
echo "API Endpoint: $API_ENDPOINT"
echo "User Pool ID: $USER_POOL_ID"
echo "Client ID: $USER_POOL_CLIENT_ID"
echo "Identity Pool ID: $IDENTITY_POOL_ID"
echo ""
echo "Next steps:"
echo "1. ✉️  Confirm your email subscription in SNS"
echo "2. 👤 Create a test user in Cognito"
echo "3. 🌐 Open web-interface/index.html to test"
echo "4. 🧪 Run tests with: python scripts/test.py"