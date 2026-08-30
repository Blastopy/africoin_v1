import logging
from typing import Dict, Any, Optional
from wallet_manager import WalletManager
import secrets
from datetime import datetime
import os, sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from db_wallet_service import DBWalletService


class TransactionHandler:
    def __init__(self, wallet_manager: WalletManager):
        self.wallet_manager = wallet_manager
        self.db_wallet_service = DBWalletService()
        self.logger = logging.getLogger('Africoin')
        
        # Remove the problematic initialization - let WalletManager handle its own initialization
        # self._ensure_wallet_system_ready()
    
    def send_transaction(self, from_address: str, to_address: str, amount: float, user_id: str = None) -> Dict[str, Any]:
        """Send transaction with simplified approach"""
        try:
            self.logger.info(f"Attempting transaction: {from_address} -> {to_address} ({amount})")
            
            # Validate inputs
            self._validate_transaction_inputs(from_address, to_address, amount)
            
            # Check wallet system for private key access (without complex initialization)
            if not self._is_wallet_accessible_simple(from_address):
                wallets = self.wallet_manager.list_wallets()
                if from_address not in wallets:
                    raise Exception(f"Address {from_address} not found in wallet system. Available: {', '.join(wallets)}")
                else:
                    raise Exception(f"Wallet {from_address} exists but private key is not accessible")
            
            # Get private key for signing
            private_key = self.wallet_manager.get_private_key(from_address)
            if not private_key:
                raise Exception(f"No private key available for address: {from_address}")
            
            # Create and sign transaction
            transaction = self._create_transaction(from_address, to_address, amount, private_key)
            
            # Broadcast transaction
            result = self._broadcast_transaction(transaction)
            
            self.logger.info(f"Transaction successful: {result['tx_hash']}")
            return {
                'success': True,
                'tx_hash': result['tx_hash'],
                'message': 'Transaction completed successfully'
            }
            
        except Exception as e:
            self.logger.error(f"Transaction failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'message': self._get_user_friendly_error(e)
            }
    
    def _is_wallet_accessible_simple(self, address: str) -> bool:
        """Simple wallet accessibility check without complex initialization"""
        try:
            self.logger.info(f"Checking wallet accessibility for: {address}")
            
            # Just check if we can list wallets and get private key
            wallets = self.wallet_manager.list_wallets()
            if address not in wallets:
                self.logger.error(f"Address {address} not found in wallet system")
                return False
            
            private_key = self.wallet_manager.get_private_key(address)
            accessible = private_key is not None
            
            if accessible:
                self.logger.info(f"Wallet {address} is accessible")
            else:
                self.logger.error(f"Private key not accessible for {address}")
                
            return accessible
            
        except Exception as e:
            self.logger.error(f"Wallet accessibility check failed: {str(e)}")
            return False
    
    def _update_balances_after_transaction(self, from_address: str, to_address: str, amount: float, user_id: str = None):
        """Update wallet balances in database after successful transaction"""
        try:
            # Update sender balance
            sender_result = self.db_wallet_service.get_wallet_by_address(from_address)
            if sender_result['success']:
                sender_balance = sender_result['wallet']['balance']
                new_sender_balance = sender_balance - amount
                update_result = self.db_wallet_service.update_wallet_balance(from_address, new_sender_balance)
                if update_result['success']:
                    self.logger.info(f"Updated sender balance: {from_address} = {new_sender_balance}")
                else:
                    self.logger.warning(f"Failed to update sender balance: {update_result.get('error')}")
            
            # Update recipient balance
            recipient_result = self.db_wallet_service.get_wallet_by_address(to_address)
            if recipient_result['success']:
                recipient_balance = recipient_result['wallet']['balance']
                new_recipient_balance = recipient_balance + amount
                update_result = self.db_wallet_service.update_wallet_balance(to_address, new_recipient_balance)
                if update_result['success']:
                    self.logger.info(f"Updated recipient balance: {to_address} = {new_recipient_balance}")
                else:
                    self.logger.warning(f"Failed to update recipient balance: {update_result.get('error')}")
                    
        except Exception as e:
            self.logger.error(f"Error updating balances: {str(e)}")

            # Don't fail the transaction if balance update fails
    
    # ... keep the rest of your existing methods the same ...
    def _get_user_friendly_error(self, error: Exception) -> str:
        """Convert technical errors to user-friendly messages"""
        error_msg = str(error)
        
        if "not found in database" in error_msg:
            return "Wallet address not found. Please check the address and try again."
        elif "No private key" in error_msg:
            return "Wallet not accessible. Please contact support."
        elif "Wallet not accessible" in error_msg:
            return "Wallet system error. Please try again later."
        elif "not found in wallet system" in error_msg:
            return "Wallet address not found in the system."
        elif "Amount must be positive" in error_msg:
            return "Transaction amount must be greater than zero."
        elif "Cannot send to same address" in error_msg:
            return "Cannot send funds to the same wallet address."
        elif "Invalid Africoin address format" in error_msg:
            return "Invalid wallet address format."
        else:
            return "Transaction failed. Please try again."

    def _validate_transaction_inputs(self, from_address: str, to_address: str, amount: float) -> None:
        """Validate transaction inputs"""
        if not from_address or not to_address:
            raise Exception("Sender and recipient addresses are required")
        
        if amount <= 0:
            raise Exception("Amount must be positive")
        
        if from_address == to_address:
            raise Exception("Cannot send to same address")
        
        # Validate address format
        if not from_address.startswith('AFC'):
            raise Exception("Invalid sender Africoin address format")
        if not to_address.startswith('AFC'):
            raise Exception("Invalid recipient Africoin address format")
    
    def _is_wallet_accessible(self, address: str) -> bool:
        """Check if wallet is accessible in wallet system"""
        try:
            self.logger.info(f"Checking wallet accessibility for: {address}")
            
            if not self.wallet_manager.fernet:
                self.logger.error("Wallet system not initialized")
                return False
            
            wallets = self.wallet_manager.list_wallets()
            if address not in wallets:
                self.logger.error(f"Address {address} not found in wallet system")
                return False
            
            private_key = self.wallet_manager.get_private_key(address)
            accessible = private_key is not None
            
            if accessible:
                self.logger.info(f"Wallet {address} is accessible")
            else:
                self.logger.error(f"Private key not accessible for {address}")
                
            return accessible
            
        except Exception as e:
            self.logger.error(f"Wallet accessibility check failed: {str(e)}")
            return False
    
    def _create_transaction(self, from_address: str, to_address: str, amount: float, private_key: str) -> Dict[str, Any]:
        """Create and sign transaction"""
        return {
            'from': from_address,
            'to': to_address,
            'amount': amount,
            'timestamp': self._get_timestamp(),
            'signature': self._sign_transaction(from_address, to_address, amount, private_key)
        }
    
    def _sign_transaction(self, from_address: str, to_address: str, amount: float, private_key: str) -> str:
        """Sign transaction with private key"""
        import hashlib
        transaction_data = f"{from_address}{to_address}{amount}{self._get_timestamp()}"
        return hashlib.sha256((transaction_data + private_key).encode()).hexdigest()
    
    def _broadcast_transaction(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Broadcast transaction to network"""
        # Your existing broadcast logic
        return {
            'tx_hash': f"tx_{secrets.token_hex(16)}",
            'status': 'confirmed',
            'timestamp': self._get_timestamp()
        }
    
    def _get_timestamp(self) -> str:
        return datetime.now().isoformat()