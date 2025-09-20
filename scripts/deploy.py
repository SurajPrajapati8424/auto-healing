#!/usr/bin/env python3
import subprocess
import sys
import json
import os

# Configuration
STACK_NAME = "s3-bucket-management-system"
REGION = "us-east-1"
ENVIRONMENT = "dev"

def run_command(command_list):
    """Run a command and return stdout, print stderr if any"""
    try:
        result = subprocess.run(command_list, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ Error: {result.stderr.strip()}")
            return None
        return result.stdout.strip()
    except Exception as e:
        print(f"❌ Exception running command: {e}")
        return None

def main():
    print("=== S3 Bucket Management System Deployment ===")
    print(f"Environment: {ENVIRONMENT}")
    print(f"Region: {REGION}")

    # 1️⃣ Check AWS CLI
    print("Checking AWS CLI configuration...")
    aws_identity = run_command(["aws", "sts", "get-caller-identity"])
    if not aws_identity:
        print("❌ AWS CLI not configured. Please run 'aws configure'.")
        sys.exit(1)
    print("✅ AWS CLI configured correctly")

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

    # 4️⃣ Deploy CloudFormation stack
    print("🚀 Deploying CloudFormation stack...")
    deploy_cmd = [
        "aws", "cloudformation", "deploy",
        "--template-file", template_file,
        "--stack-name", f"{STACK_NAME}-{ENVIRONMENT}",
        "--region", REGION,
        "--capabilities", "CAPABILITY_NAMED_IAM",
        "--parameter-overrides",
        f"NotificationEmail={params['NotificationEmail']}",
        f"Environment={ENVIRONMENT}",
        "--tags",
        f"Environment={ENVIRONMENT}",
        "Project=BucketManagement"
    ]
    result = run_command(deploy_cmd)
    if result is None:
        print("❌ Deployment failed")
        sys.exit(1)
    print("✅ Deployment successful!")

    # 5️⃣ Get stack outputs
    print("📊 Retrieving stack outputs...")
    outputs_raw = run_command([
        "aws", "cloudformation", "describe-stacks",
        "--stack-name", f"{STACK_NAME}-{ENVIRONMENT}",
        "--region", REGION,
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

    # 6️⃣ Create web config.js
    config_file = os.path.join("web-interface", "config.js")
    config_content = f"""const CONFIG = {{
    apiEndpoint: '{api_endpoint}',
    region: '{REGION}',
    userPoolId: '{user_pool_id}',
    userPoolClientId: '{user_pool_client_id}',
    identityPoolId: '{identity_pool_id}',
    environment: '{ENVIRONMENT}'
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

if __name__ == "__main__":
    main()
