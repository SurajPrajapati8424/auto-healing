#!/usr/bin/env python3
"""
Upload Lambda functions to S3 bucket.

This script packages and uploads Lambda functions to S3.
It can be run independently to update Lambda code without redeploying the entire stack.

Usage:
    python scripts/upload-lambdas.py
    python scripts/upload-lambdas.py --function create-bucket  # Upload single function
    python scripts/upload-lambdas.py --environment prod        # Specify environment
"""
import subprocess
import sys
import os
import zipfile
import tempfile
import json
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

def package_lambda_function(function_dir, output_path):
    """Package Lambda function into a ZIP file"""
    try:
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(function_dir):
                # Skip __pycache__ and .pyc files
                dirs[:] = [d for d in dirs if d != '__pycache__']
                for file in files:
                    if file.endswith('.pyc'):
                        continue
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
    # Check if bucket exists
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

def upload_lambdas(environment=ENVIRONMENT, function_name=None):
    """Upload Lambda functions to S3"""
    print("=== Lambda Functions Upload ===")
    print(f"Environment: {environment}")
    print(f"Region: {REGION}")

    # Check AWS CLI
    print("Checking AWS CLI configuration...")
    aws_identity = run_command(["aws", "sts", "get-caller-identity"])
    if not aws_identity:
        print("❌ AWS CLI not configured. Please run 'aws configure'.")
        sys.exit(1)
    print("✅ AWS CLI configured correctly")

    # Get account ID and determine bucket name
    account_id = get_account_id()
    if not account_id:
        print("❌ Failed to get AWS account ID")
        sys.exit(1)
    
    lambda_bucket_name = f"{environment}-lambda-deployment-packages-{account_id}"
    
    # Ensure bucket exists
    if not ensure_s3_bucket(lambda_bucket_name, REGION):
        sys.exit(1)
    
    # Define Lambda functions
    all_lambda_functions = [
        ("create-bucket", f"{environment}-create-bucket.zip"),
        ("list-buckets", f"{environment}-list-buckets.zip"),
        ("delete-bucket", f"{environment}-delete-bucket.zip"),
        ("monitor-buckets", f"{environment}-monitor-buckets.zip"),
    ]
    
    # Filter to specific function if requested
    if function_name:
        lambda_functions = [f for f in all_lambda_functions if f[0] == function_name]
        if not lambda_functions:
            print(f"❌ Function '{function_name}' not found. Available functions:")
            for func, _ in all_lambda_functions:
                print(f"  - {func}")
            sys.exit(1)
    else:
        lambda_functions = all_lambda_functions
    
    # Package and upload each Lambda function
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
            
            print(f"☁️ Uploading {zip_name} to s3://{lambda_bucket_name}/{zip_name}...")
            if not upload_to_s3(zip_path, lambda_bucket_name, zip_name, REGION):
                sys.exit(1)
            print(f"✅ {zip_name} uploaded successfully")
    
    print("\n✅ All Lambda functions uploaded successfully!")
    print(f"📦 Bucket: s3://{lambda_bucket_name}")
    print("\nNext steps:")
    print("  • To update Lambda functions in your stack, run:")
    print(f"    python scripts/deploy.py --update-code")
    print("  • Or redeploy the full stack:")
    print(f"    python scripts/deploy.py")

def main():
    global REGION
    parser = argparse.ArgumentParser(description='Upload Lambda functions to S3')
    parser.add_argument('--environment', '-e', 
                       default=ENVIRONMENT,
                       choices=['dev', 'staging', 'prod'],
                       help=f'Environment (default: {ENVIRONMENT})')
    parser.add_argument('--function', '-f',
                       help='Upload a specific function only (e.g., create-bucket)')
    parser.add_argument('--region', '-r',
                       default=REGION,
                       help=f'AWS region (default: {REGION})')
    
    args = parser.parse_args()
    
    # Update global REGION if provided
    REGION = args.region
    
    upload_lambdas(environment=args.environment, function_name=args.function)

if __name__ == "__main__":
    main()

