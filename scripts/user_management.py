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
        with open('web-interface/config.js', 'r') as f:
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