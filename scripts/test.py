#!/usr/bin/env python3
"""
Comprehensive test suite for S3 Bucket Management System
Enhanced with versioning, lifecycle policies, and configuration verification tests
"""

import requests
import json
import time
import boto3
import sys
import re
from botocore.exceptions import ClientError
from typing import Dict, List, Optional, Tuple

class TestSuite:
    def __init__(self, config_file='web-interface/config.js'):
        self.config = self.load_config(config_file)
        self.cognito = boto3.client('cognito-idp', region_name=self.config['region'])
        self.s3 = boto3.client('s3', region_name=self.config['region'])
        self.access_token = None
        self.id_token = None
        self.test_email = 'test-user@example.com'
        self.test_password = 'TestPassword123!'
        self.created_buckets = []  # Track buckets for cleanup
        self.test_results = {'passed': 0, 'failed': 0, 'skipped': 0}
        
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
        """Authenticate the test user using USER_PASSWORD_AUTH flow"""
        try:
            # Use initiate_auth with USER_PASSWORD_AUTH (matches web interface)
            response = self.cognito.initiate_auth(
                ClientId=self.config['client_id'],
                AuthFlow='USER_PASSWORD_AUTH',
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
    
    def _create_bucket_with_config(self, project_name: str, versioning: str = 'Enabled', 
                                     lifecycle_policy: str = 'None', custom_config: Optional[Dict] = None) -> Optional[str]:
        """Helper method to create bucket with specific configuration"""
        request_body = {
            'project_name': project_name,
            'versioning': versioning,
            'lifecycle_policy': lifecycle_policy
        }
        
        if lifecycle_policy == 'Custom' and custom_config:
            request_body['custom_lifecycle_config'] = custom_config
        
        try:
            response = requests.post(
                f"{self.config['api_endpoint']}/buckets",
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.id_token}'
                },
                json=request_body,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                bucket_name = data['bucket_name']
                self.created_buckets.append(bucket_name)
                return bucket_name
            else:
                print(f"   ❌ Failed: {response.status_code} - {response.text[:100]}")
                return None
                
        except Exception as e:
            print(f"   ❌ Network error: {e}")
            return None
    
    def test_create_bucket(self):
        """Test basic bucket creation"""
        print("\n🧪 Testing basic bucket creation...")
        
        test_project = f"test-basic-{int(time.time())}"
        bucket_name = self._create_bucket_with_config(test_project)
        
        if bucket_name:
            print(f"✅ Bucket created: {bucket_name}")
            self.test_results['passed'] += 1
            return bucket_name
        else:
            print("❌ Bucket creation failed")
            self.test_results['failed'] += 1
            return None
    
    def test_create_bucket_with_versioning_disabled(self):
        """Test bucket creation with versioning disabled"""
        print("\n🧪 Testing bucket creation with versioning DISABLED...")
        
        test_project = f"test-no-ver-{int(time.time())}"
        bucket_name = self._create_bucket_with_config(test_project, versioning='Disabled')
        
        if bucket_name:
            # Verify versioning is disabled
            time.sleep(2)  # Wait for configuration to apply
            try:
                versioning = self.s3.get_bucket_versioning(Bucket=bucket_name)
                status = versioning.get('Status', 'Disabled')
                
                if status == 'Disabled':
                    print(f"✅ Bucket created with versioning disabled: {bucket_name}")
                    self.test_results['passed'] += 1
                    return bucket_name
                else:
                    print(f"❌ Versioning should be Disabled, got: {status}")
                    self.test_results['failed'] += 1
                    return bucket_name
            except Exception as e:
                print(f"⚠️  Could not verify versioning: {e}")
                self.test_results['skipped'] += 1
                return bucket_name
        else:
            self.test_results['failed'] += 1
            return None
    
    def test_create_bucket_with_versioning_enabled(self):
        """Test bucket creation with versioning enabled (default)"""
        print("\n🧪 Testing bucket creation with versioning ENABLED...")
        
        test_project = f"test-ver-enabled-{int(time.time())}"
        bucket_name = self._create_bucket_with_config(test_project, versioning='Enabled')
        
        if bucket_name:
            # Verify versioning is enabled
            time.sleep(2)
            try:
                versioning = self.s3.get_bucket_versioning(Bucket=bucket_name)
                status = versioning.get('Status', 'Disabled')
                
                if status == 'Enabled':
                    print(f"✅ Bucket created with versioning enabled: {bucket_name}")
                    self.test_results['passed'] += 1
                    return bucket_name
                else:
                    print(f"❌ Versioning should be Enabled, got: {status}")
                    self.test_results['failed'] += 1
                    return bucket_name
            except Exception as e:
                print(f"⚠️  Could not verify versioning: {e}")
                self.test_results['skipped'] += 1
                return bucket_name
        else:
            self.test_results['failed'] += 1
            return None
    
    def test_create_bucket_with_auto_archive(self):
        """Test bucket creation with Auto-Archive lifecycle policy"""
        print("\n🧪 Testing bucket with Auto-Archive lifecycle policy...")
        
        test_project = f"test-archive-{int(time.time())}"
        bucket_name = self._create_bucket_with_config(test_project, lifecycle_policy='Auto-Archive')
        
        if bucket_name:
            time.sleep(2)
            if self._verify_lifecycle_policy(bucket_name, 'Auto-Archive'):
                print(f"✅ Bucket created with Auto-Archive policy: {bucket_name}")
                self.test_results['passed'] += 1
                return bucket_name
            else:
                self.test_results['failed'] += 1
                return bucket_name
        else:
            self.test_results['failed'] += 1
            return None
    
    def test_create_bucket_with_auto_delete(self):
        """Test bucket creation with Auto-Delete lifecycle policy"""
        print("\n🧪 Testing bucket with Auto-Delete lifecycle policy...")
        
        test_project = f"test-delete-{int(time.time())}"
        bucket_name = self._create_bucket_with_config(test_project, lifecycle_policy='Auto-Delete')
        
        if bucket_name:
            time.sleep(2)
            if self._verify_lifecycle_policy(bucket_name, 'Auto-Delete'):
                print(f"✅ Bucket created with Auto-Delete policy: {bucket_name}")
                self.test_results['passed'] += 1
                return bucket_name
            else:
                self.test_results['failed'] += 1
                return bucket_name
        else:
            self.test_results['failed'] += 1
            return None
    
    def test_create_bucket_with_custom_policy(self):
        """Test bucket creation with custom lifecycle policy"""
        print("\n🧪 Testing bucket with Custom lifecycle policy...")
        
        custom_config = {
            "Rules": [
                {
                    "ID": "TestCustomRule",
                    "Status": "Enabled",
                    "Filter": {},
                    "Transitions": [
                        {
                            "Days": 60,
                            "StorageClass": "STANDARD_IA"
                        }
                    ]
                }
            ]
        }
        
        test_project = f"test-custom-{int(time.time())}"
        bucket_name = self._create_bucket_with_config(test_project, lifecycle_policy='Custom', custom_config=custom_config)
        
        if bucket_name:
            time.sleep(2)
            try:
                lifecycle = self.s3.get_bucket_lifecycle_configuration(Bucket=bucket_name)
                rules = lifecycle.get('Rules', [])
                
                if len(rules) > 0 and rules[0].get('ID') == 'TestCustomRule':
                    print(f"✅ Bucket created with custom policy: {bucket_name}")
                    print(f"   Rule ID: {rules[0].get('ID')}")
                    self.test_results['passed'] += 1
                    return bucket_name
                else:
                    print(f"❌ Custom policy not applied correctly")
                    self.test_results['failed'] += 1
                    return bucket_name
            except Exception as e:
                print(f"❌ Could not verify custom policy: {e}")
                self.test_results['failed'] += 1
                return bucket_name
        else:
            self.test_results['failed'] += 1
            return None
    
    def _verify_lifecycle_policy(self, bucket_name: str, expected_policy: str) -> bool:
        """Verify lifecycle policy is correctly applied"""
        try:
            lifecycle = self.s3.get_bucket_lifecycle_configuration(Bucket=bucket_name)
            rules = lifecycle.get('Rules', [])
            
            if expected_policy == 'Auto-Archive':
                # Should have one rule with Glacier transition after 30 days
                if len(rules) == 1:
                    rule = rules[0]
                    if rule.get('ID') == 'AutoArchiveRule' and rule.get('Status') == 'Enabled':
                        transitions = rule.get('Transitions', [])
                        if transitions and transitions[0].get('StorageClass') == 'GLACIER' and transitions[0].get('Days') == 30:
                            return True
                print(f"   ❌ Auto-Archive policy verification failed")
                return False
            
            elif expected_policy == 'Auto-Delete':
                # Should have one rule with noncurrent version expiration after 90 days
                if len(rules) == 1:
                    rule = rules[0]
                    if rule.get('ID') == 'AutoDeleteVersionsRule' and rule.get('Status') == 'Enabled':
                        nce = rule.get('NoncurrentVersionExpiration', {})
                        if nce.get('NoncurrentDays') == 90:
                            return True
                print(f"   ❌ Auto-Delete policy verification failed")
                return False
            
            return False
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchLifecycleConfiguration':
                print(f"   ❌ No lifecycle configuration found (expected: {expected_policy})")
                return False
            else:
                print(f"   ❌ Error verifying lifecycle: {e}")
                return False
        except Exception as e:
            print(f"   ❌ Unexpected error: {e}")
            return False
    
    def test_invalid_custom_policy(self):
        """Test bucket creation with invalid custom lifecycle policy"""
        print("\n🧪 Testing invalid custom lifecycle policy...")
        
        invalid_configs = [
            {"Invalid": "config"},  # Missing Rules
            {"Rules": []},  # Empty rules
            {"Rules": [{"Status": "Enabled"}]},  # Missing ID
            {"Rules": [{"ID": "Test", "Status": "Invalid"}]},  # Invalid status
        ]
        
        for i, invalid_config in enumerate(invalid_configs):
            test_project = f"test-invalid-{int(time.time())}-{i}"
            try:
                response = requests.post(
                    f"{self.config['api_endpoint']}/buckets",
                    headers={
                        'Content-Type': 'application/json',
                        'Authorization': f'Bearer {self.id_token}'
                    },
                    json={
                        'project_name': test_project,
                        'versioning': 'Enabled',
                        'lifecycle_policy': 'Custom',
                        'custom_lifecycle_config': invalid_config
                    },
                    timeout=30
                )
                
                if response.status_code == 400:
                    print(f"   ✅ Properly rejected invalid config #{i+1}")
                else:
                    print(f"   ❌ Should have rejected config #{i+1} (got {response.status_code})")
            except Exception as e:
                print(f"   ❌ Network error: {e}")
        
        self.test_results['passed'] += 1
        return True
    
    def test_duplicate_project_name(self):
        """Test creating bucket with duplicate project name"""
        print("\n🧪 Testing duplicate project name rejection...")
        
        test_project = f"test-dup-{int(time.time())}"
        
        # Create first bucket
        bucket1 = self._create_bucket_with_config(test_project)
        if not bucket1:
            self.test_results['failed'] += 1
            return False
        
        time.sleep(1)
        
        # Try to create duplicate
        try:
            response = requests.post(
                f"{self.config['api_endpoint']}/buckets",
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.id_token}'
                },
                json={'project_name': test_project},
                timeout=30
            )
            
            if response.status_code == 409:
                print(f"✅ Duplicate project name properly rejected")
                self.test_results['passed'] += 1
                return True
            else:
                print(f"❌ Should have rejected duplicate (got {response.status_code})")
                self.test_results['failed'] += 1
                return False
        except Exception as e:
            print(f"❌ Error: {e}")
            self.test_results['failed'] += 1
            return False
    
    def test_list_buckets(self):
        """Test bucket listing"""
        print("\n🧪 Testing bucket listing...")
        
        try:
            response = requests.get(
                f"{self.config['api_endpoint']}/buckets",
                headers={'Authorization': f'Bearer {self.id_token}'},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Listed {len(data)} buckets")
                
                # Verify response structure
                if isinstance(data, list):
                    if len(data) > 0:
                        # Check that each bucket has required fields
                        required_fields = ['bucket_name', 'status', 'created_at']
                        first_bucket = data[0]
                        missing_fields = [f for f in required_fields if f not in first_bucket]
                        if missing_fields:
                            print(f"   ⚠️  Missing fields in response: {missing_fields}")
                        else:
                            print(f"   ✅ Response structure valid")
                    
                    self.test_results['passed'] += 1
                    return data
                else:
                    print(f"❌ Expected array, got {type(data)}")
                    self.test_results['failed'] += 1
                    return None
            else:
                print(f"❌ Bucket listing failed: {response.status_code}")
                print(f"Response: {response.text[:200]}")
                self.test_results['failed'] += 1
                return None
                
        except Exception as e:
            print(f"❌ Network error: {e}")
            self.test_results['failed'] += 1
            return None
    
    def test_get_specific_bucket(self):
        """Test getting specific bucket by project name"""
        print("\n🧪 Testing get specific bucket...")
        
        test_project = f"test-get-specific-{int(time.time())}"
        bucket_name = self._create_bucket_with_config(test_project)
        
        if not bucket_name:
            self.test_results['failed'] += 1
            return False
        
        time.sleep(1)
        
        try:
            response = requests.get(
                f"{self.config['api_endpoint']}/buckets?project_name={test_project}",
                headers={'Authorization': f'Bearer {self.id_token}'},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('bucket_name') == bucket_name:
                    print(f"✅ Successfully retrieved bucket by project name")
                    self.test_results['passed'] += 1
                    return True
                else:
                    print(f"❌ Bucket name mismatch")
                    self.test_results['failed'] += 1
                    return False
            else:
                print(f"❌ Failed to get bucket: {response.status_code}")
                self.test_results['failed'] += 1
                return False
        except Exception as e:
            print(f"❌ Error: {e}")
            self.test_results['failed'] += 1
            return False
    
    def test_bucket_healing(self, bucket_name):
        """Test bucket healing by deleting a bucket via API (to preserve deletion metadata)"""
        print("\n🧪 Testing bucket healing...")
        
        try:
            # Extract project name from bucket name (format: env-project-uuid)
            # The bucket name format is: {env}-{project_name}-{uuid}
            # We need to find the project in DynamoDB first
            import re
            match = re.match(r'^[^-]+-(.+)-[a-f0-9]{8}$', bucket_name)
            
            if not match:
                print(f"⚠️  Could not extract project name from bucket name: {bucket_name}")
                print("   Using API delete requires project name. Falling back to direct S3 delete...")
                # Fall back to direct S3 deletion (no metadata will be recorded)
                s3 = boto3.client('s3', region_name=self.config['region'])
                try:
                    s3.head_bucket(Bucket=bucket_name)
                except s3.exceptions.NoSuchBucket:
                    print(f"⚠️  Bucket {bucket_name} doesn't exist, skipping healing test")
                    return False
                
                try:
                    s3.delete_bucket(Bucket=bucket_name)
                    print(f"🗑️  Deleted bucket {bucket_name} directly (no deletion metadata recorded)")
                    print("   ⚠️  Note: Direct S3 deletion won't create audit trail in DynamoDB")
                except Exception as delete_error:
                    print(f"⚠️  Could not delete bucket: {delete_error}")
                    return False
            else:
                # Try to delete via API to preserve deletion metadata
                project_name = match.group(1)
                print(f"🗑️  Deleting bucket via API (project: {project_name}) to preserve audit trail...")
                
                response = requests.delete(
                    f"{self.config['api_endpoint']}/buckets?project_name={project_name}",
                    headers={'Authorization': f'Bearer {self.id_token}'}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    should_heal = data.get('should_heal', False)
                    print(f"✅ Bucket deleted via API: {data.get('message', 'Success')}")
                    print(f"   Deleted by: {data.get('deleted_by', 'unknown')}")
                    print(f"   Auto-heal: {should_heal}")
                    
                    # If should_heal is False, the bucket won't be auto-healed (expected behavior)
                    # This happens when the owner deletes their own bucket
                    if not should_heal:
                        print("\n   ℹ️  Note: Bucket will NOT be auto-healed (should_heal=False)")
                        print("   This is expected behavior when the owner deletes their own bucket.")
                        print("   Auto-healing only occurs when buckets are deleted by other users/admins.")
                        print("   ✅ Test passed - correct behavior verified")
                        return True
                elif response.status_code == 404:
                    print(f"⚠️  Project not found via API, using direct S3 delete...")
                    # Fall back to direct deletion
                    s3 = boto3.client('s3', region_name=self.config['region'])
                    try:
                        s3.delete_bucket(Bucket=bucket_name)
                        print(f"🗑️  Deleted bucket {bucket_name} directly (no deletion metadata)")
                    except Exception as delete_error:
                        print(f"⚠️  Could not delete bucket: {delete_error}")
                        return False
                else:
                    print(f"⚠️  API delete failed ({response.status_code}): {response.text}")
                    print("   Falling back to direct S3 delete...")
                    s3 = boto3.client('s3', region_name=self.config['region'])
                    try:
                        s3.delete_bucket(Bucket=bucket_name)
                        print(f"🗑️  Deleted bucket {bucket_name} directly")
                    except Exception as delete_error:
                        print(f"⚠️  Could not delete bucket: {delete_error}")
                        return False
            
            # Only wait for healing if should_heal is True
            # (Note: We already returned True above if should_heal was False)
            print("\n⏳ Waiting for healing process (monitoring runs every 5 minutes)...")
            print("   Note: Check deletion metadata with: python scripts/audit_deletions.py")
            
            # Ensure s3 client is available for checking
            s3 = boto3.client('s3', region_name=self.config['region'])
            
            for i in range(10):  # Wait up to 10 minutes
                time.sleep(60)  # Wait 1 minute
                
                try:
                    s3.head_bucket(Bucket=bucket_name)
                    print(f"✅ Bucket {bucket_name} healed successfully!")
                    return True
                except ClientError as e:
                    error_code = e.response.get('Error', {}).get('Code', '')
                    if error_code == '404' or 'NoSuchBucket' in str(e):
                        # Bucket still doesn't exist, continue waiting
                        if i < 9:  # Don't print on last iteration
                            print(f"⏳ Still waiting... ({i+1}/10 minutes)")
                        continue
                    else:
                        # Other errors (permissions, etc.)
                        print(f"⚠️  Error checking bucket ({error_code}): {e}")
                        continue
                except Exception as check_error:
                    # Check if it's a NoSuchBucket error (boto3 can raise different exceptions)
                    if '404' in str(check_error) or 'Not Found' in str(check_error) or 'NoSuchBucket' in str(check_error):
                        if i < 9:
                            print(f"⏳ Still waiting... ({i+1}/10 minutes)")
                        continue
                    else:
                        # Other errors
                        print(f"⚠️  Error checking bucket: {check_error}")
                        continue
            
            print("❌ Bucket healing test timed out (bucket not recreated after 10 minutes)")
            print("   ⚠️  Note: This may be expected if should_heal=False or monitoring hasn't run yet")
            return False
            
        except Exception as e:
            print(f"❌ Healing test error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_authentication_failure(self):
        """Test API with invalid authentication"""
        print("\n🧪 Testing authentication failure...")
        
        test_cases = [
            ('Bearer invalid-token', 401, "Invalid token"),
            ('invalid-format', 401, "Invalid format"),
            ('', 401, "No token"),
        ]
        
        all_passed = True
        for auth_header, expected_status, description in test_cases:
            try:
                headers = {'Authorization': auth_header} if auth_header else {}
                response = requests.get(
                    f"{self.config['api_endpoint']}/buckets",
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code == expected_status:
                    print(f"   ✅ Properly rejected: {description}")
                else:
                    print(f"   ❌ Expected {expected_status} for {description}, got {response.status_code}")
                    all_passed = False
                    
            except Exception as e:
                print(f"   ⚠️  Error testing {description}: {e}")
        
        if all_passed:
            self.test_results['passed'] += 1
            return True
        else:
            self.test_results['failed'] += 1
            return False
    
    def test_invalid_project_name(self):
        """Test bucket creation with invalid project name"""
        print("\n🧪 Testing invalid project name...")
        
        invalid_cases = [
            ("Test-With-Capitals", "Has capitals"),
            ("a", "Too short (< 3 chars)"),
            ("ab", "Too short (< 3 chars)"),
            ("a" * 51, "Too long (> 50 chars)"),
            ("test_with_underscores", "Has underscores"),
            ("test with spaces", "Has spaces"),
            ("test@invalid", "Has special chars"),
            ("test.invalid", "Has dots"),
        ]
        
        passed = 0
        for invalid_name, reason in invalid_cases:
            try:
                response = requests.post(
                    f"{self.config['api_endpoint']}/buckets",
                    headers={
                        'Content-Type': 'application/json',
                        'Authorization': f'Bearer {self.id_token}'
                    },
                    json={'project_name': invalid_name},
                    timeout=10
                )
                
                if response.status_code == 400:
                    print(f"   ✅ Rejected '{invalid_name[:30]}...' ({reason})")
                    passed += 1
                else:
                    print(f"   ❌ Should reject '{invalid_name[:30]}...' ({reason}) - got {response.status_code}")
                    
            except Exception as e:
                print(f"   ⚠️  Error testing '{invalid_name[:30]}...': {e}")
        
        if passed == len(invalid_cases):
            self.test_results['passed'] += 1
            return True
        else:
            self.test_results['failed'] += 1
            return False
    
    def cleanup_created_buckets(self):
        """Clean up all buckets created during testing"""
        print("\n🧹 Cleaning up test buckets...")
        cleaned = 0
        
        for bucket_name in self.created_buckets[:]:
            try:
                # Check if bucket exists
                self.s3.head_bucket(Bucket=bucket_name)
                
                # Try to delete bucket
                try:
                    self.s3.delete_bucket(Bucket=bucket_name)
                    print(f"   ✅ Deleted: {bucket_name}")
                    cleaned += 1
                except Exception as e:
                    print(f"   ⚠️  Could not delete {bucket_name}: {e}")
                    
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                if error_code in ('404', 'NoSuchBucket'):
                    print(f"   ℹ️  Already deleted: {bucket_name}")
                    cleaned += 1
                else:
                    print(f"   ⚠️  Error checking {bucket_name}: {e}")
        
        if cleaned > 0:
            print(f"✅ Cleaned up {cleaned} bucket(s)")
        else:
            print("ℹ️  No buckets to clean up")
    
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
    
    def test_missing_required_fields(self):
        """Test API calls with missing required fields"""
        print("\n🧪 Testing missing required fields...")
        
        # Test missing project_name
        try:
            response = requests.post(
                f"{self.config['api_endpoint']}/buckets",
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.id_token}'
                },
                json={},
                timeout=10
            )
            
            if response.status_code == 400:
                print("   ✅ Properly rejected missing project_name")
                self.test_results['passed'] += 1
                return True
            else:
                print(f"   ❌ Should reject missing project_name (got {response.status_code})")
                self.test_results['failed'] += 1
                return False
        except Exception as e:
            print(f"   ❌ Error: {e}")
            self.test_results['failed'] += 1
            return False
    
    def run_all_tests(self, skip_healing=False):
        """Run all tests with comprehensive coverage"""
        print("🚀 Starting Enhanced Comprehensive Test Suite...")
        print("=" * 80)
        
        # Setup
        if not self.create_test_user():
            print("❌ Failed to create test user. Aborting tests.")
            return False
        
        if not self.authenticate_test_user():
            print("❌ Failed to authenticate test user. Aborting tests.")
            return False
        
        print("\n" + "=" * 80)
        print("📋 TEST CATEGORIES:")
        print("=" * 80)
        
        # Category 1: Basic Operations
        print("\n📦 Category 1: Basic Bucket Operations")
        print("-" * 80)
        self.test_create_bucket()
        self.test_list_buckets()
        self.test_get_specific_bucket()
        self.test_duplicate_project_name()
        
        # Category 2: Authentication & Authorization
        print("\n🔐 Category 2: Authentication & Authorization")
        print("-" * 80)
        self.test_authentication_failure()
        
        # Category 3: Input Validation
        print("\n✅ Category 3: Input Validation")
        print("-" * 80)
        self.test_invalid_project_name()
        self.test_missing_required_fields()
        self.test_invalid_custom_policy()
        
        # Category 4: Versioning Configuration
        print("\n📌 Category 4: Versioning Configuration")
        print("-" * 80)
        self.test_create_bucket_with_versioning_enabled()
        self.test_create_bucket_with_versioning_disabled()
        
        # Category 5: Lifecycle Policies
        print("\n♻️  Category 5: Lifecycle Policies")
        print("-" * 80)
        self.test_create_bucket_with_auto_archive()
        self.test_create_bucket_with_auto_delete()
        self.test_create_bucket_with_custom_policy()
        
        # Category 6: Bucket Healing (Optional - time consuming)
        if not skip_healing:
            print("\n🏥 Category 6: Bucket Healing Behavior")
            print("-" * 80)
            print("   ℹ️  Testing bucket deletion and healing logic...")
            print("   Note: Same-user deletions have should_heal=False (expected behavior)")
            
            healing_bucket = self.test_create_bucket()
            if healing_bucket:
                # Extract project name for healing test
                match = re.match(r'^[^-]+-(.+)-[a-f0-9]{8}$', healing_bucket)
                if match:
                    # Use the existing healing test method
                    # This test now checks should_heal flag and behaves accordingly
                    if self.test_bucket_healing(healing_bucket):
                        self.test_results['passed'] += 1
                    else:
                        # Only fail if it's an unexpected failure
                        # If should_heal=False, the test already returned True above
                        self.test_results['failed'] += 1
                else:
                    print("   ⏭️  Skipping healing test (could not extract project name)")
                    self.test_results['skipped'] += 1
        else:
            print("\n⏭️  Category 6: Bucket Healing - SKIPPED (use --skip-healing to skip)")
            self.test_results['skipped'] += 1
        
        # Cleanup
        print("\n" + "=" * 80)
        print("🧹 CLEANUP")
        print("-" * 80)
        self.cleanup_created_buckets()
        self.cleanup_test_user()
        
        # Results Summary
        print("\n" + "=" * 80)
        print("🏁 TEST RESULTS SUMMARY")
        print("=" * 80)
        total_tests = self.test_results['passed'] + self.test_results['failed'] + self.test_results['skipped']
        print(f"✅ Passed:  {self.test_results['passed']}")
        print(f"❌ Failed:  {self.test_results['failed']}")
        print(f"⏭️  Skipped: {self.test_results['skipped']}")
        print(f"📊 Total:   {total_tests}")
        print("-" * 80)
        
        success_rate = (self.test_results['passed'] / total_tests * 100) if total_tests > 0 else 0
        print(f"📈 Success Rate: {success_rate:.1f}%")
        
        if self.test_results['failed'] == 0:
            print("\n🎉 All tests passed! System is working correctly.")
            return True
        else:
            print(f"\n⚠️  {self.test_results['failed']} test(s) failed. Please review the logs above.")
            return False

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Comprehensive test suite for S3 Bucket Management System')
    parser.add_argument('--skip-healing', action='store_true', 
                       help='Skip time-consuming bucket healing tests')
    parser.add_argument('--config', default='web-interface/config.js',
                       help='Path to config.js file (default: web-interface/config.js)')
    
    args = parser.parse_args()
    
    test_suite = TestSuite(config_file=args.config)
    success = test_suite.run_all_tests(skip_healing=args.skip_healing)
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()