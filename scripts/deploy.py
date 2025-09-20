#!/usr/bin/env python3
import subprocess
import sys
import json
import re
import os

# Configuration
STACK_NAME = "s3-bucket-management-system"
REGION = "us-east-1"
ENVIRONMENT = "dev"

def run_command(command):
    """Run a command and return the result"""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error: {result.stderr}")
            return None
        return result.stdout.strip()
    except Exception as e:
        print(f"Error running command: {e}")
        return None

def main():
    print("=== S3 Bucket Management System Deployment ===")
    print(f"Environment: {ENVIRONMENT}")
    print(f"Region: {REGION}")

    # Validate AWS CLI configuration
    print("Checking AWS CLI configuration...")
    result = run_command("aws sts get-caller-identity")
    if not result:
        print("❌ Error: AWS CLI not configured. Please run 'aws configure'")
        sys.exit(1)
    print("✅ AWS CLI configured correctly")

    # Check if parameters file exists - Fixed path
    params_file = os.path.join("infrastructure", "parameters.json")
    try:
        with open(params_file, 'r') as f:
            params = json.load(f)
            print(f"✅ Using email: {params['NotificationEmail']}")
    except FileNotFoundError:
        print(f"❌ Error: parameters.json not found at {params_file}")
        print("Please create the file infrastructure\\parameters.json with your email")
        sys.exit(1)

    # Check if CloudFormation template exists
    template_file = os.path.join("infrastructure", "cloudformation-template.yaml")
    if not os.path.exists(template_file):
        print(f"❌ Error: CloudFormation template not found at {template_file}")
        print("Please create the file infrastructure\\cloudformation-template.yaml")
        sys.exit(1)

    # Validate CloudFormation template - Fixed path
    print("🔍 Validating CloudFormation template...")
    validate_cmd = f'aws cloudformation validate-template --template-body "file://{template_file}"'
    result = run_command(validate_cmd)
    if not result:
        sys.exit(1)
    print("✅ Template validation successful!")

    # Deploy CloudFormation stack - Fixed path
    print("🚀 Deploying CloudFormation stack...")
    deploy_cmd = f'''aws cloudformation deploy --template-file "{template_file}" --stack-name {STACK_NAME}-{ENVIRONMENT} --region {REGION} --capabilities CAPABILITY_NAMED_IAM --parameter-overrides NotificationEmail={params['NotificationEmail']} Environment={ENVIRONMENT} --tags Environment={ENVIRONMENT} Project=BucketManagement'''
    
    result = run_command(deploy_cmd)
    if result is None:
        print("❌ Deployment failed")
        sys.exit(1)
    print("✅ Deployment successful!")

    # Get stack outputs
    print("📊 Getting stack outputs...")
    outputs_cmd = f"aws cloudformation describe-stacks --stack-name {STACK_NAME}-{ENVIRONMENT} --region {REGION} --query Stacks[0].Outputs"
    result = run_command(outputs_cmd)
    
    if result:
        outputs = json.loads(result)
        
        # Extract values
        api_endpoint = next((o['OutputValue'] for o in outputs if o['OutputKey'] == 'APIEndpoint'), '')
        user_pool_id = next((o['OutputValue'] for o in outputs if o['OutputKey'] == 'UserPoolId'), '')
        user_pool_client_id = next((o['OutputValue'] for o in outputs if o['OutputKey'] == 'UserPoolClientId'), '')
        identity_pool_id = next((o['OutputValue'] for o in outputs if o['OutputKey'] == 'IdentityPoolId'), '')

        # Create config file for web interface - Fixed path
        print("📝 Creating configuration file...")
        config_content = f"""const CONFIG = {{
    apiEndpoint: '{api_endpoint}',
    region: '{REGION}',
    userPoolId: '{user_pool_id}',
    userPoolClientId: '{user_pool_client_id}',
    identityPoolId: '{identity_pool_id}',
    environment: '{ENVIRONMENT}'
}};"""

        config_file = os.path.join('web-interface', 'config.js')
        with open(config_file, 'w') as f:
            f.write(config_content)

        print("\n🎉 Deployment Complete!")
        print("=" * 50)
        print(f"API Endpoint: {api_endpoint}")
        print(f"User Pool ID: {user_pool_id}")
        print(f"Client ID: {user_pool_client_id}")
        print(f"Identity Pool ID: {identity_pool_id}")
        print("\nNext steps:")
        print("1. ✉️  Confirm your email subscription in SNS")
        print("2. 👤 Create a test user: python scripts\\user_management.py create your-email@example.com Password123! \"Your Name\"")
        print("3. 🌐 Open web-interface\\index.html to test")
        print("4. 🧪 Run tests: python scripts\\test.py")

if __name__ == '__main__':
    main()