# Complete Step-by-Step Implementation Guide
This was my backup- lots of modification was done to achieve this. follow the below step but refer code from repo :-)

## Phase 1: Prerequisites and Setup (30 minutes)

### Step 1: AWS Account Setup
1. **Create AWS Account** (if you don't have one)
   - Go to https://aws.amazon.com/
   - Click "Create an AWS Account"
   - Complete verification process

2. **Configure AWS CLI**
   ```bash
   # Install AWS CLI
   pip install awscli
   
   # Configure with your credentials
   aws configure
   # Enter:
   # AWS Access Key ID: [Your access key]
   # AWS Secret Access Key: [Your secret key]
   # Default region name: us-east-1
   # Default output format: json
   ```

3. **Verify CLI Setup**
   ```bash
   aws sts get-caller-identity
   ```

### Step 2: Create Project Structure
```bash
mkdir s3-bucket-manager
cd s3-bucket-manager

# Create directory structure
mkdir -p {infrastructure,lambda-functions,web-interface,scripts,tests}

# File structure will be:
# s3-bucket-manager/
# ├── infrastructure/
# │   ├── cloudformation-template.yaml
# │   └── parameters.json
# ├── lambda-functions/
# │   ├── create-bucket/
# │   ├── monitor-buckets/
# │   └── list-buckets/
# ├── web-interface/
# │   ├── index.html
# │   └── config.js
# ├── scripts/
# │   ├── deploy.sh
# │   ├── test.py
# │   └── monitor.py
# └── tests/
```

## Phase 2: Authentication Strategy (45 minutes)

### Authentication Options for Different Use Cases:

#### Option 1: API Keys (Simplest - For Internal Use)
**Best for:** Internal teams, limited users
**Cost:** Free tier friendly

#### Option 2: AWS Cognito (Recommended - For Production)
**Best for:** Multiple users, external access
**Cost:** 50,000 MAU free

#### Option 3: IAM-based (Enterprise)
**Best for:** AWS-native applications
**Cost:** No additional cost

### Implementation: AWS Cognito Authentication

#### Step 1: Create Cognito User Pool
```yaml
# Add to CloudFormation template
CognitoUserPool:
  Type: AWS::Cognito::UserPool
  Properties:
    UserPoolName: bucket-management-users
    Policies:
      PasswordPolicy:
        MinimumLength: 8
        RequireUppercase: true
        RequireLowercase: true
        RequireNumbers: true
        RequireSymbols: false
    AutoVerifiedAttributes:
      - email
    MfaConfiguration: OFF
    EmailConfiguration:
      EmailSendingAccount: COGNITO_DEFAULT

CognitoUserPoolClient:
  Type: AWS::Cognito::UserPoolClient
  Properties:
    UserPoolId: !Ref CognitoUserPool
    ClientName: bucket-management-client
    GenerateSecret: false
    ExplicitAuthFlows:
      - ADMIN_NO_SRP_AUTH
      - USER_PASSWORD_AUTH
    PreventUserExistenceErrors: ENABLED

CognitoIdentityPool:
  Type: AWS::Cognito::IdentityPool
  Properties:
    IdentityPoolName: bucket_management_identity_pool
    AllowUnauthenticatedIdentities: false
    CognitoIdentityProviders:
      - ClientId: !Ref CognitoUserPoolClient
        ProviderName: !GetAtt CognitoUserPool.ProviderName

# IAM Role for authenticated users
CognitoAuthRole:
  Type: AWS::IAM::Role
  Properties:
    AssumeRolePolicyDocument:
      Version: '2012-10-17'
      Statement:
        - Effect: Allow
          Principal:
            Federated: cognito-identity.amazonaws.com
          Action: sts:AssumeRoleWithWebIdentity
          Condition:
            StringEquals:
              'cognito-identity.amazonaws.com:aud': !Ref CognitoIdentityPool
            'ForAnyValue:StringLike':
              'cognito-identity.amazonaws.com:amr': authenticated
    Policies:
      - PolicyName: CognitoAuthPolicy
        PolicyDocument:
          Version: '2012-10-17'
          Statement:
            - Effect: Allow
              Action:
                - execute-api:Invoke
              Resource: !Sub "${BucketManagementAPI}/*"

CognitoIdentityPoolRoleAttachment:
  Type: AWS::Cognito::IdentityPoolRoleAttachment
  Properties:
    IdentityPoolId: !Ref CognitoIdentityPool
    Roles:
      authenticated: !GetAtt CognitoAuthRole.Arn
```

#### Step 2: Update API Gateway with Cognito Authorizer
```yaml
# Add Cognito Authorizer to API Gateway
CognitoAuthorizer:
  Type: AWS::ApiGateway::Authorizer
  Properties:
    Name: CognitoAuthorizer
    Type: COGNITO_USER_POOLS
    IdentitySource: method.request.header.Authorization
    RestApiId: !Ref BucketManagementAPI
    ProviderARNs:
      - !GetAtt CognitoUserPool.Arn

# Update API methods to use authorizer
CreateBucketMethod:
  Type: AWS::ApiGateway::Method
  Properties:
    RestApiId: !Ref BucketManagementAPI
    ResourceId: !Ref BucketsResource
    HttpMethod: POST
    AuthorizationType: COGNITO_USER_POOLS
    AuthorizerId: !Ref CognitoAuthorizer  # Add this line
    Integration:
      Type: AWS_PROXY
      IntegrationHttpMethod: POST
      Uri: !Sub 
        - arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${LambdaArn}/invocations
        - LambdaArn: !GetAtt CreateBucketFunction.Arn
```

## Phase 3: Core Infrastructure Deployment (60 minutes)

### Step 1: Create Complete CloudFormation Template

Save this as `infrastructure/cloudformation-template.yaml`:

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: 'S3 Bucket Management System with Authentication'

Parameters:
  NotificationEmail:
    Type: String
    Description: Email for notifications
    Default: your-email@example.com
  Environment:
    Type: String
    Default: dev
    AllowedValues: [dev, staging, prod]

Resources:
  # Cognito User Pool
  CognitoUserPool:
    Type: AWS::Cognito::UserPool
    Properties:
      UserPoolName: !Sub "${Environment}-bucket-management-users"
      Policies:
        PasswordPolicy:
          MinimumLength: 8
          RequireUppercase: true
          RequireLowercase: true
          RequireNumbers: true
          RequireSymbols: false
      AutoVerifiedAttributes:
        - email
      MfaConfiguration: OFF
      EmailConfiguration:
        EmailSendingAccount: COGNITO_DEFAULT
      Schema:
        - Name: email
          AttributeDataType: String
          Required: true
          Mutable: true
        - Name: name
          AttributeDataType: String
          Required: true
          Mutable: true

  CognitoUserPoolClient:
    Type: AWS::Cognito::UserPoolClient
    Properties:
      UserPoolId: !Ref CognitoUserPool
      ClientName: !Sub "${Environment}-bucket-management-client"
      GenerateSecret: false
      ExplicitAuthFlows:
        - ADMIN_NO_SRP_AUTH
        - USER_PASSWORD_AUTH
        - ALLOW_USER_SRP_AUTH
        - ALLOW_REFRESH_TOKEN_AUTH
      PreventUserExistenceErrors: ENABLED
      TokenValidityUnits:
        AccessToken: hours
        IdToken: hours
        RefreshToken: days
      AccessTokenValidity: 1
      IdTokenValidity: 1
      RefreshTokenValidity: 30

  CognitoIdentityPool:
    Type: AWS::Cognito::IdentityPool
    Properties:
      IdentityPoolName: !Sub "${Environment}_bucket_management_identity_pool"
      AllowUnauthenticatedIdentities: false
      CognitoIdentityProviders:
        - ClientId: !Ref CognitoUserPoolClient
          ProviderName: !GetAtt CognitoUserPool.ProviderName

  # DynamoDB Table for metadata
  BucketMetadataTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub "${Environment}-bucket-metadata"
      BillingMode: ON_DEMAND
      AttributeDefinitions:
        - AttributeName: project_name
          AttributeType: S
        - AttributeName: bucket_name
          AttributeType: S
        - AttributeName: user_id
          AttributeType: S
      KeySchema:
        - AttributeName: project_name
          KeyType: HASH
      GlobalSecondaryIndexes:
        - IndexName: bucket-name-index
          KeySchema:
            - AttributeName: bucket_name
              KeyType: HASH
          Projection:
            ProjectionType: ALL
        - IndexName: user-id-index
          KeySchema:
            - AttributeName: user_id
              KeyType: HASH
          Projection:
            ProjectionType: ALL
      StreamSpecification:
        StreamViewType: NEW_AND_OLD_IMAGES
      PointInTimeRecoverySpecification:
        PointInTimeRecoveryEnabled: true

  # SNS Topic for notifications
  BucketNotificationTopic:
    Type: AWS::SNS::Topic
    Properties:
      TopicName: !Sub "${Environment}-bucket-notifications"
      Subscription:
        - Endpoint: !Ref NotificationEmail
          Protocol: email

  # IAM Role for Lambda functions
  BucketManagementRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Sub "${Environment}-bucket-management-role"
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: lambda.amazonaws.com
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
      Policies:
        - PolicyName: BucketManagementPolicy
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - s3:CreateBucket
                  - s3:DeleteBucket
                  - s3:GetBucketLocation
                  - s3:ListBucket
                  - s3:PutBucketPublicAccessBlock
                  - s3:PutBucketVersioning
                  - s3:PutBucketEncryption
                  - s3:HeadBucket
                Resource: '*'
              - Effect: Allow
                Action:
                  - dynamodb:GetItem
                  - dynamodb:PutItem
                  - dynamodb:UpdateItem
                  - dynamodb:DeleteItem
                  - dynamodb:Query
                  - dynamodb:Scan
                Resource: 
                  - !GetAtt BucketMetadataTable.Arn
                  - !Sub '${BucketMetadataTable.Arn}/index/*'
              - Effect: Allow
                Action:
                  - sns:Publish
                Resource: !Ref BucketNotificationTopic

  # Lambda Layer for common dependencies
  CommonLayer:
    Type: AWS::Lambda::LayerVersion
    Properties:
      LayerName: !Sub "${Environment}-bucket-management-common"
      Description: Common dependencies for bucket management
      Content:
        ZipFile: |
          # This would contain common utilities
          # For now, we'll put utilities directly in functions
      CompatibleRuntimes:
        - python3.9

  # Lambda: Create Bucket (Enhanced)
  CreateBucketFunction:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: !Sub "${Environment}-create-bucket"
      Runtime: python3.9
      Handler: index.lambda_handler
      Role: !GetAtt BucketManagementRole.Arn
      Timeout: 30
      MemorySize: 128
      Environment:
        Variables:
          TABLE_NAME: !Ref BucketMetadataTable
          SNS_TOPIC: !Ref BucketNotificationTopic
          ENVIRONMENT: !Ref Environment
      Code:
        ZipFile: |
          import json
          import boto3
          import os
          import uuid
          import re
          from datetime import datetime
          
          s3 = boto3.client('s3')
          dynamodb = boto3.resource('dynamodb')
          sns = boto3.client('sns')
          
          table = dynamodb.Table(os.environ['TABLE_NAME'])
          topic_arn = os.environ['SNS_TOPIC']
          environment = os.environ['ENVIRONMENT']
          
          def lambda_handler(event, context):
              try:
                  # Extract user info from Cognito
                  user_id = None
                  user_email = None
                  
                  if 'requestContext' in event and 'authorizer' in event['requestContext']:
                      claims = event['requestContext']['authorizer']['claims']
                      user_id = claims.get('sub')
                      user_email = claims.get('email')
                  
                  body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
                  project_name = body['project_name'].lower().strip()
                  
                  # Validate project name
                  if not re.match(r'^[a-z0-9-]+$', project_name):
                      return {
                          'statusCode': 400,
                          'headers': {'Content-Type': 'application/json'},
                          'body': json.dumps({'error': 'Project name must contain only lowercase letters, numbers, and hyphens'})
                      }
                  
                  if len(project_name) < 3 or len(project_name) > 50:
                      return {
                          'statusCode': 400,
                          'headers': {'Content-Type': 'application/json'},
                          'body': json.dumps({'error': 'Project name must be between 3 and 50 characters'})
                      }
                  
                  # Generate unique bucket name
                  bucket_name = f"{environment}-{project_name}-{str(uuid.uuid4())[:8]}"
                  
                  # Check if project already exists for this user
                  try:
                      response = table.get_item(Key={'project_name': f"{user_id}#{project_name}"})
                      if 'Item' in response:
                          return {
                              'statusCode': 409,
                              'headers': {'Content-Type': 'application/json'},
                              'body': json.dumps({'error': 'Project already exists for this user'})
                          }
                  except Exception as e:
                      pass
                  
                  # Create S3 bucket
                  s3.create_bucket(Bucket=bucket_name)
                  
                  # Configure bucket security
                  s3.put_bucket_public_access_block(
                      Bucket=bucket_name,
                      PublicAccessBlockConfiguration={
                          'BlockPublicAcls': True,
                          'IgnorePublicAcls': True,
                          'BlockPublicPolicy': True,
                          'RestrictPublicBuckets': True
                      }
                  )
                  
                  # Enable encryption
                  s3.put_bucket_encryption(
                      Bucket=bucket_name,
                      ServerSideEncryptionConfiguration={
                          'Rules': [{
                              'ApplyServerSideEncryptionByDefault': {
                                  'SSEAlgorithm': 'AES256'
                              }
                          }]
                      }
                  )
                  
                  # Store metadata
                  table.put_item(
                      Item={
                          'project_name': f"{user_id}#{project_name}",
                          'bucket_name': bucket_name,
                          'user_id': user_id,
                          'user_email': user_email or 'unknown',
                          'display_name': project_name,
                          'created_at': datetime.utcnow().isoformat(),
                          'status': 'active',
                          'last_checked': datetime.utcnow().isoformat(),
                          'environment': environment
                      }
                  )
                  
                  # Send notification
                  sns.publish(
                      TopicArn=topic_arn,
                      Message=f"Bucket {bucket_name} created for project {project_name} by user {user_email}",
                      Subject="S3 Bucket Created"
                  )
                  
                  return {
                      'statusCode': 200,
                      'headers': {
                          'Content-Type': 'application/json',
                          'Access-Control-Allow-Origin': '*'
                      },
                      'body': json.dumps({
                          'project_name': project_name,
                          'bucket_name': bucket_name,
                          'status': 'created'
                      })
                  }
                  
              except Exception as e:
                  print(f"Error: {str(e)}")
                  return {
                      'statusCode': 500,
                      'headers': {'Content-Type': 'application/json'},
                      'body': json.dumps({'error': 'Internal server error'})
                  }

  # Lambda: List Buckets (Enhanced)
  ListBucketsFunction:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: !Sub "${Environment}-list-buckets"
      Runtime: python3.9
      Handler: index.lambda_handler
      Role: !GetAtt BucketManagementRole.Arn
      Timeout: 30
      MemorySize: 128
      Environment:
        Variables:
          TABLE_NAME: !Ref BucketMetadataTable
      Code:
        ZipFile: |
          import json
          import boto3
          import os
          from boto3.dynamodb.conditions import Key
          
          dynamodb = boto3.resource('dynamodb')
          table = dynamodb.Table(os.environ['TABLE_NAME'])
          
          def lambda_handler(event, context):
              try:
                  # Extract user info from Cognito
                  user_id = None
                  if 'requestContext' in event and 'authorizer' in event['requestContext']:
                      claims = event['requestContext']['authorizer']['claims']
                      user_id = claims.get('sub')
                  
                  if not user_id:
                      return {
                          'statusCode': 401,
                          'headers': {'Content-Type': 'application/json'},
                          'body': json.dumps({'error': 'Unauthorized'})
                      }
                  
                  # Get query parameters
                  query_params = event.get('queryStringParameters', {}) or {}
                  project_name = query_params.get('project_name')
                  
                  if project_name:
                      # Get specific project for this user
                      response = table.get_item(Key={'project_name': f"{user_id}#{project_name}"})
                      if 'Item' in response:
                          item = response['Item']
                          # Remove internal user_id from response
                          item.pop('user_id', None)
                          return {
                              'statusCode': 200,
                              'headers': {
                                  'Content-Type': 'application/json',
                                  'Access-Control-Allow-Origin': '*'
                              },
                              'body': json.dumps(item, default=str)
                          }
                      else:
                          return {
                              'statusCode': 404,
                              'headers': {'Content-Type': 'application/json'},
                              'body': json.dumps({'error': 'Project not found'})
                          }
                  else:
                      # List all projects for this user
                      response = table.query(
                          IndexName='user-id-index',
                          KeyConditionExpression=Key('user_id').eq(user_id)
                      )
                      
                      items = response['Items']
                      # Clean up items for response
                      for item in items:
                          item.pop('user_id', None)
                      
                      return {
                          'statusCode': 200,
                          'headers': {
                              'Content-Type': 'application/json',
                              'Access-Control-Allow-Origin': '*'
                          },
                          'body': json.dumps(items, default=str)
                      }
                      
              except Exception as e:
                  print(f"Error: {str(e)}")
                  return {
                      'statusCode': 500,
                      'headers': {'Content-Type': 'application/json'},
                      'body': json.dumps({'error': 'Internal server error'})
                  }

  # Lambda: Monitor and Heal Buckets (Enhanced)
  MonitorBucketsFunction:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: !Sub "${Environment}-monitor-buckets"
      Runtime: python3.9
      Handler: index.lambda_handler
      Role: !GetAtt BucketManagementRole.Arn
      Timeout: 300
      MemorySize: 256
      Environment:
        Variables:
          TABLE_NAME: !Ref BucketMetadataTable
          SNS_TOPIC: !Ref BucketNotificationTopic
          ENVIRONMENT: !Ref Environment
      Code:
        ZipFile: |
          import json
          import boto3
          import os
          from datetime import datetime
          
          s3 = boto3.client('s3')
          dynamodb = boto3.resource('dynamodb')
          sns = boto3.client('sns')
          
          table = dynamodb.Table(os.environ['TABLE_NAME'])
          topic_arn = os.environ['SNS_TOPIC']
          environment = os.environ['ENVIRONMENT']
          
          def lambda_handler(event, context):
              processed_buckets = 0
              healed_buckets = 0
              
              try:
                  # Scan all active buckets
                  response = table.scan(
                      FilterExpression='#status = :status',
                      ExpressionAttributeNames={'#status': 'status'},
                      ExpressionAttributeValues={':status': 'active'}
                  )
                  
                  for item in response['Items']:
                      bucket_name = item['bucket_name']
                      project_name = item['project_name']
                      user_email = item.get('user_email', 'unknown')
                      display_name = item.get('display_name', project_name)
                      
                      processed_buckets += 1
                      
                      try:
                          # Check if bucket exists
                          s3.head_bucket(Bucket=bucket_name)
                          
                          # Update last_checked
                          table.update_item(
                              Key={'project_name': project_name},
                              UpdateExpression='SET last_checked = :timestamp',
                              ExpressionAttributeValues={
                                  ':timestamp': datetime.utcnow().isoformat()
                              }
                          )
                          
                      except s3.exceptions.NoSuchBucket:
                          # Bucket doesn't exist, recreate it
                          if recreate_bucket(bucket_name, project_name, user_email, display_name):
                              healed_buckets += 1
                          
                      except Exception as e:
                          print(f"Error checking bucket {bucket_name}: {str(e)}")
                  
                  return {
                      'statusCode': 200,
                      'body': json.dumps({
                          'message': 'Monitoring completed',
                          'processed_buckets': processed_buckets,
                          'healed_buckets': healed_buckets
                      })
                  }
                  
              except Exception as e:
                  print(f"Error in monitoring: {str(e)}")
                  return {
                      'statusCode': 500,
                      'body': json.dumps({'error': str(e)})
                  }
          
          def recreate_bucket(bucket_name, project_name, user_email, display_name):
              try:
                  # Recreate bucket
                  s3.create_bucket(Bucket=bucket_name)
                  
                  # Configure security
                  s3.put_bucket_public_access_block(
                      Bucket=bucket_name,
                      PublicAccessBlockConfiguration={
                          'BlockPublicAcls': True,
                          'IgnorePublicAcls': True,
                          'BlockPublicPolicy': True,
                          'RestrictPublicBuckets': True
                      }
                  )
                  
                  # Enable encryption
                  s3.put_bucket_encryption(
                      Bucket=bucket_name,
                      ServerSideEncryptionConfiguration={
                          'Rules': [{
                              'ApplyServerSideEncryptionByDefault': {
                                  'SSEAlgorithm': 'AES256'
                              }
                          }]
                      }
                  )
                  
                  # Update metadata
                  table.update_item(
                      Key={'project_name': project_name},
                      UpdateExpression='SET last_checked = :timestamp, healed_at = :timestamp, heal_count = if_not_exists(heal_count, :zero) + :one',
                      ExpressionAttributeValues={
                          ':timestamp': datetime.utcnow().isoformat(),
                          ':zero': 0,
                          ':one': 1
                      }
                  )
                  
                  # Send healing notification
                  sns.publish(
                      TopicArn=topic_arn,
                      Message=f"Bucket {bucket_name} for project '{display_name}' was automatically recreated.\n\nUser: {user_email}\nTime: {datetime.utcnow().isoformat()}\n\nThe bucket was deleted and has been restored with the same configuration.",
                      Subject=f"S3 Bucket Healed - {display_name}"
                  )
                  
                  print(f"Bucket {bucket_name} recreated successfully")
                  return True
                  
              except Exception as e:
                  print(f"Error recreating bucket {bucket_name}: {str(e)}")
                  return False

  # API Gateway
  BucketManagementAPI:
    Type: AWS::ApiGateway::RestApi
    Properties:
      Name: !Sub "${Environment}-bucket-management-api"
      Description: API for S3 bucket management
      EndpointConfiguration:
        Types:
          - REGIONAL

  # Cognito Authorizer
  CognitoAuthorizer:
    Type: AWS::ApiGateway::Authorizer
    Properties:
      Name: CognitoAuthorizer
      Type: COGNITO_USER_POOLS
      IdentitySource: method.request.header.Authorization
      RestApiId: !Ref BucketManagementAPI
      ProviderARNs:
        - !GetAtt CognitoUserPool.Arn

  # CORS Support
  CorsOptionsMethod:
    Type: AWS::ApiGateway::Method
    Properties:
      RestApiId: !Ref BucketManagementAPI
      ResourceId: !GetAtt BucketManagementAPI.RootResourceId
      HttpMethod: OPTIONS
      AuthorizationType: NONE
      Integration:
        Type: MOCK
        IntegrationResponses:
          - StatusCode: 200
            ResponseParameters:
              method.response.header.Access-Control-Allow-Headers: "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
              method.response.header.Access-Control-Allow-Methods: "'GET,POST,PUT,DELETE,OPTIONS'"
              method.response.header.Access-Control-Allow-Origin: "'*'"
        RequestTemplates:
          application/json: '{"statusCode": 200}'
      MethodResponses:
        - StatusCode: 200
          ResponseParameters:
            method.response.header.Access-Control-Allow-Headers: true
            method.response.header.Access-Control-Allow-Methods: true
            method.response.header.Access-Control-Allow-Origin: true

  # API Gateway Resources and Methods
  BucketsResource:
    Type: AWS::ApiGateway::Resource
    Properties:
      RestApiId: !Ref BucketManagementAPI
      ParentId: !GetAtt BucketManagementAPI.RootResourceId
      PathPart: buckets

  BucketsOptionsMethod:
    Type: AWS::ApiGateway::Method
    Properties:
      RestApiId: !Ref BucketManagementAPI
      ResourceId: !Ref BucketsResource
      HttpMethod: OPTIONS
      AuthorizationType: NONE
      Integration:
        Type: MOCK
        IntegrationResponses:
          - StatusCode: 200
            ResponseParameters:
              method.response.header.Access-Control-Allow-Headers: "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
              method.response.header.Access-Control-Allow-Methods: "'GET,POST,PUT,DELETE,OPTIONS'"
              method.response.header.Access-Control-Allow-Origin: "'*'"
        RequestTemplates:
          application/json: '{"statusCode": 200}'
      MethodResponses:
        - StatusCode: 200
          ResponseParameters:
            method.response.header.Access-Control-Allow-Headers: true
            method.response.header.Access-Control-Allow-Methods: true
            method.response.header.Access-Control-Allow-Origin: true

  CreateBucketMethod:
    Type: AWS::ApiGateway::Method
    Properties:
      RestApiId: !Ref BucketManagementAPI
      ResourceId: !Ref BucketsResource
      HttpMethod: POST
      AuthorizationType: COGNITO_USER_POOLS
      AuthorizerId: !Ref CognitoAuthorizer
      Integration:
        Type: AWS_PROXY
        IntegrationHttpMethod: POST
        Uri: !Sub 
          - arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${LambdaArn}/invocations
          - LambdaArn: !GetAtt CreateBucketFunction.Arn

  ListBucketsMethod:
    Type: AWS::ApiGateway::Method
    Properties:
      RestApiId: !Ref BucketManagementAPI
      ResourceId: !Ref BucketsResource
      HttpMethod: GET
      AuthorizationType: COGNITO_USER_POOLS
      AuthorizerId: !Ref CognitoAuthorizer
      Integration:
        Type: AWS_PROXY
        IntegrationHttpMethod: POST
        Uri: !Sub 
          - arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${LambdaArn}/invocations
          - LambdaArn: !GetAtt ListBucketsFunction.Arn

  # Lambda permissions for API Gateway
  CreateBucketPermission:
    Type: AWS::Lambda::Permission
    Properties:
      FunctionName: !Ref CreateBucketFunction
      Action: lambda:InvokeFunction
      Principal: apigateway.amazonaws.com
      SourceArn: !Sub "${BucketManagementAPI}/*/POST/buckets"

  ListBucketsPermission:
    Type: AWS::Lambda::Permission
    Properties:
      FunctionName: !Ref ListBucketsFunction
      Action: lambda:InvokeFunction
      Principal: apigateway.amazonaws.com
      SourceArn: !Sub "${BucketManagementAPI}/*/GET/buckets"

  # API Gateway Deployment
  APIDeployment:
    Type: AWS::ApiGateway::Deployment
    DependsOn:
      - CreateBucketMethod
      - ListBucketsMethod
      - BucketsOptionsMethod
      - CorsOptionsMethod
    Properties:
      RestApiId: !Ref BucketManagementAPI
      StageName: !Ref Environment

  # EventBridge Rule for monitoring
  MonitoringRule:
    Type: AWS::Events::Rule
    Properties:
      Description: "Monitor S3 buckets every 5 minutes"
      ScheduleExpression: "rate(5 minutes)"
      State: ENABLED
      Targets:
        - Arn: !GetAtt MonitorBucketsFunction.Arn
          Id: "MonitorBucketsTarget"

  # EventBridge permission for Lambda
  MonitoringPermission:
    Type: AWS::Lambda::Permission
    Properties:
      FunctionName: !Ref MonitorBucketsFunction
      Action: lambda:InvokeFunction
      Principal: events.amazonaws.com
      SourceArn: !GetAtt MonitoringRule.Arn

  # IAM Role for authenticated Cognito users
  CognitoAuthRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Federated: cognito-identity.amazonaws.com
            Action: sts:AssumeRoleWithWebIdentity
            Condition:
              StringEquals:
                'cognito-identity.amazonaws.com:aud': !Ref CognitoIdentityPool
              'ForAnyValue:StringLike':
                'cognito-identity.amazonaws.com:amr': authenticated
      Policies:
        - PolicyName: CognitoAuthPolicy
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - execute-api:Invoke
                Resource: !Sub "${BucketManagementAPI}/*"

  CognitoIdentityPoolRoleAttachment:
    Type: AWS::Cognito::IdentityPoolRoleAttachment
    Properties:
      IdentityPoolId: !Ref CognitoIdentityPool
      Roles:
        authenticated: !GetAtt CognitoAuthRole.Arn

Outputs:
  APIEndpoint:
    Description: API Gateway endpoint
    Value: !Sub "https://${BucketManagementAPI}.execute-api.${AWS::Region}.amazonaws.com/${Environment}"
    Export:
      Name: !Sub "${Environment}-bucket-api-endpoint"
  
  UserPoolId:
    Description: Cognito User Pool ID
    Value: !Ref CognitoUserPool
    Export:
      Name: !Sub "${Environment}-user-pool-id"
      
  UserPoolClientId:
    Description: Cognito User Pool Client ID
    Value: !Ref CognitoUserPoolClient
    Export:
      Name: !Sub "${Environment}-user-pool-client-id"
  
  IdentityPoolId:
    Description: Cognito Identity Pool ID
    Value: !Ref CognitoIdentityPool
    Export:
      Name: !Sub "${Environment}-identity-pool-id"
  
  DynamoDBTable:
    Description: DynamoDB table name
    Value: !Ref BucketMetadataTable
    Export:
      Name: !Sub "${Environment}-bucket-metadata-table"
    
  SNSTopic:
    Description: SNS topic ARN
    Value: !Ref BucketNotificationTopic
    Export:
      Name: !Sub "${Environment}-sns-topic"
```

### Step 2: Create Parameters File

Save this as `infrastructure/parameters.json`:

```json
{
  "NotificationEmail": "your-email@example.com",
  "Environment": "dev"
}
```

### Step 3: Create Deployment Script

Save this as `scripts/deploy.sh`:

```bash
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
```

## Phase 4: Enhanced Web Interface with Authentication (45 minutes)

### Step 1: Create Web Interface HTML

Save this as `web-interface/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>S3 Bucket Manager</title>
    
    <!-- AWS SDK -->
    <script src="https://sdk.amazonaws.com/js/aws-sdk-2.1400.0.min.js"></script>
    <!-- Configuration -->
    <script src="config.js"></script>
    
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .main-content {
            padding: 30px;
        }
        
        .auth-section, .app-section {
            display: none;
        }
        
        .auth-section.active, .app-section.active {
            display: block;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #333;
        }
        
        input {
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e1e5e9;
            border-radius: 10px;
            font-size: 16px;
            transition: border-color 0.3s ease;
        }
        
        input:focus {
            outline: none;
            border-color: #667eea;
        }
        
        button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px 24px;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 600;
            margin-right: 10px;
            margin-bottom: 10px;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        
        button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }
        
        .button-secondary {
            background: #6c757d;
        }
        
        .button-danger {
            background: #dc3545;
        }
        
        .bucket-list {
            margin-top: 30px;
        }
        
        .bucket-item {
            background: #f8f9fa;
            padding: 20px;
            margin-bottom: 15px;
            border-radius: 15px;
            border-left: 5px solid #667eea;
            transition: transform 0.2s ease;
        }
        
        .bucket-item:hover {
            transform: translateX(5px);
        }
        
        .bucket-item h3 {
            color: #667eea;
            margin-bottom: 10px;
        }
        
        .bucket-info {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 10px;
            font-size: 14px;
            color: #6c757d;
        }
        
        .status {
            padding: 15px 20px;
            margin: 15px 0;
            border-radius: 10px;
            font-weight: 500;
        }
        
        .status.success {
            background-color: #d4edda;
            color: #155724;
            border-left: 4px solid #28a745;
        }
        
        .status.error {
            background-color: #f8d7da;
            color: #721c24;
            border-left: 4px solid #dc3545;
        }
        
        .status.info {
            background-color: #cce7ff;
            color: #004085;
            border-left: 4px solid #007bff;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: #6c757d;
        }
        
        .loading::after {
            content: '';
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-left: 10px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .user-info {
            background: #e3f2fd;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        
        .auth-forms {
            display: flex;
            gap: 30px;
            flex-wrap: wrap;
        }
        
        .auth-form {
            flex: 1;
            min-width: 300px;
            background: #f8f9fa;
            padding: 25px;
            border-radius: 15px;
        }
        
        .auth-form h3 {
            margin-bottom: 20px;
            color: #333;
        }
        
        @media (max-width: 768px) {
            .auth-forms {
                flex-direction: column;
            }
            
            .header h1 {
                font-size: 2em;
            }
            
            .main-content {
                padding: 20px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🗄️ S3 Bucket Manager</h1>
            <p>Secure, Automated Bucket Management System</p>
        </div>
        
        <div class="main-content">
            <!-- Authentication Section -->
            <div id="authSection" class="auth-section active">
                <div class="auth-forms">
                    <!-- Sign In Form -->
                    <div class="auth-form">
                        <h3>Sign In</h3>
                        <div class="form-group">
                            <label for="signInEmail">Email:</label>
                            <input type="email" id="signInEmail" placeholder="Enter your email">
                        </div>
                        <div class="form-group">
                            <label for="signInPassword">Password:</label>
                            <input type="password" id="signInPassword" placeholder="Enter your password">
                        </div>
                        <button onclick="signIn()" id="signInBtn">Sign In</button>
                    </div>
                    
                    <!-- Sign Up Form -->
                    <div class="auth-form">
                        <h3>Sign Up</h3>
                        <div class="form-group">
                            <label for="signUpName">Full Name:</label>
                            <input type="text" id="signUpName" placeholder="Enter your full name">
                        </div>
                        <div class="form-group">
                            <label for="signUpEmail">Email:</label>
                            <input type="email" id="signUpEmail" placeholder="Enter your email">
                        </div>
                        <div class="form-group">
                            <label for="signUpPassword">Password:</label>
                            <input type="password" id="signUpPassword" placeholder="Create a password (min 8 chars)">
                        </div>
                        <button onclick="signUp()" id="signUpBtn">Sign Up</button>
                    </div>
                </div>
                
                <!-- Confirmation Form (hidden by default) -->
                <div id="confirmationForm" style="display: none;" class="auth-form">
                    <h3>Confirm Your Account</h3>
                    <p>Please check your email and enter the confirmation code:</p>
                    <div class="form-group">
                        <label for="confirmationCode">Confirmation Code:</label>
                        <input type="text" id="confirmationCode" placeholder="Enter 6-digit code">
                    </div>
                    <button onclick="confirmSignUp()" id="confirmBtn">Confirm Account</button>
                    <button onclick="resendConfirmation()" class="button-secondary">Resend Code</button>
                </div>
            </div>
            
            <!-- Application Section -->
            <div id="appSection" class="app-section">
                <div class="user-info">
                    <strong>Welcome, <span id="userName">User</span>!</strong>
                    <button onclick="signOut()" class="button-secondary" style="float: right;">Sign Out</button>
                </div>
                
                <div id="status"></div>
                
                <div class="form-group">
                    <label for="projectName">Project Name:</label>
                    <input type="text" id="projectName" placeholder="Enter project name (e.g., my-web-app)">
                    <small>Only lowercase letters, numbers, and hyphens allowed (3-50 characters)</small>
                </div>
                
                <button onclick="createBucket()" id="createBtn">Create Bucket</button>
                <button onclick="loadBuckets()" id="refreshBtn" class="button-secondary">Refresh List</button>
                
                <div class="bucket-list">
                    <h2>Your Buckets</h2>
                    <div id="bucketsList"></div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // AWS Configuration
        AWS.config.update({
            region: CONFIG.region,
            credentials: new AWS.CognitoIdentityCredentials({
                IdentityPoolId: CONFIG.identityPoolId
            })
        });

        const cognitoUser = new AWS.CognitoIdentityServiceProvider();
        let currentUser = null;
        let currentSession = null;

        // Initialize the app
        document.addEventListener('DOMContentLoaded', function() {
            checkAuthState();
        });

        function showStatus(message, type = 'info') {
            const statusDiv = document.getElementById('status');
            statusDiv.innerHTML = `<div class="status ${type}">${message}</div>`;
            setTimeout(() => {
                statusDiv.innerHTML = '';
            }, 5000);
        }

        function setLoading(elementId, loading) {
            const element = document.getElementById(elementId);
            if (loading) {
                element.disabled = true;
                element.textContent = element.textContent.replace('...', '') + '...';
            } else {
                element.disabled = false;
                element.textContent = element.textContent.replace('...', '');
            }
        }

        // Authentication Functions
        async function signUp() {
            const name = document.getElementById('signUpName').value.trim();
            const email = document.getElementById('signUpEmail').value.trim();
            const password = document.getElementById('signUpPassword').value;

            if (!name || !email || !password) {
                showStatus('Please fill in all fields', 'error');
                return;
            }

            if (password.length < 8) {
                showStatus('Password must be at least 8 characters long', 'error');
                return;
            }

            setLoading('signUpBtn', true);

            try {
                const params = {
                    ClientId: CONFIG.userPoolClientId,
                    Username: email,
                    Password: password,
                    UserAttributes: [
                        { Name: 'email', Value: email },
                        { Name: 'name', Value: name }
                    ]
                };

                await cognitoUser.signUp(params).promise();
                
                // Store email for confirmation
                localStorage.setItem('pendingEmail', email);
                
                // Show confirmation form
                document.getElementById('confirmationForm').style.display = 'block';
                showStatus('Account created! Please check your email for confirmation code.', 'success');
                
            } catch (error) {
                console.error('Sign up error:', error);
                showStatus(`Sign up failed: ${error.message}`, 'error');
            } finally {
                setLoading('signUpBtn', false);
            }
        }

        async function confirmSignUp() {
            const email = localStorage.getItem('pendingEmail');
            const code = document.getElementById('confirmationCode').value.trim();

            if (!code) {
                showStatus('Please enter the confirmation code', 'error');
                return;
            }

            setLoading('confirmBtn', true);

            try {
                const params = {
                    ClientId: CONFIG.userPoolClientId,
                    Username: email,
                    ConfirmationCode: code
                };

                await cognitoUser.confirmSignUp(params).promise();
                
                localStorage.removeItem('pendingEmail');
                document.getElementById('confirmationForm').style.display = 'none';
                showStatus('Account confirmed! You can now sign in.', 'success');
                
            } catch (error) {
                console.error('Confirmation error:', error);
                showStatus(`Confirmation failed: ${error.message}`, 'error');
            } finally {
                setLoading('confirmBtn', false);
            }
        }

        async function resendConfirmation() {
            const email = localStorage.getItem('pendingEmail');
            
            try {
                const params = {
                    ClientId: CONFIG.userPoolClientId,
                    Username: email
                };

                await cognitoUser.resendConfirmationCode(params).promise();
                showStatus('Confirmation code resent! Check your email.', 'success');
                
            } catch (error) {
                console.error('Resend error:', error);
                showStatus(`Resend failed: ${error.message}`, 'error');
            }
        }

        async function signIn() {
            const email = document.getElementById('signInEmail').value.trim();
            const password = document.getElementById('signInPassword').value;

            if (!email || !password) {
                showStatus('Please enter both email and password', 'error');
                return;
            }

            setLoading('signInBtn', true);

            try {
                const params = {
                    AuthFlow: 'USER_PASSWORD_AUTH',
                    ClientId: CONFIG.userPoolClientId,
                    AuthParameters: {
                        USERNAME: email,
                        PASSWORD: password
                    }
                };

                const result = await cognitoUser.initiateAuth(params).promise();
                
                if (result.AuthenticationResult) {
                    // Store tokens
                    const tokens = result.AuthenticationResult;
                    localStorage.setItem('accessToken', tokens.AccessToken);
                    localStorage.setItem('idToken', tokens.IdToken);
                    localStorage.setItem('refreshToken', tokens.RefreshToken);
                    
                    // Update AWS credentials
                    AWS.config.credentials = new AWS.CognitoIdentityCredentials({
                        IdentityPoolId: CONFIG.identityPoolId,
                        Logins: {
                            [`cognito-idp.${CONFIG.region}.amazonaws.com/${CONFIG.userPoolId}`]: tokens.IdToken
                        }
                    });

                    await AWS.config.credentials.refresh();
                    
                    showStatus('Successfully signed in!', 'success');
                    showAppSection();
                    loadUserInfo();
                    loadBuckets();
                } else {
                    showStatus('Sign in failed. Please try again.', 'error');
                }
                
            } catch (error) {
                console.error('Sign in error:', error);
                showStatus(`Sign in failed: ${error.message}`, 'error');
            } finally {
                setLoading('signInBtn', false);
            }
        }

        function signOut() {
            localStorage.removeItem('accessToken');
            localStorage.removeItem('idToken');
            localStorage.removeItem('refreshToken');
            
            AWS.config.credentials = new AWS.CognitoIdentityCredentials({
                IdentityPoolId: CONFIG.identityPoolId
            });
            
            showAuthSection();
            showStatus('Signed out successfully', 'info');
        }

        function checkAuthState() {
            const idToken = localStorage.getItem('idToken');
            if (idToken) {
                // Verify token is still valid
                try {
                    const payload = JSON.parse(atob(idToken.split('.')[1]));
                    if (payload.exp * 1000 > Date.now()) {
                        // Token is still valid
                        AWS.config.credentials = new AWS.CognitoIdentityCredentials({
                            IdentityPoolId: CONFIG.identityPoolId,
                            Logins: {
                                [`cognito-idp.${CONFIG.region}.amazonaws.com/${CONFIG.userPoolId}`]: idToken
                            }
                        });
                        
                        showAppSection();
                        loadUserInfo();
                        loadBuckets();
                        return;
                    }
                } catch (e) {
                    console.error('Token validation error:', e);
                }
            }
            
            showAuthSection();
        }

        function showAuthSection() {
            document.getElementById('authSection').classList.add('active');
            document.getElementById('appSection').classList.remove('active');
        }

        function showAppSection() {
            document.getElementById('authSection').classList.remove('active');
            document.getElementById('appSection').classList.add('active');
        }

        function loadUserInfo() {
            const idToken = localStorage.getItem('idToken');
            if (idToken) {
                try {
                    const payload = JSON.parse(atob(idToken.split('.')[1]));
                    document.getElementById('userName').textContent = payload.name || payload.email || 'User';
                } catch (e) {
                    console.error('Error parsing token:', e);
                }
            }
        }

        // Bucket Management Functions
        async function createBucket() {
            const projectName = document.getElementById('projectName').value.trim().toLowerCase();
            
            if (!projectName) {
                showStatus('Please enter a project name', 'error');
                return;
            }

            if (!/^[a-z0-9-]+$/.test(projectName)) {
                showStatus('Project name must contain only lowercase letters, numbers, and hyphens', 'error');
                return;
            }

            if (projectName.length < 3 || projectName.length > 50) {
                showStatus('Project name must be between 3 and 50 characters', 'error');
                return;
            }

            setLoading('createBtn', true);

            try {
                const response = await fetch(`${CONFIG.apiEndpoint}/buckets`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': localStorage.getItem('idToken')
                    },
                    body: JSON.stringify({
                        project_name: projectName
                    })
                });

                const data = await response.json();

                if (response.ok) {
                    showStatus(`✅ Bucket created successfully: ${data.bucket_name}`, 'success');
                    document.getElementById('projectName').value = '';
                    loadBuckets();
                } else {
                    showStatus(`❌ ${data.error || 'Failed to create bucket'}`, 'error');
                }
            } catch (error) {
                console.error('Create bucket error:', error);
                showStatus('❌ Network error: Failed to create bucket', 'error');
            } finally {
                setLoading('createBtn', false);
            }
        }

        async function loadBuckets() {
            setLoading('refreshBtn', true);
            
            const bucketsList = document.getElementById('bucketsList');
            bucketsList.innerHTML = '<div class="loading">Loading buckets</div>';

            try {
                const response = await fetch(`${CONFIG.apiEndpoint}/buckets`, {
                    method: 'GET',
                    headers: {
                        'Authorization': localStorage.getItem('idToken')
                    }
                });

                const data = await response.json();

                if (response.ok) {
                    if (data.length === 0) {
                        bucketsList.innerHTML = '<p>No buckets found. Create your first bucket above! 🚀</p>';
                    } else {
                        bucketsList.innerHTML = data.map(bucket => `
                            <div class="bucket-item">
                                <h3>📦 ${bucket.display_name || bucket.project_name}</h3>
                                <div class="bucket-info">
                                    <div><strong>Bucket Name:</strong> <code>${bucket.bucket_name}</code></div>
                                    <div><strong>Status:</strong> <span style="color: ${bucket.status === 'active' ? 'green' : 'orange'}">${bucket.status}</span></div>
                                    <div><strong>Created:</strong> ${formatDate(bucket.created_at)}</div>
                                    <div><strong>Last Checked:</strong> ${formatDate(bucket.last_checked)}</div>
                                    ${bucket.healed_at ? `<div><strong>Last Healed:</strong> ${formatDate(bucket.healed_at)}</div>` : ''}
                                    ${bucket.heal_count ? `<div><strong>Heal Count:</strong> ${bucket.heal_count}</div>` : ''}
                                </div>
                            </div>
                        `).join('');
                    }
                } else {
                    bucketsList.innerHTML = '<p style="color: red;">❌ Failed to load buckets</p>';
                    showStatus(`❌ ${data.error || 'Failed to load buckets'}`, 'error');
                }
            } catch (error) {
                console.error('Load buckets error:', error);
                bucketsList.innerHTML = '<p style="color: red;">❌ Network error: Failed to load buckets</p>';
                showStatus('❌ Network error: Failed to load buckets', 'error');
            } finally {
                setLoading('refreshBtn', false);
            }
        }

        function formatDate(dateString) {
            try {
                return new Date(dateString).toLocaleString();
            } catch (e) {
                return dateString;
            }
        }

        // Handle Enter key for forms
        document.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                const activeSection = document.querySelector('.auth-section.active, .app-section.active');
                if (activeSection.id === 'authSection') {
                    if (document.getElementById('confirmationForm').style.display !== 'none') {
                        confirmSignUp();
                    } else if (document.getElementById('signInEmail').value) {
                        signIn();
                    } else if (document.getElementById('signUpEmail').value) {
                        signUp();
                    }
                } else if (activeSection.id === 'appSection') {
                    if (document.getElementById('projectName').value) {
                        createBucket();
                    }
                }
            }
        });
    </script>
