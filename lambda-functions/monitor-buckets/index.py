import json
import boto3
import os
from datetime import datetime
from botocore.exceptions import ClientError

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')

table = dynamodb.Table(os.environ['TABLE_NAME'])
topic_arn = os.environ['SNS_TOPIC']
environment = os.environ['ENVIRONMENT']
region = os.environ.get('REGION', 'us-east-1')

def lambda_handler(event, context):
    processed_buckets = 0
    healed_buckets = 0
    
    try:
        # Scan all active buckets
        response = table.scan(
            FilterExpression='attribute_not_exists(deleted_at) OR #status = :active',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={':active': 'active'}
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
                
            except ClientError as e:
                # Extract error code from boto3 ClientError
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                error_message = str(e)
                
                # Check if bucket doesn't exist (404, NoSuchBucket, or NotFound)
                if (error_code in ('404', 'NoSuchBucket', 'NotFound') or 
                    '404' in error_message or 
                    'Not Found' in error_message or
                    'NoSuchBucket' in error_message):
                    
                    # Check if bucket should be healed based on deletion metadata
                    should_heal = item.get('should_heal', True)  # Default to True for backwards compatibility
                    deleted_at = item.get('deleted_at')
                    deleted_by = item.get('deleted_by')
                    
                    if deleted_at:
                        # Bucket was explicitly deleted - check if should heal
                        if should_heal:
                            print(f"Detected missing bucket {bucket_name} (deleted by non-owner/admin), initiating healing...")
                            if recreate_bucket(bucket_name, project_name, user_email, display_name):
                                healed_buckets += 1
                                print(f"Successfully healed bucket {bucket_name}")
                            else:
                                print(f"Failed to heal bucket {bucket_name}")
                        else:
                            print(f"Bucket {bucket_name} was deleted by owner/admin - skipping auto-heal")
                    else:
                        # No deletion metadata - treat as orphaned bucket (heal it)
                        print(f"Detected missing bucket {bucket_name} (orphaned), initiating healing...")
                        if recreate_bucket(bucket_name, project_name, user_email, display_name):
                            healed_buckets += 1
                            print(f"Successfully healed bucket {bucket_name}")
                        else:
                            print(f"Failed to heal bucket {bucket_name}")
                else:
                    print(f"Error checking bucket {bucket_name}: {error_code} - {error_message}")
            except Exception as e:
                # Handle other exceptions (including s3.exceptions.NoSuchBucket)
                error_message = str(e)
                if ('404' in error_message or 
                    'Not Found' in error_message or 
                    'NoSuchBucket' in error_message or
                    hasattr(e, '__class__') and 'NoSuchBucket' in str(e.__class__)):
                    print(f"Detected missing bucket {bucket_name}, initiating healing...")
                    if recreate_bucket(bucket_name, project_name, user_email, display_name):
                        healed_buckets += 1
                        print(f"Successfully healed bucket {bucket_name}")
                    else:
                        print(f"Failed to heal bucket {bucket_name}")
                else:
                    print(f" Unexpected error checking bucket {bucket_name}: {error_message}")
        
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
        print(f"Attempting to recreate bucket {bucket_name}...")
        
        # Recreate bucket (region-aware)
        try:
            if region == "us-east-1":
                s3.create_bucket(Bucket=bucket_name)
            else:
                s3.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': region}
                )
            print(f"Bucket {bucket_name} created")
        except s3.exceptions.BucketAlreadyExists:
            print(f"Bucket {bucket_name} already exists (may have been recreated by another process)")
            # Bucket exists, continue with configuration
        except s3.exceptions.BucketAlreadyOwnedByYou:
            print(f"Bucket {bucket_name} already owned by you")
            # Bucket exists, continue with configuration
        except Exception as create_error:
            error_msg = str(create_error)
            # Check if it's a name availability issue
            if "BucketAlreadyExists" in error_msg or "AlreadyOwnedByYou" in error_msg:
                print(f"Bucket {bucket_name} already exists, continuing with configuration")
            else:
                raise  # Re-raise if it's a different error
        
        # Configure security (non-blocking)
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
            print(f"WARNING: Failed to configure public access block: {str(config_error)}")
        
        # Enable encryption (non-blocking)
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
            print(f"WARNING: Failed to configure encryption: {str(encrypt_error)}")
        
        # Update metadata
        try:
            table.update_item(
                Key={'project_name': project_name},
                UpdateExpression='SET last_checked = :timestamp, healed_at = :timestamp, heal_count = if_not_exists(heal_count, :zero) + :one',
                ExpressionAttributeValues={
                    ':timestamp': datetime.utcnow().isoformat(),
                    ':zero': 0,
                    ':one': 1
                }
            )
            print(f"DynamoDB updated for {bucket_name}")
        except Exception as db_error:
            print(f"ERROR: Failed to update DynamoDB: {str(db_error)}")
            # Don't fail healing if DynamoDB update fails, bucket was recreated
        
        # Send healing notification (non-blocking)
        try:
            sns.publish(
                TopicArn=topic_arn,
                Message=f"Bucket {bucket_name} for project '{display_name}' was automatically recreated.\n\nUser: {user_email}\nTime: {datetime.utcnow().isoformat()}\n\nThe bucket was deleted and has been restored with the same configuration.",
                Subject=f"S3 Bucket Healed - {display_name}"
            )
            print(f"Notification sent for {bucket_name}")
        except Exception as sns_error:
            print(f"WARNING: Failed to send notification: {str(sns_error)}")
        
        print(f"Bucket {bucket_name} healed successfully")
        return True
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"ERROR recreating bucket {bucket_name}: {str(e)}")
        print(f"Traceback: {error_trace}")
        return False

