import json
import boto3
import os
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
cognito = boto3.client('cognito-idp')

table = dynamodb.Table(os.environ['TABLE_NAME'])
user_pool_id = os.environ.get('USER_POOL_ID', '')

def get_user_groups(user_email):
    """Get list of Cognito groups for a user"""
    if not user_pool_id or not user_email:
        return []
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
    groups = get_user_groups(user_email)
    return 'admins' in groups

def is_business_admin(user_email):
    """Check if user is a Business Admin (business-admins group)"""
    groups = get_user_groups(user_email)
    return 'business-admins' in groups

def is_admin(user_email):
    """Check if user is any type of admin"""
    return is_super_admin(user_email) or is_business_admin(user_email)

def lambda_handler(event, context):
    try:
        # Extract user info from Cognito
        user_id = None
        user_email = None
        if 'requestContext' in event and 'authorizer' in event['requestContext']:
            claims = event['requestContext']['authorizer']['claims']
            user_id = claims.get('sub')
            user_email = claims.get('email')
        
        if not user_id:
            return {
                'statusCode': 401,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Unauthorized'})
            }
        
        # Check if user is admin or business admin
        is_super_admin_user = is_super_admin(user_email) if user_email else False
        is_business_admin_user = is_business_admin(user_email) if user_email else False
        is_admin_user = is_super_admin_user or is_business_admin_user
        
        # Get query parameters
        query_params = event.get('queryStringParameters', {}) or {}
        project_name = query_params.get('project_name')
        
        if project_name:
            # Get specific project
            if is_admin_user:
                # Admins can access any project - search across all buckets
                scan_response = table.scan(
                    FilterExpression='display_name = :display',
                    ExpressionAttributeValues={':display': project_name}
                )
                if scan_response.get('Items'):
                    item = scan_response['Items'][0]
                    # Remove internal user_id from response (or keep it for admin view)
                    user_id_in_item = item.pop('user_id', None)
                    # Add owner info for admin view
                    item['owner_user_id'] = user_id_in_item
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
                        'headers': {
                            'Content-Type': 'application/json',
                            'Access-Control-Allow-Origin': '*'
                        },
                        'body': json.dumps({'error': 'Project not found'})
                    }
            else:
                # Normal users can only access their own projects
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
                        'headers': {
                            'Content-Type': 'application/json',
                            'Access-Control-Allow-Origin': '*'
                        },
                        'body': json.dumps({'error': 'Project not found'})
                    }
        else:
            # List projects
            if is_admin_user:
                # Admins and Business Admins can see all buckets
                response = table.scan()
                items = response.get('Items', [])
                
                # For pagination support (if needed in future)
                while 'LastEvaluatedKey' in response:
                    response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
                    items.extend(response.get('Items', []))
                
                # Clean up items and add owner info
                for item in items:
                    # Keep user_id but rename for clarity
                    if 'user_id' in item:
                        item['owner_user_id'] = item.pop('user_id')
                    # Add role indicator
                    item['user_role'] = 'super_admin' if is_super_admin_user else 'business_admin'
            else:
                # Normal users can only see their own buckets
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
        import traceback
        print(traceback.format_exc())
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Internal server error', 'details': str(e)})
        }