</body>
</html>
```

## Step 2: Create User Management Script

Save this as `scripts/user_management.py`:

```python
#!/usr/bin/env python3
"""
User management script for S3 Bucket Management System
"""

import boto3
import json
import sys
from botocore.exceptions import ClientError

def load_config():
    """Load configuration from CloudFormation outputs"""
    try:
        with open('../web-interface/config.js', 'r') as f:
            content = f.read()
            # Extract values from JavaScript config
            import re
            
            user_pool_id = re.search(r"userPoolId: '([^']+)'", content).group(1)
            client_id = re.search(r"userPoolClientId: '([^']+)'", content).group(1)
            region = re.search(r"region: '([^']+)'", content).group(1)
            
            return {
                'user_pool_id': user_pool_id,
                'client_id': client_id,
                'region': region
            }
    except Exception as e:
        print(f"Error loading config: {e}")
        print("Please run deployment first to generate config.js")
        sys.exit(1)

def create_admin_user(config, email, password, name):
    """Create an admin user"""
    cognito = boto3.client('cognito-idp', region_name=config['region'])
    
    try:
        # Create user
        response = cognito.admin_create_user(
            UserPoolId=config['user_pool_id'],
            Username=email,
            UserAttributes=[
                {'Name': 'email', 'Value': email},
                {'Name': 'name', 'Value': name},
                {'Name': 'email_verified', 'Value': 'true'}
            ],
            TemporaryPassword=password,
            MessageAction='SUPPRESS'  # Don't send welcome email
        )
        
        # Set permanent password
        cognito.admin_set_user_password(
            UserPoolId=config['user_pool_id'],
            Username=email,
            Password=password,
            Permanent=True
        )
        
        print(f"✅ Admin user created successfully!")
        print(f"Email: {email}")
        print(f"Password: {password}")
        print(f"Name: {name}")
        
        return True
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'UsernameExistsException':
            print(f"❌ User {email} already exists")
        else:
            print(f"❌ Error creating user: {e.response['Error']['Message']}")
        return False

