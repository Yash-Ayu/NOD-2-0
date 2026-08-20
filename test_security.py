import requests

s = requests.Session()

# 1. SIGN UP (Pehli baar ke liye)
print("=" * 50)
print("STEP 1: SIGN UP")
print("=" * 50)
signup = s.post('http://127.0.0.1:5000/api/auth/signup', json={
    'name': 'Test User',
    'email': 'test@test.com',
    'password': 'password123'
})
print("Status:", signup.status_code)
print("Response:", signup.json())

# 2. LOGIN
print("\n" + "=" * 50)
print("STEP 2: LOGIN")
print("=" * 50)
login = s.post('http://127.0.0.1:5000/api/auth/login', json={
    'email': 'test@test.com',
    'password': 'password123'
})
print("Status:", login.status_code)
print("Response:", login.json())

# 3. SUDO TOKEN (PIN = 3014)
print("\n" + "=" * 50)
print("STEP 3: SUDO TOKEN")
print("=" * 50)
sudo = s.post('http://127.0.0.1:5000/api/auth/sudo', json={
    'pin': '3014'
})
print("Status:", sudo.status_code)
print("Response:", sudo.json())

# 4. AUDIT LOGS
print("\n" + "=" * 50)
print("STEP 4: AUDIT LOGS")
print("=" * 50)
audit = s.get('http://127.0.0.1:5000/api/security/audit')
print("Status:", audit.status_code)
print("Response:", audit.json())

# 5. HEALTH CHECK
print("\n" + "=" * 50)
print("STEP 5: HEALTH CHECK")
print("=" * 50)
health = s.get('http://127.0.0.1:5000/api/health')
print("Status:", health.status_code)
print("Response:", health.json())