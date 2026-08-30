import hashlib
import hmac
import os
import time
from typing import Optional, Dict, List
import jwt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

class AdvancedSecurity:
    def __init__(self):
        self.fernet_key = Fernet.generate_key()
        self.fernet = Fernet(self.fernet_key)
        self.failed_attempts: Dict[str, int] = {}
        self.locked_accounts: Dict[str, float] = {}
        
    def hash_password(self, password: str, salt: Optional[bytes] = None) -> Dict[str, bytes]:
        """Hash password with salt using PBKDF2"""
        if salt is None:
            salt = os.urandom(32)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return {
            'hash': key,
            'salt': salt
        }
    
    def verify_password(self, password: str, password_hash: bytes, salt: bytes) -> bool:
        """Verify password against hash"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        
        try:
            new_hash = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            return hmac.compare_digest(new_hash, password_hash)
        except Exception:
            return False
    
    def encrypt_private_key(self, private_key: str, password: str) -> str:
        """Encrypt private key with password"""
        # Derive key from password
        salt = os.urandom(32)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        
        # Encrypt private key
        f = Fernet(key)
        encrypted = f.encrypt(private_key.encode())
        
        return base64.urlsafe_b64encode(salt + encrypted).decode()
    
    def decrypt_private_key(self, encrypted_key: str, password: str) -> Optional[str]:
        """Decrypt private key with password"""
        try:
            data = base64.urlsafe_b64decode(encrypted_key.encode())
            salt = data[:32]
            encrypted = data[32:]
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            
            f = Fernet(key)
            decrypted = f.decrypt(encrypted)
            return decrypted.decode()
        except Exception:
            return None
    
    def check_rate_limit(self, identifier: str, max_attempts: int = 5, lock_time: int = 900) -> bool:
        """Check rate limiting for authentication attempts"""
        now = time.time()
        
        # Clean old lockouts
        self.locked_accounts = {k: v for k, v in self.locked_accounts.items() if v > now}
        
        # Check if account is locked
        if identifier in self.locked_accounts:
            return False
        
        # Check failed attempts
        attempts = self.failed_attempts.get(identifier, 0)
        if attempts >= max_attempts:
            self.locked_accounts[identifier] = now + lock_time
            del self.failed_attempts[identifier]
            return False
        
        return True
    
    def record_failed_attempt(self, identifier: str):
        """Record failed authentication attempt"""
        self.failed_attempts[identifier] = self.failed_attempts.get(identifier, 0) + 1
    
    def reset_attempts(self, identifier: str):
        """Reset failed attempts for identifier"""
        if identifier in self.failed_attempts:
            del self.failed_attempts[identifier]
        if identifier in self.locked_accounts:
            del self.locked_accounts[identifier]

class SecurityMonitoring:
    def __init__(self):
        self.suspicious_activities = []
        self.threat_level = "LOW"
        
    def log_suspicious_activity(self, activity: str, severity: str = "MEDIUM"):
        """Log suspicious activity"""
        event = {
            'timestamp': time.time(),
            'activity': activity,
            'severity': severity,
            'threat_level': self.threat_level
        }
        self.suspicious_activities.append(event)
        
        # Adjust threat level based on severity and frequency
        recent_events = [e for e in self.suspicious_activities 
                        if time.time() - e['timestamp'] < 3600]
        
        high_severity = sum(1 for e in recent_events if e['severity'] == "HIGH")
        
        if high_severity >= 3:
            self.threat_level = "CRITICAL"
        elif high_severity >= 1:
            self.threat_level = "HIGH"
        elif len(recent_events) >= 10:
            self.threat_level = "MEDIUM"
        else:
            self.threat_level = "LOW"
    
    def get_security_report(self) -> Dict:
        """Generate security report"""
        recent_events = [e for e in self.suspicious_activities
                        if time.time() - e['timestamp'] < 86400]
        
        return {
            'threat_level': self.threat_level,
            'events_24h': len(recent_events),
            'high_severity_events': sum(1 for e in recent_events if e['severity'] == "HIGH"),
            'recommendations': self.generate_recommendations()
        }
    
    def generate_recommendations(self) -> List[str]:
        """Generate security recommendations"""
        recommendations = []
        
        if self.threat_level == "CRITICAL":
            recommendations.extend([
                "Immediate security review required",
                "Consider temporary network isolation",
                "Activate emergency response protocol"
            ])
        elif self.threat_level == "HIGH":
            recommendations.extend([
                "Enhanced monitoring activated",
                "Review recent authentication attempts",
                "Check for unusual transaction patterns"
            ])
        
        return recommendations