def list_users(config):
    """List all users in the user pool"""
    cognito = boto3.client('cognito-idp', region_name=config['region'])
    
    try:
        response = cognito.list_users(UserPoolId=config['user_pool_id'])
        
        print("Users in the system:")
        print("-" * 50)
        
        for user in response['Users']:
            username = user['Username']
            status = user['UserStatus']
            created = user['UserCreateDate'].strftime('%Y-%m-%d %H:%M:%S')
            
            # Get user attributes
            email = next((attr['Value'] for attr in user['Attributes'] if attr['Name'] == 'email'), 'N/A')
            name = next((attr['Value'] for attr in user['Attributes'] if attr['Name'] == 'name'), 'N/A')
            
            print(f"Email: {email}")
            print(f"Name: {name}")
            print(f"Status: {status}")
            print(f"Created: {created}")
            print("-" * 30)
            
    except ClientError as e:
        print(f"❌ Error listing users: {e.response['Error']['Message']}")

def delete_user(config, email):
    """Delete a user"""
    cognito = boto3.client('cognito-idp', region_name=config['region'])
    
    try:
        cognito.admin_delete_user(
            UserPoolId=config['user_pool_id'],
            Username=email
        )
        print(f"✅ User {email} deleted successfully")
        
    except ClientError as e:
        print(f"❌ Error deleting user: {e.response['Error']['Message']}")

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python user_management.py create <email> <password> <name>")
        print("  python user_management.py list")
        print("  python user_management.py delete <email>")
        sys.exit(1)
    
    config = load_config()
    command = sys.argv[1]
    
    if command == 'create':
        if len(sys.argv) != 5:
            print("Usage: python user_management.py create <email> <password> <name>")
            sys.exit(1)
        
        email = sys.argv[2]
        password = sys.argv[3]
        name = sys.argv[4]
        
        create_admin_user(config, email, password, name)
        
    elif command == 'list':
        list_users(config)
        
    elif command == 'delete':
        if len(sys.argv) != 3:
            print("Usage: python user_management.py delete <email>")
            sys.exit(1)
        
        email = sys.argv[2]
        delete_user(config, email)
        
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == '__main__':
    main()
