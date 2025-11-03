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
region = os.environ.get('REGION', 'us-east-1')

def lambda_handler(event, context):
    try:
        # Extract user info from Cognito
        user_id = None
        user_email = None
        
        if 'requestContext' in event and 'authorizer' in event['requestContext']:
            claims = event['requestContext']['authorizer'].get('claims', {})
            user_id = claims.get('sub')
            user_email = claims.get('email')
        
        # Validate authentication
        if not user_id:
            print("ERROR: user_id is None - authorization may have failed")
            print(f"Event structure: {json.dumps(event.get('requestContext', {}))}")
            return {
                'statusCode': 401,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Unauthorized: User authentication required'})
            }
        
        body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        
        if 'project_name' not in body:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'project_name is required'})
            }
        
        # Get bucket configuration (defaults to recommended values)
        versioning = body.get('versioning', 'Enabled')
        lifecycle_policy = body.get('lifecycle_policy', 'None')
        custom_lifecycle_config = body.get('custom_lifecycle_config')
        
        # Validate versioning value
        if versioning not in ['Enabled', 'Disabled']:
            versioning = 'Enabled'
        
        # Validate lifecycle_policy value
        if lifecycle_policy not in ['None', 'Auto-Archive', 'Auto-Delete', 'Custom']:
            lifecycle_policy = 'None'
        
        # If Custom policy is selected, ensure custom config is provided
        if lifecycle_policy == 'Custom' and not custom_lifecycle_config:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Custom lifecycle policy requires custom_lifecycle_config field'})
            }
        
        project_name_raw = body['project_name'].strip()
        
        # Validate project name BEFORE converting to lowercase
        # Check for invalid characters (uppercase, underscores, spaces, etc.)
        if not re.match(r'^[a-z0-9-]+$', project_name_raw.lower()):
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Project name must contain only lowercase letters, numbers, and hyphens'})
            }
        
        # Reject if original contains uppercase (even if lowercase version would be valid)
        if project_name_raw != project_name_raw.lower():
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Project name must contain only lowercase letters, numbers, and hyphens (no uppercase letters allowed)'})
            }
        
        # Now convert to lowercase for storage
        project_name = project_name_raw.lower()
        
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
            print(f"DynamoDB get_item warning: {e}")
        
        # Create S3 bucket (region-aware)
        bucket_created = False
        try:
            if region == "us-east-1":
                s3.create_bucket(Bucket=bucket_name)
            else:
                s3.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': region}
                )
            bucket_created = True
            print(f"Bucket {bucket_name} created successfully")
        except Exception as create_error:
            print(f"ERROR: Failed to create bucket {bucket_name}: {str(create_error)}")
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Failed to create bucket', 'details': str(create_error)})
            }
        
        # Configure bucket security (non-blocking - log errors but continue)
        config_errors = []
        try:
            s3.put_public_access_block(
                Bucket=bucket_name,
                PublicAccessBlockConfiguration={
                    'BlockPublicAcls': True,
                    'IgnorePublicAcls': True,
                    'BlockPublicPolicy': True,
                    'RestrictPublicBuckets': True
                }
            )
            print(f"Public access block configured for {bucket_name}")
        except Exception as config_error:
            error_msg = f"Failed to configure public access block: {str(config_error)}"
            print(f"WARNING: {error_msg}")
            config_errors.append(error_msg)
        
        # Enable encryption (non-blocking - log errors but continue)
        try:
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
            print(f"Encryption configured for {bucket_name}")
        except Exception as encrypt_error:
            error_msg = f"Failed to configure encryption: {str(encrypt_error)}"
            print(f"WARNING: {encrypt_error}")
            config_errors.append(error_msg)
        
        # Enable versioning (non-blocking - log errors but continue)
        if versioning == 'Enabled':
            try:
                s3.put_bucket_versioning(
                    Bucket=bucket_name,
                    VersioningConfiguration={
                        'Status': 'Enabled'
                    }
                )
                print(f"Versioning enabled for {bucket_name}")
            except Exception as version_error:
                error_msg = f"Failed to enable versioning: {str(version_error)}"
                print(f"WARNING: {error_msg}")
                config_errors.append(error_msg)
        
        # Apply lifecycle policy (non-blocking - log errors but continue)
        if lifecycle_policy != 'None':
            try:
                lifecycle_config = None
                
                if lifecycle_policy == 'Custom':
                    # Use the provided custom configuration
                    lifecycle_config = custom_lifecycle_config
                    if not isinstance(lifecycle_config, dict) or 'Rules' not in lifecycle_config:
                        raise ValueError("Custom lifecycle config must be a dict with 'Rules' key")
                    
                    # Normalize 'Id' to 'ID' in all rules (AWS requires uppercase)
                    if isinstance(lifecycle_config.get('Rules'), list):
                        for rule in lifecycle_config['Rules']:
                            if 'Id' in rule and 'ID' not in rule:
                                rule['ID'] = rule.pop('Id')
                    
                    print(f"Custom lifecycle policy configured for {bucket_name}")
                    
                elif lifecycle_policy == 'Auto-Archive':
                    # Transition objects to Glacier after 30 days
                    lifecycle_config = {'Rules': []}
                    lifecycle_config['Rules'].append({
                        'ID': 'AutoArchiveRule',
                        'Status': 'Enabled',
                        'Filter': {},
                        'Transitions': [{
                            'Days': 30,
                            'StorageClass': 'GLACIER'
                        }]
                    })
                    print(f"Auto-Archive lifecycle policy configured for {bucket_name} (transition to Glacier after 30 days)")
                
                elif lifecycle_policy == 'Auto-Delete':
                    # Delete noncurrent versions after 90 days
                    lifecycle_config = {'Rules': []}
                    lifecycle_config['Rules'].append({
                        'ID': 'AutoDeleteVersionsRule',
                        'Status': 'Enabled',
                        'Filter': {},
                        'NoncurrentVersionExpiration': {
                            'NoncurrentDays': 90
                        }
                    })
                    print(f"Auto-Delete lifecycle policy configured for {bucket_name} (delete noncurrent versions after 90 days)")
                
                if lifecycle_config and lifecycle_config.get('Rules'):
                    s3.put_bucket_lifecycle_configuration(
                        Bucket=bucket_name,
                        LifecycleConfiguration=lifecycle_config
                    )
            except Exception as lifecycle_error:
                error_msg = f"Failed to configure lifecycle policy: {str(lifecycle_error)}"
                print(f"WARNING: {error_msg}")
                config_errors.append(error_msg)
        
        # Store metadata in DynamoDB (CRITICAL - must succeed)
        try:
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
                    'environment': environment,
                    'versioning': versioning,
                    'lifecycle_policy': lifecycle_policy
                }
            )
            # Store custom lifecycle config if provided
            if lifecycle_policy == 'Custom' and custom_lifecycle_config:
                table.update_item(
                    Key={'project_name': f"{user_id}#{project_name}"},
                    UpdateExpression='SET custom_lifecycle_config = :config',
                    ExpressionAttributeValues={
                        ':config': custom_lifecycle_config
                    }
                )
            print(f"Successfully stored metadata for bucket {bucket_name} with user_id {user_id}")
            print(f"  Versioning: {versioning}, Lifecycle Policy: {lifecycle_policy}")
        except Exception as db_error:
            # If DynamoDB write fails, this is critical - bucket exists but won't be tracked
            print(f"ERROR: Failed to write to DynamoDB: {str(db_error)}")
            print(f"WARNING: Bucket {bucket_name} exists but metadata was not stored!")
            
            # Try to delete the bucket (may fail if bucket is not empty or has configurations)
            try:
                # First, try to remove any bucket configurations that might prevent deletion
                try:
                    s3.delete_bucket_encryption(Bucket=bucket_name)
                except:
                    pass
                try:
                    s3.delete_public_access_block(Bucket=bucket_name)
                except:
                    pass
                
                s3.delete_bucket(Bucket=bucket_name)
                print(f"Cleaned up bucket {bucket_name} due to DynamoDB failure")
            except Exception as cleanup_error:
                print(f"WARNING: Could not cleanup bucket {bucket_name}: {str(cleanup_error)}")
                print(f"Bucket exists in AWS but not tracked in DynamoDB. Manual cleanup may be required.")
            
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Failed to store bucket metadata', 
                    'details': str(db_error),
                    'note': 'Bucket may have been created but is not tracked'
                })
            }
        
        # Send notification (non-blocking)
        try:
            sns.publish(
                TopicArn=topic_arn,
                Message=f"Bucket {bucket_name} created for project {project_name} by user {user_email}",
                Subject="S3 Bucket Created"
            )
        except Exception as sns_error:
            print(f"WARNING: Failed to send SNS notification: {str(sns_error)}")
            # Don't fail the request if notification fails
        
        # Return useful response for API clients
        response_data = {
                'project_name': project_name,
                'bucket_name': bucket_name,
                'status': 'created',
                'region': region,
                'user': user_email
            }
        
        # Include any configuration warnings if present
        if config_errors:
            response_data['warnings'] = config_errors
            print(f"Bucket created with configuration warnings: {config_errors}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_data)
        }
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"ERROR in create bucket lambda: {str(e)}")
        print(f"Traceback: {error_details}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Internal server error', 'details': str(e)})
        }

