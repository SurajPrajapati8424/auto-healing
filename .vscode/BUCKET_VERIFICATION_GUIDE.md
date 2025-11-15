# S3 Bucket Configuration Verification Guide

This guide explains how to verify that your bucket configurations (versioning, lifecycle policies, etc.) are correctly applied to your S3 buckets.

## Table of Contents
1. [Checking Bucket Versioning](#checking-bucket-versioning)
2. [Checking Lifecycle Policies](#checking-lifecycle-policies)
3. [Verifying Custom Lifecycle Policies](#verifying-custom-lifecycle-policies)
4. [Verification Methods](#verification-methods)
   - [AWS Console (Web UI)](#aws-console-web-ui)
   - [AWS CLI](#aws-cli)
   - [Python/Boto3](#pythonboto3)

---

## Checking Bucket Versioning

### Method 1: AWS Console (Easiest)

1. Go to [AWS S3 Console](https://s3.console.aws.amazon.com/)
2. Click on your bucket name
3. Navigate to the **"Properties"** tab
4. Scroll down to **"Bucket Versioning"** section
5. You should see:
   - **Enabled** ✅ - Versioning is active
   - **Disabled** ❌ - Versioning is not enabled
   - **Suspended** ⚠️ - Versioning was enabled but is now suspended

**Expected Result:**
- If you selected "Yes (Recommended)" → Should show **"Enabled"**
- If you selected "No" → Should show **"Disabled"**

### Method 2: AWS CLI

```bash
# Check versioning status
aws s3api get-bucket-versioning --bucket YOUR-BUCKET-NAME

# Example output when enabled:
# {
#     "Status": "Enabled"
# }

# Example output when disabled:
# (no output or Status: "Suspended")
```

### Method 3: Python/Boto3

```python
import boto3

s3 = boto3.client('s3')
bucket_name = 'your-bucket-name'

try:
    response = s3.get_bucket_versioning(Bucket=bucket_name)
    status = response.get('Status', 'Disabled')
    
    if status == 'Enabled':
        print(f"✅ Versioning is ENABLED for {bucket_name}")
    else:
        print(f"❌ Versioning is {status} for {bucket_name}")
except Exception as e:
    print(f"Error: {e}")
```

---

## Checking Lifecycle Policies

### Method 1: AWS Console (Easiest)

1. Go to [AWS S3 Console](https://s3.console.aws.amazon.com/)
2. Click on your bucket name
3. Navigate to the **"Management"** tab
4. Click on **"Lifecycle rules"** in the left sidebar
5. You should see:
   - **No rules configured** - If you selected "None"
   - **One or more rules** - If you selected a lifecycle policy

**For Auto-Archive Policy:**
- Look for a rule named "AutoArchiveRule"
- Check that it has a **Transition** action
- Should transition to "Glacier" storage class after **30 days**

**For Auto-Delete Policy:**
- Look for a rule named "AutoDeleteVersionsRule"
- Check that it has **Noncurrent version expiration**
- Should expire noncurrent versions after **90 days**

**For Custom Policy:**
- Look for rules matching your custom configuration
- Verify each rule's configuration matches what you defined

### Method 2: AWS CLI

```bash
# Check lifecycle configuration
aws s3api get-bucket-lifecycle-configuration --bucket YOUR-BUCKET-NAME

# Example output for Auto-Archive:
# {
#     "Rules": [
#         {
#             "Id": "AutoArchiveRule",
#             "Status": "Enabled",
#             "Filter": {},
#             "Transitions": [
#                 {
#                     "Days": 30,
#                     "StorageClass": "GLACIER"
#                 }
#             ]
#         }
#     ]
# }

# Example output for Auto-Delete:
# {
#     "Rules": [
#         {
#             "Id": "AutoDeleteVersionsRule",
#             "Status": "Enabled",
#             "Filter": {},
#             "NoncurrentVersionExpiration": {
#                 "NoncurrentDays": 90
#             }
#         }
#     ]
# }

# If no lifecycle policy exists:
# An error occurred (NoSuchLifecycleConfiguration) when calling the GetBucketLifecycleConfiguration operation
```

### Method 3: Python/Boto3

```python
import boto3
import json

s3 = boto3.client('s3')
bucket_name = 'your-bucket-name'

try:
    response = s3.get_bucket_lifecycle_configuration(Bucket=bucket_name)
    rules = response.get('Rules', [])
    
    if not rules:
        print(f"❌ No lifecycle rules found for {bucket_name}")
    else:
        print(f"✅ Found {len(rules)} lifecycle rule(s) for {bucket_name}")
        for rule in rules:
            print(f"\n  Rule ID: {rule['Id']}")
            print(f"  Status: {rule['Status']}")
            
            if 'Transitions' in rule:
                print(f"  Transitions:")
                for transition in rule['Transitions']:
                    print(f"    - After {transition['Days']} days → {transition['StorageClass']}")
            
            if 'NoncurrentVersionExpiration' in rule:
                exp = rule['NoncurrentVersionExpiration']
                print(f"  Noncurrent Version Expiration: {exp.get('NoncurrentDays')} days")
            
            if 'Expiration' in rule:
                exp = rule['Expiration']
                if 'Days' in exp:
                    print(f"  Expiration: {exp['Days']} days")
                elif 'Date' in exp:
                    print(f"  Expiration Date: {exp['Date']}")
                    
        # Pretty print full config
        print(f"\nFull Configuration:")
        print(json.dumps(response, indent=2, default=str))
        
except s3.exceptions.ClientError as e:
    error_code = e.response['Error']['Code']
    if error_code == 'NoSuchLifecycleConfiguration':
        print(f"❌ No lifecycle configuration found for {bucket_name} (this is expected if you selected 'None')")
    else:
        print(f"Error: {e}")
```

---

## Verifying Custom Lifecycle Policies

If you created a bucket with a **Custom Policy**, verify it matches exactly what you configured:

### Step 1: Retrieve the Configuration

```bash
# Using AWS CLI
aws s3api get-bucket-lifecycle-configuration --bucket YOUR-BUCKET-NAME > lifecycle-config.json
cat lifecycle-config.json
```

### Step 2: Compare with Your Configuration

1. Open the JSON file from the CLI output
2. Compare it with the JSON you entered in the web UI
3. Verify:
   - All rules are present
   - Rule IDs match
   - Status values match (Enabled/Disabled)
   - Transition/Expiration rules match your configuration
   - Filters match (if specified)

### Step 3: Validate Rule Logic

For each rule, verify:
- **Id**: Unique identifier for the rule
- **Status**: Must be "Enabled" or "Disabled"
- **Filter**: Object prefix/tag filters (empty `{}` means all objects)
- **Transitions**: Storage class transitions (STANDARD → GLACIER, etc.)
- **Expiration**: When objects should be deleted
- **NoncurrentVersionExpiration**: When noncurrent versions should be deleted

---

## Quick Verification Checklist

Use this checklist to quickly verify your bucket configuration:

### ✅ Versioning Check
- [ ] Navigate to bucket Properties tab
- [ ] Check "Bucket Versioning" section
- [ ] Verify status matches your selection (Enabled/Disabled)

### ✅ Lifecycle Policy Check
- [ ] Navigate to bucket Management tab
- [ ] Open "Lifecycle rules"
- [ ] Verify rules match your selection:
  - [ ] **None**: No rules should exist
  - [ ] **Auto-Archive**: Rule with Glacier transition after 30 days
  - [ ] **Auto-Delete**: Rule expiring noncurrent versions after 90 days
  - [ ] **Custom**: Rules match your custom JSON configuration

### ✅ Configuration Consistency
- [ ] Check DynamoDB metadata (if you have access)
- [ ] Verify stored `versioning` field matches bucket status
- [ ] Verify stored `lifecycle_policy` field matches bucket rules
- [ ] For custom policies, verify `custom_lifecycle_config` is stored correctly

---

## Common Issues and Solutions

### Issue 1: Versioning Shows "Suspended" Instead of "Enabled"
**Cause**: Versioning was previously enabled, then suspended
**Solution**: Re-enable versioning through the console or wait for auto-heal to restore it

### Issue 2: Lifecycle Rules Not Appearing
**Possible Causes**:
1. Policy application failed (check CloudWatch logs)
2. Wrong bucket selected
3. IAM permissions issue

**Solution**:
- Check CloudWatch logs for the create-bucket Lambda function
- Verify bucket name is correct
- Ensure Lambda execution role has `s3:PutLifecycleConfiguration` permission

### Issue 3: Custom Policy Not Applied Correctly
**Cause**: JSON validation failed or invalid format
**Solution**:
- Use the "Validate JSON" button in the web UI before creating
- Check Lambda logs for specific error messages
- Verify JSON follows AWS S3 lifecycle configuration format

---

## Testing Lifecycle Policies

### Test Auto-Archive Policy

1. Upload a test file to the bucket
2. Wait 30+ days (or use S3 Object Lambda to simulate)
3. Check object storage class:
   ```bash
   aws s3api head-object --bucket YOUR-BUCKET --key test-file.txt
   # Look for "StorageClass": "GLACIER"
   ```

### Test Auto-Delete Policy

1. Enable versioning on the bucket
2. Upload a file
3. Delete the file (creates a delete marker)
4. Wait 90+ days
5. Check that noncurrent versions are deleted:
   ```bash
   aws s3api list-object-versions --bucket YOUR-BUCKET --prefix test-file.txt
   ```

**Note**: For testing purposes, you can modify the lifecycle policy to use shorter timeframes (e.g., 1 day instead of 30/90 days) for faster verification.

---

## Verification Script

Here's a complete Python script to verify all bucket configurations:

```python
#!/usr/bin/env python3
"""
S3 Bucket Configuration Verification Script
Usage: python verify_bucket.py YOUR-BUCKET-NAME
"""

import boto3
import sys
import json
from datetime import datetime

def verify_bucket(bucket_name):
    s3 = boto3.client('s3')
    
    print(f"🔍 Verifying bucket: {bucket_name}\n")
    print("=" * 60)
    
    # 1. Check if bucket exists
    try:
        s3.head_bucket(Bucket=bucket_name)
        print(f"✅ Bucket exists: {bucket_name}\n")
    except Exception as e:
        print(f"❌ Error accessing bucket: {e}\n")
        return
    
    # 2. Check Versioning
    print("📋 VERSIONING STATUS:")
    print("-" * 60)
    try:
        versioning = s3.get_bucket_versioning(Bucket=bucket_name)
        status = versioning.get('Status', 'Disabled')
        
        if status == 'Enabled':
            mfa_delete = versioning.get('MfaDelete', 'Disabled')
            print(f"  Status: ✅ ENABLED")
            print(f"  MFA Delete: {mfa_delete}")
        else:
            print(f"  Status: ❌ {status}")
    except Exception as e:
        print(f"  Error: {e}")
    print()
    
    # 3. Check Lifecycle Configuration
    print("📋 LIFECYCLE POLICY:")
    print("-" * 60)
    try:
        lifecycle = s3.get_bucket_lifecycle_configuration(Bucket=bucket_name)
        rules = lifecycle.get('Rules', [])
        
        if not rules:
            print("  ❌ No lifecycle rules configured")
        else:
            print(f"  ✅ Found {len(rules)} rule(s):\n")
            for i, rule in enumerate(rules, 1):
                print(f"  Rule #{i}: {rule['Id']}")
                print(f"    Status: {rule['Status']}")
                
                if 'Transitions' in rule:
                    print("    Transitions:")
                    for trans in rule['Transitions']:
                        days = trans.get('Days', 'N/A')
                        storage_class = trans.get('StorageClass', 'N/A')
                        print(f"      - After {days} days → {storage_class}")
                
                if 'Expiration' in rule:
                    exp = rule['Expiration']
                    if 'Days' in exp:
                        print(f"    Expiration: {exp['Days']} days")
                    elif 'Date' in exp:
                        print(f"    Expiration Date: {exp['Date']}")
                
                if 'NoncurrentVersionExpiration' in rule:
                    nce = rule['NoncurrentVersionExpiration']
                    days = nce.get('NoncurrentDays', 'N/A')
                    print(f"    Noncurrent Version Expiration: {days} days")
                
                if 'NoncurrentVersionTransitions' in rule:
                    print("    Noncurrent Version Transitions:")
                    for trans in rule['NoncurrentVersionTransitions']:
                        days = trans.get('NoncurrentDays', 'N/A')
                        storage_class = trans.get('StorageClass', 'N/A')
                        print(f"      - After {days} days → {storage_class}")
                
                print()
    except s3.exceptions.ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchLifecycleConfiguration':
            print("  ❌ No lifecycle configuration (expected if 'None' was selected)")
        else:
            print(f"  ❌ Error: {e}")
    except Exception as e:
        print(f"  ❌ Error: {e}")
    print()
    
    # 4. Check Encryption
    print("📋 ENCRYPTION:")
    print("-" * 60)
    try:
        encryption = s3.get_bucket_encryption(Bucket=bucket_name)
        rules = encryption.get('ServerSideEncryptionConfiguration', {}).get('Rules', [])
        if rules:
            sse_config = rules[0].get('ApplyServerSideEncryptionByDefault', {})
            algorithm = sse_config.get('SSEAlgorithm', 'N/A')
            print(f"  ✅ Encryption: {algorithm}")
        else:
            print("  ⚠️  No encryption configuration found")
    except Exception as e:
        print(f"  ❌ Error: {e}")
    print()
    
    # 5. Check Public Access Block
    print("📋 PUBLIC ACCESS BLOCK:")
    print("-" * 60)
    try:
        pab = s3.get_public_access_block(Bucket=bucket_name)
        config = pab.get('PublicAccessBlockConfiguration', {})
        print(f"  Block Public ACLs: {'✅' if config.get('BlockPublicAcls') else '❌'}")
        print(f"  Ignore Public ACLs: {'✅' if config.get('IgnorePublicAcls') else '❌'}")
        print(f"  Block Public Policy: {'✅' if config.get('BlockPublicPolicy') else '❌'}")
        print(f"  Restrict Public Buckets: {'✅' if config.get('RestrictPublicBuckets') else '❌'}")
    except Exception as e:
        print(f"  ❌ Error: {e}")
    print()
    
    print("=" * 60)
    print(f"✅ Verification complete at {datetime.now().isoformat()}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python verify_bucket.py YOUR-BUCKET-NAME")
        sys.exit(1)
    
    bucket_name = sys.argv[1]
    verify_bucket(bucket_name)
```

**Save this as `verify_bucket.py` and run:**
```bash
python verify_bucket.py your-bucket-name
```

---

## Summary

- **Versioning**: Check in Properties → Bucket Versioning
- **Lifecycle Policies**: Check in Management → Lifecycle rules
- **Custom Policies**: Compare CLI output with your JSON configuration
- **Use the verification script** for comprehensive automated checks

For any issues, check:
1. CloudWatch logs for the create-bucket Lambda function
2. DynamoDB metadata to verify stored configuration
3. IAM permissions for S3 operations

---

**Need Help?** Check the Lambda function logs in CloudWatch for detailed error messages.

