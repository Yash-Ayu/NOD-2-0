"""
NOD 2.0 - Secure AI Assistant Backend
Flask + Ollama + Security Layer
"""

import os
import json
import uuid
import hashlib
from datetime import datetime, timezone
from functools import wraps

from flask import (
    Flask, render_template, request, jsonify,
    session, redirect, url_for, Response, stream_with_context
)
import requests

# Import NOD 2.0 Security Core
from core.config import Config
from core.security import (
    hash_password, verify_password, generate_jwt, decode_jwt,
    generate_sudo_token, verify_sudo_token, login_required, sudo_required,
    generate_device_fingerprint
)

# Placeholder function
def is_new_device(email: str) -> bool:
    return False

from core.acl import acl
from core.scanner import scanner
from core.vault import vault
from core.audit import audit

# Initialize config
Config.ensure_dirs()

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = Config.SECRET_KEY
app.config["PERMANENT_SESSION_LIFETIME"] = Config.SESSION_TIMEOUT

OLLAMA_URL = Config.OLLAMA_URL
DEFAULT_MODEL = Config.DEFAULT_MODEL
DATA_DIR = Config.DATA_DIR

USERS_FILE = os.path.join(DATA_DIR, "users.json")
CHATS_DIR = os.path.join(DATA_DIR, "chats")
os.makedirs(CHATS_DIR, exist_ok=True)

# Login attempt tracking
login_attempts = {}


def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)


def get_user_chats_file(email):
    safe = hashlib.md5(email.encode()).hexdigest()
    return os.path.join(CHATS_DIR, f"{safe}.json")


def load_user_chats(email):
    path = get_user_chats_file(email)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_user_chats(email, chats):
    path = get_user_chats_file(email)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(chats, f, indent=2, ensure_ascii=False)


# =========================================================
# AUTH ROUTES (SECURED WITH BCRYPT + JWT)
# =========================================================

@app.route("/")
def root():
    if "user" in session:
        return redirect(url_for("chat"))
    return redirect(url_for("login"))


@app.route("/login")
def login():
    if "user" in session:
        return redirect(url_for("chat"))
    return render_template("login.html")


@app.route("/signup")
def signup():
    if "user" in session:
        return redirect(url_for("chat"))
    return render_template("signup.html")


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    remember = data.get("remember", False)
    ip = request.remote_addr

    # Rate limiting
    if email in login_attempts:
        attempts = login_attempts[email]
        if attempts["count"] >= Config.MAX_LOGIN_ATTEMPTS:
            if (datetime.now(timezone.utc) - attempts["last"]).seconds < Config.LOCKOUT_DURATION:
                audit.log_auth("login_locked", email, False, ip)
                return jsonify({"error": "Account locked. Try again in 5 minutes."}), 429
            else:
                login_attempts[email] = {"count": 0, "last": datetime.now(timezone.utc)}

    users = load_users()
    if email not in users:
        _track_failed_login(email)
        return jsonify({"error": "Invalid credentials"}), 401

    if not verify_password(password, users[email]["password"]):
        _track_failed_login(email)
        audit.log_auth("login_failed", email, False, ip)
        return jsonify({"error": "Invalid credentials"}), 401

    # Success
    login_attempts[email] = {"count": 0, "last": datetime.now(timezone.utc)}
    session["user"] = email
    session.permanent = remember

    token = generate_jwt(email, users[email].get("name", "User"))
    audit.log_auth("login_success", email, True, ip)

    return jsonify({
        "success": True,
        "email": email,
        "token": token,
        "name": users[email].get("name", "User")
    })


def _track_failed_login(email):
    if email not in login_attempts:
        login_attempts[email] = {"count": 0, "last": datetime.now(timezone.utc)}
    login_attempts[email]["count"] += 1
    login_attempts[email]["last"] = datetime.now(timezone.utc)


@app.route("/api/auth/signup", methods=["POST"])
def api_signup():
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    name = data.get("name", "").strip()
    ip = request.remote_addr

    if not email or not password or len(password) < 6:
        return jsonify({"error": "Invalid data. Password must be 6+ chars."}), 400

    users = load_users()
    if email in users:
        return jsonify({"error": "Email already registered"}), 409

    # Hash password with bcrypt
    users[email] = {
        "name": name or email.split("@")[0],
        "password": hash_password(password),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "device_fingerprint": generate_device_fingerprint()
    }
    save_users(users)
        
    # 🎉 SEND WELCOME EMAIL
    try:
        from core.emailer import send_welcome_email
        email_result = send_welcome_email(email, users[email]["name"])
        if email_result["success"]:
            print(f"📧 Welcome email sent to {email} via {email_result['method']}")
        else:
            print(f"⚠️ Welcome email failed: {email_result['error']}")
    except Exception as e:
        print(f"⚠️ Email error: {e}")
    
    session["user"] = email
    token = generate_jwt(email, users[email]["name"])
    audit.log_auth("signup", email, True, ip)

    return jsonify({
        "success": True,
        "email": email,
        "token": token,
        "name": users[email]["name"]
    })


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    email = session.get("user", "anonymous")
    audit.log_auth("logout", email, True, request.remote_addr)
    session.pop("user", None)
    return jsonify({"success": True})


