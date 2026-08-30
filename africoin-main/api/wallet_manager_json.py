# wallet_manager.py uses json to save data
import json
import os
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import secrets
from typing import Optional, Dict, Any

class WalletManager:
    def __init__(self, wallet_file: str = "data/wallets.json", key_file: str = "data/master.key"):
        # Create data directory if it doesn't exist
        os.makedirs(os.path.dirname(wallet_file) if os.path.dirname(wallet_file) else '.', exist_ok=True)
        os.makedirs(os.path.dirname(key_file) if os.path.dirname(key_file) else '.', exist_ok=True)
        
        self.wallet_file = wallet_file
        self.key_file = key_file
        self.fernet = None
        self.current_address = None
        self.logger = logging.getLogger('Africoin')
        
    def initialize_wallet_system(self, password: str) -> bool:
        """Initialize the wallet system with a master password"""
        try:
            self.logger.info(f"Starting wallet initialization...")
            
            # Validate password
            if not password or len(password) < 8:
                raise Exception("Password must be at least 8 characters long")
            
            # Generate salt
            salt = secrets.token_bytes(16)
            self.logger.info(f"Generated salt: {len(salt)} bytes")
            
            # Create key derivation function
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            self.logger.info("KDF created successfully")
            
            # Derive key from password
            key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            self.logger.info(f"Key derived successfully: {len(key)} bytes")
            
            # Save master key with salt
            with open(self.key_file, 'wb') as f:
                f.write(salt + key)
            self.logger.info(f"Master key saved to: {self.key_file}")
            
            # Initialize Fernet
            self.fernet = Fernet(key)
            self.logger.info("Fernet cipher initialized")
            
            # Initialize empty wallets file
            self._save_wallets({})
            self.logger.info(f"Empty wallets file created: {self.wallet_file}")
            
            self.logger.info("Wallet system initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize wallet system: {str(e)}", exc_info=True)
            return False
    
    def load_wallet_system(self, password: str) -> bool:
        """Load existing wallet system"""
        try:
            self.logger.info(f"Attempting to load wallet system...")
            
            if not os.path.exists(self.key_file):
                self.logger.error(f"Key file not found: {self.key_file}")
                return False
            
            with open(self.key_file, 'rb') as f:
                data = f.read()
            self.logger.info(f"Read key file: {len(data)} bytes")
            
            if len(data) < 16:
                raise Exception("Key file corrupted: insufficient data")
            
            salt = data[:16]
            stored_key = data[16:]
            
            self.logger.info(f"Salt: {len(salt)} bytes, Stored key: {len(stored_key)} bytes")
            
            # Derive key from password
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            
            if key != stored_key:
                self.logger.error("Password verification failed")
                return False
            
            self.fernet = Fernet(key)
            self.logger.info("Wallet system loaded successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load wallet system: {str(e)}", exc_info=True)
            return False
    
    def create_wallet(self, wallet_name: str) -> Optional[str]:
        """Create a new wallet"""
        try:
            if not self.fernet:
                raise Exception("Wallet system not initialized. Call initialize_wallet_system() first")
            
            # Generate new private key and address
            private_key = secrets.token_hex(32)
            address = self._generate_address(private_key)
            
            # Encrypt private key
            encrypted_private_key = self.fernet.encrypt(private_key.encode()).decode()
            
            # Load existing wallets
            wallets = self._load_wallets()
            
            # Save new wallet
            wallets[address] = {
                'name': wallet_name,
                'encrypted_private_key': encrypted_private_key,
                'public_key': self._get_public_key(private_key),
                'balance': 0
            }
            
            self._save_wallets(wallets)
            self.current_address = address
            
            self.logger.info(f"Wallet created successfully: {address}")
            return address
            
        except Exception as e:
            self.logger.error(f"Failed to create wallet: {str(e)}")
            return None
    
    def import_wallet(self, private_key: str, wallet_name: str) -> Optional[str]:
        """Import existing wallet from private key"""
        try:
            if not self.fernet:
                raise Exception("Wallet system not initialized")
            
            address = self._generate_address(private_key)
            encrypted_private_key = self.fernet.encrypt(private_key.encode()).decode()
            
            wallets = self._load_wallets()
            wallets[address] = {
                'name': wallet_name,
                'encrypted_private_key': encrypted_private_key,
                'public_key': self._get_public_key(private_key),
                'balance': 0
            }
            
            self._save_wallets(wallets)
            self.current_address = address
            
            self.logger.info(f"Wallet imported successfully: {address}")
            return address
            
        except Exception as e:
            self.logger.error(f"Failed to import wallet: {str(e)}")
            return None
    
    def get_private_key(self, address: str) -> Optional[str]:
        """Get decrypted private key for address"""
        try:
            if not self.fernet:
                raise Exception("Wallet system not initialized")
            
            wallets = self._load_wallets()
            
            if address not in wallets:
                raise Exception(f"No private key for address {address}")
            
            encrypted_private_key = wallets[address]['encrypted_private_key']
            private_key = self.fernet.decrypt(encrypted_private_key.encode()).decode()
            
            return private_key
            
        except Exception as e:
            self.logger.error(f"Error getting private key: {str(e)}")
            return None
    
    def get_wallet_info(self, address: str) -> Optional[Dict[str, Any]]:
        """Get wallet information without private key"""
        try:
            wallets = self._load_wallets()
            return wallets.get(address)
        except Exception as e:
            self.logger.error(f"Error getting wallet info: {str(e)}")
            return None
    
    def list_wallets(self) -> list:
        """List all wallets"""
        try:
            wallets = self._load_wallets()
            return list(wallets.keys())
        except Exception as e:
            self.logger.error(f"Error listing wallets: {str(e)}")
            return []
    
    def _generate_address(self, private_key: str) -> str:
        """Generate Africoin address from private key"""
        # Simplified address generation - replace with your actual logic
        import hashlib
        public_key = self._get_public_key(private_key)
        address_hash = hashlib.sha256(public_key.encode()).hexdigest()[:40]
        return f"AFC{address_hash}"
    
    def _get_public_key(self, private_key: str) -> str:
        """Generate public key from private key"""
        # Simplified - replace with your actual public key generation
        import hashlib
        return hashlib.sha256(private_key.encode()).hexdigest()
    
    def _load_wallets(self) -> Dict[str, Any]:
        """Load wallets from file"""
        if not os.path.exists(self.wallet_file):
            return {}
        
        with open(self.wallet_file, 'r') as f:
            return json.load(f)
    
    def _save_wallets(self, wallets: Dict[str, Any]) -> None:
        """Save wallets to file"""
        with open(self.wallet_file, 'w') as f:
            json.dump(wallets, f, indent=2)