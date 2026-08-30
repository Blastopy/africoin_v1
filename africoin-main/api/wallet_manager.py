# wallet_manager.py
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import secrets
import hashlib
from typing import Optional, Dict, Any
import os, sys
import json
from datetime import datetime
import logging

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from models import User, WalletMeta # Import your models
from web.extensions import db  # Import your database instance

class WalletManager:
    def __init__(self):
        self.fernet = None
        self.is_initialized = False
        self.logger = logging.getLogger('wallet_manager')
        self.wallets_file = 'wallets.json'

    def store_salt_db(self, salt: bytes, iterations: int = 390000):
        meta = WalletMeta.query.get(1)

        if meta is None:
            meta = WalletMeta(
                id=1,
                salt=salt,
                iterations=iterations,
                version=1
            )
            db.session.add(meta)
        else:
            meta.salt = salt
            meta.iterations = iterations

        db.session.commit()
    def load_salt_db(self):
        meta = WalletMeta.query.get(1)

        if meta is None:
            raise Exception("Wallet not initialized — no metadata found.")

        return meta.salt, meta.iterations

    def unlock_wallet_system(self, password: str):
        salt, iterations = self.load_salt_db()

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=iterations,
        )

        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        self.fernet = Fernet(key)
        self.is_initialized = True

            
    def initialize_wallet_system(self, master_password):
        """Initialize the wallet system with master password"""
        try:
            # Check if already initialized - if so, return True (success)
            if self.fernet is not None and self.is_initialized:
                logging.info("Wallet system already initialized - returning success")
                return True
            
            logging.info(f"Initializing new wallet system with master password")
            
            # Validate master password
            if not master_password or len(master_password) < 8:
                logging.error("Master password is too short or empty")
                return False
            
            # Generate encryption key from master password
            from cryptography.fernet import Fernet
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            import base64
            
            # Use a fixed salt for development
            salt = b'africoin_salt_2025'
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            
            key = base64.urlsafe_b64encode(kdf.derive(master_password.encode()))
            self.fernet = Fernet(key)
            self.is_initialized = True
            
            # Initialize empty wallets file if it doesn't exist
            if not os.path.exists(self.wallets_file):
                with open(self.wallets_file, 'w') as f:
                    json.dump({}, f)
            
            logging.info("Wallet system initialized successfully")
            return True
            
        except Exception as e:
            logging.error(f"Wallet system initialization failed: {str(e)}")
            self.fernet = None
            self.is_initialized = False
            return False
    
    def load_wallet_system(self, master_password):
        """Load existing wallet system"""
        try:
            # For now, just try to initialize
            # In a real implementation, you'd load existing encrypted data
            return self.initialize_wallet_system(master_password)
        except Exception as e:
            logging.error(f"Failed to load wallet system: {str(e)}")
            return False

    
    def create_wallet(self, wallet_name="My Africoin Wallet"):
        """Create a new wallet - returns wallet address only"""
        try:
            if not self.fernet:
                logging.error("Wallet system not initialized")
                return None
            
            # Generate new wallet (cryptographic key pair)
            private_key = secrets.token_hex(32)
            public_key = hashlib.sha256(private_key.encode()).hexdigest()
            
            # Generate Africoin-style address
            wallet_address = f"AFC{public_key[:40]}"
            
            # Encrypt private key
            encrypted_private_key = self.fernet.encrypt(private_key.encode()).decode()
            
            # Store wallet in simple JSON file (for now)
            wallets = {}
            if os.path.exists(self.wallets_file):
                with open(self.wallets_file, 'r') as f:
                    wallets = json.load(f)
            

            wallet_data = {
                'wallet_name': wallet_name,
                'wallet_address': wallet_address,
                'encrypted_private_key': encrypted_private_key,
                'public_key': public_key,
                'balance': 0.0,
                'created_at': datetime.utcnow().isoformat()
            }
            
            wallets[wallet_address] = wallet_data
            
            with open(self.wallets_file, 'w') as f:
                json.dump(wallets, f, indent=2)
            
            logging.info(f"Wallet created: {wallet_address}")
            return wallet_address
            
        except Exception as e:
            logging.error(f"Failed to create wallet: {str(e)}")
            return None                                 
    
    def import_wallet(self, private_key: str, wallet_name: str, id: int = None) -> Optional[str]:
        """Import existing wallet from private key and store in database"""
        try:
            if not self.fernet:
                raise Exception("Wallet system not initialized")
            
            wallet_address = self._generate_wallet_address(private_key)
            encrypted_private_key = self.fernet.encrypt(private_key.encode()).decode()
            public_key = self._get_public_key(private_key)
            
            # Check if wallet already exists
            existing_wallet = User.query.filter_by(wallet_address=wallet_address).first()
            if existing_wallet:
                self.logger.warning(f"Wallet already exists: {wallet_address}")
                return wallet_address
            
            # Create wallet in database
            wallet = User(
                wallet_address=wallet_address,
                name=wallet_name,
                encrypted_private_key=encrypted_private_key,
                public_key=public_key,
                balance=0.0,
                id=id,
                is_active=True
            )
            
            db.session.add(wallet)
            db.session.commit()
            
            # If id provided, update user's wallet_wallet_address
            if id:
                user = User.query.get(id)
                if user:
                    user.wallet_wallet_address = wallet_address
                    db.session.commit()
            
            self.current_wallet_address = wallet_address
            self.logger.info(f"Wallet imported successfully: {wallet_address} for user {id}")
            return wallet_address
            
        except Exception as e:
            self.logger.error(f"Failed to import wallet: {str(e)}")
            db.session.rollback()
            return None
    
    def get_private_key(self, wallet_address: str) -> Optional[str]:
        """Get decrypted private key for wallet_address from database"""
        try:
            if not self.fernet:
                raise Exception("Wallet system not initialized")
            
            # Get wallet from database
            wallet = User.query.filter_by(wallet_address=wallet_address, is_active=True).first()
            
            if not wallet:
                raise Exception(f"No wallet found for wallet_address {wallet_address}")
            
            if not wallet.encrypted_private_key:
                raise Exception(f"No private key stored for wallet_address {wallet_address}")
            
            # Decrypt private key
            private_key = self.fernet.decrypt(wallet.encrypted_private_key.encode()).decode()
            
            return private_key
            
        except Exception as e:
            self.logger.error(f"Error getting private key: {str(e)}")
            return None
    
    def get_wallet_info(self, wallet_address: str) -> Optional[Dict[str, Any]]:
        """Get wallet information without private key from database"""
        try:
            wallet = User.query.filter_by(wallet_address=wallet_address, is_active=True).first()
            
            if not wallet:
                return None
            
            return {
                'name': wallet.wallet_name,
                'public_key': wallet.public_key,
                'balance': wallet.balance,
                'id': wallet.id,
                'created_at': wallet.created_at.isoformat() if wallet.created_at else None,
                'is_active': wallet.is_active
            }
            
        except Exception as e:
            self.logger.error(f"Error getting wallet info: {str(e)}")
            return None
    
    def list_wallets(self) -> list:
        """List all wallet wallet_addresses from database"""
        try:
            wallets = User.query.filter_by(is_active=True).with_entities(User.wallet_address).all()
            return [wallet.wallet_address for wallet in wallets]
        except Exception as e:
            self.logger.error(f"Error listing wallets: {str(e)}")
            return []
    
    def get_wallet_by_id(self, id: int) -> Optional[Dict[str, Any]]:
        """Get wallet by user ID"""
        try:
            wallet = User.query.filter_by(id=id, is_active=True).first()
            
            if not wallet:
                return None
            
            return {
                'wallet_address': wallet.wallet_address,
                'name': wallet.name,
                'balance': wallet.balance,
                'public_key': wallet.public_key,
                'created_at': wallet.created_at.isoformat() if wallet.created_at else None
            }
            
        except Exception as e:
            self.logger.error(f"Error getting wallet by user ID: {str(e)}")
            return None
    
    def update_wallet_balance(self, wallet_address: str, new_balance: float) -> bool:
        """Update wallet balance in database"""
        try:
            wallet = User.query.filter_by(wallet_address=wallet_address, is_active=True).first()
            
            if not wallet:
                raise Exception(f"Wallet not found: {wallet_address}")
            
            old_balance = wallet.balance
            wallet.balance = new_balance
            db.session.commit()
            
            self.logger.info(f"Updated balance for {wallet_address}: {old_balance} -> {new_balance}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating wallet balance: {str(e)}")
            db.session.rollback()
            return False
    
    def get_wallet_balance(self, wallet_address: str) -> Optional[float]:
        """Get wallet balance from database"""
        try:
            wallet = User.query.filter_by(wallet_address=wallet_address, is_active=True).first()
            
            if not wallet:
                raise Exception(f"Wallet not found: {wallet_address}")
            
            return wallet.balance
            
        except Exception as e:
            self.logger.error(f"Error getting wallet balance: {str(e)}")
            return None
    
    def delete_wallet(self, wallet_address: str) -> bool:
        """Soft delete wallet (set is_active to False)"""
        try:
            wallet = User.query.filter_by(wallet_address=wallet_address).first()
            
            if not wallet:
                raise Exception(f"Wallet not found: {wallet_address}")
            
            wallet.is_active = False
            db.session.commit()
            
            self.logger.info(f"Wallet deactivated: {wallet_address}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting wallet: {str(e)}")
            db.session.rollback()
            return False
    
    def get_all_wallets_info(self) -> list:
        """Get information for all wallets"""
        try:
            wallets = User.query.filter_by(is_active=True).all()
            wallet_list = []
            
            for wallet in wallets:
                wallet_list.append({
                    'wallet_address': wallet.wallet_address,
                    'name': wallet.name,
                    'balance': wallet.balance,
                    'id': wallet.id,
                    'created_at': wallet.created_at.isoformat() if wallet.created_at else None,
                    'user_username': wallet.owner.username if wallet.owner else None
                })
            
            return wallet_list
            
        except Exception as e:
            self.logger.error(f"Error getting all wallets info: {str(e)}")
            return []
    
    def _generate_wallet_address(self, private_key: str) -> str:
        """Generate Africoin wallet_address from private key"""
        public_key = self._get_public_key(private_key)
        wallet_address_hash = hashlib.sha256(public_key.encode()).hexdigest()[:40]
        return f"AFC{wallet_address_hash}"
    
    def _get_public_key(self, private_key: str) -> str:
        """Generate public key from private key"""
        return hashlib.sha256(private_key.encode()).hexdigest()
    