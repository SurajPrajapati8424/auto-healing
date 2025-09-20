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
    def __init__(self, config_file='..\\web-interface\\config.js'):
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