import json
import boto3
import os
from datetime import datetime
from botocore.exceptions import ClientError

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
cognito = boto3.client('cognito-idp')

table = dynamodb.Table(os.environ['TABLE_NAME'])
user_pool_id = os.environ['USER_POOL_ID']
region = os.environ.get('REGION', 'us-east-1')

def get_user_groups(user_email):
    """Get list of Cognito groups for a user"""
    try:
        response = cognito.admin_list_groups_for_user(
            UserPoolId=user_pool_id,
            Username=user_email
        )
        return [g['GroupName'] for g in response.get('Groups', [])]
    except Exception as e:
        print(f"Error getting user groups: {e}")
        return []

def is_super_admin(user_email):
    """Check if user is a Super Admin (admins group)"""
    try:
        # Get admin emails from environment or check Cognito group
        admin_emails_env = os.environ.get('ADMIN_EMAILS', '')
        if admin_emails_env:
            admin_emails = [email.strip() for email in admin_emails_env.split(',') if email.strip()]
            if user_email in admin_emails:
                return True
        
        groups = get_user_groups(user_email)
        return 'admins' in groups
    except Exception as e:
        print(f"Error checking super admin status: {e}")
        return False

def is_business_admin(user_email):
    """Check if user is a Business Admin (business-admins group)"""
    try:
        groups = get_user_groups(user_email)
        return 'business-admins' in groups
    except Exception as e:
        print(f"Error checking business admin status: {e}")
        return False

def is_admin(user_email):
    """Check if user is any type of admin (Super Admin or Business Admin)"""
    return is_super_admin(user_email) or is_business_admin(user_email)

def lambda_handler(event, context):
    try:
        # Extract user info from Cognito
        user_id = None
        user_email = None
        
        if 'requestContext' in event and 'authorizer' in event['requestContext']:
            claims = event['requestContext']['authorizer'].get('claims', {})
            user_id = claims.get('sub')
            user_email = claims.get('email')
        
        if not user_id:
            return {
                'statusCode': 401,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Unauthorized: User authentication required'})
            }
        
        # Get project name from query parameters
        query_params = event.get('queryStringParameters') or {}
        project_name = query_params.get('project_name')
        
        if not project_name:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'project_name query parameter is required'})
            }
        
        # Check user roles
        is_super_admin_user = is_super_admin(user_email) if user_email else False
        is_business_admin_user = is_business_admin(user_email) if user_email else False
        is_admin_user = is_super_admin_user or is_business_admin_user
        
        # Get bucket metadata
        # For admins and business admins, we need to allow deleting any bucket
        # First try with user's own bucket key, then if admin, try to find by project name across all users
        bucket_key = f"{user_id}#{project_name}"
        
        try:
            response = table.get_item(Key={'project_name': bucket_key})
            
            # If not found and user is admin/business admin, search by project name across all buckets
            if 'Item' not in response and is_admin_user:
                # Search by display_name (project name) across all buckets
                scan_response = table.scan(
                    FilterExpression='display_name = :display',
                    ExpressionAttributeValues={':display': project_name}
                )
                if scan_response.get('Items'):
                    # Take first match (or could handle multiple matches if needed)
                    response = {'Item': scan_response['Items'][0]}
                    bucket_key = scan_response['Items'][0]['project_name']
            
            if 'Item' not in response:
                return {
                    'statusCode': 404,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({'error': 'Bucket not found'})
                }
            
            bucket_item = response['Item']
            bucket_name = bucket_item['bucket_name']
            bucket_owner_id = bucket_item['user_id']
            bucket_owner_email = bucket_item.get('user_email', '')
            
        except Exception as db_error:
            print(f"Error fetching bucket: {db_error}")
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Failed to fetch bucket metadata'})
            }
        
        # Check if user is owner
        is_owner = (user_id == bucket_owner_id)
        
        # Authorization check: Non-admins can only delete their own buckets
        if not is_admin_user and not is_owner:
            return {
                'statusCode': 403,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Forbidden: You can only delete your own buckets'})
            }
        
        # Determine should_heal based on hierarchy:
        # 1. Normal User (owner): should_heal=False
        # 2. Normal User (other user): should_heal=True (but shouldn't happen due to auth check above)
        # 3. Business Admin: should_heal=True
        # 4. Super Admin: should_heal=False
        if is_owner and not is_admin_user:
            # Normal user deleting own bucket
            should_heal = False
        elif is_business_admin_user:
            # Business Admin deleting any bucket
            should_heal = True
        elif is_super_admin_user:
            # Super Admin deleting any bucket
            should_heal = False
        elif not is_owner and not is_admin_user:
            # Normal user deleting someone else's bucket (shouldn't reach here, but just in case)
            should_heal = True
        else:
            # Default fallback
            should_heal = False
        
        # Delete bucket from S3 (must be empty)
        try:
            # List and delete all objects (required before deleting bucket)
            try:
                paginator = s3.get_paginator('list_objects_v2')
                pages = paginator.paginate(Bucket=bucket_name)
                for page in pages:
                    if 'Contents' in page:
                        objects = [{'Key': obj['Key']} for obj in page['Contents']]
                        if objects:
                            s3.delete_objects(Bucket=bucket_name, Delete={'Objects': objects})
            except ClientError as list_error:
                error_code = list_error.response.get('Error', {}).get('Code', '')
                if error_code != 'NoSuchBucket':
                    print(f"Warning listing objects: {list_error}")
            
            # Delete the bucket
            s3.delete_bucket(Bucket=bucket_name)
            print(f"Bucket {bucket_name} deleted from S3")
        except ClientError as delete_error:
            error_code = delete_error.response.get('Error', {}).get('Code', '')
            if error_code == 'NoSuchBucket':
                print(f"Bucket {bucket_name} already deleted")
            else:
                return {
                    'statusCode': 500,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'error': 'Failed to delete bucket',
                        'details': delete_error.response.get('Error', {}).get('Message', str(delete_error))
                    })
                }
        
        # Update DynamoDB with deletion metadata
        try:
            update_expr = 'SET deleted_at = :timestamp, deleted_by = :deleter, deleted_by_email = :deleter_email, should_heal = :should_heal, #status = :deleted'
            expr_names = {'#status': 'status'}
            expr_values = {
                ':timestamp': datetime.utcnow().isoformat(),
                ':deleter': user_id,
                ':deleter_email': user_email or 'unknown',
                ':should_heal': should_heal,
                ':deleted': 'deleted'
            }
            
            table.update_item(
                Key={'project_name': bucket_key},
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_values,
                ExpressionAttributeNames=expr_names
            )
            print(f"Bucket {bucket_name} deletion recorded (should_heal={should_heal})")
        except Exception as db_error:
            print(f"Error updating deletion metadata: {db_error}")
            # Don't fail the request, bucket was deleted
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'Bucket deleted successfully',
                'bucket_name': bucket_name,
                'deleted_by': user_email,
                'should_heal': should_heal
            })
        }
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"ERROR in delete bucket lambda: {str(e)}")
        print(f"Traceback: {error_details}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Internal server error', 'details': str(e)})
        }

