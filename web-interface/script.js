// AWS Configuration
AWS.config.update({
    region: CONFIG.region,
    credentials: new AWS.CognitoIdentityCredentials({
        IdentityPoolId: CONFIG.identityPoolId
    })
});

const cognitoUser = new AWS.CognitoIdentityServiceProvider();
let currentUser = null;
let currentSession = null;

// Initialize the app
document.addEventListener('DOMContentLoaded', function() {
    checkAuthState();
    // showAppSection();   // Force show the app section
    // document.getElementById('userName').textContent = "Demo User";
});

function showStatus(message, type = 'info') {
    const statusDiv = document.getElementById('status');
    statusDiv.innerHTML = `<div class="status ${type}">${message}</div>`;
    setTimeout(() => {
        statusDiv.innerHTML = '';
    }, 5000);
}

function setLoading(elementId, loading) {
    const element = document.getElementById(elementId);
    if (loading) {
        element.disabled = true;
        element.textContent = element.textContent.replace('...', '') + '...';
    } else {
        element.disabled = false;
        element.textContent = element.textContent.replace('...', '');
    }
}

// Authentication Functions
async function signUp() {
    const name = document.getElementById('signUpName').value.trim();
    const email = document.getElementById('signUpEmail').value.trim();
    const password = document.getElementById('signUpPassword').value;

    if (!name || !email || !password) {
        showStatus('Please fill in all fields', 'error');
        return;
    }

    if (password.length < 8) {
        showStatus('Password must be at least 8 characters long', 'error');
        return;
    }

    setLoading('signUpBtn', true);

    try {
        const params = {
            ClientId: CONFIG.userPoolClientId,
            Username: email,
            Password: password,
            UserAttributes: [
                { Name: 'email', Value: email },
                { Name: 'name', Value: name }
            ]
        };

        await cognitoUser.signUp(params).promise();
        
        // Store email for confirmation
        localStorage.setItem('pendingEmail', email);
        
        // Show confirmation form
        document.getElementById('confirmationForm').style.display = 'block';
        showStatus('Account created! Please check your email for confirmation code.', 'success');
        
    } catch (error) {
        console.error('Sign up error:', error);
        showStatus(`Sign up failed: ${error.message}`, 'error');
    } finally {
        setLoading('signUpBtn', false);
    }
}

async function confirmSignUp() {
    const email = localStorage.getItem('pendingEmail');
    const code = document.getElementById('confirmationCode').value.trim();

    if (!code) {
        showStatus('Please enter the confirmation code', 'error');
        return;
    }

    setLoading('confirmBtn', true);

    try {
        const params = {
            ClientId: CONFIG.userPoolClientId,
            Username: email,
            ConfirmationCode: code
        };

        await cognitoUser.confirmSignUp(params).promise();
        
        localStorage.removeItem('pendingEmail');
        document.getElementById('confirmationForm').style.display = 'none';
        showStatus('Account confirmed! You can now sign in.', 'success');
        
    } catch (error) {
        console.error('Confirmation error:', error);
        showStatus(`Confirmation failed: ${error.message}`, 'error');
    } finally {
        setLoading('confirmBtn', false);
    }
}

async function resendConfirmation() {
    const email = localStorage.getItem('pendingEmail');
    
    try {
        const params = {
            ClientId: CONFIG.userPoolClientId,
            Username: email
        };

        await cognitoUser.resendConfirmationCode(params).promise();
        showStatus('Confirmation code resent! Check your email.', 'success');
        
    } catch (error) {
        console.error('Resend error:', error);
        showStatus(`Resend failed: ${error.message}`, 'error');
    }
}