```

## Phase 5: Testing and Validation (30 minutes)

### Step 1: Create Comprehensive Test Suite

Save this as `scripts/test.py`:

```python
#!/usr/bin/env python3
"""
Comprehensive test suite for S3 Bucket Management System
"""

import requests
import json
import time
import boto3
import sys
from botocore.exceptions import ClientError

class TestSuite:
    def __init__(self, config_file='../web-interface/config.js'):
        self.config = self.load_config(config_file)
        self.cognito = boto3.client('cognito-idp', region_name=self.config['region'])
        self.access_token = None
        self.id_token = None
        self.test_email = 'test-user@example.com'
        self.test_password = 'TestPassword123!'
        
    def load_config(self, config_file):
        """Load configuration from JavaScript config file"""
        try:
            with open(config_file, 'r') as f:
                content = f.read()
                import re
                
                api_endpoint = re.search(r"apiEndpoint: '([^']+)'", content).group(1)
                user_pool_id = re.search(r"userPoolId: '([^']+)'", content).group(1)
                client_id = re.search(r"userPoolClientId: '([^']+)'", content).group(1)
                region = re.search(r"region: '([^']+)'", content).group(1)
                
                return {
                    'api_endpoint': api_endpoint,
                    'user_pool_id': user_pool_id,
                    'client_id': client_id,
                    'region': region
                }
        except Exception as e:
            print(f"❌ Error loading config: {e}")
            print("Please run deployment first to generate config.js")
            sys.exit(1)
    
    def create_test_user(self):
        """Create a test user for testing"""
        try:
            # Create user
            self.cognito.admin_create_user(
                UserPoolId=self.config['user_pool_id'],
                Username=self.test_email,
                UserAttributes=[
                    {'Name': 'email', 'Value': self.test_email},
                    {'Name': 'name', 'Value': 'Test User'},
                    {'Name': 'email_verified', 'Value': 'true'}
                ],
                TemporaryPassword=self.test_password,
                MessageAction='SUPPRESS'
            )
            
            # Set permanent password
            self.cognito.admin_set_user_password(
                UserPoolId=self.config['user_pool_id'],
                Username=self.test_email,
                Password=self.test_password,
                Permanent=True
            )
            
            print("✅ Test user created")
            return True
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'UsernameExistsException':
                print("ℹ️  Test user already exists")
                return True
            else:
                print(f"❌ Error creating test user: {e.response['Error']['Message']}")
                return False
    
    def authenticate_test_user(self):
        """Authenticate the test user"""
        try:
            response = self.cognito.admin_initiate_auth(
                UserPoolId=self.config['user_pool_id'],
                ClientId=self.config['client_id'],
                AuthFlow='ADMIN_NO_SRP_AUTH',
                AuthParameters={
                    'USERNAME': self.test_email,
                    'PASSWORD': self.test_password
                }
            )
            
            if 'AuthenticationResult' in response:
                self.access_token = response['AuthenticationResult']['AccessToken']
                self.id_token = response['AuthenticationResult']['IdToken']
                print("✅ Test user authenticated")
                return True
            else:
                print("❌ Authentication failed")
                return False
                
        except ClientError as e:
            print(f"❌ Authentication error: {e.response['Error']['Message']}")
            return False
    
    def test_create_bucket(self):
        """Test bucket creation"""
        print("\n🧪 Testing bucket creation...")
        
        test_project = f"test-project-{int(time.time())}"
        
        try:
            response = requests.post(
                f"{self.config['api_endpoint']}/buckets",
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': self.id_token
                },
                json={'project_name': test_project}
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Bucket created: {data['bucket_name']}")
                return data['bucket_name']
            else:
                print(f"❌ Bucket creation failed: {response.status_code}")
                print(f"Response: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Network error: {e}")
            return None
    
    def test_list_buckets(self):
        """Test bucket listing"""
        print("\n🧪 Testing bucket listing...")
        
        try:
            response = requests.get(
                f"{self.config['api_endpoint']}/buckets",
                headers={'Authorization': self.id_token}
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Listed {len(data)} buckets")
                return data
            else:
                print(f"❌ Bucket listing failed: {response.status_code}")
                print(f"Response: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Network error: {e}")
            return None
    
    def test_bucket_healing(self, bucket_name):
        """Test bucket healing by deleting a bucket"""
        print("\n🧪 Testing bucket healing...")
        
        try:
            s3 = boto3.client('s3', region_name=self.config['region'])
            
            # Delete the bucket to trigger healing
            s3.delete_bucket(Bucket=bucket_name)
            print(f"🗑️  Deleted bucket {bucket_name} to test healing")
            
            # Wait for healing (monitoring runs every 5 minutes)
            print("⏳ Waiting for healing process (this may take up to 5 minutes)...")
            
            for i in range(10):  # Wait up to 10 minutes
                time.sleep(60)  # Wait 1 minute
                
                try:
                    s3.head_bucket(Bucket=bucket_name)
                    print(f"✅ Bucket {bucket_name} healed successfully!")
                    return True
                except s3.exceptions.NoSuchBucket:
                    print(f"⏳ Still waiting... ({i+1}/10 minutes)")
                    continue
            
            print("❌ Bucket healing test timed out")
            return False
            
        except Exception as e:
            print(f"❌ Healing test error: {e}")
            return False
    
    def test_authentication_failure(self):
        """Test API with invalid authentication"""
        print("\n🧪 Testing authentication failure...")
        
        try:
            response = requests.get(
                f"{self.config['api_endpoint']}/buckets",
                headers={'Authorization': 'invalid-token'}
            )
            
            if response.status_code == 401:
                print("✅ Authentication properly rejected")
                return True
            else:
                print(f"❌ Expected 401, got {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Network error: {e}")
            return False
    
    def test_invalid_project_name(self):
        """Test bucket creation with invalid project name"""
        print("\n🧪 Testing invalid project name...")
        
        invalid_names = [
            "Test-With-Capitals",  # Has capitals
            "a",  # Too short
            "a" * 51,  # Too long
            "test_with_underscores",  # Has underscores
            "test with spaces"  # Has spaces
        ]
        
        for invalid_name in invalid_names:
            try:
                response = requests.post(
                    f"{self.config['api_endpoint']}/buckets",
                    headers={
                        'Content-Type': 'application/json',
                        'Authorization': self.id_token
                    },
                    json={'project_name': invalid_name}
                )
                
                if response.status_code == 400:
                    print(f"✅ Properly rejected: '{invalid_name}'")
                else:
                    print(f"❌ Should have rejected: '{invalid_name}' (got {response.status_code})")
                    
            except Exception as e:
                print(f"❌ Network error testing '{invalid_name}': {e}")
        
        return True
    
    def cleanup_test_user(self):
        """Clean up test user"""
        try:
            self.cognito.admin_delete_user(
                UserPoolId=self.config['user_pool_id'],
                Username=self.test_email
            )
            print("🧹 Test user cleaned up")
            
        except ClientError as e:
            if e.response['Error']['Code'] != 'UserNotFoundException':
                print(f"Warning: Could not delete test user: {e.response['Error']['Message']}")
    
    def run_all_tests(self):
        """Run all tests"""
        print("🚀 Starting comprehensive test suite...")
        print("=" * 60)
        
        # Setup
        if not self.create_test_user():
            print("❌ Failed to create test user. Aborting tests.")
            return False
        
        if not self.authenticate_test_user():
            print("❌ Failed to authenticate test user. Aborting tests.")
            return False
        
        tests_passed = 0
        total_tests = 5
        
        # Test 1: Create bucket
        bucket_name = self.test_create_bucket()
        if bucket_name:
            tests_passed += 1
        
        # Test 2: List buckets
        if self.test_list_buckets():
            tests_passed += 1
        
        # Test 3: Authentication failure
        if self.test_authentication_failure():
            tests_passed += 1
        
        # Test 4: Invalid project names
        if self.test_invalid_project_name():
            tests_passed += 1
        
        # Test 5: Bucket healing (only if we have a bucket)
        if bucket_name and self.test_bucket_healing(bucket_name):
            tests_passed += 1
        elif not bucket_name:
            print("⏭️  Skipping healing test (no bucket created)")
        
        # Cleanup
        self.cleanup_test_user()
        
        # Results
        print("\n" + "=" * 60)
        print(f"🏁 Test Results: {tests_passed}/{total_tests} tests passed")
        
        if tests_passed == total_tests:
            print("🎉 All tests passed! System is working correctly.")
            return True
        else:
            print("⚠️  Some tests failed. Please check the logs above.")
            return False

def main():
    test_suite = TestSuite()
    success = test_suite.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
```

### Step 2: Create Monitoring Script

Save this as `scripts/monitor.py`:

```python
#!/usr/bin/env python3
"""
Monitoring and health check script
"""

import boto3
import json
import time
from datetime import datetime, timedelta
from botocore.exceptions import ClientError

class SystemMonitor:
    def __init__(self):
        self.cloudwatch = boto3.client('cloudwatch')
        self.dynamodb = boto3.resource('dynamodb')
        self.lambda_client = boto3.client('lambda')
        self.s3 = boto3.client('s3')
        
    def check_lambda_health(self, function_names):
        """Check Lambda function health"""
        print("🔍 Checking Lambda function health...")
        
        for func_name in function_names:
            try:
                # Get function configuration
                response = self.lambda_client.get_function(FunctionName=func_name)
                state = response['Configuration']['State']
                
                if state == 'Active':
                    print(f"✅ {func_name}: {state}")
                else:
                    print(f"⚠️  {func_name}: {state}")
                    
                # Check recent errors
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(hours=1)
                
                errors = self.cloudwatch.get_metric_statistics(
                    Namespace='AWS/Lambda',
                    MetricName='Errors',
                    Dimensions=[{'Name': 'FunctionName', 'Value': func_name}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=3600,
                    Statistics=['Sum']
                )
                
                error_count = sum([point['Sum'] for point in errors['Datapoints']])
                if error_count > 0:
                    print(f"⚠️  {func_name}: {error_count} errors in the last hour")
                    
            except ClientError as e:
                print(f"❌ Error checking {func_name}: {e.response['Error']['Message']}")
    
    def check_dynamodb_health(self, table_name):
        """Check DynamoDB table health"""
        print("\n🔍 Checking DynamoDB health...")
        
        try:
            table = self.dynamodb.Table(table_name)
            response = table.describe_table()
            
            status = response['Table']['TableStatus']
            item_count = response['Table']['ItemCount']
            
            print(f"✅ Table {table_name}: {status}")
            print(f"📊 Item count: {item_count}")
            
            # Check for throttling
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=1)
            
            throttles = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/DynamoDB',
                MetricName='ReadThrottleEvents',
                Dimensions=[{'Name': 'TableName', 'Value': table_name}],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,
                Statistics=['Sum']
            )
            
            throttle_count = sum([point['Sum'] for point in throttles['Datapoints']])
            if throttle_count > 0:
                print(f"⚠️  Read throttling detected: {throttle_count} events in the last hour")
            else:
                print("✅ No throttling detected")
                
        except ClientError as e:
            print(f"❌ Error checking DynamoDB: {e.response['Error']['Message']}")
    
    def check_bucket_integrity(self, table_name):
        """Check that all buckets in metadata actually exist"""
        print("\n🔍 Checking bucket integrity...")
        
        try:
            table = self.dynamodb.Table(table_name)
            
            # Scan all active buckets
            response = table.scan(
                FilterExpression='#status = :status',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={':status': 'active'}
            )
            
            total_buckets = len(response['Items'])
            missing_buckets = []
            
            for item in response['Items']:
                bucket_name = item['bucket_name']
                
                try:
                    self.s3.head_bucket(Bucket=bucket_name)
                except self.s3.exceptions.NoSuchBucket:
                    missing_buckets.append(bucket_name)
                except ClientError as e:
                    if e.response['Error']['Code'] == '404':
                        missing_buckets.append(bucket_name)
            
            print(f"📊 Total buckets: {total_buckets}")
            print(f"🗑️  Missing buckets: {len(missing_buckets)}")
            
            if missing_buckets:
                print("⚠️  Missing buckets (will be healed):")
                for bucket in missing_buckets:
                    print(f"   - {bucket}")
            else:
                print("✅ All buckets exist")
                
        except ClientError as e:
            print(f"❌ Error checking bucket integrity: {e.response['Error']['Message']}")
    
    def check_cost_usage(self):
        """Check AWS cost and usage"""
        print("\n💰 Checking cost usage...")
        
        try:
            ce = boto3.client('ce')
            
            # Get current month costs
            now = datetime.utcnow()
            start_of_month = now.replace(day=1).strftime('%Y-%m-%d')
            today = now.strftime('%Y-%m-%d')
            
            response = ce.get_cost_and_usage(
                TimePeriod={'Start': start_of_month, 'End': today},
                Granularity='MONTHLY',
                Metrics=['BlendedCost'],
                GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}]
            )
            
            total_cost = 0
            service_costs = {}
            
            for result in response['ResultsByTime']:
                for group in result['Groups']:
                    service = group['Keys'][0]
                    cost = float(group['Metrics']['BlendedCost']['Amount'])
                    if cost > 0:
                        service_costs[service] = cost
                        total_cost += cost
            
            print(f"📊 Total cost this month: ${total_cost:.2f}")
            
            if service_costs:
                print("Service breakdown:")
                for service, cost in sorted(service_costs.items(), key=lambda x: x[1], reverse=True):
                    print(f"   - {service}: ${cost:.2f}")
            
            if total_cost > 5.0:
                print("⚠️  WARNING: Monthly cost exceeds $5!")
            elif total_cost > 2.5:
                print("⚠️  Cost approaching $5 limit")
            else:
                print("✅ Cost within acceptable range")
                
        except ClientError as e:
            print(f"❌ Error checking costs: {e.response['Error']['Message']}")
    
    def run_health_check(self):
        """Run complete health check"""
        print("🏥 Starting system health check...")
        print("=" * 50)
        
        # Determine environment and resource names
        try:
            with open('../web-interface/config.js', 'r') as f:
                content = f.read()
                import re
                environment = re.search(r"environment: '([^']+)'", content).group(1)
        except:
            environment = 'dev'  # Default
        
        function_names = [
            f"{environment}-create-bucket",
            f"{environment}-list-buckets",
            f"{environment}-monitor-buckets"
        ]
        
        table_name = f"{environment}-bucket-metadata"
        
        # Run checks
        self.check_lambda_health(function_names)
        self.check_dynamodb_health(table_name)
        self.check_bucket_integrity(table_name)
        self.check_cost_usage()
        
        print("\n" + "=" * 50)
        print("🏁 Health check complete!")

