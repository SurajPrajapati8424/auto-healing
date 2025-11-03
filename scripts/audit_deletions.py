#!/usr/bin/env python3
"""
Audit script to view deletion history for buckets

This script queries DynamoDB to show:
- Which buckets were deleted
- When they were deleted
- Who deleted them
- Whether they were healed
"""

import boto3
import json
import sys
import re
from datetime import datetime

def load_config(config_file='web-interface/config.js'):
    """Load configuration from JavaScript config file"""
    try:
        with open(config_file, 'r') as f:
            content = f.read()
            
            table_name_match = re.search(r"environment: '([^']+)'", content)
            region_match = re.search(r"region: '([^']+)'", content)
            
            if not table_name_match or not region_match:
                raise ValueError("Could not parse config file")
            
            environment = table_name_match.group(1)
            region = region_match.group(1)
            table_name = f"{environment}-bucket-metadata"
            
            return {
                'table_name': table_name,
                'region': region,
                'environment': environment
            }
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        print("Please run deployment first to generate config.js")
        sys.exit(1)

def query_deletion_history(table, bucket_name=None, project_name=None):
    """Query DynamoDB for deletion history"""
    dynamodb = boto3.resource('dynamodb', region_name=table.region)
    table_resource = dynamodb.Table(table.table_name)
    
    try:
        if bucket_name:
            # Query by bucket name using GSI
            response = table_resource.query(
                IndexName='bucket-name-index',
                KeyConditionExpression='bucket_name = :bucket',
                ExpressionAttributeValues={':bucket': bucket_name}
            )
            items = response.get('Items', [])
        elif project_name:
            # Query by project name (needs user_id prefix)
            # If project_name doesn't have user_id, we need to scan
            response = table_resource.get_item(Key={'project_name': project_name})
            if 'Item' in response:
                items = [response['Item']]
            else:
                items = []
        else:
            # Scan all items with deletion metadata
            response = table_resource.scan(
                FilterExpression='attribute_exists(deleted_at) OR attribute_exists(healed_at)'
            )
            items = response.get('Items', [])
            
            # Get paginated results
            while 'LastEvaluatedKey' in response:
                response = table_resource.scan(
                    FilterExpression='attribute_exists(deleted_at) OR attribute_exists(healed_at)',
                    ExclusiveStartKey=response['LastEvaluatedKey']
                )
                items.extend(response.get('Items', []))
        
        return items
        
    except Exception as e:
        print(f"❌ Error querying DynamoDB: {e}")
        return []

def format_deletion_info(item):
    """Format deletion information for display"""
    bucket_name = item.get('bucket_name', 'unknown')
    project_name = item.get('project_name', 'unknown')
    display_name = item.get('display_name', 'unknown')
    status = item.get('status', 'unknown')
    
    deleted_at = item.get('deleted_at')
    deleted_by = item.get('deleted_by', 'unknown')
    deleted_by_email = item.get('deleted_by_email', 'unknown')
    should_heal = item.get('should_heal', False)
    
    healed_at = item.get('healed_at')
    heal_count = item.get('heal_count', 0)
    
    info = {
        'bucket_name': bucket_name,
        'project_name': display_name,
        'status': status,
        'deleted_at': deleted_at,
        'deleted_by_user_id': deleted_by,
        'deleted_by_email': deleted_by_email,
        'should_heal': should_heal,
        'healed_at': healed_at,
        'heal_count': int(heal_count) if heal_count else 0
    }
    
    return info

