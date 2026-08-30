import requests
import logging
import secrets
from flask import current_app

class WalletService:
    def __init__(self):
        self.base_url = "http://localhost:5000"
        self.api_key = "your_internal_api_key_456"
        logging.info(f"WalletService using direct config: {self.base_url}")
        
    
    def create_wallet_for_user(self, user_data):
        """Create a wallet for a new user"""
        try:
            # Skip initialization and try to create wallet directly first
            wallet_name = user_data.get('wallet_name', f"{user_data['first_name']} {user_data['last_name']}'s Wallet")
            
            payload = {
                'name': wallet_name
            }
            
            logging.info(f"Attempting to create wallet: {wallet_name}")
            
            # Try to create wallet directly
            response = requests.post(
                f"{self.base_url}/wallet/create",
                headers={'Content-Type': 'application/json'},
                json=payload,
                timeout=10
            )
            
            logging.info(f"Direct wallet creation response: {response.status_code} - {response.text}")
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    return result
                else:
                    # Wallet creation failed, try initialization first
                    logging.info("Wallet creation failed, attempting initialization...")
                    return self._create_wallet_with_initialization(user_data)
            else:
                # API error, try initialization
                logging.info(f"API error {response.status_code}, attempting initialization...")
                return self._create_wallet_with_initialization(user_data)
                
        except Exception as e:
            logging.error(f"Wallet creation failed: {str(e)}")
            return {'success': False, 'error': str(e)}

    def _create_wallet_with_initialization(self, user_data):
        """Fallback method with initialization"""
        try:
            # Initialize wallet system
            init_response = requests.post(
                f"{self.base_url}/wallet/init",
                headers={'Content-Type': 'application/json'},
                json={'password': 'default_master_password_123'},
                timeout=10
            )
            
            if init_response.status_code == 200 and init_response.json().get('success'):
                # Now create wallet
                wallet_name = user_data.get('wallet_name', f"{user_data['first_name']} {user_data['last_name']}'s Wallet")
                
                wallet_response = requests.post(
                    f"{self.base_url}/wallet/create",
                    headers={'Content-Type': 'application/json'},
                    json={'name': wallet_name},
                    timeout=10
                )
                
                return wallet_response.json()
            else:
                return {'success': False, 'error': 'Wallet system initialization failed'}
                
        except Exception as e:
            return {'success': False, 'error': f'Initialization failed: {str(e)}'}
    
    def get_wallet_balance(self, wallet_address):
        """Get wallet balance"""
        try:
            # First get the user ID from our database
            from models import User  # Import your User model
            user = User.query.filter_by(wallet_address=wallet_address).first()
            
            if not user or not user.api_user_id:
                return {'success': False, 'error': 'User or API user ID not found'}
            
            response = requests.get(
                f"{self.base_url}/api/user/{user.api_user_id}/wallet",
                headers={
                    'X-API-Key': self.api_key
                },
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                if result['success']:
                    return {'success': True, 'balance': result['user']['balance']}
                else:
                    return result
            else:
                return {'success': False, 'error': f'API returned status {response.status_code}'}
                
        except Exception as e:
            logging.error(f"Error getting wallet balance: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def send_transaction(self, from_wallet_address, to_address, amount):
        """Send transaction from user's wallet"""
        try:
            # Get user from database
            from models import User
            user = User.query.filter_by(wallet_address=from_wallet_address).first()
            
            if not user or not user.api_user_id:
                return {'success': False, 'error': 'User not found'}
            
            payload = {
                'to_address': to_address,
                'amount': amount
            }
            
            response = requests.post(
                f"{self.base_url}/api/user/{user.api_user_id}/transaction",
                headers={
                    'X-API-Key': self.api_key,
                    'Content-Type': 'application/json'
                },
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {'success': False, 'error': f'API returned status {response.status_code}'}
                
        except Exception as e:
            logging.error(f"Error sending transaction: {str(e)}")
            return {'success': False, 'error': str(e)}