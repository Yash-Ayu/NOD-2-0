"""
NOD 2.0 - Security Module
Handles: Authentication, JWT, Password Hashing, Sessions
"""
import bcrypt
import jwt
import os
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import request, jsonify, session

JWT_SECRET = os.environ.get("JWT_SECRET", "nod-jwt-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

active_sessions = {}


def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against bcrypt hash"""
    return bcrypt.checkpw(password.encode(), hashed.encode())


def generate_jwt(email: str, name: str) -> str:
    payload = {
        "email": email,
        "name": name,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
        "type": "access"
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return {"error": "Token expired"}
    except jwt.InvalidTokenError:
        return {"error": "Invalid token"}


def generate_sudo_token(email: str) -> str:
    """Short-lived sudo token for risky operations"""
    payload = {
        "email": email,
        "sudo": True,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=10)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_sudo_token(token: str, email: str) -> bool:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("sudo") is True and payload.get("email") == email
    except:
        return False


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" in session:
            return f(*args, **kwargs)
        
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            payload = decode_jwt(token)
            if "error" not in payload:
                request.current_user = payload
                return f(*args, **kwargs)
        
        return jsonify({"error": "Unauthorized. Please login."}), 401
    return decorated


def sudo_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return jsonify({"error": "Login required"}), 401
        
        sudo_token = request.headers.get("X-Sudo-Token") or (request.json or {}).get("sudo_token", "")
        if not verify_sudo_token(sudo_token, session["user"]):
            return jsonify({
                "error": "Sudo confirmation required",
                "requires_sudo": True,
                "message": "This action requires PIN confirmation. Please verify your identity."
            }), 403
        
        return f(*args, **kwargs)
    return decorated


def generate_device_fingerprint() -> str:
    user_agent = request.headers.get("User-Agent", "")
    ip = request.remote_addr or "unknown"
    import hashlib
    return hashlib.sha256(f"{user_agent}:{ip}".encode()).hexdigest()[:16]