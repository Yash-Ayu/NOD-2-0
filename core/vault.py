"""
NOD 2.0 - Encrypted Vault
Stores critical files with AES-256 encryption
"""
import os
import json
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

VAULT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "nod_data", "vault")
os.makedirs(VAULT_DIR, exist_ok=True)
VAULT_INDEX = os.path.join(VAULT_DIR, ".vault_index")


class SecureVault:
    def __init__(self):
        self.vault_dir = VAULT_DIR
    
    def _derive_key(self, pin: str, salt: bytes = None):
        if salt is None:
            salt = os.urandom(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(pin.encode()))
        return key, salt
    
    def store_file(self, file_path: str, pin: str, metadata: dict = None) -> dict:
        try:
            with open(file_path, "rb") as f:
                data = f.read()
            key, salt = self._derive_key(pin)
            fernet = Fernet(key)
            encrypted = fernet.encrypt(data)
            import hashlib
            vault_name = hashlib.sha256(os.path.basename(file_path).encode()).hexdigest()[:16]
            vault_path = os.path.join(self.vault_dir, vault_name + ".enc")
            with open(vault_path, "wb") as f:
                f.write(salt + encrypted)
            
            index = self._load_index()
            index[vault_name] = {
                "original_name": os.path.basename(file_path),
                "vault_path": vault_path,
                "size": len(data),
                "metadata": metadata or {},
                "created_at": str(__import__("datetime").datetime.now())
            }
            self._save_index(index)
            return {"success": True, "vault_id": vault_name, "message": "File secured in vault"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def retrieve_file(self, vault_id: str, pin: str) -> dict:
        try:
            index = self._load_index()
            if vault_id not in index:
                return {"success": False, "error": "File not found"}
            info = index[vault_id]
            with open(info["vault_path"], "rb") as f:
                raw = f.read()
            salt = raw[:16]
            encrypted = raw[16:]
            key, _ = self._derive_key(pin, salt)
            decrypted = Fernet(key).decrypt(encrypted)
            return {
                "success": True,
                "data": decrypted,
                "filename": info["original_name"],
                "metadata": info.get("metadata", {})
            }
        except:
            return {"success": False, "error": "Invalid PIN or corrupted file"}
    
    def list_vault(self) -> list:
        index = self._load_index()
        return [
            {"vault_id": vid, "filename": info["original_name"], "size": info["size"]}
            for vid, info in index.items()
        ]
    
    def _load_index(self) -> dict:
        if os.path.exists(VAULT_INDEX):
            with open(VAULT_INDEX, "r") as f:
                return json.load(f)
        return {}
    
    def _save_index(self, index: dict):
        with open(VAULT_INDEX, "w") as f:
            json.dump(index, f, indent=2)


vault = SecureVault()