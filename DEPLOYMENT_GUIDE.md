# Deployment Guide

## Overview

The deployment process has been **separated into two steps** for better flexibility and CI/CD integration:

1. **Upload Lambda Functions** (`upload-lambdas.py`) - Packages and uploads Lambda code to S3
2. **Deploy Stack** (`deploy.py`) - Deploys/updates CloudFormation stack

## Quick Start

### First-Time Deployment

```bash
# Step 1: Upload Lambda functions to S3
python scripts/upload-lambdas.py

# Step 2: Deploy CloudFormation stack
python scripts/deploy.py
```

### Updating Lambda Code Only (Fast Iteration)

```bash
# Step 1: Upload updated Lambda functions
python scripts/upload-lambdas.py

# Step 2: Update Lambda functions without redeploying stack
python scripts/deploy.py --update-code
```

### Updating a Single Lambda Function

```bash
# Upload only one function
python scripts/upload-lambdas.py --function create-bucket

# Update that function
python scripts/deploy.py --update-code
```

## Commands Reference

### upload-lambdas.py

Packages and uploads Lambda functions to S3.

**Options:**
- `--environment, -e`: Environment (dev, staging, prod) - Default: `dev`
- `--function, -f`: Upload a specific function only (e.g., `create-bucket`)
- `--region, -r`: AWS region - Default: `us-east-1`

**Examples:**
```bash
# Upload all functions for dev environment
python scripts/upload-lambdas.py

# Upload all functions for production
python scripts/upload-lambdas.py --environment prod

# Upload only create-bucket function
python scripts/upload-lambdas.py --function create-bucket

# Upload for specific region
python scripts/upload-lambdas.py --region eu-west-1
```

### deploy.py

Deploys CloudFormation stack or updates Lambda function code.

**Options:**
- `--environment, -e`: Environment (dev, staging, prod) - Default: `dev`
- `--region, -r`: AWS region - Default: `us-east-1`
- `--update-code`: Update Lambda function code only (skip stack deployment)
- `--skip-upload-check`: Skip checking if Lambda code exists in S3

**Examples:**
```bash
# Full stack deployment
python scripts/deploy.py

# Deploy for production environment
python scripts/deploy.py --environment prod

# Update Lambda code only (fast, no stack changes)
python scripts/deploy.py --update-code

# Deploy stack without checking Lambda code exists
python scripts/deploy.py --skip-upload-check
```

## Workflow Scenarios

### Scenario 1: Initial Deployment

```bash
# 1. Upload Lambda functions first
python scripts/upload-lambdas.py --environment dev

# 2. Deploy the stack (it will check for Lambda code)
python scripts/deploy.py --environment dev
```

### Scenario 2: Code-Only Update (Most Common)

When you've made changes to Lambda function code and don't need to change infrastructure:

```bash
# 1. Upload new Lambda code
python scripts/upload-lambdas.py --environment dev

# 2. Update Lambda functions (takes ~10 seconds vs ~5 minutes for full deploy)
python scripts/deploy.py --update-code --environment dev
```

### Scenario 3: Infrastructure Changes Only

When you've changed CloudFormation template but Lambda code is unchanged:

```bash
# Just deploy (it will warn if Lambda code is missing)
python scripts/deploy.py --environment dev

# Or skip the check if you're sure
python scripts/deploy.py --environment dev --skip-upload-check
```

### Scenario 4: Single Function Update

When updating only one Lambda function:

```bash
# Upload specific function
python scripts/upload-lambdas.py --function create-bucket

# Update that function
python scripts/deploy.py --update-code --environment dev
```

## Benefits of Separation

✅ **Faster Iterations**: Update Lambda code in ~10 seconds without full stack deployment  
✅ **Better CI/CD**: Separate jobs for code vs infrastructure  
✅ **Lower Risk**: Code updates don't touch infrastructure  
✅ **Flexibility**: Deploy infrastructure once, update code multiple times  
✅ **Parallel Work**: Developers can update code while others manage infrastructure  

## Migration from Old Script

If you were using the old combined `deploy.py`, the equivalent is:

**Old way:**
```bash
python scripts/deploy.py  # Did everything
```

**New way:**
```bash
python scripts/upload-lambdas.py  # Upload code
python scripts/deploy.py           # Deploy stack
```

## Troubleshooting

### Error: "Lambda code files are missing in S3"
**Solution:** Run `python scripts/upload-lambdas.py` first, then deploy again.

### Error: "Bucket does not exist"
**Solution:** The upload script will create the bucket automatically. Run it first.

### Error: "Function not found" when updating code
**Solution:** Make sure the stack is deployed first. The `--update-code` flag only updates existing functions.

## Tips

1. **During Development**: Use `--update-code` for rapid Lambda code iterations
2. **Before Production**: Always do a full stack deployment to catch any issues
3. **In CI/CD**: Separate the jobs - one for Lambda uploads, one for stack deployment
4. **Single Function Testing**: Use `--function` flag to update just the function you're working on

