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
            with open('..\\web-interface\\config.js', 'r') as f:
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