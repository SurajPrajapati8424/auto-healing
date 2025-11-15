# S3 Bucket Management System - Professional Documentation

**Version:** 3.0  
**Last Updated:** 2025-01-15  
**Project Type:** Serverless AWS Application  
**Technology Stack:** AWS Lambda, API Gateway, DynamoDB, Cognito, S3, EventBridge, SNS

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Project Structure](#project-structure)
4. [Core Components](#core-components)
5. [Lambda Functions](#lambda-functions)
6. [Web Interface](#web-interface)
7. [Infrastructure](#infrastructure)
8. [Authentication & Authorization](#authentication--authorization)
9. [Data Models](#data-models)
10. [API Reference](#api-reference)
11. [Deployment Guide](#deployment-guide)
12. [Testing](#testing)
13. [Monitoring & Maintenance](#monitoring--maintenance)
14. [Troubleshooting](#troubleshooting)
15. [Security](#security)
16. [Cost Analysis](#cost-analysis)
17. [Development Workflow](#development-workflow)
18. [Scripts Reference](#scripts-reference)
19. [Configuration](#configuration)
20. [Best Practices](#best-practices)

---

## Executive Summary

The **S3 Bucket Management System** is a production-ready, serverless application built on AWS that provides secure, automated management of S3 buckets with advanced features including:

- **User Authentication**: AWS Cognito-based authentication with role-based access control
- **Automated Bucket Management**: Create, list, and delete S3 buckets via RESTful API
- **Intelligent Healing**: Automatic detection and restoration of deleted buckets based on business rules
- **Comprehensive Audit Trail**: Complete tracking of all bucket operations with metadata
- **Advanced Configuration**: Support for versioning, lifecycle policies, and custom configurations
- **Modern Web Interface**: Responsive, user-friendly web UI for non-technical users
- **Enterprise Features**: Role-based permissions (Super Admin, Business Admin, Regular Users)

### Key Technologies

- **Compute**: AWS Lambda (Python 3.9)
- **API**: Amazon API Gateway (REST)
- **Database**: Amazon DynamoDB (NoSQL)
- **Authentication**: Amazon Cognito (User Pools & Identity Pools)
- **Storage**: Amazon S3
- **Orchestration**: AWS EventBridge (Scheduled Tasks)
- **Notifications**: Amazon SNS
- **Infrastructure as Code**: AWS CloudFormation

---

## System Architecture

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Web Browser                              │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  index.html + script.js + style.css                     │   │
│  │  - Cognito Authentication                                │   │
│  │  - Bucket Management UI                                  │   │
│  │  - Real-time Status Updates                             │   │
│  └──────────────────────────────────────────────────────────┘   │
└───────────────────────┬─────────────────────────────────────────┘
                        │ HTTPS
                        │
┌───────────────────────▼─────────────────────────────────────────┐
│                    API Gateway (REST)                           │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Cognito Authorizer                                      │  │
│  │  - Validates JWT Tokens                                  │  │
│  │  - Extracts User Claims                                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Endpoints:                                                     │
│  POST /buckets  → Create Bucket                                │
│  GET  /buckets  → List Buckets                                 │
│  DELETE /buckets → Delete Bucket                               │
└───────────────────────┬─────────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   Lambda     │ │   Lambda     │ │   Lambda     │
│ Create-Bucket│ │ List-Buckets │ │Delete-Bucket │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │
       └────────────┬───┴────────────────┘
                    │
        ┌───────────┼───────────┐
        │           │           │
        ▼           ▼           ▼
┌──────────┐  ┌──────────┐  ┌──────────┐
│    S3    │  │ DynamoDB │  │   SNS    │
│ Buckets  │  │ Metadata │  │Notif.    │
└──────────┘  └──────────┘  └──────────┘

┌───────────────────────────────────────────────────────────────┐
│              EventBridge (Scheduled: Every 5 min)            │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  Monitor-Buckets Lambda                                  │ │
│  │  - Checks bucket existence                              │ │
│  │  - Heals deleted buckets (if should_heal=True)          │ │
│  │  - Updates last_checked timestamps                      │ │
│  └──────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **User Authentication Flow**:
   - User signs in via Cognito → Receives ID Token, Access Token, Refresh Token
   - ID Token stored in browser localStorage
   - Token sent in `Authorization: Bearer {token}` header with each API request

2. **Bucket Creation Flow**:
   - Web UI → API Gateway → Create-Bucket Lambda
   - Lambda validates project name, creates S3 bucket, configures security
   - Stores metadata in DynamoDB, sends SNS notification
   - Returns bucket details to user

3. **Bucket Listing Flow**:
   - Web UI → API Gateway → List-Buckets Lambda
   - Lambda queries DynamoDB (user-specific or admin view)
   - Returns filtered bucket list based on user role

4. **Bucket Deletion Flow**:
   - Web UI → API Gateway → Delete-Bucket Lambda
   - Lambda validates permissions, deletes bucket from S3
   - Records deletion metadata in DynamoDB (who, when, should_heal flag)
   - Returns deletion confirmation

5. **Monitoring & Healing Flow**:
   - EventBridge triggers Monitor-Buckets Lambda every 5 minutes
   - Lambda scans DynamoDB for buckets needing monitoring
   - Checks S3 bucket existence, heals if missing and should_heal=True
   - Updates metadata and sends notifications

---

## Project Structure

```
s3-bucket-manager/
│
├── .vscode/                                    # VS Code configuration
│   ├── DOC_V3.md                              # This documentation
│   ├── PROJECT_DOCUMENTATION.md               # General documentation
│   └── PROBLEM_SOLVER.md                     # Architecture rationale
│
├── infrastructure/                             # Infrastructure as Code
│   ├── cloudformation-template.yaml           # Main CloudFormation template (529 lines)
│   └── parameters.json                        # Deployment parameters
│
├── lambda-functions/                           # Lambda function source code
│   ├── create-bucket/
│   │   └── index.py                           # Create bucket Lambda (446 lines)
│   ├── delete-bucket/
│   │   └── index.py                           # Delete bucket Lambda (264 lines)
│   ├── list-buckets/
│   │   └── index.py                           # List buckets Lambda (176 lines)
│   └── monitor-buckets/
│       └── index.py                           # Monitor & heal Lambda (410 lines)
│
├── web-interface/                             # Frontend application
│   ├── index.html                             # Main HTML file (165 lines)
│   ├── script.js                              # JavaScript logic (1042 lines)
│   ├── style.css                              # CSS styling (447 lines)
│   └── config.js                              # Auto-generated config (gitignored)
│
├── scripts/                                   # Utility and deployment scripts
│   ├── deploy.py                              # CloudFormation deployment (278 lines)
│   ├── upload-lambdas.py                     # Lambda packaging & upload (231 lines)
│   ├── test.py                                # Comprehensive test suite (910 lines)
│   ├── monitor.py                             # System health monitoring (213 lines)
│   ├── user_management.py                     # Cognito user management (268 lines)
│   └── audit_deletions.py                     # Deletion audit viewer (240 lines)
│
├── tests/                                     # Test files directory
│
├── out/                                       # Build artifacts
│
├── README.md                                  # Main project README
├── DEPLOYMENT_GUIDE.md                        # Deployment instructions
└── .gitignore                                 # Git ignore rules
```

### File Statistics

- **Total Lines of Code**: ~4,500+ lines
- **Lambda Functions**: 4 functions, ~1,296 lines
- **Web Interface**: ~1,654 lines
- **Scripts**: ~2,040 lines
- **Infrastructure**: 529 lines (CloudFormation)
- **Documentation**: Multiple comprehensive guides

---

## Core Components

### 1. Authentication System

**Technology**: AWS Cognito

**Components**:
- **Cognito User Pool**: User registration, authentication, password management
- **Cognito User Pool Client**: Application client configuration
- **Cognito Identity Pool**: Federated identity for AWS service access
- **Cognito Authorizer**: API Gateway integration for token validation

**User Attributes**:
- `email` (required, verified)
- `name` (required)
- `sub` (Cognito User ID, automatically generated)

**User Groups**:
- `admins`: Super Administrators (highest privilege, no auto-heal on delete)
- `business-admins`: Business Administrators (can delete any bucket, auto-heal enabled)
- Regular users: No group membership (can only manage own buckets)

**Token Configuration**:
- Access Token: 1 hour validity
- ID Token: 1 hour validity
- Refresh Token: 30 days validity

**Authentication Flows**:
- `USER_PASSWORD_AUTH`: Direct username/password authentication
- `ALLOW_REFRESH_TOKEN_AUTH`: Token refresh capability

### 2. Metadata Storage

**Technology**: Amazon DynamoDB

**Table Name**: `{environment}-bucket-metadata`

**Primary Key**: `project_name` (String)
- Format: `{user_id}#{project_name}`
- Example: `us-east-1:abc123#my-web-app`

**Global Secondary Indexes**:
1. **bucket-name-index**: Query by `bucket_name` (HASH)
2. **user-id-index**: Query by `user_id` (HASH)

**Table Features**:
- Billing Mode: `PAY_PER_REQUEST` (on-demand)
- DynamoDB Streams: Enabled (NEW_AND_OLD_IMAGES)
- Point-in-Time Recovery: Enabled
- Encryption: Server-side encryption (default)

### 3. Notification System

**Technology**: Amazon SNS

**Topic Name**: `{environment}-bucket-notifications`

**Subscriptions**:
- Email subscription (configured via `NotificationEmail` parameter)

**Notification Events**:
- Bucket creation
- Bucket healing/recovery
- System alerts

### 4. Monitoring System

**Technology**: AWS EventBridge

**Schedule**: Every 5 minutes (`rate(5 minutes)`)

**Target**: Monitor-Buckets Lambda function

**Functionality**:
- Scans all buckets in DynamoDB
- Checks S3 bucket existence
- Heals buckets when `status='deleted'` and `should_heal=True`
- Updates `last_checked` timestamps
- Sends healing notifications

---

## Lambda Functions

### 1. Create-Bucket Lambda

**Function Name**: `{environment}-create-bucket`  
**Runtime**: Python 3.9  
**Timeout**: 30 seconds  
**Memory**: 128 MB  
**Handler**: `index.lambda_handler`

#### Environment Variables

- `TABLE_NAME`: DynamoDB table name
- `SNS_TOPIC`: SNS topic ARN
- `ENVIRONMENT`: Environment name (dev/staging/prod)
- `REGION`: AWS region

#### Functionality

**Input Validation**:
- Validates project name format (lowercase, alphanumeric, hyphens only)
- Validates project name length (3-50 characters)
- Rejects uppercase letters explicitly
- Validates versioning value (Enabled/Disabled)
- Validates lifecycle policy (None/Auto-Archive/Auto-Delete/Custom)
- Validates custom lifecycle configuration JSON structure

**Bucket Creation**:
- Generates unique bucket name: `{environment}-{project_name}-{uuid8}`
- Creates S3 bucket (region-aware: us-east-1 vs other regions)
- Configures public access block (all settings enabled)
- Enables server-side encryption (AES256)
- Configures versioning (if requested)
- Applies lifecycle policy (if requested)

**Metadata Storage**:
- Stores bucket metadata in DynamoDB
- Primary key: `{user_id}#{project_name}`
- Stores: bucket_name, user_id, user_email, display_name, created_at, status, environment, versioning, lifecycle_policy
- Stores custom lifecycle configuration (if Custom policy)

**Error Handling**:
- Validates DynamoDB write success (critical)
- Rolls back bucket creation if metadata storage fails
- Non-blocking errors for configuration (logs warnings)
- Returns detailed error messages

**Response Format**:
```json
{
  "project_name": "my-web-app",
  "bucket_name": "dev-my-web-app-a1b2c3d4",
  "status": "created",
  "region": "us-east-1",
  "user": "user@example.com",
  "warnings": []  // Optional: configuration warnings
}
```

#### Key Functions

- `_validate_custom_lifecycle_config(custom_config)`: Validates custom lifecycle JSON structure
- `lambda_handler(event, context)`: Main handler function

#### API Endpoint

**POST** `/buckets`

**Request Body**:
```json
{
  "project_name": "my-web-app",
  "versioning": "Enabled",  // Optional, default: "Enabled"
  "lifecycle_policy": "None",  // Optional, default: "None"
  "custom_lifecycle_config": {}  // Required if lifecycle_policy="Custom"
}
```

**Response Codes**:
- `200`: Success
- `400`: Validation error
- `401`: Unauthorized
- `409`: Project already exists
- `500`: Internal server error

---

### 2. List-Buckets Lambda

**Function Name**: `{environment}-list-buckets`  
**Runtime**: Python 3.9  
**Timeout**: 30 seconds  
**Memory**: 128 MB  
**Handler**: `index.lambda_handler`

#### Environment Variables

- `TABLE_NAME`: DynamoDB table name
- `USER_POOL_ID`: Cognito User Pool ID

#### Functionality

**Role-Based Access Control**:
- **Regular Users**: Query by `user_id` using `user-id-index` GSI
- **Business Admins**: Scan all buckets, add `user_role: 'business_admin'`
- **Super Admins**: Scan all buckets, add `owner_user_id` and `user_role: 'super_admin'`

**Query Modes**:
1. **List All**: GET `/buckets` (no query parameters)
2. **Get Specific**: GET `/buckets?project_name={name}`

**Admin Features**:
- Admins can access any project by `display_name`
- Owner information exposed in responses
- Role indicator included in responses

**Response Format**:
```json
[
  {
    "display_name": "my-web-app",
    "bucket_name": "dev-my-web-app-a1b2c3d4",
    "user_email": "user@example.com",
    "created_at": "2025-01-15T10:30:00.000Z",
    "status": "active",
    "last_checked": "2025-01-15T10:35:00.000Z",
    "versioning": "Enabled",
    "lifecycle_policy": "Auto-Archive",
    "environment": "dev",
    "owner_user_id": "...",  // Admin only
    "user_role": "super_admin"  // Admin only
  }
]
```

#### Key Functions

- `get_user_groups(user_email)`: Retrieves Cognito groups for user
- `is_super_admin(user_email)`: Checks if user is in 'admins' group
- `is_business_admin(user_email)`: Checks if user is in 'business-admins' group
- `is_admin(user_email)`: Checks if user is any type of admin
- `lambda_handler(event, context)`: Main handler function

#### API Endpoint

**GET** `/buckets` or **GET** `/buckets?project_name={name}`

**Response Codes**:
- `200`: Success
- `401`: Unauthorized
- `404`: Project not found (when querying specific project)
- `500`: Internal server error

---

### 3. Delete-Bucket Lambda

**Function Name**: `{environment}-delete-bucket`  
**Runtime**: Python 3.9  
**Timeout**: 30 seconds  
**Memory**: 128 MB  
**Handler**: `index.lambda_handler`

#### Environment Variables

- `TABLE_NAME`: DynamoDB table name
- `USER_POOL_ID`: Cognito User Pool ID
- `REGION`: AWS region
- `ADMIN_EMAILS`: Comma-separated admin emails (optional)

#### Functionality

**Authorization Logic**:
- Regular users can only delete their own buckets
- Business Admins can delete any bucket (`should_heal=True`)
- Super Admins can delete any bucket (`should_heal=False`)
- Admin lookup: First by Cognito groups, then by `ADMIN_EMAILS` env var

**Deletion Process**:
1. Validates bucket exists in DynamoDB
2. Checks user permissions (owner or admin)
3. Lists and deletes all objects in bucket (required before bucket deletion)
4. Deletes bucket from S3
5. Updates DynamoDB with deletion metadata

**Deletion Metadata**:
- `deleted_at`: ISO timestamp
- `deleted_by`: User ID (Cognito sub)
- `deleted_by_email`: User email
- `should_heal`: Boolean flag (determines if monitoring will restore)
- `status`: Set to 'deleted'

**Healing Logic** (`should_heal` flag):
- **Owner deletes own bucket**: `should_heal=False` (intentional deletion)
- **Business Admin deletes**: `should_heal=True` (might be accidental)
- **Super Admin deletes**: `should_heal=False` (authoritative deletion)

**Response Format**:
```json
{
  "message": "Bucket deleted successfully",
  "bucket_name": "dev-my-web-app-a1b2c3d4",
  "deleted_by": "user@example.com",
  "should_heal": false
}
```

#### Key Functions

- `get_user_groups(user_email)`: Retrieves Cognito groups
- `is_super_admin(user_email)`: Checks super admin status (groups + env var)
- `is_business_admin(user_email)`: Checks business admin status
- `is_admin(user_email)`: Checks if any admin type
- `lambda_handler(event, context)`: Main handler function

#### API Endpoint

**DELETE** `/buckets?project_name={name}`

**Response Codes**:
- `200`: Success
- `400`: Missing project_name parameter
- `401`: Unauthorized
- `403`: Forbidden (not owner/admin)
- `404`: Bucket not found
- `500`: Failed to delete bucket

---

### 4. Monitor-Buckets Lambda

**Function Name**: `{environment}-monitor-buckets`  
**Runtime**: Python 3.9  
**Timeout**: 300 seconds (5 minutes)  
**Memory**: 256 MB  
**Handler**: `index.lambda_handler`

#### Environment Variables

- `TABLE_NAME`: DynamoDB table name
- `SNS_TOPIC`: SNS topic ARN
- `ENVIRONMENT`: Environment name (dev/staging/prod)
- `REGION`: AWS region

#### Functionality

**Monitoring Scope**:
- Scans all buckets in DynamoDB table
- Filters buckets that need monitoring:
  - Active buckets (`status='active'`)
  - Deleted buckets with `should_heal=True` and `status='deleted'`

**Bucket Health Check**:
- Uses `s3.head_bucket()` to verify bucket existence
- Handles multiple error types (ClientError, NoSuchBucket exceptions)
- Updates `last_checked` timestamp for existing buckets

**Healing Logic**:
- Detects missing buckets via `NoSuchBucket` errors or 404 responses
- Checks `should_heal` flag from DynamoDB metadata
- Only heals buckets where `should_heal=True` and `status='deleted'`
- Preserves deletion history for audit trail

**Bucket Restoration Process**:
1. Retrieves stored bucket configuration from DynamoDB:
   - `versioning` setting
   - `lifecycle_policy` setting
   - `custom_lifecycle_config` (if Custom policy)
2. Recreates bucket (region-aware)
3. Restores security configuration:
   - Public access block (all settings enabled)
   - Server-side encryption (AES256)
4. Restores versioning (if originally enabled)
5. Restores lifecycle policy:
   - Auto-Archive: Transitions to Glacier after 30 days
   - Auto-Delete: Deletes noncurrent versions after 90 days
   - Custom: Restores custom JSON configuration
6. Updates DynamoDB:
   - Sets `status='active'`
   - Records `healed_at` timestamp
   - Increments `heal_count`
   - Removes `should_heal` flag
   - Preserves deletion metadata (deleted_at, deleted_by, deleted_by_email)
7. Sends SNS notification with deletion history

**Error Handling**:
- Non-blocking errors for configuration steps (logs warnings)
- Continues processing other buckets if one fails
- Comprehensive error logging with tracebacks

**Response Format**:
```json
{
  "message": "Monitoring completed",
  "processed_buckets": 10,
  "healed_buckets": 2
}
```

#### Key Functions

- `lambda_handler(event, context)`: Main handler function
  - Scans DynamoDB for buckets to monitor
  - Processes each bucket
  - Returns summary statistics
- `recreate_bucket(bucket_name, project_name, user_email, display_name, deletion_info)`: 
  - Recreates deleted bucket with original configuration
  - Handles all configuration restoration
  - Returns boolean success status

#### Trigger

**EventBridge Rule**: Runs every 5 minutes
- Schedule Expression: `rate(5 minutes)`
- State: ENABLED
- Target: Monitor-Buckets Lambda function

#### Monitoring Statistics

Tracks:
- `processed_buckets`: Total buckets checked
- `healed_buckets`: Number of buckets successfully restored

---

## Web Interface

The web interface is a single-page application (SPA) built with vanilla JavaScript, HTML5, and CSS3. It provides a modern, responsive user experience for bucket management.

### Components

#### 1. HTML Structure (`index.html`)

**Main Sections**:
- **Header**: Application title and description
- **Authentication Section**: Sign up, sign in, and confirmation forms
- **Application Section**: Bucket management interface

**Key Elements**:
- Sign In Form: Email and password fields
- Sign Up Form: Name, email, and password fields
- Confirmation Form: Email verification code input
- Bucket Configuration Section:
  - Versioning toggle (Enabled/Disabled)
  - Lifecycle policy selector (None/Auto-Archive/Auto-Delete/Custom)
  - Custom lifecycle JSON textarea (for Custom policy)
- Bucket List: Display area with filtering and sorting controls

**Dependencies**:
- AWS SDK v2.1400.0 (CDN)
- `config.js` (auto-generated during deployment)

#### 2. JavaScript Logic (`script.js`)

**Global Variables**:
- `cognitoUser`: AWS Cognito Identity Service Provider instance
- `currentUser`: Currently authenticated user object
- `currentSession`: Active user session
- `bucketsData`: Array storing bucket data for client-side operations

**Authentication Functions**:
- `signUp()`: Creates new Cognito user account
- `confirmSignUp()`: Confirms email verification code
- `resendConfirmation()`: Resends verification code
- `signIn()`: Authenticates user and retrieves tokens
- `signOut()`: Clears tokens and resets session
- `checkAuthState()`: Validates stored tokens on page load
- `loadUserInfo()`: Extracts and displays user information from ID token

**Bucket Management Functions**:
- `createBucket()`: Creates new bucket via API
  - Validates project name client-side
  - Collects versioning and lifecycle configuration
  - Validates custom lifecycle JSON (if Custom policy)
  - Sends POST request to API
  - Handles success/error responses
- `loadBuckets()`: Retrieves bucket list from API
  - Fetches all buckets for authenticated user
  - Handles admin view (if applicable)
  - Populates buckets list
- `deleteBucket(projectName)`: Deletes bucket via API
  - Confirms deletion with user
  - Sends DELETE request
  - Reloads bucket list on success
- `applyFilters()`: Client-side filtering and sorting
  - Status filter (all/active/deleted)
  - Sort options: newest, oldest, name (A-Z), name (Z-A), status
- `displayBuckets(buckets)`: Renders bucket list HTML

**Configuration Functions**:
- `updateLifecycleDescription()`: Updates description text based on selected policy
- `toggleCustomPolicy()`: Shows/hides custom JSON textarea
- `validateCustomPolicy()`: Comprehensive JSON validation
  - Validates JSON syntax
  - Validates rule structure (ID, Status, Expiration, Transitions, etc.)
  - Validates storage classes
  - Validates field names (catches common errors like "ExpirationDays" vs "Expiration.Days")
  - Provides detailed error messages

**UI Utility Functions**:
- `showNotification(message, type, duration)`: Toast notification system
  - Types: success, error, warning, info
  - Auto-dismisses after duration (default 5 seconds)
  - Positioned top-right corner
  - Supports manual dismissal
- `showStatus(message, type)`: Legacy status display (redirects to notifications)
- `setLoading(elementId, loading)`: Manages button loading states
- `formatDate(dateString)`: Formats ISO timestamps for display

**Event Handlers**:
- Enter key support for form submissions
- Dynamic lifecycle policy description updates
- Filter and sort controls

#### 3. CSS Styling (`style.css`)

**Design System**:
- **Color Scheme**: Purple gradient theme (#667eea to #764ba2)
- **Typography**: Segoe UI font family
- **Layout**: Responsive grid system
- **Components**: Modern card-based design

**Key Styles**:
- **Container**: White card with rounded corners and shadow
- **Header**: Gradient background with white text
- **Forms**: Clean input fields with focus states
- **Buttons**: Gradient buttons with hover effects
- **Notifications**: Toast-style notifications (top-right)
- **Bucket Items**: Card layout with hover effects
- **Responsive**: Mobile-friendly breakpoints at 768px

**Notification System**:
- Fixed position (top-right)
- Slide-in animation
- Color-coded by type (success: green, error: red, warning: yellow, info: blue)
- Auto-dismiss with fade-out animation

**Responsive Features**:
- Stacked layout on mobile
- Flexible form layouts
- Adaptive button sizes
- Mobile-optimized notifications

#### 4. Configuration File (`config.js`)

**Auto-Generated**: Created during CloudFormation deployment

**Structure**:
```javascript
const CONFIG = {
    apiEndpoint: 'https://{api-id}.execute-api.{region}.amazonaws.com/{env}',
    region: 'us-east-1',
    userPoolId: 'us-east-1_xxxxxxxx',
    userPoolClientId: 'xxxxxxxxxxxxxxxxxxxxxxxxxx',
    identityPoolId: 'us-east-1:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx',
    environment: 'dev'
};
```

**Generated By**: `scripts/deploy.py` after successful stack deployment

---

## Infrastructure

### CloudFormation Template

**File**: `infrastructure/cloudformation-template.yaml`  
**Lines**: 529  
**Format**: YAML  
**Version**: 2010-09-09

#### Parameters

1. **NotificationEmail** (String)
   - Description: Email for SNS notifications
   - Default: `your-email@example.com`
   - Required: Yes

2. **Environment** (String)
   - Description: Deployment environment
   - Allowed Values: `dev`, `staging`, `prod`
   - Default: `dev`
   - Required: Yes

3. **AdminEmails** (CommaDelimitedList)
   - Description: Comma-separated admin email addresses
   - Default: `""`
   - Required: No
   - Example: `admin1@example.com,admin2@example.com`

#### Resources Created

**1. Cognito User Pool** (`CognitoUserPool`)
- User authentication and management
- Password policy: 8+ chars, uppercase, lowercase, numbers
- Email verification required
- Custom attributes: `name`, `email`

**2. Cognito User Pool Client** (`CognitoUserPoolClient`)
- Application client configuration
- Auth flows: `USER_PASSWORD_AUTH`, `REFRESH_TOKEN_AUTH`
- Token validity: 1 hour (Access/ID), 30 days (Refresh)

**3. Cognito Identity Pool** (`CognitoIdentityPool`)
- Federated identity for AWS service access
- Authenticated identities only

**4. Cognito Groups**:
- **AdminGroup** (`admins`): Super Administrators
- **BusinessAdminGroup** (`business-admins`): Business Administrators

**5. DynamoDB Table** (`BucketMetadataTable`)
- Table name: `{environment}-bucket-metadata`
- Billing: `PAY_PER_REQUEST`
- Primary Key: `project_name` (String)
- GSI 1: `bucket-name-index` (bucket_name)
- GSI 2: `user-id-index` (user_id)
- Features: Streams enabled, Point-in-Time Recovery enabled

**6. SNS Topic** (`BucketNotificationTopic`)
- Topic name: `{environment}-bucket-notifications`
- Email subscription to NotificationEmail

**7. IAM Role** (`BucketManagementRole`)
- Lambda execution role
- Permissions:
  - S3: CreateBucket, DeleteBucket, ListBucket, PutBucket* operations
  - DynamoDB: Full table access (GetItem, PutItem, UpdateItem, Query, Scan)
  - SNS: Publish to notification topic
  - Cognito: List groups for users
  - S3: Read from Lambda deployment bucket

**8. Lambda Functions** (4 functions):
- Create-Bucket Function
- List-Buckets Function
- Delete-Bucket Function
- Monitor-Buckets Function

**9. API Gateway** (`BucketManagementAPI`)
- REST API
- Regional endpoint
- CORS enabled
- Cognito authorizer

**10. API Gateway Resources**:
- `/buckets` resource
- Methods: POST (create), GET (list), DELETE (delete)
- OPTIONS methods for CORS

**11. EventBridge Rule** (`MonitoringRule`)
- Schedule: `rate(5 minutes)`
- Target: Monitor-Buckets Lambda

**12. Cognito Identity Pool Role** (`CognitoAuthRole`)
- IAM role for authenticated users
- Permissions: API Gateway invoke

#### Outputs

- `APIEndpoint`: API Gateway endpoint URL
- `UserPoolId`: Cognito User Pool ID
- `UserPoolClientId`: Cognito User Pool Client ID
- `IdentityPoolId`: Cognito Identity Pool ID
- `DynamoDBTable`: DynamoDB table name
- `SNSTopic`: SNS topic ARN

### Deployment Parameters

**File**: `infrastructure/parameters.json`

```json
{
  "NotificationEmail": "your-email@example.com",
  "Environment": "dev",
  "AdminEmails": "admin1@example.com,admin2@example.com"
}
```

---

## Authentication & Authorization

### Authentication Flow

1. **User Registration**:
   - User provides: name, email, password
   - Cognito creates user account
   - Email verification code sent
   - User confirms email with code

2. **User Sign In**:
   - User provides: email, password
   - Cognito authenticates via `USER_PASSWORD_AUTH` flow
   - Returns: Access Token, ID Token, Refresh Token
   - Tokens stored in browser `localStorage`

3. **API Request Authentication**:
   - ID Token sent in `Authorization: Bearer {token}` header
   - API Gateway Cognito Authorizer validates token
   - User claims extracted and passed to Lambda
   - Lambda receives: `user_id` (sub), `email`, groups

4. **Token Refresh**:
   - Refresh Token used to obtain new Access/ID tokens
   - Token expiration: 1 hour (can be refreshed)

### Authorization Model

#### User Roles

**1. Regular Users** (No group membership):
- **Create**: Own buckets only
- **List**: Own buckets only
- **Delete**: Own buckets only (`should_heal=False`)
- **Access**: Limited to own projects

**2. Business Admins** (`business-admins` group):
- **Create**: Any bucket
- **List**: All buckets (with owner information)
- **Delete**: Any bucket (`should_heal=True`)
- **Access**: Full system access with healing enabled

**3. Super Admins** (`admins` group or `ADMIN_EMAILS`):
- **Create**: Any bucket
- **List**: All buckets (with `owner_user_id` and `user_role`)
- **Delete**: Any bucket (`should_heal=False`)
- **Access**: Full system access, no auto-healing

#### Permission Matrix

| Action | Regular User | Business Admin | Super Admin |
|--------|--------------|----------------|-------------|
| Create own bucket | ✅ | ✅ | ✅ |
| Create other's bucket | ❌ | ✅ | ✅ |
| List own buckets | ✅ | ✅ | ✅ |
| List all buckets | ❌ | ✅ | ✅ |
| Delete own bucket | ✅ (`should_heal=False`) | ✅ (`should_heal=True`) | ✅ (`should_heal=False`) |
| Delete other's bucket | ❌ | ✅ (`should_heal=True`) | ✅ (`should_heal=False`) |

### Group Management

**Add User to Group**:
```bash
aws cognito-idp admin-add-user-to-group \
  --user-pool-id <USER_POOL_ID> \
  --username <EMAIL> \
  --group-name admins
```

**Remove User from Group**:
```bash
aws cognito-idp admin-remove-user-from-group \
  --user-pool-id <USER_POOL_ID> \
  --username <EMAIL> \
  --group-name admins
```

**List User Groups**:
```bash
aws cognito-idp admin-list-groups-for-user \
  --user-pool-id <USER_POOL_ID> \
  --username <EMAIL>
```

---

## Data Models

### DynamoDB Schema

#### Primary Table: `{environment}-bucket-metadata`

**Primary Key**: `project_name` (String)
- Format: `{user_id}#{project_name}`
- Example: `us-east-1:abc123#my-web-app`

#### Attributes

**Required Attributes**:
- `project_name` (String): Primary key, format `{user_id}#{project_name}`
- `bucket_name` (String): S3 bucket name
- `user_id` (String): Cognito user ID (sub)
- `user_email` (String): User email address
- `display_name` (String): Project display name (lowercase project_name)
- `created_at` (String): ISO 8601 timestamp
- `status` (String): `active` or `deleted`
- `last_checked` (String): ISO 8601 timestamp
- `environment` (String): Environment name (dev/staging/prod)

**Optional Attributes**:
- `versioning` (String): `Enabled` or `Disabled`
- `lifecycle_policy` (String): `None`, `Auto-Archive`, `Auto-Delete`, or `Custom`
- `custom_lifecycle_config` (Map): Custom lifecycle configuration JSON (if Custom policy)
- `deleted_at` (String): ISO 8601 timestamp (when deleted)
- `deleted_by` (String): User ID who deleted (Cognito sub)
- `deleted_by_email` (String): Email of user who deleted
- `should_heal` (Boolean): Whether bucket should be auto-healed
- `healed_at` (String): ISO 8601 timestamp (when healed)
- `heal_count` (Number): Number of times bucket has been healed

#### Global Secondary Indexes

**1. bucket-name-index**:
- Partition Key: `bucket_name` (String)
- Projection: ALL attributes
- Use Case: Query by bucket name

**2. user-id-index**:
- Partition Key: `user_id` (String)
- Projection: ALL attributes
- Use Case: Query all buckets for a user

#### Example Item

```json
{
  "project_name": "us-east-1:abc123#my-web-app",
  "bucket_name": "dev-my-web-app-a1b2c3d4",
  "user_id": "us-east-1:abc123",
  "user_email": "user@example.com",
  "display_name": "my-web-app",
  "created_at": "2025-01-15T10:30:00.000Z",
  "status": "active",
  "last_checked": "2025-01-15T10:35:00.000Z",
  "environment": "dev",
  "versioning": "Enabled",
  "lifecycle_policy": "Auto-Archive"
}
```

#### Deleted Item Example

```json
{
  "project_name": "us-east-1:abc123#my-web-app",
  "bucket_name": "dev-my-web-app-a1b2c3d4",
  "user_id": "us-east-1:abc123",
  "user_email": "user@example.com",
  "display_name": "my-web-app",
  "created_at": "2025-01-15T10:30:00.000Z",
  "status": "deleted",
  "deleted_at": "2025-01-15T11:00:00.000Z",
  "deleted_by": "us-east-1:xyz789",
  "deleted_by_email": "admin@example.com",
  "should_heal": true,
    "last_checked": "2025-01-15T11:05:00.000Z"
}
```

#### Healed Item Example

```json
{
  "project_name": "us-east-1:abc123#my-web-app",
  "bucket_name": "dev-my-web-app-a1b2c3d4",
  "user_id": "us-east-1:abc123",
  "user_email": "user@example.com",
  "display_name": "my-web-app",
  "created_at": "2025-01-15T10:30:00.000Z",
  "status": "active",
  "deleted_at": "2025-01-15T11:00:00.000Z",
  "deleted_by": "us-east-1:xyz789",
  "deleted_by_email": "admin@example.com",
  "healed_at": "2025-01-15T11:05:00.000Z",
  "heal_count": 1,
  "last_checked": "2025-01-15T11:05:00.000Z"
}
```

---

## API Reference

### Base URL

```
https://{api-id}.execute-api.{region}.amazonaws.com/{environment}
```

### Authentication


All endpoints require authentication via Cognito ID token in the Authorization header:

```
Authorization: Bearer {id-token}
```

### Endpoints

#### POST /buckets

Create a new S3 bucket for a project.

**Request Headers**:
```
Content-Type: application/json
Authorization: Bearer {id-token}
```

**Request Body**:
```json
{
  "project_name": "my-web-app",
  "versioning": "Enabled",  // Optional, default: "Enabled"
  "lifecycle_policy": "None",  // Optional, default: "None"
  "custom_lifecycle_config": {}  // Required if lifecycle_policy="Custom"
}
```

**Valid Values**:
- `versioning`: `"Enabled"` or `"Disabled"`
- `lifecycle_policy`: `"None"`, `"Auto-Archive"`, `"Auto-Delete"`, or `"Custom"`
- `custom_lifecycle_config`: Valid S3 lifecycle configuration JSON (required if `lifecycle_policy="Custom"`)

**Response** (200 OK):
```json
{
  "project_name": "my-web-app",
  "bucket_name": "dev-my-web-app-a1b2c3d4",
  "status": "created",
  "region": "us-east-1",
  "user": "user@example.com",
  "warnings": []  // Optional: configuration warnings
}
```

**Error Responses**:
- `400 Bad Request`: Invalid project name, validation error, or invalid custom lifecycle config
- `401 Unauthorized`: Missing or invalid token
- `409 Conflict`: Project already exists for this user
- `500 Internal Server Error`: Failed to create bucket or store metadata

**Example**:
```bash
curl -X POST "https://api-id.execute-api.us-east-1.amazonaws.com/dev/buckets" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -d '{
    "project_name": "my-web-app",
    "versioning": "Enabled",
    "lifecycle_policy": "Auto-Archive"
  }'
```

---

#### GET /buckets

List all buckets for the authenticated user.

**Query Parameters** (optional):
- `project_name`: Get specific bucket by project name

**Request Headers**:
```
Authorization: Bearer {id-token}
```

**Response** (200 OK):
```json
[
  {
    "display_name": "my-web-app",
    "bucket_name": "dev-my-web-app-a1b2c3d4",
    "user_email": "user@example.com",
    "created_at": "2025-01-15T10:30:00.000Z",
    "status": "active",
    "last_checked": "2025-01-15T10:35:00.000Z",
    "versioning": "Enabled",
    "lifecycle_policy": "Auto-Archive",
    "environment": "dev"
  }
]
```

**Admin Response** (200 OK) - Includes additional fields:
```json
[
  {
    "display_name": "my-web-app",
    "bucket_name": "dev-my-web-app-a1b2c3d4",
    "user_email": "user@example.com",
    "owner_user_id": "us-east-1:abc123",
    "user_role": "super_admin",
    "created_at": "2025-01-15T10:30:00.000Z",
    "status": "active",
    "last_checked": "2025-01-15T10:35:00.000Z",
    "environment": "dev"
  }
]
```

**Query by Project Name** (GET `/buckets?project_name=my-web-app`):
- Returns single bucket object (not array)
- Regular users: Returns only if they own the project
- Admins: Returns any project by display_name

**Error Responses**:
- `401 Unauthorized`: Missing or invalid token
- `404 Not Found`: Project not found (when querying specific project)
- `500 Internal Server Error`: Failed to query DynamoDB

**Example**:
```bash
# List all buckets
curl -X GET "https://api-id.execute-api.us-east-1.amazonaws.com/dev/buckets" \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."

# Get specific bucket
curl -X GET "https://api-id.execute-api.us-east-1.amazonaws.com/dev/buckets?project_name=my-web-app" \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
```

---

#### DELETE /buckets

Delete a bucket for a project.

**Query Parameters** (required):
- `project_name`: Project name of bucket to delete

**Request Headers**:
```
Authorization: Bearer {id-token}

**Query by Project Name** (GET `/buckets?project_name=my-web-app`):
- Returns single bucket object (not array)
- Regular users: Returns only if they own the project
- Admins: Returns any project by display_name

**Error Responses**:
- `401 Unauthorized`: Missing or invalid token
- `404 Not Found`: Project not found (when querying specific project)
- `500 Internal Server Error`: Failed to query DynamoDB

**Example**:
```bash
# List all buckets
curl -X GET "https://api-id.execute-api.us-east-1.amazonaws.com/dev/buckets" \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."

# Get specific bucket
curl -X GET "https://api-id.execute-api.us-east-1.amazonaws.com/dev/buckets?project_name=my-web-app" \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
```

---

#### DELETE /buckets

Delete a bucket for a project.

**Query Parameters** (required):
- `project_name`: Project name of bucket to delete

**Request Headers**:
```
Authorization: Bearer {id-token}
```

**Response** (200 OK):
```json
{
  "message": "Bucket deleted successfully",
  "bucket_name": "dev-my-web-app-a1b2c3d4",
  "deleted_by": "user@example.com",
  "should_heal": false
}
```

**Healing Behavior**:
- `should_heal=true`: Bucket will be automatically restored by monitoring system
- `should_heal=false`: Bucket deletion is permanent (no auto-healing)

**Error Responses**:
- `400 Bad Request`: Missing `project_name` parameter
- `401 Unauthorized`: Missing or invalid token
- `403 Forbidden`: User not authorized to delete this bucket (not owner/admin)
- `404 Not Found`: Bucket not found
- `500 Internal Server Error`: Failed to delete bucket from S3

**Example**:
```bash
curl -X DELETE "https://api-id.execute-api.us-east-1.amazonaws.com/dev/buckets?project_name=my-web-app" \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**Notes**:
- Bucket must be empty before deletion (Lambda automatically empties it)
- Deletion metadata is stored in DynamoDB for audit trail
- Admin users can delete any bucket (healing behavior depends on admin type)

---

## Deployment Guide

### Prerequisites

1. **AWS Account** with appropriate permissions
2. **AWS CLI** installed and configured
   ```bash
   aws configure
   # Enter Access Key, Secret Key, Region, Output format
   ```
3. **Python 3.9+** installed
4. **Required Python Packages**:
   ```bash
   pip install boto3 requests
   ```
5. **Git** (optional, for version control)

### Initial Deployment

#### Step 1: Configure Parameters

Edit `infrastructure/parameters.json`:
```json
{
  "NotificationEmail": "your-email@example.com",
  "Environment": "dev",
  "AdminEmails": "admin@example.com"
}
```

#### Step 2: Upload Lambda Functions

```bash
python scripts/upload-lambdas.py --environment dev
```

This will:
- Package all Lambda functions into ZIP files
- Create S3 deployment bucket (if it doesn't exist)
- Upload ZIP files to S3
- Configure bucket with versioning and lifecycle policies

**Output**: Lambda functions uploaded to `s3://{env}-lambda-deployment-packages-{account-id}/`

#### Step 3: Deploy CloudFormation Stack

```bash
python scripts/deploy.py --environment dev
```

This will:
- Validate CloudFormation template
- Check for Lambda code in S3
- Deploy/update CloudFormation stack
- Create all AWS resources
- Generate `web-interface/config.js` with stack outputs

**Duration**: ~5-10 minutes (first deployment)

#### Step 4: Confirm SNS Subscription

1. Check email inbox for SNS subscription confirmation
2. Click confirmation link in email
3. Subscription status: Confirmed

#### Step 5: Create First User

```bash
python scripts/user_management.py create admin@example.com SecurePass123! "Admin User"
```

#### Step 6: Add User to Admin Group (Optional)

```bash
python scripts/user_management.py add-group admin@example.com admins
```

#### Step 7: Test Deployment

```bash
# Run comprehensive test suite
python scripts/test.py

# Check system health
python scripts/monitor.py
```

### Updating Deployment

#### Update Lambda Code Only

```bash
# 1. Upload updated Lambda code
python scripts/upload-lambdas.py --environment dev

# 2. Update Lambda functions (fast, ~10 seconds)
python scripts/deploy.py --update-code --environment dev
```

#### Update Infrastructure Only

```bash
# Just deploy (Lambda code already exists)
python scripts/deploy.py --environment dev
```

#### Update Single Lambda Function

```bash
# Upload specific function
python scripts/upload-lambdas.py --function create-bucket --environment dev

# Update that function
python scripts/deploy.py --update-code --environment dev
```
### Production Deployment

1. **Update Parameters**:
   ```json
   {
     "NotificationEmail": "ops@company.com",
     "Environment": "prod",
     "AdminEmails": "admin1@company.com,admin2@company.com"
   }
   ```

2. **Deploy**:
   ```bash
   python scripts/upload-lambdas.py --environment prod
   python scripts/deploy.py --environment prod
   ```

3. **Verify**:
   - Check CloudFormation stack status
   - Test API endpoints
   - Verify SNS notifications
   - Run health checks

### Rollback Procedure

If deployment fails:

1. **Check Stack Status**:
   ```bash
   aws cloudformation describe-stacks \
     --stack-name s3-bucket-management-system-dev \
     --query 'Stacks[0].StackStatus'
      ```

2. **If ROLLBACK_COMPLETE**:
   - Stack will be automatically deleted on next deployment
   - Or manually delete: `aws cloudformation delete-stack --stack-name s3-bucket-management-system-dev`

3. **If UPDATE_ROLLBACK_COMPLETE**:
   - Fix issues in template
   - Redeploy with corrected template

4. **Restore Previous Lambda Code**:
   - Lambda deployment packages are versioned in S3
   - Can restore from previous version

---

## Testing

### Automated Testing

**Test Suite**: `scripts/test.py`

**Test Coverage**:
1. ✅ User creation and authentication
2. ✅ Basic bucket creation
3. ✅ Bucket creation with versioning disabled
4. ✅ Bucket creation with versioning enabled
5. ✅ Bucket creation with Auto-Archive lifecycle policy
6. ✅ Bucket creation with Auto-Delete lifecycle policy
7. ✅ Bucket creation with Custom lifecycle policy
8. ✅ Bucket listing
9. ✅ Invalid project name validation
10. ✅ Authentication failure handling
11. ✅ Bucket healing (optional, long-running test)

**Run Tests**:
```bash
python scripts/test.py
```

**Test Output**:
```
🚀 Starting comprehensive test suite...
============================================================
✅ Test user created
✅ Test user authenticated

🧪 Testing basic bucket creation...
✅ Bucket created: dev-test-basic-1234567890-abc12345

🧪 Testing bucket creation with versioning DISABLED...
✅ Bucket created with versioning disabled: dev-test-no-ver-1234567890-abc12345

🧪 Testing bucket creation with versioning ENABLED...
✅ Bucket created with versioning enabled: dev-test-ver-enabled-1234567890-abc12345

...

============================================================
🏁 Test Results: 10/10 tests passed
🎉 All tests passed! System is working correctly.
```

### Manual Testing

#### Web Interface Testing

1. **Open Web Interface**:
   - Open `web-interface/index.html` in browser
   - Verify `config.js` exists (auto-generated during deployment)

2. **Test Authentication**:
   - Sign up with new account
   - Confirm email with verification code
   - Sign in with credentials

3. **Test Bucket Creation**:
   - Create bucket with default settings
   - Create bucket with versioning disabled
   - Create bucket with Auto-Archive lifecycle
   - Create bucket with Custom lifecycle policy

4. **Test Bucket Listing**:
   - Verify buckets appear in list
   - Test filtering (all/active/deleted)
   - Test sorting (newest/oldest/name/status)

5. **Test Bucket Deletion**:
   - Delete own bucket
   - Verify deletion confirmation
   - Check if bucket appears in deleted status

#### API Testing (curl)

```bash
# Set variables
export API_ENDPOINT="https://api-id.execute-api.us-east-1.amazonaws.com/dev"
export ID_TOKEN="your-id-token-here"

# Create bucket
curl -X POST "$API_ENDPOINT/buckets" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ID_TOKEN" \
  -d '{"project_name": "test-project", "versioning": "Enabled", "lifecycle_policy": "Auto-Archive"}'

# List buckets
curl -X GET "$API_ENDPOINT/buckets" \
  -H "Authorization: Bearer $ID_TOKEN"

# Get specific bucket
curl -X GET "$API_ENDPOINT/buckets?project_name=test-project" \
  -H "Authorization: Bearer $ID_TOKEN"

# Delete bucket
curl -X DELETE "$API_ENDPOINT/buckets?project_name=test-project" \
  -H "Authorization: Bearer $ID_TOKEN"
```

---

## Monitoring & Maintenance

### System Health Monitoring

**Script**: `scripts/monitor.py`

**Checks Performed**:
1. **Lambda Function Health**:
   - Function state (Active/Inactive)
   - Error count (last hour)
   - Function configuration

2. **DynamoDB Health**:
   - Table status
   - Item count
   - Read throttling events

3. **Bucket Integrity**:
   - Scans DynamoDB for active buckets
   - Verifies each bucket exists in S3
   - Reports missing buckets (will be healed)

4. **Cost Usage**:
   - Current month AWS costs
      - Service breakdown (Lambda, DynamoDB, S3, etc.)
   - Cost alerts (if exceeds thresholds)

**Run Health Check**:
```bash
python scripts/monitor.py
```

**Output Example**:
```
🏥 Starting system health check...
==================================================
🔍 Checking Lambda function health...
✅ dev-create-bucket: Active
✅ dev-list-buckets: Active
✅ dev-monitor-buckets: Active

🔍 Checking DynamoDB health...
✅ Table dev-bucket-metadata: ACTIVE
📊 Item count: 15
✅ No throttling detected

🔍 Checking bucket integrity...
📊 Total buckets: 15
✅ All buckets exist

💰 Checking cost usage...
📊 Total cost this month: $2.45
Service breakdown:
   - AWS Lambda: $0.85
   - Amazon DynamoDB: $0.60
   - Amazon S3: $1.00
✅ Cost within acceptable range
==================================================
🏁 Health check complete!
```
### CloudWatch Logs

**Lambda Log Groups**:
- `/aws/lambda/{environment}-create-bucket`
- `/aws/lambda/{environment}-list-buckets`
- `/aws/lambda/{environment}-delete-bucket`
- `/aws/lambda/{environment}-monitor-buckets`

**View Logs**:
```bash
# Tail logs for create-bucket function
aws logs tail /aws/lambda/dev-create-bucket --follow

# View recent errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/dev-create-bucket \
  --filter-pattern "ERROR" \
  --max-items 10
```

### Deletion Audit

**Script**: `scripts/audit_deletions.py`

**Features**:
- View all bucket deletions
- Filter by bucket name or project name
- Show deletion metadata (who, when, should_heal)
- Display healing status
- Optional CloudWatch Logs integration

**Usage**:
```bash
# List all deletions
python scripts/audit_deletions.py

# Filter by bucket name
python scripts/audit_deletions.py --bucket dev-my-app-abc123

# Filter by project name
python scripts/audit_deletions.py --project my-web-app

# Include CloudWatch Logs
python scripts/audit_deletions.py --include-logs
```

**Output Example**:
```
================================================================================
DELETION HISTORY AUDIT (3 bucket(s) found)
================================================================================

Bucket: dev-my-app-abc12345
Project: my-web-app
Status: active
Heal Count: 1
--------------------------------------------------------------------------------
  ❌ DELETED
     Deleted At: 2025-01-15T11:00:00.000Z
     Deleted By (User ID): us-east-1:xyz789
     Deleted By (Email): admin@example.com
     Auto-Heal Enabled: true
  ✅ HEALED
     Healed At: 2025-01-15T11:05:00.000Z
     Times Healed: 1
```

### Scheduled Monitoring

**EventBridge Rule**: Runs every 5 minutes
- Automatically checks all buckets
- Heals deleted buckets (when `should_heal=True`)
- Updates `last_checked` timestamps
- Sends notifications for healing events

**Monitoring Statistics**:
- View in CloudWatch Logs for Monitor-Buckets Lambda
- Check `processed_buckets` and `healed_buckets` counts

---

## Troubleshooting

### Common Issues

#### 1. "Access Denied" when creating buckets

**Symptoms**: Lambda function returns 500 error, CloudWatch logs show permission errors

**Causes**:
- Lambda role missing S3 permissions
- Bucket name conflicts (already exists globally)
- Region configuration mismatch

**Solutions**:
- Check IAM role permissions in CloudFormation template
- Verify Lambda role has `s3:CreateBucket` permission
- Check bucket name uniqueness (globally unique required)
- Verify region configuration matches

#### 2. "User not found" during authentication

**Symptoms**: Sign in fails, 401 Unauthorized errors

**Causes**:
- User doesn't exist in Cognito User Pool
- Email not verified
- User account disabled

**Solutions**:
- Create user: `python scripts/user_management.py create email@example.com Password123! "Name"`
- Verify email: Check email inbox for verification code
- Check user status: `aws cognito-idp admin-get-user --user-pool-id <ID> --username <EMAIL>`

#### 3. "Token expired" errors

**Symptoms**: API requests return 401 after some time

**Causes**:
- ID token expired (default: 1 hour)
- Refresh token expired (default: 30 days)
- Token refresh not implemented in web interface

**Solutions**:
- Implement token refresh in `script.js` (not currently implemented)
- Re-sign in to get new tokens
- Increase token validity in CloudFormation template (not recommended for security)

#### 4. Buckets not healing

**Symptoms**: Deleted buckets with `should_heal=True` not being restored


**Causes**:
- EventBridge rule disabled
- Lambda function errors
- `should_heal` flag not set correctly
- Monitoring Lambda timeout

**Solutions**:
- Check EventBridge rule status: `aws events describe-rule --name <rule-name>`
- Check Monitor-Buckets Lambda logs in CloudWatch
- Verify `should_heal=True` in DynamoDB: `python scripts/audit_deletions.py`
- Check Lambda timeout (should be 300 seconds for monitoring)

#### 5. "Lambda code files are missing in S3"

**Symptoms**: Deployment fails with missing Lambda code warning

**Causes**:
- Lambda functions not uploaded before stack deployment
- S3 bucket doesn't exist
- Wrong environment/account ID

**Solutions**:
- Upload Lambda functions first: `python scripts/upload-lambdas.py`
- Verify S3 bucket exists: `aws s3 ls | grep lambda-deployment`
- Check account ID matches: `aws sts get-caller-identity`

#### 6. High AWS costs

**Symptoms**: Monthly costs exceed expectations

**Causes**:
- Too many buckets created
- High Lambda invocation count
- DynamoDB on-demand pricing with high traffic
- S3 storage costs

**Solutions**:
- Run cost check: `python scripts/monitor.py`
- Review CloudWatch metrics for Lambda invocations
- Consider reducing monitoring frequency (currently 5 minutes)
- Review S3 bucket usage and delete unused buckets

#### 7. Custom lifecycle policy validation errors

**Symptoms**: "Invalid custom lifecycle config" error when creating bucket

**Causes**:
- Invalid JSON syntax
- Wrong field names (e.g., "ExpirationDays" instead of "Expiration.Days")
- Invalid storage class names
- Missing required fields (ID, Status)

**Solutions**:
- Use web interface "Validate JSON" button before submitting
- Check AWS S3 lifecycle configuration documentation
- Ensure all rule IDs are strings (not numbers)
- Verify Status is exactly "Enabled" or "Disabled" (case-sensitive)

### Debugging Tips

1. **Check CloudWatch Logs**:
   ```bash
   aws logs tail /aws/lambda/dev-create-bucket --follow
   ```

2. **Verify DynamoDB Data**:
   ```bash
   aws dynamodb scan --table-name dev-bucket-metadata --limit 5
   ```

3. **Test API Directly**:
   ```bash
   curl -X GET "$API_ENDPOINT/buckets" \
     -H "Authorization: Bearer $ID_TOKEN" \
     -v  # Verbose output
   ```

4. **Check Cognito User**:
   ```bash
   aws cognito-idp list-users --user-pool-id <USER_POOL_ID>
   ```

5. **Verify IAM Permissions**:
   ```bash
   aws iam get-role-policy \
     --role-name dev-bucket-management-role \
     --policy-name BucketManagementPolicy
   ```

---

## Security

### Security Features

1. **Authentication**:
   - AWS Cognito User Pool with secure password policy
   - JWT tokens with expiration
   - Token validation on every API request

2. **Authorization**:
   - Role-based access control (RBAC)
   - User isolation (regular users see only own buckets)
   - Admin permissions clearly defined

3. **Bucket Security**:
   - Public access block enabled by default (all settings)
   - Server-side encryption (AES256) enabled
   - Unique bucket names prevent collisions

4. **Data Protection**:
   - User data isolated by `user_id` in DynamoDB
   - Sensitive data (user_id) not exposed in API responses
   - Audit trail for all deletions

5. **API Security**:
   - Cognito authorizer on all endpoints
   - CORS configured properly
   - Input validation on all requests

### Security Best Practices

1. **IAM Permissions**:
   - ✅ Least-privilege principle applied
   - ✅ Lambda roles have minimal required permissions
   - ✅ No wildcard permissions except for S3 bucket operations (required)

2. **Password Policy**:
   - Minimum 8 characters
   - Requires uppercase, lowercase, numbers
   - No symbol requirement (can be enabled)

3. **Token Management**:
   - Short token validity (1 hour)
   - Refresh tokens for long sessions (30 days)
   - Tokens stored in browser localStorage (consider httpOnly cookies for production)

4. **Data Encryption**:
   - DynamoDB: Server-side encryption enabled by default
   - S3 Buckets: AES256 encryption enabled on all buckets
   - Data in transit: HTTPS/TLS for all API communications
   - Token encryption: JWT tokens signed by Cognito

5. **Audit & Compliance**:
   - Complete deletion audit trail in DynamoDB
   - CloudWatch logs for all Lambda functions
   - SNS notifications for critical events
   - Point-in-Time Recovery enabled on DynamoDB

6. **Production Recommendations**:
   - Enable MFA for AWS root account
   - Rotate access keys regularly
   - Use AWS Secrets Manager for sensitive configs
   - Enable CloudTrail for API audit logging
   - Implement WAF rules for API Gateway
   - Use httpOnly cookies instead of localStorage for tokens
   - Enable Cognito advanced security features
   - Set up CloudWatch alarms for security events

---

## Cost Analysis

### AWS Free Tier Coverage

**Free Tier Limits** (per month):
- **Lambda**: 1M requests, 400,000 GB-seconds
- **API Gateway**: 1M requests
- **DynamoDB**: 25GB storage, 2.5M read units, 2.5M write units (on-demand pricing)
- **S3**: 5GB storage, 20,000 GET requests, 2,000 PUT requests
- **SNS**: 1,000 emails
- **EventBridge**: 2M custom events
- **Cognito**: 50,000 MAU (Monthly Active Users)

### Estimated Monthly Costs

**Development Environment** (low usage):
- Lambda: ~$0 (within free tier)
- API Gateway: ~$0 (within free tier)
- DynamoDB: ~$0-1 (small data volume)
- S3: ~$0 (minimal storage)
- SNS: ~$0 (few notifications)
- EventBridge: ~$0 (within free tier)
- **Total**: ~$0-5/month

**Production Environment** (moderate usage):
- Lambda: ~$2-5 (if exceeding free tier)
- API Gateway: ~$3-10 (if exceeding free tier)
- DynamoDB: ~$5-15 (depends on data volume)
- S3: ~$1-5 (storage + operations)
- SNS: ~$0-1 (if exceeding free tier)
- **Total**: ~$10-50/month

### Cost Optimization Tips

1. **Monitor Usage**: Run `python scripts/monitor.py` regularly
2. **DynamoDB**: Use on-demand billing (no capacity planning needed)
3. **S3**: Use lifecycle policies to transition to Glacier/Deep Archive
4. **Lambda**: Optimize memory allocation (currently 128-256 MB)
5. **EventBridge**: Current 5-minute schedule is reasonable (8,640/month)
6. **SNS**: Batch notifications if possible

### Cost Monitoring

**CloudWatch Metrics to Monitor**:
- Lambda invocations and duration
- API Gateway request count
- DynamoDB read/write units
- S3 storage and request metrics
- SNS message delivery

**Alarms to Set Up**:
- Monthly cost > $50
- Lambda errors > threshold
- DynamoDB throttling events
- S3 bucket size growth

---

## Development Workflow

### Local Development Setup

1. **Prerequisites**:
   ```bash
   # Install Python 3.9+
   python --version
   
   # Install AWS CLI
   pip install awscli
   aws configure
   
   # Install Python dependencies
   pip install boto3 requests
   ```

2. **Clone Repository**:
   ```bash
   git clone <repository-url>
   cd s3-bucket-manager
   ```

3. **Configure Parameters**:
   ```bash
   # Edit infrastructure/parameters.json
   {
     "NotificationEmail": "your-email@example.com",
     "Environment": "dev",
     "AdminEmails": "admin@example.com"
   }
  ```

### Development Cycle

**1. Make Code Changes**:
- Edit Lambda functions in `lambda-functions/*/index.py`
- Edit web interface files in `web-interface/`
- Update CloudFormation template if needed

**2. Test Locally**:
```bash
# Run test suite
python scripts/test.py

# Check for syntax errors
python -m py_compile lambda-functions/create-bucket/index.py
```

**3. Upload Lambda Code**:
```bash
# Upload all functions
python scripts/upload-lambdas.py

# Upload specific function
python scripts/upload-lambdas.py --function create-bucket
```

**4. Update Lambda Functions** (Fast - ~10 seconds):
```bash
python scripts/deploy.py --update-code
```

**5. Full Stack Deployment** (if infrastructure changed):
```bash
python scripts/deploy.py
```

### Code Quality

**Python Best Practices**:
- Follow PEP 8 style guide
- Use type hints where possible
- Add docstrings to functions
- Handle exceptions gracefully
- Log errors with context

**JavaScript Best Practices**:
- Use modern ES6+ syntax
- Validate inputs client-side
- Handle errors gracefully
- Use async/await for API calls
- Sanitize user input to prevent XSS

### Version Control

**Git Workflow**:
```bash
# Create feature branch
git checkout -b feature/new-feature

# Commit changes
git add .
git commit -m "Add new feature"

# Push and create PR
git push origin feature/new-feature
```

**Files to Commit**:
- ✅ Lambda function code
- ✅ Web interface files
- ✅ Scripts
- ✅ CloudFormation templates
- ✅ Documentation

**Files NOT to Commit** (in .gitignore):
- ❌ `web-interface/config.js` (auto-generated)
- ❌ `/.vscode` (except documentation)
- ❌ AWS credentials
- ❌ Build artifacts

---

## Scripts Reference

### deploy.py

**Purpose**: Deploy or update CloudFormation stack

**Usage**:
```bash
# Full deployment
python scripts/deploy.py

# Update Lambda code only (fast)
python scripts/deploy.py --update-code

# Deploy to specific environment
python scripts/deploy.py --environment prod

# Skip Lambda upload check
python scripts/deploy.py --skip-upload-check
```

**Features**:
- Validates AWS CLI configuration
- Validates CloudFormation template
- Checks for Lambda code in S3
- Handles ROLLBACK_COMPLETE state
- Generates `web-interface/config.js`
- Outputs stack information

**Exit Codes**:
- `0`: Success
- `1`: Error (check output for details)

---

### upload-lambdas.py

**Purpose**: Package and upload Lambda functions to S3

**Usage**:
```bash
# Upload all functions
python scripts/upload-lambdas.py

# Upload specific function
python scripts/upload-lambdas.py --function create-bucket

# Upload for specific environment
python scripts/upload-lambdas.py --environment prod

# Upload for specific region
python scripts/upload-lambdas.py --region eu-west-1
```

**Features**:
- Packages Lambda functions into ZIP files
- Creates S3 deployment bucket if needed
- Configures bucket versioning and lifecycle
- Uploads to: `{environment}-lambda-deployment-packages-{account-id}`

**Process**:
1. Validates AWS CLI
2. Gets AWS account ID
3. Creates/verifies S3 bucket
4. Packages each Lambda function
5. Uploads ZIP files to S3

---

### test.py

**Purpose**: Comprehensive automated test suite

**Usage**:
```bash
python scripts/test.py
```

**Test Coverage**:
1. ✅ Test user creation
2. ✅ User authentication
3. ✅ Basic bucket creation
4. ✅ Bucket creation with versioning disabled
5. ✅ Bucket creation with versioning enabled
6. ✅ Bucket creation with Auto-Archive lifecycle
7. ✅ Bucket creation with Auto-Delete lifecycle
8. ✅ Bucket creation with custom lifecycle policy
9. ✅ Bucket listing
10. ✅ Invalid project name validation
11. ✅ Authentication failure handling
12. ✅ Bucket healing (optional, long-running)

**Test Results**:
- Tracks: passed, failed, skipped
- Provides detailed output for each test
- Cleans up test user after completion

**Note**: Healing test can take up to 10 minutes (waits for EventBridge trigger)

---

### monitor.py

**Purpose**: System health monitoring and diagnostics

**Usage**:
```bash
python scripts/monitor.py
```

**Checks Performed**:
1. **Lambda Health**:
   - Function state (Active/Inactive)
   - Error count in last hour
   - CloudWatch metrics

2. **DynamoDB Health**:
   - Table status
   - Item count
   - Read throttling events

3. **Bucket Integrity**:
   - Scans all active buckets in DynamoDB
   - Verifies each bucket exists in S3
   - Reports missing buckets (will be healed)

4. **Cost Usage**:
   - Current month costs
   - Service breakdown
   - Warnings if approaching limits

**Output**: Detailed health report with status indicators
---

### user_management.py

**Purpose**: Cognito user management operations

**Usage**:
```bash
# Create user
python scripts/user_management.py create email@example.com Password123! "Full Name" [group]

# List all users
python scripts/user_management.py list

# Delete user
python scripts/user_management.py delete email@example.com

# Add user to group
python scripts/user_management.py add-group email@example.com admins

# Remove user from group
python scripts/user_management.py remove-group email@example.com admins

# List user groups
python scripts/user_management.py list-groups email@example.com
```

**Groups**:
- `admins`: Super Administrators
- `business-admins`: Business Administrators

**Features**:
- Creates users with email verification
- Sets permanent passwords
- Adds users to groups
- Lists all users with their roles


---

### audit_deletions.py

**Purpose**: View bucket deletion audit trail

**Usage**:
```bash
# List all deletions
python scripts/audit_deletions.py

# Filter by bucket name
python scripts/audit_deletions.py --bucket-name dev-my-app-abc123

# Filter by project name
python scripts/audit_deletions.py --project my-web-app

# Include CloudWatch logs
python scripts/audit_deletions.py --include-logs
```

**Information Displayed**:
- Bucket name and project name
- Deletion timestamp
- Who deleted (user ID and email)
- Auto-heal status (should_heal flag)
- Healing status (if healed)
- Heal count
- Deletion history

**Use Cases**:
- Compliance audits
- Security investigations
- Understanding deletion patterns
- Verifying healing behavior

---

## Configuration

### Environment Variables

**Lambda Functions**:

**Create-Bucket Lambda**:
- `TABLE_NAME`: DynamoDB table name
- `SNS_TOPIC`: SNS topic ARN
- `ENVIRONMENT`: Environment name
- `REGION`: AWS region

**List-Buckets Lambda**:
- `TABLE_NAME`: DynamoDB table name
- `USER_POOL_ID`: Cognito User Pool ID

**Delete-Bucket Lambda**:
- `TABLE_NAME`: DynamoDB table name
- `USER_POOL_ID`: Cognito User Pool ID
- `REGION`: AWS region
- `ADMIN_EMAILS`: Comma-separated admin emails (optional)

**Monitor-Buckets Lambda**:
- `TABLE_NAME`: DynamoDB table name
- `SNS_TOPIC`: SNS topic ARN
- `ENVIRONMENT`: Environment name
- `REGION`: AWS region

### Web Interface Configuration

**File**: `web-interface/config.js` (auto-generated)

**Structure**:
```javascript
const CONFIG = {
    apiEndpoint: 'https://{api-id}.execute-api.{region}.amazonaws.com/{env}',
    region: 'us-east-1',
    userPoolId: 'us-east-1_xxxxxxxx',
    userPoolClientId: 'xxxxxxxxxxxxxxxxxxxxxxxxxx',
    identityPoolId: 'us-east-1:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx',
    environment: 'dev'
};
```

**Generated By**: `scripts/deploy.py` after successful stack deployment

**Manual Update**: Edit directly if needed, but will be overwritten on next deployment

---

## Best Practices

### Development

1. **Always Test Before Deploying**:
   ```bash
   python scripts/test.py
   ```

2. **Use Environment-Specific Deployments**:
   - Develop in `dev` environment
   - Test in `staging` environment
   - Deploy to `prod` only after thorough testing

3. **Version Control**:
   - Commit frequently with meaningful messages
   - Use feature branches for new features
   - Tag releases

4. **Code Review**:
   - Review all changes before merging
   - Test locally before pushing
   - Check for security issues

### Operations

1. **Monitor Regularly**:
   ```bash
   python scripts/monitor.py
   ```

2. **Set Up CloudWatch Alarms**:
   - Lambda errors
   - DynamoDB throttling
   - Cost thresholds
   - API Gateway errors

3. **Review Logs**:
   ```bash
   aws logs tail /aws/lambda/dev-create-bucket --follow
   ```

4. **Backup Strategy**:
   - DynamoDB Point-in-Time Recovery enabled
   - S3 versioning enabled on buckets
   - Regular exports of DynamoDB data

### Security

1. **Regular Audits**:
   - Review IAM policies quarterly
   - Audit user access regularly
   - Review deletion audit logs

2. **Access Management**:
   - Use least-privilege principle
   - Rotate credentials regularly
   - Remove unused users

3. **Monitoring**:
   - Monitor for unusual activity
   - Set up alerts for security events
   - Review CloudTrail logs

### Performance

1. **Lambda Optimization**:
   - Right-size memory allocation
   - Optimize cold starts
   - Use connection pooling for DynamoDB

2. **DynamoDB**:
   - Use appropriate indexes
   - Monitor throttling
   - Consider caching for frequently accessed data

3. **API Gateway**:
   - Enable caching where appropriate
   - Monitor latency
   - Set up throttling limits

---

## Troubleshooting Guide

### Common Issues

#### 1. "Access Denied" when creating buckets

**Symptoms**: Lambda function fails with AccessDenied error

**Causes**:
- Lambda role lacks S3 permissions
- Bucket name collision (already exists globally)
- Region mismatch

**Solutions**:
- Check IAM role permissions in CloudFormation template
- Verify bucket name uniqueness (S3 bucket names are globally unique)
- Ensure region configuration matches

**Commands**:
```bash
# Check Lambda role
aws iam get-role-policy --role-name dev-bucket-management-role --policy-name BucketManagementPolicy

# Check bucket name availability
aws s3api head-bucket --bucket bucket-name
```

---

#### 2. "User not found" during authentication

**Symptoms**: API returns 401 Unauthorized

**Causes**:
- User doesn't exist in Cognito
- Email not verified
- User account disabled

**Solutions**:
- Create user: `python scripts/user_management.py create email@example.com Password123! "Name"`
- Verify email in Cognito console
- Check user status: `aws cognito-idp admin-get-user --user-pool-id <ID> --username <EMAIL>`

---

#### 3. "Token expired" errors

**Symptoms**: API requests fail with 401 after some time

**Causes**:
- ID token expired (1 hour validity)
- No token refresh implemented

**Solutions**:
- Implement token refresh in web interface
- Check token expiration: Decode JWT and check `exp` claim
- Increase token validity (not recommended for security)

**Token Refresh Implementation**:
```javascript
// Check token expiration before API calls
const token = localStorage.getItem('idToken');
const payload = JSON.parse(atob(token.split('.')[1]));
if (payload.exp * 1000 < Date.now()) {
    // Refresh token
    await refreshToken();
}
```

---
#### 4. Buckets not healing

**Symptoms**: Deleted buckets not being restored

**Causes**:
- EventBridge rule disabled
- `should_heal=False` in DynamoDB
- Lambda function errors
- Monitoring Lambda not running

**Solutions**:
- Check EventBridge rule status:
  ```bash
  aws events describe-rule --name dev-monitor-buckets-rule
  ```
- Verify `should_heal` flag in DynamoDB:
  ```bash
  aws dynamodb get-item --table-name dev-bucket-metadata --key '{"project_name": {"S": "..."}}'
  ```
- Check Monitor Lambda logs:
  ```bash
  aws logs tail /aws/lambda/dev-monitor-buckets --follow
  ```
- Manually trigger Lambda:
  ```bash
  aws lambda invoke --function-name dev-monitor-buckets response.json
  ```

---

#### 5. "Lambda code files are missing in S3"

**Symptoms**: Deployment fails with missing Lambda code error

**Causes**:
- Lambda code not uploaded before stack deployment
- Wrong environment specified
- S3 bucket doesn't exist

**Solutions**:
- Upload Lambda code first:
  ```bash
  python scripts/upload-lambdas.py --environment dev
  ```
- Verify files in S3:
  ```bash
  aws s3 ls s3://dev-lambda-deployment-packages-{account-id}/
  ```
- Check environment matches:
  ```bash
  # Ensure environment matches in both commands
  python scripts/upload-lambdas.py --environment dev
  python scripts/deploy.py --environment dev
  ```

---

#### 6. High AWS costs

**Symptoms**: Monthly costs exceed expectations

**Causes**:
- High Lambda invocations
- Large DynamoDB data volume
- S3 storage growth
- Excessive API Gateway requests

**Solutions**:
- Run cost analysis:
  ```bash
  python scripts/monitor.py
  ```
- Review CloudWatch metrics:
  ```bash
  aws cloudwatch get-metric-statistics --namespace AWS/Lambda --metric-name Invocations
  ```
- Optimize monitoring frequency (currently 5 minutes)
- Review S3 bucket sizes and lifecycle policies
- Check for unnecessary API calls

---

#### 7. Custom lifecycle policy validation fails

**Symptoms**: "Invalid custom lifecycle config" error

**Causes**:
- Invalid JSON syntax
- Missing required fields (ID, Status)
- Invalid storage class names
- Incorrect field names (e.g., "ExpirationDays" instead of "Expiration.Days")

**Solutions**:
- Use web interface validation button
- Check AWS S3 lifecycle documentation
- Common errors:
  - Use `ID` (uppercase) not `Id`
  - Use `Expiration: {Days: ...}` not `ExpirationDays`
  - Use `Transitions: [{Days: ..., StorageClass: ...}]` not `AfterDays`

**Example Valid Policy**:
```json
{
  "Rules": [{
    "ID": "MyRule",
    "Status": "Enabled",
    "Filter": {},
    "Transitions": [{
      "Days": 30,
      "StorageClass": "GLACIER"
    }]
  }]
}
```

---

#### 8. DynamoDB throttling

**Symptoms**: Slow responses, throttling errors

**Causes**:
- High read/write throughput
- Hot partition key
- Insufficient capacity

**Solutions**:
- Use on-demand billing mode (already configured)
- Distribute load across partitions
- Review query patterns
- Consider caching frequently accessed data

---

### Debugging Commands

**Check Lambda Logs**:
```bash
# View recent logs
aws logs tail /aws/lambda/dev-create-bucket --follow
# Search for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/dev-create-bucket \
  --filter-pattern "ERROR"
```

**Check DynamoDB Data**:
```bash
# Scan table
aws dynamodb scan --table-name dev-bucket-metadata --limit 10

# Get specific item
aws dynamodb get-item \
  --table-name dev-bucket-metadata \
  --key '{"project_name": {"S": "user-id#project-name"}}'
```

**Check API Gateway**:
```bash
# Get API details
aws apigateway get-rest-api --rest-api-id <API_ID>

# Check deployment status
aws apigateway get-deployment --rest-api-id <API_ID> --deployment-id <DEPLOYMENT_ID>
```

**Check Cognito**:
```bash
# List users
aws cognito-idp list-users --user-pool-id <USER_POOL_ID>
# Get user details
aws cognito-idp admin-get-user --user-pool-id <USER_POOL_ID> --username <EMAIL>
```

---

## Additional Resources

### AWS Documentation

- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [AWS API Gateway Documentation](https://docs.aws.amazon.com/apigateway/)
- [AWS DynamoDB Documentation](https://docs.aws.amazon.com/dynamodb/)
- [AWS Cognito Documentation](https://docs.aws.amazon.com/cognito/)
- [AWS S3 Documentation](https://docs.aws.amazon.com/s3/)
- [AWS EventBridge Documentation](https://docs.aws.amazon.com/eventbridge/)
- [AWS CloudFormation Documentation](https://docs.aws.amazon.com/cloudformation/)

### S3 Lifecycle Configuration

- [S3 Lifecycle Configuration](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html)
- [Storage Classes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage-class-intro.html)
- [Lifecycle Transition Examples](https://docs.aws.amazon.com/AmazonS3/latest/userguide/lifecycle-transition-general-considerations.html)

### Project-Specific Documentation

- `README.md`: Main project overview
- `DEPLOYMENT_GUIDE.md`: Detailed deployment instructions
- `.vscode/PROJECT_DOCUMENTATION.md`: General project documentation
- `.vscode/PROBLEM_SOLVER.md`: Architecture rationale and problem analysis

---

## Appendices

### Appendix A: Project Name Validation Rules

**Format**: Lowercase letters, numbers, and hyphens only
**Length**: 3-50 characters
**Pattern**: `^[a-z0-9-]+$`

**Valid Examples**:
- ✅ `my-web-app`
- ✅ `project123`
- ✅ `api-service`
- ✅ `test-123-project`

**Invalid Examples**:
- ❌ `My-Web-App` (uppercase letters)
- ❌ `my_web_app` (underscores)
- ✅ `my web app` (spaces)
- ❌ `my@web#app` (special characters)
- ❌ `ab` (too short)
- ❌ `a` * 51 (too long)

---

### Appendix B: Bucket Naming Convention

**Format**: `{environment}-{project_name}-{uuid8}`

**Components**:
- `environment`: dev, staging, or prod
- `project_name`: Validated project name (lowercase, alphanumeric, hyphens)
- `uuid8`: First 8 characters of UUID v4

**Examples**:
- `dev-my-web-app-a1b2c3d4`
- `prod-api-service-f5e6d7c8`
- `staging-test-project-12345678`

**Why This Format**:
- Environment prefix: Easy identification
- Project name: Human-readable
- UUID suffix: Ensures global uniqueness

---

### Appendix C: Lifecycle Policy Examples

#### Auto-Archive Policy (Built-in)

Transitions objects to Glacier after 30 days:
```json
{
  "Rules": [{
    "ID": "AutoArchiveRule",
    "Status": "Enabled",
    "Filter": {},
    "Transitions": [{
      "Days": 30,
      "StorageClass": "GLACIER"
    }]
  }]
}
```

#### Auto-Delete Policy (Built-in)

Deletes noncurrent versions after 90 days:
```json
{
  "Rules": [{
    "ID": "AutoDeleteVersionsRule",
    "Status": "Enabled",
    "Filter": {},
    "NoncurrentVersionExpiration": {
      "NoncurrentDays": 90
    }
  }]
}
```

#### Custom Policy Example: Multi-Tier Archiving

Transitions objects through multiple storage tiers for cost optimization:

```json
{
  "Rules": [{
    "ID": "MultiTierArchive",
    "Status": "Enabled",
    "Filter": {},
    "Transitions": [
      {
        "Days": 30,
        "StorageClass": "STANDARD_IA"
      },
      {
        "Days": 90,
        "StorageClass": "GLACIER"
      },
      {
        "Days": 180,
        "StorageClass": "DEEP_ARCHIVE"
      }
    ],
    "Expiration": {
      "Days": 365
    }
  }]
}
```

**Explanation**:
- After 30 days: Move to Infrequent Access (lower storage cost)
- After 90 days: Move to Glacier (archival storage)
- After 180 days: Move to Deep Archive (lowest cost)
- After 365 days: Delete objects

---

#### Custom Policy Example: Intelligent Version Management

Manages object versions with automatic cleanup:

```json
{
  "Rules": [{
    "ID": "VersionManagement",
    "Status": "Enabled",
    "Filter": {},
    "NoncurrentVersionTransitions": [
      {
        "NoncurrentDays": 30,
        "StorageClass": "GLACIER"
      }
    ],
    "NoncurrentVersionExpiration": {
      "NoncurrentDays": 90
    },
    "Expiration": {
      "Days": 365
    }
  }]
}
```

**Explanation**:
- Noncurrent versions move to Glacier after 30 days
- Noncurrent versions deleted after 90 days
- Current versions deleted after 365 days

---

#### Custom Policy Example: Prefix-Based Policies

Different lifecycle rules for different object prefixes:

```json
{
  "Rules": [
    {
      "ID": "LogsArchive",
      "Status": "Enabled",
      "Filter": {
        "Prefix": "logs/"
      },
      "Transitions": [
        {
          "Days": 7,
          "StorageClass": "GLACIER"
        }
      ],
      "Expiration": {
        "Days": 90
      }
    },
    {
      "ID": "DataRetention",
      "Status": "Enabled",
      "Filter": {
        "Prefix": "data/"
      },
      "Transitions": [
        {
          "Days": 60,
          "StorageClass": "STANDARD_IA"
        },
        {
          "Days": 180,
          "StorageClass": "GLACIER"
        }
      ]
    }
  ]
}
```

**Explanation**:
- `logs/` prefix: Archive after 7 days, delete after 90 days
- `data/` prefix: Move to IA after 60 days, Glacier after 180 days

---

### Appendix D: Error Codes Reference

#### API Error Codes

| Code | Message | Description | Solution |
|------|---------|-------------|----------|
| `400` | Bad Request | Invalid input parameters | Check request format and parameters |
| `401` | Unauthorized | Missing or invalid token | Re-authenticate and get new token |
| `403` | Forbidden | Insufficient permissions | Check user role and permissions |
| `404` | Not Found | Bucket or resource not found | Verify resource exists |
| `409` | Conflict | Bucket name already exists | Use a different project name |
| `500` | Internal Server Error | AWS service error | Check CloudWatch logs |

#### Lambda Error Patterns

**Common Error Messages**:
- `"Bucket name already exists"`: S3 bucket name collision (globally unique)
- `"Invalid project name"`: Project name doesn't match validation rules
- `"Access denied"`: IAM permissions issue
- `"User not found"`: Cognito user doesn't exist
- `"Invalid lifecycle config"`: Custom lifecycle policy JSON is invalid

**Error Response Format**:
```json
{
  "error": "Error message",
  "code": "ERROR_CODE",
  "details": {
    "field": "additional context"
  }
}
```

---

### Appendix E: Deployment Checklist

#### Pre-Deployment

- [ ] AWS CLI configured with appropriate credentials
- [ ] AWS account has sufficient permissions
- [ ] Environment variables set (if needed)
- [ ] Parameters file updated (`infrastructure/parameters.json`)
- [ ] Lambda code tested locally
- [ ] CloudFormation template validated

#### Deployment Steps

- [ ] Upload Lambda functions: `python scripts/upload-lambdas.py`
- [ ] Deploy CloudFormation stack: `python scripts/deploy.py`
- [ ] Verify stack creation: Check AWS Console
- [ ] Test API endpoints: Run `python scripts/test.py`
- [ ] Verify web interface: Open `web-interface/index.html`
- [ ] Check CloudWatch logs for errors

#### Post-Deployment

- [ ] Create initial admin users: `python scripts/user_management.py`
- [ ] Configure SNS subscriptions (email notifications)
- [ ] Set up CloudWatch alarms
- [ ] Test bucket creation workflow
- [ ] Test bucket deletion workflow
- [ ] Verify healing mechanism (optional)
- [ ] Run monitoring script: `python scripts/monitor.py`

#### Production Deployment

- [ ] Enable MFA on root account
- [ ] Set up CloudTrail logging
- [ ] Configure WAF rules for API Gateway
- [ ] Set up cost alerts
- [ ] Enable Cognito advanced security features
- [ ] Review and tighten IAM policies
- [ ] Set up backup strategy for DynamoDB
- [ ] Document runbooks for common issues

---

### Appendix F: CloudFormation Template Structure

#### Resource Dependencies

```
Cognito User Pool
    ↓
Cognito User Pool Client
    ↓
Cognito Identity Pool
    ↓
DynamoDB Table
    ↓
SNS Topic
    ↓
IAM Role
    ↓
Lambda Functions (Create, List, Delete, Monitor)
    ↓
API Gateway
    ↓
EventBridge Rule
```

#### Key Outputs

The CloudFormation stack generates these outputs:
- `UserPoolId`: Cognito User Pool ID
- `UserPoolClientId`: Cognito User Pool Client ID
- `IdentityPoolId`: Cognito Identity Pool ID
- `ApiEndpoint`: API Gateway endpoint URL
- `TableName`: DynamoDB table name
- `SnsTopicArn`: SNS topic ARN

These are used to generate `web-interface/config.js`.

---

### Appendix G: API Rate Limits

#### Current Limits

**API Gateway**:
- Default throttling: 10,000 requests/second (burst)
- Account-level throttling: 5,000 requests/second

**Lambda**:
- Concurrent executions: 1,000 (default per region)
- Burst capacity: 3,000
- Can be increased via AWS Support

**DynamoDB**:
- On-demand billing: Scales automatically
- No fixed throughput limits
- Throttling based on usage patterns

**S3**:
- No API rate limits
- Request rate: 3,500 PUT/COPY/POST/DELETE per prefix
- Request rate: 5,500 GET/HEAD per prefix

#### Recommendations

- Monitor API usage with CloudWatch
- Implement client-side rate limiting
- Use exponential backoff for retries
- Consider caching for frequently accessed data

---

### Appendix H: Change Log

#### Version History

**v1.0.0** (Initial Release):
- Basic bucket creation, listing, and deletion
- Cognito authentication
- DynamoDB metadata storage
- Web interface
- Automated healing mechanism
- EventBridge monitoring
- SNS notifications

**Future Enhancements** (Planned):
- Multi-region support
- Bucket replication configuration
- Advanced analytics dashboard
- Bucket tagging system
- Cost optimization recommendations
- Automated backup scheduling
- Integration with other AWS services (CloudFront, etc.)

---

### Appendix I: Glossary

**Cognito User Pool**: AWS service for user management, authentication, and authorization.

**Cognito Identity Pool**: AWS service that provides temporary AWS credentials for authenticated users.

**DynamoDB**: AWS NoSQL database service used for storing bucket metadata.

**EventBridge**: AWS event-driven service that triggers Lambda functions on schedules or events.

**SNS**: Amazon Simple Notification Service for sending notifications (email, SMS, etc.).

**API Gateway**: AWS service for creating RESTful APIs with authentication and authorization.

**Lambda**: AWS serverless compute service for running code without managing servers.

**CloudFormation**: AWS Infrastructure as Code service for defining and deploying AWS resources.

**GSI**: Global Secondary Index - DynamoDB feature for querying data by alternate keys.

**IAM Role**: AWS Identity and Access Management role that defines permissions for AWS services.

**JWT Token**: JSON Web Token - a compact, URL-safe token format for authentication.

**Lifecycle Policy**: S3 feature for automatically managing object transitions and deletions.

**Public Access Block**: S3 feature that prevents public access to buckets and objects.

**Point-in-Time Recovery**: DynamoDB feature for automatic backups with point-in-time restore capability.

---

## Conclusion

This S3 Bucket Manager is a comprehensive, production-ready solution for managing S3 buckets with enterprise-grade features including:

- ✅ **Secure Authentication & Authorization**: AWS Cognito with role-based access control
- ✅ **Automated Healing**: Self-healing infrastructure with EventBridge monitoring
- ✅ **Comprehensive Metadata**: Full audit trail and bucket history in DynamoDB
- ✅ **User-Friendly Interface**: Modern web interface for all operations
- ✅ **Lifecycle Management**: Built-in and custom S3 lifecycle policies
- ✅ **Cost Optimization**: Efficient resource usage within AWS Free Tier
- ✅ **Scalability**: Serverless architecture that scales automatically
- ✅ **Observability**: CloudWatch logging and monitoring built-in

The system is designed to be:
- **Secure**: Multiple layers of security and authentication
- **Reliable**: Automated healing and monitoring
- **Scalable**: Serverless architecture handles any load
- **Maintainable**: Well-documented code and infrastructure
- **Cost-Effective**: Optimized for AWS Free Tier usage

For questions, issues, or contributions, please refer to the project repository or contact the development team.

---

**Document Version**: 3.0  
**Last Updated**: 2024  
**Maintained By**: Development Team