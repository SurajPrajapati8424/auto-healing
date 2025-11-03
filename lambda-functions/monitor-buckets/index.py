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
        print("=== Monitor Buckets Lambda Started ===")
        print(f"Environment: {environment}, Region: {region}")
        
        # Scan all buckets that need monitoring:
        # 1. Active buckets (to check if they still exist)
        # 2. Deleted buckets with should_heal=True (to restore them)
        # Note: We scan all items and filter in code for better control
        print("Scanning DynamoDB table...")
        response = table.scan()
        all_items = response.get('Items', [])
        print(f"Initial scan returned {len(all_items)} items")
        
        # Get paginated results
        while 'LastEvaluatedKey' in response:
            response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            all_items.extend(response.get('Items', []))
        
        # Filter buckets that need monitoring
        items_to_monitor = []
        for item in all_items:
            status = item.get('status', 'active')
            deleted_at = item.get('deleted_at')
            should_heal = item.get('should_heal', False)
            
            # Handle DynamoDB boolean types (could be bool or Decimal)
            if isinstance(should_heal, (str, int, float)):
                should_heal = bool(should_heal)
            elif should_heal is None:
                should_heal = False
            
            # Include if: active, or deleted with should_heal=True
            if status == 'active' or (status == 'deleted' and deleted_at and should_heal):
                items_to_monitor.append(item)
        
        print(f"Scanned DynamoDB: {len(all_items)} total buckets, {len(items_to_monitor)} buckets to monitor")
        
        if len(items_to_monitor) == 0:
            print("⚠️  No buckets found to monitor. This might be normal if no buckets exist or all deleted buckets have should_heal=False")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Monitoring completed - no buckets to process',
                    'processed_buckets': 0,
                    'healed_buckets': 0
                })
            }
        
        for item in items_to_monitor:
            bucket_name = item['bucket_name']
            project_name = item['project_name']
            user_email = item.get('user_email', 'unknown')
            display_name = item.get('display_name', project_name)
            
            processed_buckets += 1
            current_status = item.get('status', 'active')
            should_heal_flag = item.get('should_heal', False)
            deleted_at = item.get('deleted_at')
            
            # Handle DynamoDB boolean types
            if isinstance(should_heal_flag, (str, int, float)):
                should_heal_flag = bool(should_heal_flag)
            elif should_heal_flag is None:
                should_heal_flag = False
            
            print(f"Checking bucket {bucket_name} (status={current_status}, should_heal={should_heal_flag}, deleted_at={deleted_at})")
            
            try:
                # Check if bucket exists
                s3.head_bucket(Bucket=bucket_name)
                
                # Bucket exists
                if current_status == 'deleted' and should_heal_flag:
                    # Bucket exists but status is deleted - this shouldn't happen, but update status back to active
                    # Preserve deletion history for auditing
                    print(f"WARNING: Bucket {bucket_name} exists but status is 'deleted'. Restoring status to active.")
                    table.update_item(
                        Key={'project_name': project_name},
                        UpdateExpression='SET last_checked = :timestamp, #status = :active REMOVE should_heal',
                        ExpressionAttributeNames={'#status': 'status'},
                        ExpressionAttributeValues={
                            ':timestamp': datetime.utcnow().isoformat(),
                            ':active': 'active'
                        }
                    )
                else:
                    # Normal case: active bucket exists - update last_checked
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
                    should_heal_flag = item.get('should_heal', False)
                    deleted_at = item.get('deleted_at')
                    deleted_by = item.get('deleted_by')
                    current_status = item.get('status', 'active')
                    
                    if deleted_at:
                        # Bucket was explicitly deleted - check if should heal
                        if should_heal_flag and current_status == 'deleted':
                            print(f"Detected missing bucket {bucket_name} (status=deleted, should_heal=True), initiating healing...")
                            print(f"  Deleted at: {deleted_at}, Deleted by: {deleted_by}")
                            deleted_by_email = item.get('deleted_by_email', 'unknown')
                            print(f"  Deleted by email: {deleted_by_email}")
                            
                            # Pass deletion info to recreate_bucket function
                            deletion_info = {
                                'deleted_at': deleted_at,
                                'deleted_by': deleted_by,
                                'deleted_by_email': deleted_by_email
                            }
                            if recreate_bucket(bucket_name, project_name, user_email, display_name, deletion_info):
                                healed_buckets += 1
                                print(f"Successfully healed bucket {bucket_name}")
                            else:
                                print(f"Failed to heal bucket {bucket_name}")
                        else:
                            print(f"Bucket {bucket_name} was deleted but should_heal={should_heal_flag}, status={current_status} - skipping auto-heal")
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
                    print(f"Detected missing bucket {bucket_name} (exception-based detection), initiating healing...")
                    if recreate_bucket(bucket_name, project_name, user_email, display_name, None):
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
        import traceback
        error_details = traceback.format_exc()
        print(f"ERROR in monitoring: {str(e)}")
        print(f"Traceback: {error_details}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e), 'traceback': error_details})
        }

def recreate_bucket(bucket_name, project_name, user_email, display_name, deletion_info=None):
    """
    Recreate a deleted bucket
    
    Args:
        deletion_info: Dict with deletion metadata (deleted_at, deleted_by, deleted_by_email)
    """
    try:
        print(f"Attempting to recreate bucket {bucket_name}...")
        if deletion_info:
            print(f"  Preserving deletion history: {deletion_info}")
        
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
        
        # Update metadata - restore bucket to active status but preserve deletion history for auditing
        try:
            # We keep deletion metadata (deleted_at, deleted_by, deleted_by_email) for audit trail
            # Only remove should_heal since it's no longer needed
            # Note: deletion_info will be preserved in the item (not removed)
            update_expr = 'SET last_checked = :timestamp, healed_at = :timestamp, heal_count = if_not_exists(heal_count, :zero) + :one, #status = :active REMOVE should_heal'
            expr_values = {
                ':timestamp': datetime.utcnow().isoformat(),
                ':zero': 0,
                ':one': 1,
                ':active': 'active'
            }
            
            table.update_item(
                Key={'project_name': project_name},
                UpdateExpression=update_expr,
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues=expr_values
            )
            
            # Log deletion history for audit
            if deletion_info:
                print(f"DynamoDB updated for {bucket_name} - status restored to active")
                print(f"  Deletion history preserved: deleted_at={deletion_info.get('deleted_at')}, deleted_by={deletion_info.get('deleted_by_email')}")
            else:
                print(f"DynamoDB updated for {bucket_name} - status restored to active")
        except Exception as db_error:
            print(f"ERROR: Failed to update DynamoDB: {str(db_error)}")
            # Don't fail healing if DynamoDB update fails, bucket was recreated
        
        # Send healing notification with deletion history (non-blocking)
        try:
            # Include deletion history in notification if available
            deletion_info_text = ""
            if deletion_info:
                deleted_by_display = deletion_info.get('deleted_by_email') or deletion_info.get('deleted_by', 'unknown')
                deletion_info_text = f"\n\nDeletion History:\n  - Deleted at: {deletion_info.get('deleted_at', 'unknown')}\n  - Deleted by: {deleted_by_display}\n  - Original owner: {user_email}"
            
            sns.publish(
                TopicArn=topic_arn,
                Message=f"Bucket {bucket_name} for project '{display_name}' was automatically recreated.\n\nOriginal User: {user_email}\nHealed at: {datetime.utcnow().isoformat()}{deletion_info_text}\n\nThe bucket was deleted and has been restored with the same configuration.",
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

