#!/usr/bin/env python3
"""
Deploy CloudFormation stack for S3 Bucket Management System.

This script handles CloudFormation stack deployment. 
Lambda functions should be uploaded separately using upload-lambdas.py.

Usage:
    python scripts/deploy.py                           # Full deployment
    python scripts/deploy.py --update-code             # Update Lambda code only
    python scripts/deploy.py --environment prod        # Specify environment
    python scripts/deploy.py --skip-upload              # Skip Lambda upload check
"""
import subprocess
import sys
import json
import os
import argparse

# Configuration
STACK_NAME = "s3-bucket-management-system"
REGION = "us-east-1"
ENVIRONMENT = "dev"

def run_command(command_list):
    """Run a command and return stdout, print stderr if any"""
    try:
        result = subprocess.run(command_list, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error: {result.stderr.strip()}")
            return None
        return result.stdout.strip()
    except Exception as e:
        print(f"❌ Exception running command: {e}")
        return None

def get_account_id():
    """Get AWS account ID"""
    identity = run_command(["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"])
    if not identity:
        return None
    return identity.strip()

def check_lambda_code_in_s3(environment, account_id, region):
    """Check if Lambda code exists in S3"""
    lambda_bucket_name = f"{environment}-lambda-deployment-packages-{account_id}"
    lambda_functions = [
        f"{environment}-create-bucket.zip",
        f"{environment}-list-buckets.zip",
        f"{environment}-delete-bucket.zip",
        f"{environment}-monitor-buckets.zip",
    ]
    
    missing = []
    for zip_name in lambda_functions:
        check_cmd = [
            "aws", "s3api", "head-object",
            "--bucket", lambda_bucket_name,
            "--key", zip_name,
            "--region", region
        ]
        result = subprocess.run(check_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            missing.append(zip_name)
    
    return missing

def update_lambda_code(environment, account_id, region):
    """Update Lambda function code from S3"""
    lambda_bucket_name = f"{environment}-lambda-deployment-packages-{account_id}"
    lambda_functions = {
        "create-bucket": f"{environment}-create-bucket",
        "list-buckets": f"{environment}-list-buckets",
        "delete-bucket": f"{environment}-delete-bucket",
        "monitor-buckets": f"{environment}-monitor-buckets",
    }
    
    print("🔄 Updating Lambda function code...")
    for func_name, zip_name in lambda_functions.items():
        function_name = zip_name
        s3_key = f"{zip_name}.zip"
        
        print(f"📦 Updating {func_name}...")
        update_cmd = [
            "aws", "lambda", "update-function-code",
            "--function-name", function_name,
            "--s3-bucket", lambda_bucket_name,
            "--s3-key", s3_key,
            "--region", region
        ]
        result = run_command(update_cmd)
        if result:
            print(f"✅ {func_name} updated successfully")
        else:
            print(f"❌ Failed to update {func_name}")
            return False
    
    return True

def main():
    parser = argparse.ArgumentParser(description='Deploy CloudFormation stack')
    parser.add_argument('--environment', '-e', 
                       default=ENVIRONMENT,
                       choices=['dev', 'staging', 'prod'],
                       help=f'Environment (default: {ENVIRONMENT})')
    parser.add_argument('--region', '-r',
                       default=REGION,
                       help=f'AWS region (default: {REGION})')
    parser.add_argument('--update-code', action='store_true',
                       help='Update Lambda function code only (skip stack deployment)')
    parser.add_argument('--skip-upload-check', action='store_true',
                       help='Skip checking if Lambda code is uploaded to S3')
    
    args = parser.parse_args()
    
    environment = args.environment
    region = args.region
    
    print("=== S3 Bucket Management System Deployment ===")
    print(f"Environment: {environment}")
    print(f"Region: {region}")

    # 1️⃣ Check AWS CLI
    print("Checking AWS CLI configuration...")
    aws_identity = run_command(["aws", "sts", "get-caller-identity"])
    if not aws_identity:
        print("❌ AWS CLI not configured. Please run 'aws configure'.")
        sys.exit(1)
    print("✅ AWS CLI configured correctly")

    # Get account ID
    account_id = get_account_id()
    if not account_id:
        print("❌ Failed to get AWS account ID")
        sys.exit(1)

    # If update-code only, just update Lambda functions
    if args.update_code:
        if not update_lambda_code(environment, account_id, region):
            sys.exit(1)
        print("\n✅ Lambda code update complete!")
        return

    # 2️⃣ Load parameters
    params_file = os.path.join("infrastructure", "parameters.json")
    if not os.path.exists(params_file):
        print(f"❌ parameters.json not found at {params_file}")
        sys.exit(1)

    with open(params_file, 'r') as f:
        params = json.load(f)
        print(f"✅ Using email: {params['NotificationEmail']}")

    # 3️⃣ Validate CloudFormation template
    template_file = os.path.join("infrastructure", "cloudformation-template.yaml")
    if not os.path.exists(template_file):
        print(f"❌ Template not found at {template_file}")
        sys.exit(1)

    print("🔍 Validating CloudFormation template...")
    validate = run_command(["aws", "cloudformation", "validate-template", "--template-body", f"file://{template_file}"])
    if not validate:
        sys.exit(1)
    print("✅ Template validation successful!")

    # 3.5️⃣ Check if Lambda code exists in S3 (unless skipped)
    stack_name = f"{STACK_NAME}-{environment}"
    if not args.skip_upload_check:
        print("🔍 Checking if Lambda code is uploaded to S3...")
        missing = check_lambda_code_in_s3(environment, account_id, region)
        if missing:
            print("⚠️  Warning: Some Lambda code files are missing in S3:")
            for zip_name in missing:
                print(f"   - {zip_name}")
            print("\n💡 Run this command first to upload Lambda functions:")
            print(f"   python scripts/upload-lambdas.py --environment {environment}")
            
            response = input("\nContinue anyway? (y/N): ").strip().lower()
            if response != 'y':
                print("❌ Deployment cancelled. Please upload Lambda functions first.")
                sys.exit(1)

    # 4️⃣ Check stack status and handle ROLLBACK_COMPLETE
    stack_status_cmd = [
        "aws", "cloudformation", "describe-stacks",
        "--stack-name", stack_name,
        "--region", region,
        "--query", "Stacks[0].StackStatus",
        "--output", "text"
    ]
    stack_status = run_command(stack_status_cmd)
    
    if stack_status and "ROLLBACK_COMPLETE" in stack_status:
        print("⚠️  Stack is in ROLLBACK_COMPLETE state. Deleting it before redeployment...")
        delete_cmd = ["aws", "cloudformation", "delete-stack", "--stack-name", stack_name, "--region", region]
        if run_command(delete_cmd):
            print("⏳ Waiting for stack deletion to complete...")
            wait_cmd = ["aws", "cloudformation", "wait", "stack-delete-complete", "--stack-name", stack_name, "--region", region]
            run_command(wait_cmd)
            print("✅ Stack deleted successfully")
        else:
            print("❌ Failed to delete stack")
            sys.exit(1)
    
    # 5️⃣ Deploy CloudFormation stack
    print("🚀 Deploying CloudFormation stack...")
    deploy_cmd = [
        "aws", "cloudformation", "deploy",
        "--template-file", template_file,
        "--stack-name", stack_name,
        "--region", region,
        "--capabilities", "CAPABILITY_NAMED_IAM",
        "--parameter-overrides",
        f"NotificationEmail={params['NotificationEmail']}",
        f"Environment={environment}",
        "--tags",
        f"Environment={environment}",
        "Project=BucketManagement"
    ]
    result = run_command(deploy_cmd)
    if result is None:
        print("❌ Deployment failed")
        sys.exit(1)
    print("✅ Deployment successful!")

    # 6️⃣ Get stack outputs
    print("📊 Retrieving stack outputs...")
    outputs_raw = run_command([
        "aws", "cloudformation", "describe-stacks",
        "--stack-name", stack_name,
        "--region", region,
        "--query", "Stacks[0].Outputs"
    ])
    if not outputs_raw:
        print("❌ Failed to retrieve stack outputs")
        sys.exit(1)

    outputs = json.loads(outputs_raw)
    def get_output(key):
        return next((o['OutputValue'] for o in outputs if o['OutputKey'] == key), '')

    api_endpoint = get_output("APIEndpoint")
    user_pool_id = get_output("UserPoolId")
    user_pool_client_id = get_output("UserPoolClientId")
    identity_pool_id = get_output("IdentityPoolId")

    # 7️⃣ Create web config.js
    config_file = os.path.join("web-interface", "config.js")
    config_content = f"""const CONFIG = {{
    apiEndpoint: '{api_endpoint}',
    region: '{region}',
    userPoolId: '{user_pool_id}',
    userPoolClientId: '{user_pool_client_id}',
    identityPoolId: '{identity_pool_id}',
    environment: '{environment}'
}};"""
    os.makedirs(os.path.dirname(config_file), exist_ok=True)
    with open(config_file, 'w') as f:
        f.write(config_content)

    print("\n🎉 Deployment Complete!")
    print("=" * 50)
    print(f"API Endpoint: {api_endpoint}")
    print(f"User Pool ID: {user_pool_id}")
    print(f"User Pool Client ID: {user_pool_client_id}")
    print(f"Identity Pool ID: {identity_pool_id}")
    print("\nNext steps:")
    print(f"1. ✉️ Confirm your email subscription in SNS ({params['NotificationEmail']})")
    print("2. 👤 Create a test user: python scripts\\user_management.py create your-email@example.com Password123! \"Your Name\"")
    print("3. 🌐 Open web-interface\\index.html to test")
    print("4. 🧪 Run tests: python scripts\\test.py")
    print("\n💡 To update Lambda code without redeploying:")
    print(f"   python scripts/upload-lambdas.py --environment {environment}")
    print(f"   python scripts/deploy.py --update-code --environment {environment}")

if __name__ == "__main__":
    main()