if __name__ == '__main__':
    monitor = SystemMonitor()
    monitor.run_health_check()
```

## Phase 6: Production Deployment (15 minutes)

### Step 1: Make deployment script executable and run

```bash
# Make scripts executable
chmod +x scripts/deploy.sh

# Update parameters with your email
nano infrastructure/parameters.json

# Deploy the system
cd scripts
./deploy.sh
```

### Step 2: Create first admin user

```bash
# Create admin user
python user_management.py create admin@yourcompany.com SecurePassword123! "Admin User"
```

### Step 3: Run tests

```bash
# Run comprehensive tests
python test.py
```

### Step 4: Set up monitoring

```bash
# Run health check
python monitor.py

# Set up cron job for daily monitoring (optional)
echo "0 9 * * * cd /path/to/s3-bucket-manager/scripts && python monitor.py >> ../logs/monitor.log 2>&1" | crontab -
```

## API Documentation

### Authentication

All API endpoints require authentication via Cognito ID token in the Authorization header:

```
Authorization: eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Endpoints

#### POST /buckets
Create a new S3 bucket for a project.

**Request:**
```json
{
    "project_name": "my-web-app"
}
```

**Response:**
```json
{
    "project_name": "my-web-app",
    "bucket_name": "dev-my-web-app-a1b2c3d4",
    "status": "created"
}
```

