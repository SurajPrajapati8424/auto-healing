# S3 Bucket Management System - Project Documentation

## 📋 Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Project Structure](#project-structure)
4. [Components](#components)
5. [Authentication & Authorization](#authentication--authorization)
6. [Development Workflow](#development-workflow)
7. [Deployment](#deployment)
8. [Testing](#testing)
9. [Monitoring & Maintenance](#monitoring--maintenance)
10. [Troubleshooting](#troubleshooting)
11. [API Reference](#api-reference)
12. [Security Best Practices](#security-best-practices)

---

## 🎯 Project Overview

The **S3 Bucket Management System** is a serverless AWS-based application that provides secure, automated management of S3 buckets with the following features:

- **User Authentication**: AWS Cognito-based authentication
- **Role-Based Access Control**: Super Admin, Business Admin, and regular user roles
- **Automated Bucket Management**: Create, list, and delete S3 buckets via REST API
- **Bucket Healing**: Automatic detection and restoration of deleted buckets (when enabled)
- **Deletion Audit Trail**: Complete tracking of bucket deletions with metadata
- **Monitoring**: Automated monitoring and health checks
- **Web Interface**: Modern, responsive web UI for bucket management

### Key Technologies
- **AWS Lambda**: Serverless compute for business logic
- **API Gateway**: RESTful API endpoints
- **DynamoDB**: Metadata storage and audit logging
- **AWS Cognito**: User authentication and authorization
- **S3**: Storage for deployment packages and bucket storage
- **SNS**: Notification service
- **EventBridge**: Scheduled monitoring jobs
- **CloudFormation**: Infrastructure as Code

---

## 🏗️ Architecture

### High-Level Architecture

```
┌─────────────────┐
│   Web Browser   │
│  (index.html)   │
└────────┬────────┘
         │ HTTPS
         ▼
┌─────────────────┐
│  API Gateway     │ ← Cognito Authorizer
│  (REST API)      │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐ ┌────────┐
│Lambda  │ │Lambda   │
│Create  │ │List     │
└───┬────┘ └───┬────┘
    │          │
    ▼          ▼
┌────────┐ ┌────────┐
│   S3   │ │DynamoDB│
└────────┘ └────────┘

┌─────────────────┐
│ EventBridge     │
│ (Scheduled)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│Monitor Lambda   │
│(Healing Logic)  │
└─────────────────┘
```

### Data Flow

1. **User Authentication**: User signs in via Cognito → Receives ID token
2. **API Request**: Browser sends request to API Gateway with ID token
3. **Authorization**: API Gateway validates token via Cognito Authorizer
4. **Lambda Execution**: Authorized request triggers Lambda function
5. **Data Operations**: Lambda interacts with S3 and DynamoDB
6. **Response**: Results returned to browser

---

## 📁 Project Structure

```
s3-bucket-manager/
├── .vscode/                          # VS Code configuration and documentation
│   └── PROJECT_DOCUMENTATION.md     # This file
│
├── infrastructure/                   # Infrastructure as Code
│   ├── cloudformation-template.yaml # Main CloudFormation template
│   └── parameters.json              # CloudFormation parameters
│
├── lambda-functions/                 # Lambda function code
│   ├── create-bucket/
│   │   └── index.py                # Create bucket Lambda
│   ├── delete-bucket/
│   │   └── index.py                 # Delete bucket Lambda (with audit)
│   ├── list-buckets/
│   │   └── index.py                 # List buckets Lambda (role-aware)
│   └── monitor-buckets/
│       └── index.py                 # Monitoring & healing Lambda
│
├── web-interface/                    # Frontend application
│   ├── index.html                   # Main HTML file
│   ├── script.js                   # JavaScript logic
│   ├── style.css                    # Styling
│   └── config.js                    # Auto-generated config (gitignored)
│
├── scripts/                          # Utility and deployment scripts
│   ├── deploy.py                    # CloudFormation stack deployment
│   ├── upload-lambdas.py            # Lambda code packaging & upload
│   ├── test.py                      # Comprehensive test suite
│   ├── monitor.py                   # System health monitoring
│   ├── user_management.py          # Cognito user management
│   └── audit_deletions.py           # Deletion audit viewer
│
├── tests/                            # Test files (placeholder)
│
├── out/                              # Build artifacts (if any)
│
├── README.md                         # Main project README
├── DEPLOYMENT_GUIDE.md              # Deployment instructions
└── .gitignore                        # Git ignore rules
```

---

## 🧩 Components

### 1. Lambda Functions

#### `create-bucket/index.py`
**Purpose**: Create new S3 buckets for projects

**Features**:
- Validates project name (lowercase, alphanumeric, hyphens only, 3-50 chars)
- Generates unique bucket name: `{env}-{project}-{uuid}`
- Configures bucket security (public access block, encryption)
- Stores metadata in DynamoDB
- Sends SNS notifications
- User-specific bucket isolation (user_id#project_name as key)

**Environment Variables**:
- `TABLE_NAME`: DynamoDB table name
- `SNS_TOPIC`: SNS topic ARN
- `ENVIRONMENT`: Environment name (dev/staging/prod)
- `REGION`: AWS region

**API Endpoint**: `POST /buckets`

---

#### `list-buckets/index.py`
**Purpose**: List buckets with role-based access control

**Features**:
- **Regular Users**: See only their own buckets
- **Business Admins**: See all buckets
- **Super Admins**: See all buckets with owner information
- Supports query by project name
- Uses DynamoDB indexes for efficient queries

**Environment Variables**:
- `TABLE_NAME`: DynamoDB table name
- `USER_POOL_ID`: Cognito User Pool ID

**API Endpoints**: 
- `GET /buckets` - List all buckets
- `GET /buckets?project_name={name}` - Get specific bucket

---

#### `delete-bucket/index.py`
**Purpose**: Delete buckets with audit trail

**Features**:
- Role-based deletion permissions
- **Owners**: Can delete own buckets (should_heal=False)
- **Business Admins**: Can delete any bucket (should_heal=True)
- **Super Admins**: Can delete any bucket (should_heal=False)
- Records deletion metadata (who, when, should_heal flag)
- Empties bucket before deletion

**Deletion Metadata Stored**:
- `deleted_at`: Timestamp
- `deleted_by`: User ID
- `deleted_by_email`: User email
- `should_heal`: Boolean flag for healing
- `status`: Set to 'deleted'

**API Endpoint**: `DELETE /buckets?project_name={name}`

---

#### `monitor-buckets/index.py`
**Purpose**: Monitor and heal buckets (scheduled via EventBridge)

**Features**:
- Runs every 5 minutes via EventBridge
- Checks active buckets for existence
- Heals deleted buckets when `should_heal=True`
- Updates `last_checked` timestamps
- Sends healing notifications via SNS
- Tracks `heal_count` for statistics

**Healing Logic**:
1. Scans DynamoDB for buckets with `status='deleted'` and `should_heal=True`
2. Verifies bucket doesn't exist in S3
3. Recreates bucket with original configuration
4. Updates status back to 'active'
5. Increments `heal_count`

**Environment Variables**:
- `TABLE_NAME`: DynamoDB table name
- `SNS_TOPIC`: SNS topic ARN
- `ENVIRONMENT`: Environment name
- `REGION`: AWS region

---

### 2. Web Interface

#### `index.html`
Modern single-page application with:
- Cognito authentication (sign up, sign in, sign out)
- Bucket creation form
- Bucket list with details
- Responsive design
- Real-time status updates

**Dependencies**:
- AWS SDK v2.1400.0 (loaded from CDN)
- `config.js` (auto-generated during deployment)

#### `script.js`
Contains all client-side JavaScript logic:
- Authentication functions
- API calls to backend
- UI state management
- Error handling

#### `style.css`
Responsive CSS styling with modern UI design

---

### 3. Infrastructure

#### `cloudformation-template.yaml`
Comprehensive CloudFormation template defining:
- **Cognito User Pool** with groups (admins, business-admins)
- **Cognito Identity Pool** for authenticated access
- **DynamoDB Table** with GSI (bucket-name-index, user-id-index)
- **SNS Topic** for notifications
- **Lambda Functions** (create, list, delete, monitor)
- **API Gateway** REST API with Cognito authorizer
- **EventBridge Rule** for scheduled monitoring
- **IAM Roles** with least-privilege policies

**Parameters**:
- `NotificationEmail`: Email for SNS notifications
- `Environment`: dev/staging/prod
- `AdminEmails`: Comma-separated admin emails

---

### 4. Scripts

#### `deploy.py`
**Purpose**: Deploy/update CloudFormation stack

**Features**:
- Validates AWS CLI configuration
- Checks for Lambda code in S3 before deployment
- Supports `--update-code` flag for fast Lambda updates
- Generates `web-interface/config.js` automatically
- Supports multiple environments

**Usage**:
```bash
python scripts/deploy.py                    # Full deployment
python scripts/deploy.py --update-code      # Update Lambda code only
python scripts/deploy.py --environment prod  # Deploy to production
```

---

#### `upload-lambdas.py`
**Purpose**: Package and upload Lambda functions to S3

**Features**:
- Packages Lambda functions into ZIP files
- Uploads to S3 deployment bucket
- Supports single function upload
- Creates S3 bucket if it doesn't exist

**Usage**:
```bash
python scripts/upload-lambdas.py                      # Upload all functions
python scripts/upload-lambdas.py --function create-bucket  # Upload single function
python scripts/upload-lambdas.py --environment prod        # Upload for prod
```

---

#### `test.py`
**Purpose**: Comprehensive automated testing

**Test Coverage**:
- Test user creation
- Authentication flow
- Bucket creation
- Bucket listing
- Invalid project name validation
- Authentication failure handling
- Bucket healing (optional, can take up to 10 minutes)

**Usage**:
```bash
python scripts/test.py
```

---

#### `monitor.py`
**Purpose**: System health monitoring

**Checks**:
- Lambda function health and errors
- DynamoDB table status and throttling
- Bucket integrity (DynamoDB vs S3)
- AWS cost usage

**Usage**:
```bash
python scripts/monitor.py
```

---

#### `user_management.py`
**Purpose**: Cognito user management

**Features**:
- Create users (admin or regular)
- List all users
- Delete users
- Set user passwords

**Usage**:
```bash
python scripts/user_management.py create email@example.com password123 "Full Name"
python scripts/user_management.py list
python scripts/user_management.py delete email@example.com
```

---

#### `audit_deletions.py`
**Purpose**: View bucket deletion audit trail

**Features**:
- Query deletion history from DynamoDB
- Filter by bucket name or project name
- Show deletion metadata (who, when, should_heal)
- Display healing status

**Usage**:
```bash
python scripts/audit_deletions.py                    # List all deletions
python scripts/audit_deletions.py --bucket-name abc   # Filter by bucket
python scripts/audit_deletions.py --project my-app    # Filter by project
```

---

## 🔐 Authentication & Authorization

### User Roles

#### 1. Regular Users
- Can create their own buckets
- Can list only their own buckets
- Can delete only their own buckets (no healing)

#### 2. Business Admins (`business-admins` group)
- Can see all buckets
- Can delete any bucket
- Deleted buckets will be healed (`should_heal=True`)

#### 3. Super Admins (`admins` group or `ADMIN_EMAILS`)
- Can see all buckets with owner information
- Can delete any bucket
- Deleted buckets will NOT be healed (`should_heal=False`)

### Authentication Flow

1. User signs up/signs in via Cognito
2. Receives ID token, Access token, Refresh token
3. ID token is sent in `Authorization: Bearer {token}` header
4. API Gateway validates token via Cognito Authorizer
5. User claims (sub, email, groups) passed to Lambda

### Setting Up User Roles

```bash
# Add user to admins group
aws cognito-idp admin-add-user-to-group \
  --user-pool-id <USER_POOL_ID> \
  --username <EMAIL> \
  --group-name admins

# Add user to business-admins group
aws cognito-idp admin-add-user-to-group \
  --user-pool-id <USER_POOL_ID> \
  --username <EMAIL> \
  --group-name business-admins
```

---

## 💻 Development Workflow

### Prerequisites

1. **AWS Account** with appropriate permissions
2. **AWS CLI** installed and configured
   ```bash
   aws configure
   ```
3. **Python 3.9+** for running scripts
4. **Required Python packages**:
   ```bash
   pip install boto3 requests
   ```

### Initial Setup

1. **Clone repository**
   ```bash
   git clone <repository-url>
   cd s3-bucket-manager
   ```

2. **Configure parameters**
   ```bash
   # Edit infrastructure/parameters.json
   {
     "NotificationEmail": "your-email@example.com",
     "Environment": "dev",
     "AdminEmails": "admin@example.com"
   }
   ```

3. **Deploy infrastructure**
   ```bash
   # Step 1: Upload Lambda functions
   python scripts/upload-lambdas.py
   
   # Step 2: Deploy stack
   python scripts/deploy.py
   ```

4. **Create first user**
   ```bash
   python scripts/user_management.py create admin@example.com SecurePass123! "Admin User"
   ```

### Development Cycle

#### Updating Lambda Code
```bash
# 1. Make changes to lambda-functions/*/index.py

# 2. Upload updated code
python scripts/upload-lambdas.py --function create-bucket

# 3. Update Lambda function (fast, ~10 seconds)
python scripts/deploy.py --update-code
```

#### Updating Infrastructure
```bash
# 1. Make changes to cloudformation-template.yaml

# 2. Upload Lambda code if changed
python scripts/upload-lambdas.py

# 3. Deploy stack (full deployment, ~5 minutes)
python scripts/deploy.py
```

#### Testing Changes
```bash
# Run comprehensive test suite
python scripts/test.py

# Check system health
python scripts/monitor.py
```

---

## 🚀 Deployment

### Deployment Process

The deployment is **separated into two steps** for flexibility:

1. **Upload Lambda Code** (`upload-lambdas.py`)
   - Packages Lambda functions
   - Uploads to S3 deployment bucket

2. **Deploy Stack** (`deploy.py`)
   - Deploys CloudFormation stack
   - Creates/updates infrastructure
   - Updates Lambda functions from S3

### Deployment Scenarios

#### Initial Deployment
```bash
python scripts/upload-lambdas.py --environment dev
python scripts/deploy.py --environment dev
```

#### Code-Only Update (Most Common)
```bash
python scripts/upload-lambdas.py
python scripts/deploy.py --update-code
```

#### Production Deployment
```bash
python scripts/upload-lambdas.py --environment prod
python scripts/deploy.py --environment prod
```

### Post-Deployment Steps

1. **Confirm SNS subscription**
   - Check email inbox for SNS subscription confirmation
   - Click confirmation link

2. **Create admin users**
   ```bash
   python scripts/user_management.py create admin@example.com Password123! "Admin"
   ```

3. **Add users to admin groups** (if needed)
   ```bash
   aws cognito-idp admin-add-user-to-group \
     --user-pool-id <USER_POOL_ID> \
     --username admin@example.com \
     --group-name admins
   ```

4. **Test deployment**
   ```bash
   python scripts/test.py
   ```

5. **Configure web interface**
   - Open `web-interface/index.html` in browser
   - `config.js` is auto-generated during deployment

---

## 🧪 Testing

### Automated Testing

Run the comprehensive test suite:
```bash
python scripts/test.py
```

**Test Coverage**:
- ✅ User creation and authentication
- ✅ Bucket creation with validation
- ✅ Bucket listing
- ✅ Invalid project name rejection
- ✅ Authentication failure handling
- ✅ Bucket healing (optional, long-running)

### Manual Testing

1. **Web Interface Testing**
   - Open `web-interface/index.html`
   - Sign up with new account
   - Create a bucket
   - List buckets
   - Delete a bucket (if you have permission)

2. **API Testing** (using curl)
   ```bash
   # Get ID token from browser console after login
   # Store in variable
   TOKEN="your-id-token-here"
   API_ENDPOINT="https://your-api-id.execute-api.us-east-1.amazonaws.com/dev"
   
   # Create bucket
   curl -X POST "$API_ENDPOINT/buckets" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"project_name": "test-project"}'
   
   # List buckets
   curl -X GET "$API_ENDPOINT/buckets" \
     -H "Authorization: Bearer $TOKEN"
   ```

### Test Data Cleanup

```bash
# Test script automatically cleans up test user
# For manual cleanup, use:
python scripts/user_management.py delete test-user@example.com
```

---

## 📊 Monitoring & Maintenance

### System Health Checks

Run health monitoring:
```bash
python scripts/monitor.py
```

**What it checks**:
- Lambda function status and errors
- DynamoDB table health and throttling
- Bucket integrity (missing buckets)
- AWS cost usage

### Monitoring Schedule

- **Automated**: Monitor Lambda runs every 5 minutes (EventBridge)
- **Manual**: Run `monitor.py` script for detailed health check

### Deletion Audit

View deletion history:
```bash
python scripts/audit_deletions.py
```

**Features**:
- See all deleted buckets
- View deletion metadata (who, when)
- Check healing status
- Filter by bucket or project name

### CloudWatch Logs

Lambda logs are available in CloudWatch:
```
/aws/lambda/{environment}-create-bucket
/aws/lambda/{environment}-list-buckets
/aws/lambda/{environment}-delete-bucket
/aws/lambda/{environment}-monitor-buckets
```

View logs:
```bash
aws logs tail /aws/lambda/dev-create-bucket --follow
```

---

## 🔧 Troubleshooting

### Common Issues

#### 1. "Access Denied" when creating buckets
**Cause**: Lambda role lacks S3 permissions  
**Solution**: Check IAM role in CloudFormation template

#### 2. "User not found" during authentication
**Cause**: User doesn't exist in Cognito  
**Solution**: Create user using `user_management.py`

#### 3. "Token expired" errors
**Cause**: ID token expired (default: 1 hour)  
**Solution**: Implement token refresh in web interface

#### 4. Buckets not healing
**Cause**: EventBridge rule disabled or Lambda errors  
**Solution**: 
- Check EventBridge rule status
- Check Lambda logs in CloudWatch
- Verify `should_heal=True` in DynamoDB

#### 5. "Lambda code files are missing in S3"
**Cause**: Lambda code not uploaded before deployment  
**Solution**: Run `python scripts/upload-lambdas.py` first

#### 6. High AWS costs
**Solution**:
- Run `python scripts/monitor.py` to check usage
- Review CloudWatch metrics
- Consider reducing monitoring frequency (currently 5 minutes)

### Debugging Tips

1. **Check CloudWatch Logs**
   ```bash
   aws logs tail /aws/lambda/dev-create-bucket --follow
   ```

2. **Verify DynamoDB Data**
   ```bash
   aws dynamodb scan --table-name dev-bucket-metadata --limit 10
   ```

3. **Test API directly**
   ```bash
   curl -X GET "$API_ENDPOINT/buckets" \
     -H "Authorization: Bearer $TOKEN"
   ```

4. **Check Cognito User**
   ```bash
   aws cognito-idp list-users --user-pool-id <USER_POOL_ID>
   ```

---

## 📡 API Reference

### Base URL
```
https://{api-id}.execute-api.{region}.amazonaws.com/{environment}
```

### Authentication
All endpoints require a Cognito ID token in the Authorization header:
```
Authorization: Bearer {id-token}
```

### Endpoints

#### POST /buckets
Create a new S3 bucket for a project.

**Request**:
```json
{
  "project_name": "my-web-app"
}
```

**Response** (200):
```json
{
  "project_name": "my-web-app",
  "bucket_name": "dev-my-web-app-a1b2c3d4",
  "status": "created",
  "region": "us-east-1",
  "user": "user@example.com"
}
```

**Errors**:
- `400`: Invalid project name (validation failed)
- `401`: Unauthorized (missing/invalid token)
- `409`: Project already exists
- `500`: Internal server error

---

#### GET /buckets
List all buckets for the authenticated user.

**Query Parameters** (optional):
- `project_name`: Get specific bucket by project name

**Response** (200):
```json
[
  {
    "display_name": "my-web-app",
    "bucket_name": "dev-my-web-app-a1b2c3d4",
    "user_email": "user@example.com",
    "created_at": "2025-01-15T10:30:00.000Z",
    "status": "active",
    "last_checked": "2025-01-15T10:35:00.000Z",
    "environment": "dev"
  }
]
```

**Admin Users**: See all buckets with `owner_user_id` and `user_role` fields.

**Errors**:
- `401`: Unauthorized
- `404`: Project not found (when using project_name query)

---

#### DELETE /buckets
Delete a bucket for a project.

**Query Parameters** (required):
- `project_name`: Project name of bucket to delete

**Response** (200):
```json
{
  "message": "Bucket deleted successfully",
  "bucket_name": "dev-my-web-app-a1b2c3d4",
  "deleted_by": "user@example.com",
  "should_heal": false
}
```

**Authorization**:
- Regular users can only delete their own buckets
- Business Admins can delete any bucket (`should_heal=true`)
- Super Admins can delete any bucket (`should_heal=false`)

**Errors**:
- `400`: Missing project_name parameter
- `401`: Unauthorized
- `403`: Forbidden (not owner/admin)
- `404`: Bucket not found
- `500`: Failed to delete bucket

---

### Project Name Validation

- **Format**: Lowercase letters, numbers, and hyphens only
- **Length**: 3-50 characters
- **Examples**:
  - ✅ Valid: `my-web-app`, `project123`, `api-service`
  - ❌ Invalid: `My-Web-App` (uppercase), `my_web_app` (underscores), `my web app` (spaces)

---

## 🔒 Security Best Practices

### 1. IAM Permissions
- ✅ Lambda functions use least-privilege IAM roles
- ✅ API Gateway uses Cognito authorizer
- ✅ Users can only access their own buckets (unless admin)

### 2. Bucket Security
- ✅ All buckets have public access blocked by default
- ✅ Server-side encryption (AES256) enabled
- ✅ Unique bucket names prevent collisions

### 3. Data Protection
- ✅ User data isolated by user_id in DynamoDB
- ✅ Audit trail for all deletions
- ✅ Sensitive data (user_id) not exposed in responses

### 4. Authentication
- ✅ Cognito ID tokens (JWT) with expiration
- ✅ Password policy enforced (8+ chars, uppercase, lowercase, numbers)
- ✅ Token validation on every API request

### 5. Monitoring
- ✅ All deletions logged with metadata
- ✅ CloudWatch logs for all Lambda functions
- ✅ Cost monitoring via `monitor.py`

### 6. Production Checklist

Before deploying to production:
- [ ] Change default passwords
- [ ] Enable MFA for AWS root account
- [ ] Review and restrict admin emails
- [ ] Enable CloudWatch alarms
- [ ] Set up SNS notifications for critical events
- [ ] Review IAM policies
- [ ] Enable CloudTrail
- [ ] Configure backup strategy for DynamoDB
- [ ] Test disaster recovery procedures

---

## 📝 Notes

### Bucket Naming Convention
```
{environment}-{project_name}-{uuid}
```
Example: `dev-my-web-app-a1b2c3d4`

### DynamoDB Schema

**Primary Key**: `project_name` (format: `{user_id}#{project_name}`)

**Attributes**:
- `bucket_name`: S3 bucket name
- `user_id`: Cognito user ID
- `user_email`: User email
- `display_name`: Project display name
- `created_at`: ISO timestamp
- `status`: `active` or `deleted`
- `last_checked`: Last monitoring check timestamp
- `deleted_at`: Deletion timestamp (if deleted)
- `deleted_by`: User ID who deleted (if deleted)
- `deleted_by_email`: Email of deleter (if deleted)
- `should_heal`: Boolean flag for healing
- `healed_at`: Healing timestamp (if healed)
- `heal_count`: Number of times healed
- `environment`: Environment name

**Global Secondary Indexes**:
- `bucket-name-index`: Query by bucket_name
- `user-id-index`: Query by user_id

### Cost Estimation

**Free Tier Limits**:
- Lambda: 1M requests/month
- API Gateway: 1M requests/month
- DynamoDB: 25GB storage, on-demand pricing
- S3: 5GB storage, first-tier pricing
- SNS: 1,000 emails/month
- EventBridge: 2M custom events/month

**Estimated Monthly Cost** (for small usage):
- Development: ~$0-5/month
- Production: ~$10-50/month (depends on usage)

---

## 🔗 Useful Commands

### AWS CLI Commands

```bash
# Get stack outputs
aws cloudformation describe-stacks \
  --stack-name s3-bucket-management-system-dev \
  --query 'Stacks[0].Outputs'

# List Lambda functions
aws lambda list-functions --query "Functions[?contains(FunctionName, 'bucket')]"

# View DynamoDB table
aws dynamodb scan --table-name dev-bucket-metadata --limit 5

# Check SNS subscriptions
aws sns list-subscriptions

# View CloudWatch logs
aws logs tail /aws/lambda/dev-create-bucket --follow
```

### Python Scripts

```bash
# Full deployment
python scripts/upload-lambdas.py && python scripts/deploy.py

# Quick code update
python scripts/upload-lambdas.py && python scripts/deploy.py --update-code

# Health check
python scripts/monitor.py

# View deletions
python scripts/audit_deletions.py

# Create user
python scripts/user_management.py create user@example.com Password123! "User Name"

# Run tests
python scripts/test.py
```

---

## 📚 Additional Resources

- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [AWS Cognito Documentation](https://docs.aws.amazon.com/cognito/)
- [DynamoDB Best Practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)
- [CloudFormation User Guide](https://docs.aws.amazon.com/cloudformation/)

---

## 🤝 Contributing

When contributing to this project:

1. Follow the existing code structure
2. Add tests for new features
3. Update this documentation
4. Test thoroughly before submitting
5. Follow security best practices

---

## 📄 License

[Add your license information here]

---

**Last Updated**: 2025-01-15  
**Version**: 1.0.0  
**Maintainer**: [Your Name/Team]