async function signIn() {
    const email = document.getElementById('signInEmail').value.trim();
    const password = document.getElementById('signInPassword').value;

    if (!email || !password) {
        showStatus('Please enter both email and password', 'error');
        return;
    }

    setLoading('signInBtn', true);

    try {
        const params = {
            AuthFlow: 'USER_PASSWORD_AUTH',
            ClientId: CONFIG.userPoolClientId,
            AuthParameters: {
                USERNAME: email,
                PASSWORD: password
            }
        };

        const result = await cognitoUser.initiateAuth(params).promise();
        
        if (result.AuthenticationResult) {
            // Store tokens
            const tokens = result.AuthenticationResult;
            localStorage.setItem('accessToken', tokens.AccessToken);
            localStorage.setItem('idToken', tokens.IdToken);
            localStorage.setItem('refreshToken', tokens.RefreshToken);
            
            // Update AWS credentials
            AWS.config.credentials = new AWS.CognitoIdentityCredentials({
                IdentityPoolId: CONFIG.identityPoolId,
                Logins: {
                    [`cognito-idp.${CONFIG.region}.amazonaws.com/${CONFIG.userPoolId}`]: tokens.IdToken
                }
            });

            await AWS.config.credentials.refresh();
            
            showStatus('Successfully signed in!', 'success');
            showAppSection();
            loadUserInfo();
            loadBuckets();
        } else {
            showStatus('Sign in failed. Please try again.', 'error');
        }
        
    } catch (error) {
        console.error('Sign in error:', error);
        showStatus(`Sign in failed: ${error.message}`, 'error');
    } finally {
        setLoading('signInBtn', false);
    }
}

function signOut() {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('idToken');
    localStorage.removeItem('refreshToken');
    
    AWS.config.credentials = new AWS.CognitoIdentityCredentials({
        IdentityPoolId: CONFIG.identityPoolId
    });
    
    showAuthSection();
    showStatus('Signed out successfully', 'info');
}

function checkAuthState() {
    const idToken = localStorage.getItem('idToken');
    if (idToken) {
        // Verify token is still valid
        try {
            const payload = JSON.parse(atob(idToken.split('.')[1]));
            if (payload.exp * 1000 > Date.now()) {
                // Token is still valid
                AWS.config.credentials = new AWS.CognitoIdentityCredentials({
                    IdentityPoolId: CONFIG.identityPoolId,
                    Logins: {
                        [`cognito-idp.${CONFIG.region}.amazonaws.com/${CONFIG.userPoolId}`]: idToken
                    }
                });
                
                showAppSection();
                loadUserInfo();
                loadBuckets();
                return;
            }
        } catch (e) {
            console.error('Token validation error:', e);
        }
    }
    
    showAuthSection();
}

function showAuthSection() {
    document.getElementById('authSection').classList.add('active');
    document.getElementById('appSection').classList.remove('active');
}

function showAppSection() {
    document.getElementById('authSection').classList.remove('active');
    document.getElementById('appSection').classList.add('active');
}

function loadUserInfo() {
    const idToken = localStorage.getItem('idToken');
    if (idToken) {
        try {
            const payload = JSON.parse(atob(idToken.split('.')[1]));
            document.getElementById('userName').textContent = payload.name || payload.email || 'User';
        } catch (e) {
            console.error('Error parsing token:', e);
        }
    }
}

