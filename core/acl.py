"""
NOD 2.0 - Access Control List (ACL)
Sandboxed file access with explicit allowlist
"""
import os
from typing import List

SANDBOX_ROOT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "nod_data")
os.makedirs(SANDBOX_ROOT, exist_ok=True)

BLOCKED_PATHS = [
    "/", "/etc", "/usr", "/bin", "/sbin", "/lib", "/sys", "/proc",
    os.path.expanduser("~/.ssh"), os.path.expanduser("~/.gnupg"),
    os.path.expanduser("~/.aws"), os.path.expanduser("~/.config"),
]


class ACLManager:
    def __init__(self):
        self.allowed_paths: List[str] = []
        self.readonly_paths: List[str] = []
        self.blocked_commands = [
            "rm", "del", "rmdir", "format", "fdisk", "mkfs", "dd",
            "shred", "wipe", "reg", "delete", "drop", "truncate"
        ]
        self.restricted_commands = [
            "install", "pip", "npm", "wget", "curl", "shutdown",
            "reboot", "restart", "kill", "taskkill", "format"
        ]
    
    def is_path_safe(self, path: str) -> bool:
        abs_path = os.path.abspath(path)
        if not abs_path.startswith(os.path.abspath(SANDBOX_ROOT)):
            if not any(abs_path.startswith(os.path.abspath(p)) for p in self.allowed_paths):
                return False
        for blocked in BLOCKED_PATHS:
            if abs_path.startswith(os.path.abspath(blocked)):
                return False
        return True
    
    def is_command_safe(self, command: str) -> dict:
        cmd_lower = command.lower().strip()
        for blocked in self.blocked_commands:
            if blocked in cmd_lower:
                return {
                    "allowed": False,
                    "reason": f"Command '{blocked}' is permanently blocked",
                    "severity": "critical"
                }
        for restricted in self.restricted_commands:
            if restricted in cmd_lower:
                return {
                    "allowed": False,
                    "reason": f"Command '{restricted}' requires sudo PIN",
                    "severity": "high",
                    "requires_sudo": True
                }
        return {"allowed": True, "reason": "OK"}
    
    def allow_path(self, path: str, readonly: bool = False):
        abs_path = os.path.abspath(path)
        if abs_path not in self.allowed_paths:
            self.allowed_paths.append(abs_path)
        if readonly and abs_path not in self.readonly_paths:
            self.readonly_paths.append(abs_path)


acl = ACLManager()