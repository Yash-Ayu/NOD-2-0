"""
NOD 2.0 - Sensitive Data Scanner
Auto-detects financial documents, IDs, passwords
"""
import re
import os
from pathlib import Path
from typing import List, Dict

PATTERNS = {
    "pan_card": {
        "regex": r"[A-Z]{5}[0-9]{4}[A-Z]{1}",
        "description": "Indian PAN Card Number",
        "severity": "critical"
    },
    "aadhaar": {
        "regex": r"\b\d{4}\s?\d{4}\s?\d{4}\b",
        "description": "Indian Aadhaar Number",
        "severity": "critical"
    },
    "credit_card": {
        "regex": r"\b(?:\d{4}[- ]?){3}\d{4}\b",
        "description": "Credit/Debit Card Number",
        "severity": "critical"
    },
    "bank_account": {
        "regex": r"\b\d{9,18}\b",
        "description": "Potential Bank Account Number",
        "severity": "high"
    },
    "upi_id": {
        "regex": r"[a-zA-Z0-9._-]+@[a-zA-Z]{3,}",
        "description": "UPI ID",
        "severity": "high"
    },
    "ifsc_code": {
        "regex": r"[A-Z]{4}0[A-Z0-9]{6}",
        "description": "IFSC Code",
        "severity": "medium"
    },
    "password": {
        "regex": r"(?i)(password|passwd|pwd)\s*[:=]\s*\S+",
        "description": "Password in plaintext",
        "severity": "critical"
    },
    "api_key": {
        "regex": r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*['\"]?[a-zA-Z0-9_-]{16,}['\"]?",
        "description": "API Key or Secret",
        "severity": "critical"
    },
}

SENSITIVE_KEYWORDS = [
    "salary", "income", "tax", "itr", "form16", "bank_statement",
    "passbook", "cheque", "investment", "insurance", "loan",
    "credit_score", "kyc", "passport", "driving_license", "voter_id"
]


class SensitiveDataScanner:
    def __init__(self):
        self.patterns = PATTERNS
        self.keywords = SENSITIVE_KEYWORDS
    
    def scan_text(self, text: str) -> List[Dict]:
        findings = []
        for name, pattern in self.patterns.items():
            matches = re.finditer(pattern["regex"], text)
            for match in matches:
                value = match.group()
                masked = value[:2] + "*" * (len(value) - 4) + value[-2:] if len(value) > 4 else "****"
                findings.append({
                    "type": name,
                    "description": pattern["description"],
                    "severity": pattern["severity"],
                    "masked_value": masked,
                    "requires_vault": pattern["severity"] == "critical"
                })
        return findings
    
    def scan_file(self, file_path: str) -> Dict:
        result = {
            "file": file_path,
            "is_sensitive": False,
            "findings": [],
            "recommended_action": "none"
        }
        filename_lower = os.path.basename(file_path).lower()
        for keyword in self.keywords:
            if keyword in filename_lower:
                result["findings"].append({
                    "type": "filename_keyword",
                    "description": f"Filename contains: {keyword}",
                    "severity": "high",
                    "requires_vault": True
                })
                result["is_sensitive"] = True
        
        text_extensions = {".txt", ".md", ".csv", ".json", ".xml", ".html", ".py", ".js", ".css", ".log", ".env"}
        if Path(file_path).suffix.lower() in text_extensions:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text_findings = self.scan_text(f.read())
                    if text_findings:
                        result["findings"].extend(text_findings)
                        result["is_sensitive"] = True
            except:
                pass
        
        if any(f.get("requires_vault") for f in result["findings"]):
            result["recommended_action"] = "move_to_vault"
        elif result["is_sensitive"]:
            result["recommended_action"] = "encrypt"
        return result


scanner = SensitiveDataScanner()