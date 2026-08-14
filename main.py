#!/usr/bin/env python3
"""
NOD - AI Assistant Backend
Flask + Ollama Integration
"""

import os
import json
import uuid
import hashlib
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, jsonify,
    session, redirect, url_for, Response, stream_with_context
)
import requests

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.environ.get("SECRET_KEY", "nod-secret-key-change-in-production")

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "qwen3:8b")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

USERS_FILE = os.path.join(DATA_DIR, "users.json")
CHATS_DIR = os.path.join(DATA_DIR, "chats")
os.makedirs(CHATS_DIR, exist_ok=True)


def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


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


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


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
    users = load_users()
    if email not in users:
        return jsonify({"error": "User not found"}), 404
    if users[email]["password"] != hash_password(password):
        return jsonify({"error": "Invalid password"}), 401
    session["user"] = email
    session.permanent = remember
    return jsonify({"success": True, "email": email})


@app.route("/api/auth/signup", methods=["POST"])
def api_signup():
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    name = data.get("name", "").strip()
    if not email or not password or len(password) < 6:
        return jsonify({"error": "Invalid data. Password must be 6+ chars."}), 400
    users = load_users()
    if email in users:
        return jsonify({"error": "Email already registered"}), 409
    users[email] = {
        "name": name or email.split("@")[0],
        "password": hash_password(password),
        "created_at": datetime.now().isoformat()
    }
    save_users(users)
    session["user"] = email
    return jsonify({"success": True, "email": email})


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    session.pop("user", None)
    return jsonify({"success": True})


@app.route("/api/auth/me")
@login_required
def api_me():
    users = load_users()
    email = session["user"]
    return jsonify({
        "email": email,
        "name": users.get(email, {}).get("name", "User")
    })


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
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "messages": []
    }
    save_user_chats(session["user"], chats)
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
    chats[chat_id]["updated_at"] = datetime.now().isoformat()
    save_user_chats(session["user"], chats)
    return jsonify(chats[chat_id])


@app.route("/api/chats/<chat_id>", methods=["DELETE"])
@login_required
def delete_chat(chat_id):
    chats = load_user_chats(session["user"])
    if chat_id in chats:
        del chats[chat_id]
        save_user_chats(session["user"], chats)
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
    chats[chat_id]["updated_at"] = datetime.now().isoformat()
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
    chats[chat_id]["updated_at"] = datetime.now().isoformat()
    save_user_chats(session["user"], chats)
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
        "time": datetime.now().isoformat()
    }
    chats[chat_id]["messages"].append(msg_obj)
    if chats[chat_id]["title"] == "New Chat" and len(chats[chat_id]["messages"]) == 1:
        chats[chat_id]["title"] = user_message[:40] + ("..." if len(user_message) > 40 else "")
    chats[chat_id]["updated_at"] = datetime.now().isoformat()
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
                "time": datetime.now().isoformat()
            }
            chats[chat_id]["messages"].append(assistant_msg)
            chats[chat_id]["updated_at"] = datetime.now().isoformat()
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
    return jsonify({"status": "ok", "ollama": ollama_status, "model": DEFAULT_MODEL})


if __name__ == "__main__":
    print("=" * 50)
    print("  NOD AI Assistant")
    print("  URL: http://127.0.0.1:5000")
    print("=" * 50)
    app.run(debug=True, host="0.0.0.0", port=5000, threaded=True)