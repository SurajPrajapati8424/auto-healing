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

def create_user(config, email, password, name, group=None):
    """Create a user (optionally add to a group)"""
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
        
        # Add to group if specified
        if group:
            cognito.admin_add_user_to_group(
                UserPoolId=config['user_pool_id'],
                Username=email,
                GroupName=group
            )
            print(f"✅ User created and added to '{group}' group!")
        else:
            print(f"✅ User created successfully!")
        
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

def add_user_to_group(config, email, group_name):
    """Add an existing user to a group"""
    cognito = boto3.client('cognito-idp', region_name=config['region'])
    
    try:
        cognito.admin_add_user_to_group(
            UserPoolId=config['user_pool_id'],
            Username=email,
            GroupName=group_name
        )
        print(f"✅ User {email} added to '{group_name}' group successfully!")
        return True
    except ClientError as e:
        print(f"❌ Error adding user to group: {e.response['Error']['Message']}")
        return False

def remove_user_from_group(config, email, group_name):
    """Remove a user from a group"""
    cognito = boto3.client('cognito-idp', region_name=config['region'])
    
    try:
        cognito.admin_remove_user_from_group(
            UserPoolId=config['user_pool_id'],
            Username=email,
            GroupName=group_name
        )
        print(f"✅ User {email} removed from '{group_name}' group successfully!")
        return True
    except ClientError as e:
        print(f"❌ Error removing user from group: {e.response['Error']['Message']}")
        return False

def list_user_groups(config, email):
    """List groups for a user"""
    cognito = boto3.client('cognito-idp', region_name=config['region'])
    
    try:
        response = cognito.admin_list_groups_for_user(
            UserPoolId=config['user_pool_id'],
            Username=email
        )
        groups = [g['GroupName'] for g in response.get('Groups', [])]
        if groups:
            print(f"User {email} is in groups: {', '.join(groups)}")
        else:
            print(f"User {email} is not in any groups (normal user)")
        return groups
    except ClientError as e:
        print(f"❌ Error listing user groups: {e.response['Error']['Message']}")
        return []

def list_users(config):
    """List all users in the user pool with their groups"""
    cognito = boto3.client('cognito-idp', region_name=config['region'])
    
    try:
        response = cognito.list_users(UserPoolId=config['user_pool_id'])
        
        print("Users in the system:")
        print("-" * 70)
        
        for user in response['Users']:
            username = user['Username']
            status = user['UserStatus']
            created = user['UserCreateDate'].strftime('%Y-%m-%d %H:%M:%S')
            
            # Get user attributes
            email = next((attr['Value'] for attr in user['Attributes'] if attr['Name'] == 'email'), 'N/A')
            name = next((attr['Value'] for attr in user['Attributes'] if attr['Name'] == 'name'), 'N/A')
            
            # Get user groups
            try:
                groups_response = cognito.admin_list_groups_for_user(
                    UserPoolId=config['user_pool_id'],
                    Username=username
                )
                groups = [g['GroupName'] for g in groups_response.get('Groups', [])]
                role = 'Normal User' if not groups else (', '.join(groups))
            except:
                role = 'Normal User'
            
            print(f"Email: {email}")
            print(f"Name: {name}")
            print(f"Role: {role}")
            print(f"Status: {status}")
            print(f"Created: {created}")
            print("-" * 70)
            
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
        print("  python user_management.py create <email> <password> <name> [group]")
        print("  python user_management.py list")
        print("  python user_management.py delete <email>")
        print("  python user_management.py add-group <email> <group>")
        print("  python user_management.py remove-group <email> <group>")
        print("  python user_management.py list-groups <email>")
        print("\nGroups: 'admins' (Super Admin), 'business-admins' (Business Admin)")
        sys.exit(1)
    
    config = load_config()
    command = sys.argv[1]
    
    if command == 'create':
        if len(sys.argv) < 5:
            print("Usage: python user_management.py create <email> <password> <name> [group]")
            print("Groups: 'admins' (Super Admin), 'business-admins' (Business Admin)")
            sys.exit(1)
        
        email = sys.argv[2]
        password = sys.argv[3]
        name = sys.argv[4]
        group = sys.argv[5] if len(sys.argv) > 5 else None
        
        if group and group not in ['admins', 'business-admins']:
            print(f"❌ Invalid group: {group}. Must be 'admins' or 'business-admins'")
            sys.exit(1)
        
        create_user(config, email, password, name, group)
        
    elif command == 'list':
        list_users(config)
        
    elif command == 'delete':
        if len(sys.argv) != 3:
            print("Usage: python user_management.py delete <email>")
            sys.exit(1)
        
        email = sys.argv[2]
        delete_user(config, email)
    
    elif command == 'add-group':
        if len(sys.argv) != 4:
            print("Usage: python user_management.py add-group <email> <group>")
            print("Groups: 'admins' (Super Admin), 'business-admins' (Business Admin)")
            sys.exit(1)
        
        email = sys.argv[2]
        group = sys.argv[3]
        
        if group not in ['admins', 'business-admins']:
            print(f"❌ Invalid group: {group}. Must be 'admins' or 'business-admins'")
            sys.exit(1)
        
        add_user_to_group(config, email, group)
    
    elif command == 'remove-group':
        if len(sys.argv) != 4:
            print("Usage: python user_management.py remove-group <email> <group>")
            sys.exit(1)
        
        email = sys.argv[2]
        group = sys.argv[3]
        remove_user_from_group(config, email, group)
    
    elif command == 'list-groups':
        if len(sys.argv) != 3:
            print("Usage: python user_management.py list-groups <email>")
            sys.exit(1)
        
        email = sys.argv[2]
        list_user_groups(config, email)
        
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == '__main__':
    main()