def print_deletion_history(items):
    """Print formatted deletion history"""
    if not items:
        print("No deletion history found.")
        return
    
    print(f"\n{'='*80}")
    print(f"DELETION HISTORY AUDIT ({len(items)} bucket(s) found)")
    print(f"{'='*80}\n")
    
    for item in items:
        info = format_deletion_info(item)
        
        print(f"Bucket: {info['bucket_name']}")
        print(f"Project: {info['project_name']}")
        print(f"Status: {info['status']}")
        print(f"Heal Count: {info['heal_count']}")
        print("-" * 80)
        
        if info['deleted_at']:
            print(f"  ❌ DELETED")
            print(f"     Deleted At: {info['deleted_at']}")
            print(f"     Deleted By (User ID): {info['deleted_by_user_id']}")
            print(f"     Deleted By (Email): {info['deleted_by_email']}")
            print(f"     Auto-Heal Enabled: {info['should_heal']}")
            
            if info['healed_at']:
                print(f"  ✅ HEALED")
                print(f"     Healed At: {info['healed_at']}")
                print(f"     Times Healed: {info['heal_count']}")
            elif info['should_heal']:
                print(f"  ⏳ PENDING HEALING (should_heal=True but not yet healed)")
            else:
                print(f"  🚫 NO AUTO-HEAL (should_heal=False - deleted by owner or super admin)")
        elif info['healed_at']:
            # Healed but no deletion metadata (orphaned bucket that was healed)
            print(f"  ✅ HEALED (orphaned bucket)")
            print(f"     Healed At: {info['healed_at']}")
            print(f"     Times Healed: {info['heal_count']}")
            print(f"     ⚠️  No deletion metadata - bucket was likely deleted outside the system")
        else:
            print(f"  ℹ️  Active bucket (no deletion history)")
        
        print()

def query_cloudwatch_logs(region, function_name, bucket_name=None, limit=50):
    """Query CloudWatch Logs for delete operations"""
    print(f"\n{'='*80}")
    print(f"CLOUDWATCH LOGS AUDIT (Delete Bucket Lambda)")
    print(f"{'='*80}\n")
    
    try:
        logs = boto3.client('logs', region_name=region)
        log_group = f'/aws/lambda/{function_name}'
        
        # Search for deletion events
        filter_pattern = 'deleted from S3' if not bucket_name else f'deleted from S3.*{bucket_name}'
        
        print(f"Querying logs from: {log_group}")
        print(f"Filter pattern: {filter_pattern}\n")
        
        response = logs.filter_log_events(
            logGroupName=log_group,
            filterPattern=filter_pattern,
            limit=limit
        )
        
        events = response.get('events', [])
        
        if not events:
            print("No deletion events found in CloudWatch Logs.")
            print("Note: Buckets deleted outside the API (e.g., via AWS Console or test scripts) won't appear here.")
            return
        
        print(f"Found {len(events)} deletion event(s):\n")
        
        for event in events:
            message = event.get('message', '')
            timestamp = datetime.fromtimestamp(event['timestamp'] / 1000)
            
            # Extract bucket name and deletion info from log message
            print(f"Timestamp: {timestamp}")
            print(f"Message: {message.strip()}")
            print("-" * 80)
        
    except Exception as e:
        print(f"⚠️  Could not query CloudWatch Logs: {e}")
        print("Note: This requires appropriate IAM permissions.")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Audit bucket deletion history')
    parser.add_argument('--bucket', '-b', help='Filter by bucket name')
    parser.add_argument('--project', '-p', help='Filter by project name (display_name)')
    parser.add_argument('--include-logs', '-l', action='store_true', 
                       help='Also query CloudWatch Logs for deletion events')
    parser.add_argument('--config', '-c', default='web-interface/config.js',
                       help='Path to config.js file')
    
    args = parser.parse_args()
    
    config = load_config(args.config)
    
    dynamodb = boto3.client('dynamodb', region_name=config['region'])
    table_name = config['table_name']
    
    # Query DynamoDB
    items = query_deletion_history(
        type('Table', (), {'region': config['region'], 'table_name': table_name})(),
        bucket_name=args.bucket,
        project_name=args.project
    )
    
    print_deletion_history(items)
    
    # Optionally query CloudWatch Logs
    if args.include_logs:
        function_name = f"{config['environment']}-delete-bucket"
        query_cloudwatch_logs(config['region'], function_name, args.bucket)

if __name__ == '__main__':
    main()

