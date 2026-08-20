"""
NOD 2.0 - Audit Logger
Logs every action for transparency
"""
import os
import json
from datetime import datetime, timezone

AUDIT_LOG = os.path.join(os.path.dirname(os.path.dirname(__file__)), "nod_data", "audit.log")
os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)


class AuditLogger:
    def __init__(self):
        self.log_file = AUDIT_LOG
    
    def log(self, action: str, details: dict, user: str = "anonymous",
            severity: str = "info", ip: str = None):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": user,
            "action": action,
            "details": details,
            "severity": severity,
            "ip": ip or "unknown"
        }
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        if severity in ["alert", "critical"]:
            print(f"AUDIT ALERT: {action} by {user}")
    
    def log_auth(self, action: str, user: str, success: bool, ip: str = None):
        self.log(f"auth_{action}", {"success": success}, user,
                 "info" if success else "alert", ip)
    
    def log_vault(self, action: str, vault_id: str, user: str, success: bool):
        self.log(f"vault_{action}", {"vault_id": vault_id, "success": success},
                 user, "warning" if action in ["access", "delete"] else "info")
    
    def get_logs(self, user: str = None, limit: int = 100) -> list:
        if not os.path.exists(self.log_file):
            return []
        logs = []
        with open(self.log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if user is None or entry.get("user") == user:
                        logs.append(entry)
                except:
                    continue
        return logs[-limit:]


audit = AuditLogger()