// Bucket Management Functions
async function createBucket() {
    const projectName = document.getElementById('projectName').value.trim().toLowerCase();
    
    if (!projectName) {
        showStatus('Please enter a project name', 'error');
        return;
    }

    if (!/^[a-z0-9-]+$/.test(projectName)) {
        showStatus('Project name must contain only lowercase letters, numbers, and hyphens', 'error');
        return;
    }

    if (projectName.length < 3 || projectName.length > 50) {
        showStatus('Project name must be between 3 and 50 characters', 'error');
        return;
    }

    setLoading('createBtn', true);

    try {
        const idToken = localStorage.getItem('idToken');
        if (!idToken) {
            showStatus('Please sign in to create buckets', 'error');
            return;
        }

        const response = await fetch(`${CONFIG.apiEndpoint}/buckets`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${idToken}`
            },
            body: JSON.stringify({
                project_name: projectName
            })
        });

        if (!response.ok) {
            let errorMessage = 'Failed to create bucket';
            try {
                const errorData = await response.json();
                errorMessage = errorData.error || errorMessage;
            } catch (e) {
                errorMessage = `HTTP ${response.status}: ${response.statusText}`;
            }
            showStatus(`❌ ${errorMessage}`, 'error');
            return;
        }

        const data = await response.json();

        if (data.bucket_name) {
            showStatus(`✅ Bucket created successfully: ${data.bucket_name}`, 'success');
            document.getElementById('projectName').value = '';
            loadBuckets();
        } else {
            showStatus(`❌ Unexpected response format`, 'error');
        }
    } catch (error) {
        console.error('Create bucket error:', error);
        if (error.message === 'Failed to fetch' || error.message.includes('NetworkError')) {
            showStatus('❌ Network error: Cannot reach API. Please check your connection and API endpoint.', 'error');
        } else {
            showStatus(`❌ Error: ${error.message}`, 'error');
        }
    } finally {
        setLoading('createBtn', false);
    }
}

async function loadBuckets() {
    setLoading('refreshBtn', true);
    
    const bucketsList = document.getElementById('bucketsList');
    bucketsList.innerHTML = '<div class="loading">Loading buckets</div>';

    try {
        const idToken = localStorage.getItem('idToken');
        if (!idToken) {
            bucketsList.innerHTML = '<p style="color: red;">Please sign in to view buckets</p>';
            return;
        }

        const response = await fetch(`${CONFIG.apiEndpoint}/buckets`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${idToken}`
            }
        });

        if (!response.ok) {
            let errorMessage = 'Failed to load buckets';
            try {
                const errorData = await response.json();
                errorMessage = errorData.error || errorMessage;
            } catch (e) {
                errorMessage = `HTTP ${response.status}: ${response.statusText}`;
            }
            bucketsList.innerHTML = `<p style="color: red;">❌ ${errorMessage}</p>`;
            showStatus(`❌ ${errorMessage}`, 'error');
            return;
        }

        const data = await response.json();

        if (Array.isArray(data)) {
            if (data.length === 0) {
                bucketsList.innerHTML = '<p>No buckets found. Create your first bucket above! 🚀</p>';
            } else {
                bucketsList.innerHTML = data.map(bucket => `
                    <div class="bucket-item">
                        <h3>📦 ${bucket.display_name || bucket.project_name}</h3>
                        <div class="bucket-info">
                            <div><strong>Bucket Name:</strong> <code>${bucket.bucket_name}</code></div>
                            <div><strong>Status:</strong> <span style="color: ${bucket.status === 'active' ? 'green' : 'orange'}">${bucket.status}</span></div>
                            <div><strong>Created:</strong> ${formatDate(bucket.created_at)}</div>
                            <div><strong>Last Checked:</strong> ${formatDate(bucket.last_checked)}</div>
                            ${bucket.healed_at ? `<div><strong>Last Healed:</strong> ${formatDate(bucket.healed_at)}</div>` : ''}
                            ${bucket.heal_count ? `<div><strong>Heal Count:</strong> ${bucket.heal_count}</div>` : ''}
                        </div>
                    </div>
                `).join('');
            }
        } else {
            bucketsList.innerHTML = '<p style="color: red;">❌ Unexpected response format</p>';
        }
    } catch (error) {
        console.error('Load buckets error:', error);
        if (error.message === 'Failed to fetch' || error.message.includes('NetworkError')) {
            bucketsList.innerHTML = '<p style="color: red;">❌ Network error: Cannot reach API. Please check your connection and API endpoint.</p>';
            showStatus('❌ Network error: Cannot reach API. Please check your connection and API endpoint.', 'error');
        } else {
            bucketsList.innerHTML = `<p style="color: red;">❌ Error: ${error.message}</p>`;
            showStatus(`❌ Error: ${error.message}`, 'error');
        }
    } finally {
        setLoading('refreshBtn', false);
    }
}

function formatDate(dateString) {
    try {
        return new Date(dateString).toLocaleString();
    } catch (e) {
        return dateString;
    }
}

// Handle Enter key for forms
document.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        const activeSection = document.querySelector('.auth-section.active, .app-section.active');
        if (activeSection.id === 'authSection') {
            if (document.getElementById('confirmationForm').style.display !== 'none') {
                confirmSignUp();
            } else if (document.getElementById('signInEmail').value) {
                signIn();
            } else if (document.getElementById('signUpEmail').value) {
                signUp();
            }
        } else if (activeSection.id === 'appSection') {
            if (document.getElementById('projectName').value) {
                createBucket();
            }
        }
    }
});