@app.route("/api/auth/me")
@login_required
def api_me():
    users = load_users()
    email = session.get("user") or request.current_user.get("email")
    return jsonify({
        "email": email,
        "name": users.get(email, {}).get("name", "User")
    })


@app.route("/api/auth/sudo", methods=["POST"])
@login_required
def api_sudo():
    """Verify PIN and return sudo token for risky operations"""
    data = request.get_json() or {}
    pin = data.get("pin", "")
    email = session.get("user")

    # In production, verify PIN against stored hash
    if pin != "3014":
        audit.log("sudo_denied", {"reason": "invalid_pin"}, email, "alert")
        return jsonify({"error": "Invalid PIN"}), 403

    token = generate_sudo_token(email)
    audit.log("sudo_granted", {"expires_in": "10min"}, email, "warning")

    return jsonify({"success": True, "sudo_token": token})


# =========================================================
# CHAT ROUTES (PROTECTED)
# =========================================================

@app.route("/chat")
def chat():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("index.html")


@app.route("/api/chats", methods=["GET"])
@login_required
def get_chats():
    return jsonify(load_user_chats(session["user"]))


@app.route("/api/chats", methods=["POST"])
@login_required
def create_chat():
    data = request.get_json() or {}
    chat_id = data.get("id") or str(uuid.uuid4())
    title = data.get("title", "New Chat")
    chats = load_user_chats(session["user"])
    chats[chat_id] = {
        "id": chat_id,
        "title": title,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "messages": []
    }
    save_user_chats(session["user"], chats)
    audit.log("chat_created", {"chat_id": chat_id}, session["user"])
    return jsonify(chats[chat_id])


@app.route("/api/chats/<chat_id>", methods=["GET"])
@login_required
def get_chat(chat_id):
    chats = load_user_chats(session["user"])
    if chat_id not in chats:
        return jsonify({"error": "Chat not found"}), 404
    return jsonify(chats[chat_id])


