#!/usr/bin/env python3
import subprocess
import sys
import json
import os
import zipfile
import tempfile

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

def package_lambda_function(function_dir, output_path):
    """Package Lambda function into a ZIP file"""
    try:
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(function_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arc_name = os.path.relpath(file_path, function_dir)
                    zipf.write(file_path, arc_name)
        return True
    except Exception as e:
        print(f"❌ Error packaging {function_dir}: {e}")
        return False

def upload_to_s3(local_path, bucket_name, s3_key, region):
    """Upload file to S3"""
    try:
        cmd = [
            "aws", "s3", "cp", local_path,
            f"s3://{bucket_name}/{s3_key}",
            "--region", region
        ]
        result = run_command(cmd)
        return result is not None
    except Exception as e:
        print(f"❌ Error uploading to S3: {e}")
        return False

def ensure_s3_bucket(bucket_name, region):
    """Ensure S3 bucket exists, create if it doesn't"""
    # Check if bucket exists (head-bucket returns 0 if exists, 255 if not)
    check_cmd = ["aws", "s3api", "head-bucket", "--bucket", bucket_name]
    try:
        result = subprocess.run(check_cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ S3 bucket {bucket_name} already exists")
            return True
    except Exception:
        pass  # Bucket doesn't exist, continue to create
    
    # Create bucket
    print(f"📦 Creating S3 bucket {bucket_name}...")
    if region == "us-east-1":
        create_cmd = ["aws", "s3api", "create-bucket", "--bucket", bucket_name, "--region", region]
    else:
        create_cmd = [
            "aws", "s3api", "create-bucket",
            "--bucket", bucket_name,
            "--region", region,
            "--create-bucket-configuration", f"LocationConstraint={region}"
        ]
    
    result = run_command(create_cmd)
    if result:
        print(f"✅ S3 bucket {bucket_name} created")
        
        # Configure bucket to match CloudFormation template properties
        # Enable versioning
        version_cmd = ["aws", "s3api", "put-bucket-versioning",
                      "--bucket", bucket_name,
                      "--versioning-configuration", "Status=Enabled"]
        run_command(version_cmd)
        
        # Configure lifecycle
        lifecycle_config = {
            "Rules": [{
                "Id": "DeleteOldVersions",
                "Status": "Enabled",
                "NoncurrentVersionExpiration": {"NoncurrentDays": 30}
            }]
        }
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(lifecycle_config, f)
            lifecycle_file = f.name
        
        try:
            lifecycle_cmd = ["aws", "s3api", "put-bucket-lifecycle-configuration",
                           "--bucket", bucket_name,
                           "--lifecycle-configuration", f"file://{lifecycle_file}"]
            run_command(lifecycle_cmd)
        finally:
            os.unlink(lifecycle_file)
        
        return True
    else:
        print(f"❌ Failed to create S3 bucket {bucket_name}")
        return False

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

    # 3.5️⃣ Package and upload Lambda functions
    print("📦 Packaging Lambda functions...")
    account_id = get_account_id()
    if not account_id:
        print("❌ Failed to get AWS account ID")
        sys.exit(1)
    
    lambda_bucket_name = f"{ENVIRONMENT}-lambda-deployment-packages-{account_id}"
    stack_name = f"{STACK_NAME}-{ENVIRONMENT}"
    
    # Check if stack exists
    stack_exists_cmd = [
        "aws", "cloudformation", "describe-stacks",
        "--stack-name", stack_name,
        "--region", REGION
    ]
    stack_exists = run_command(stack_exists_cmd) is not None
    
    # If stack doesn't exist, we need to create bucket first before deploying
    # This is because CloudFormation needs the bucket to exist to upload Lambda code
    if not stack_exists:
        print("📦 Stack doesn't exist yet. Creating S3 bucket for Lambda code...")
        print("   (This bucket will be managed by CloudFormation after deployment)")
        if not ensure_s3_bucket(lambda_bucket_name, REGION):
            sys.exit(1)
    else:
        # Check if bucket exists (it should, from the stack)
        print(f"✅ Stack exists, verifying bucket: {lambda_bucket_name}")
        bucket_check = ["aws", "s3api", "head-bucket", "--bucket", lambda_bucket_name]
        bucket_result = subprocess.run(bucket_check, capture_output=True, text=True)
        if bucket_result.returncode != 0:
            print(f"⚠️  Warning: Bucket {lambda_bucket_name} not found. Creating it...")
            if not ensure_s3_bucket(lambda_bucket_name, REGION):
                sys.exit(1)
    
    # Package and upload each Lambda function
    lambda_functions = [
        ("create-bucket", f"{ENVIRONMENT}-create-bucket.zip"),
        ("list-buckets", f"{ENVIRONMENT}-list-buckets.zip"),
        ("delete-bucket", f"{ENVIRONMENT}-delete-bucket.zip"),
        ("monitor-buckets", f"{ENVIRONMENT}-monitor-buckets.zip"),
    ]
    
    with tempfile.TemporaryDirectory() as temp_dir:
        for func_dir, zip_name in lambda_functions:
            lambda_path = os.path.join("lambda-functions", func_dir)
            if not os.path.exists(lambda_path):
                print(f"❌ Lambda function directory not found: {lambda_path}")
                sys.exit(1)
            
            zip_path = os.path.join(temp_dir, zip_name)
            print(f"📦 Packaging {func_dir}...")
            if not package_lambda_function(lambda_path, zip_path):
                sys.exit(1)
            
            print(f"☁️ Uploading {zip_name} to S3...")
            if not upload_to_s3(zip_path, lambda_bucket_name, zip_name, REGION):
                sys.exit(1)
            print(f"✅ {zip_name} uploaded successfully")
    
    print("✅ All Lambda functions packaged and uploaded!")

    # 4️⃣ Check stack status and handle ROLLBACK_COMPLETE
    stack_status_cmd = [
        "aws", "cloudformation", "describe-stacks",
        "--stack-name", stack_name,
        "--region", REGION,
        "--query", "Stacks[0].StackStatus",
        "--output", "text"
    ]
    stack_status = run_command(stack_status_cmd)
    
    if stack_status and "ROLLBACK_COMPLETE" in stack_status:
        print("⚠️  Stack is in ROLLBACK_COMPLETE state. Deleting it before redeployment...")
        delete_cmd = ["aws", "cloudformation", "delete-stack", "--stack-name", stack_name, "--region", REGION]
        if run_command(delete_cmd):
            print("⏳ Waiting for stack deletion to complete...")
            wait_cmd = ["aws", "cloudformation", "wait", "stack-delete-complete", "--stack-name", stack_name, "--region", REGION]
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

    # 6️⃣ Get stack outputs
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

    # 7️⃣ Create web config.js
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