#### GET /buckets
List all buckets for the authenticated user.

**Response:**
```json
[
    {
        "display_name": "my-web-app",
        "bucket_name": "dev-my-web-app-a1b2c3d4",
        "user_email": "user@example.com",
        "created_at": "2025-01-15T10:30:00.000Z",
        "status": "active",
        "last_checked": "2025-01-15T10:35:00.000Z",
        "healed_at": "2025-01-15T10:35:00.000Z",
        "heal_count": 1
    }
]
```

#### GET /buckets?project_name=my-web-app
Get details for a specific project.

## Free Tier Cost Breakdown

### Daily Limits (to stay within monthly free tier):
- **Lambda invocations**: 33,333/day (1M/month)
- **API Gateway calls**: 33,333/day (1M/month)
- **DynamoDB operations**: Unlimited (25GB storage)
- **S3 operations**: 667 GET, 67 PUT per day
- **SNS emails**: 33/day (1,000/month)

### Monitoring Strategy:
- EventBridge: Every 5 minutes = 8,640 invocations/month
- Lambda monitoring: 8,640 invocations/month
- Well within free tier limits

## Troubleshooting Guide

### Common Issues:

1. **"Access Denied" when creating buckets**
   - Check IAM permissions for Lambda role
   - Verify S3 service permissions

2. **"User not found" during authentication**
   - Confirm user exists in Cognito User Pool
   - Check if email is verified

3. **"Token expired" errors**
   - Implement token refresh in web interface
   - Check token expiration settings in Cognito

4. **Buckets not healing**
   - Check EventBridge rule is enabled
   - Verify Lambda function has S3 permissions
   - Check CloudWatch logs for errors

5. **High costs**
   - Run `python monitor.py` to check usage
   - Review CloudWatch metrics
   - Consider reducing monitoring frequency

### Logs Location:
- **Lambda logs**: CloudWatch Logs `/aws/lambda/[function-name]`
- **API Gateway logs**: CloudWatch Logs (if enabled)
- **EventBridge**: CloudWatch Events

## Security Best Practices

1. **Never commit credentials** to version control
2. **Use least privilege** IAM policies
3. **Enable MFA** for AWS root account
4. **Regularly rotate** access keys
5. **Monitor costs** daily
6. **Review CloudTra