@app.route("/api/chats/<chat_id>", methods=["PUT"])
@login_required
def update_chat(chat_id):
    data = request.get_json() or {}
    chats = load_user_chats(session["user"])
    if chat_id not in chats:
        return jsonify({"error": "Chat not found"}), 404
    if "title" in data:
        chats[chat_id]["title"] = data["title"]
    if "messages" in data:
        chats[chat_id]["messages"] = data["messages"]
    chats[chat_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_user_chats(session["user"], chats)
    return jsonify(chats[chat_id])


@app.route("/api/chats/<chat_id>", methods=["DELETE"])
@login_required
def delete_chat(chat_id):
    chats = load_user_chats(session["user"])
    if chat_id in chats:
        del chats[chat_id]
        save_user_chats(session["user"], chats)
        audit.log("chat_deleted", {"chat_id": chat_id}, session["user"], "warning")
    return jsonify({"success": True})


@app.route("/api/chats/<chat_id>/rename", methods=["POST"])
@login_required
def rename_chat(chat_id):
    data = request.get_json() or {}
    new_title = data.get("title", "")
    if not new_title:
        return jsonify({"error": "Title required"}), 400
    chats = load_user_chats(session["user"])
    if chat_id not in chats:
        return jsonify({"error": "Chat not found"}), 404
    chats[chat_id]["title"] = new_title
    chats[chat_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_user_chats(session["user"], chats)
    return jsonify(chats[chat_id])


@app.route("/api/chats/<chat_id>/clear", methods=["POST"])
@login_required
def clear_chat(chat_id):
    chats = load_user_chats(session["user"])
    if chat_id not in chats:
        return jsonify({"error": "Chat not found"}), 404
    chats[chat_id]["messages"] = []
    chats[chat_id]["title"] = "New Chat"
    chats[chat_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_user_chats(session["user"], chats)
    audit.log("chat_cleared", {"chat_id": chat_id}, session["user"])
    return jsonify(chats[chat_id])


@app.route("/api/chats/<chat_id>/send", methods=["POST"])
@login_required
def send_message(chat_id):
    data = request.get_json() or {}
    user_message = data.get("message", "").strip()
    model = data.get("model", DEFAULT_MODEL)

    if not user_message:
        return jsonify({"error": "Message is empty"}), 400

    chats = load_user_chats(session["user"])
    if chat_id not in chats:
        return jsonify({"error": "Chat not found"}), 404

    msg_obj = {
        "role": "user",
        "content": user_message,
        "time": datetime.now(timezone.utc).isoformat()
    }
    chats[chat_id]["messages"].append(msg_obj)

    if chats[chat_id]["title"] == "New Chat" and len(chats[chat_id]["messages"]) == 1:
        chats[chat_id]["title"] = user_message[:40] + ("..." if len(user_message) > 40 else "")

    chats[chat_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_user_chats(session["user"], chats)

    conversation = []
    for msg in chats[chat_id]["messages"][-20:]:
        conversation.append({"role": msg["role"], "content": msg["content"]})

    def generate():
        assistant_content = ""
        try:
            payload = {"model": model, "messages": conversation, "stream": True}
            with requests.post(
                f"{OLLAMA_URL}/api/chat",
                json=payload,
                stream=True,
                timeout=300
            ) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if line:
                        try:
                            chunk = json.loads(line)
                            if "message" in chunk and "content" in chunk["message"]:
                                text = chunk["message"]["content"]
                                assistant_content += text
                                yield f"data: {json.dumps({'text': text, 'done': False})}\n\n"
                            if chunk.get("done"):
                                break
                        except json.JSONDecodeError:
                            continue

            assistant_msg = {
                "role": "assistant",
                "content": assistant_content,
                "time": datetime.now(timezone.utc).isoformat()
            }
            chats[chat_id]["messages"].append(assistant_msg)
            chats[chat_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
            save_user_chats(session["user"], chats)
            yield f"data: {json.dumps({'done': True, 'full': assistant_content})}\n\n"

        except Exception as e:
            error_msg = f"Error: {str(e)}. Make sure Ollama is running."
            yield f"data: {json.dumps({'error': error_msg})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


# =========================================================
# SECURITY API ROUTES
# =========================================================

@app.route("/api/security/scan", methods=["POST"])
@login_required
def scan_file():
    data = request.get_json() or {}
    file_path = data.get("path", "")

    if not acl.is_path_safe(file_path):
        audit.log_file_access(file_path, "scan_denied", session["user"], False, "ACL denied")
        return jsonify({"error": "Access denied by security policy"}), 403

    result = scanner.scan_file(file_path)
    audit.log("file_scanned", {"path": file_path, "sensitive": result["is_sensitive"]}, session["user"])
    return jsonify(result)


@app.route("/api/security/acl/allow", methods=["POST"])
@login_required
@sudo_required
def allow_path():
    data = request.get_json() or {}
    path = data.get("path", "")
    readonly = data.get("readonly", False)

    acl.allow_path(path, readonly)
    audit.log("acl_allow", {"path": path, "readonly": readonly}, session["user"], "warning")
    return jsonify({"success": True, "message": f"Access granted to {path}"})


@app.route("/api/security/audit", methods=["GET"])
@login_required
def get_audit_logs():
    logs = audit.get_logs(user=session["user"], limit=100)
    return jsonify({"logs": logs})


@app.route("/api/security/alerts", methods=["GET"])
@login_required
def get_security_alerts():
    alerts = audit.get_security_alerts(limit=50)
    return jsonify({"alerts": alerts})


@app.route("/api/vault/store", methods=["POST"])
@login_required
def vault_store():
    data = request.get_json() or {}
    file_path = data.get("path", "")
    pin = data.get("pin", "")

    result = vault.store_file(file_path, pin, {"owner": session["user"]})
    if result["success"]:
        audit.log_vault("store", result["vault_id"], session["user"], True)
    return jsonify(result)


@app.route("/api/vault/list", methods=["GET"])
@login_required
def vault_list():
    return jsonify({"files": vault.list_vault()})


@app.route("/api/vault/retrieve", methods=["POST"])
@login_required
def vault_retrieve():
    data = request.get_json() or {}
    vault_id = data.get("vault_id", "")
    pin = data.get("pin", "")

    result = vault.retrieve_file(vault_id, pin)
    audit.log_vault("access", vault_id, session["user"], result["success"])
    return jsonify(result)


@app.route("/api/models")
@login_required
def get_models():
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        r.raise_for_status()
        data = r.json()
        models = [m["name"] for m in data.get("models", [])]
        return jsonify({"models": models})
    except Exception as e:
        return jsonify({"models": [DEFAULT_MODEL], "error": str(e)})


@app.route("/api/health")
def health():
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        ollama_status = "connected" if r.status_code == 200 else "error"
    except:
        ollama_status = "disconnected"
    return jsonify({
        "status": "ok",
        "ollama": ollama_status,
        "model": DEFAULT_MODEL,
        "version": "2.0.0-secure",
        "security": "enabled"
    })


if __name__ == "__main__":
    print("=" * 60)
    print("  NOD 2.0 - Secure AI Assistant")
    print("  URL: http://127.0.0.1:5000")
    print("  Security: ENABLED (bcrypt + JWT + ACL + Vault + Audit)")
    print("=" * 60)
    app.run(debug=True, host="0.0.0.0", port=5000, threaded=True)