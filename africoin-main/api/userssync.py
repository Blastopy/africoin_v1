from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
import os
import traceback
import hashlib
import requests
from wallet_manager import WalletManager
from api.transaction_handler import TransactionHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/africoin.log'),
        logging.StreamHandler()
    ]
)

app = Flask(__name__)
CORS(app)

# Initialize managers
wallet_manager = WalletManager()
transaction_handler = TransactionHandler(wallet_manager)

# Configuration
USERS_FILE = "data/users.json"
EXTERNAL_API_BASE_URL = "https://yourapi.com/api"  # Replace with your actual API base URL
API_AUTH_TOKEN = "your_api_auth_token"  # Replace with your actual API token

def load_users():
    """Load users from file"""
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        app.logger.error(f"Error loading users: {str(e)}")
        return {}

def save_users(users):
    """Save users to file"""
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=2)
        return True
    except Exception as e:
        app.logger.error(f"Error saving users: {str(e)}")
        return False

def hash_password(password):
    """Hash password for storage"""
    return hashlib.sha256(password.encode()).hexdigest()

def call_external_api(endpoint, method='GET', data=None):
    """Make API call to external service"""
    try:
        headers = {
            'Authorization': f'Bearer {API_AUTH_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        url = f"{EXTERNAL_API_BASE_URL}/{endpoint}"
        
        if method.upper() == 'GET':
            response = requests.get(url, headers=headers, params=data)
        elif method.upper() == 'POST':
            response = requests.post(url, headers=headers, json=data)
        elif method.upper() == 'PUT':
            response = requests.put(url, headers=headers, json=data)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.RequestException as e:
        app.logger.error(f"API call failed: {str(e)}")
        return None
    except Exception as e:
        app.logger.error(f"API call error: {str(e)}")
        return None

@app.route('/api/register', methods=['POST'])
def api_register_user():
    """Register user from external API and create wallet"""
    try:
        app.logger.info("Received API registration request")
        
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data received'
            }), 400
        
        # Validate API key (optional security measure)
        api_key = request.headers.get('X-API-Key')
        if api_key != os.getenv('INTERNAL_API_KEY', 'default_key'):
            return jsonify({
                'success': False,
                'error': 'Invalid API key'
            }), 401
        
        # Extract user data from API request
        user_data = data.get('user', {})
        
        # Required fields from API
        required_fields = ['user_id', 'username', 'email']
        for field in required_fields:
            if field not in user_data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        user_id = user_data['user_id']
        username = user_data['username']
        email = user_data['email']
        
        # Optional fields with defaults
        wallet_name = user_data.get('wallet_name', f"{username}'s Wallet")
        initial_balance = user_data.get('initial_balance', 0)
        
        app.logger.info(f"Processing registration for user: {username} (ID: {user_id})")
        
        # Load existing users
        users = load_users()
        
        # Check if user already exists
        if user_id in users:
            app.logger.info(f"User {user_id} already exists, returning existing wallet")
            existing_user = users[user_id]
            return jsonify({
                'success': True,
                'message': 'User already registered',
                'user': {
                    'user_id': user_id,
                    'username': existing_user['username'],
                    'wallet_address': existing_user['wallet_address'],
                    'existing': True
                }
            })
        
        # Check if username already exists
        for existing_user in users.values():
            if existing_user['username'] == username:
                return jsonify({
                    'success': False,
                    'error': 'Username already exists'
                }), 400
        
        # Step 1: Initialize wallet system if not already initialized
        master_password = os.getenv('WALLET_MASTER_PASSWORD', 'default_master_password_123')
        if not wallet_manager.fernet:
            app.logger.info("Initializing wallet system for API user")
            if not wallet_manager.initialize_wallet_system(master_password):
                return jsonify({
                    'success': False,
                    'error': 'Failed to initialize wallet system'
                }), 500
        
        # Step 2: Create wallet for user
        wallet_address = wallet_manager.create_wallet(wallet_name)
        
        if not wallet_address:
            return jsonify({
                'success': False,
                'error': 'Failed to create wallet for user'
            }), 500
        
        # Step 3: Set initial balance if specified
        if initial_balance > 0:
            wallets = wallet_manager._load_wallets()
            if wallet_address in wallets:
                wallets[wallet_address]['balance'] = initial_balance
                wallet_manager._save_wallets(wallets)
        
        # Step 4: Save user data locally
        users[user_id] = {
            'user_id': user_id,
            'username': username,
            'email': email,
            'wallet_address': wallet_address,
            'wallet_name': wallet_name,
            'initial_balance': initial_balance,
            'registered_via_api': True,
            'created_at': datetime.now().isoformat(),
            'api_data': user_data  # Store original API data for reference
        }
        
        if not save_users(users):
            return jsonify({
                'success': False,
                'error': 'Failed to save user data'
            }), 500
        
        # Step 5: Optional - Call webhook to notify external API
        webhook_url = data.get('webhook_url')
        if webhook_url:
            try:
                webhook_data = {
                    'user_id': user_id,
                    'username': username,
                    'wallet_address': wallet_address,
                    'status': 'created',
                    'timestamp': datetime.now().isoformat()
                }
                requests.post(webhook_url, json=webhook_data, timeout=5)
            except Exception as e:
                app.logger.warning(f"Webhook call failed: {str(e)}")
        
        app.logger.info(f"User {username} registered via API with wallet {wallet_address}")
        
        return jsonify({
            'success': True,
            'message': 'User registered successfully via API',
            'user': {
                'user_id': user_id,
                'username': username,
                'email': email,
                'wallet_address': wallet_address,
                'wallet_name': wallet_name,
                'initial_balance': initial_balance
            }
        })
        
    except Exception as e:
        app.logger.error(f"API registration error: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': f'Internal server error during API registration: {str(e)}'
        }), 500

@app.route('/api/user/<user_id>/wallet', methods=['GET'])
def get_user_wallet(user_id):
    """Get wallet information for a user via API"""
    try:
        # Validate API key
        api_key = request.headers.get('X-API-Key')
        if api_key != os.getenv('INTERNAL_API_KEY', 'default_key'):
            return jsonify({
                'success': False,
                'error': 'Invalid API key'
            }), 401
        
        users = load_users()
        
        if user_id not in users:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        user = users[user_id]
        wallet_info = wallet_manager.get_wallet_info(user['wallet_address'])
        
        return jsonify({
            'success': True,
            'user': {
                'user_id': user_id,
                'username': user['username'],
                'email': user['email'],
                'wallet_address': user['wallet_address'],
                'wallet_name': user.get('wallet_name', 'Unknown'),
                'balance': wallet_info.get('balance', 0) if wallet_info else 0,
                'created_at': user['created_at']
            }
        })
        
    except Exception as e:
        app.logger.error(f"API wallet info error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to get wallet information'
        }), 500

@app.route('/api/user/<user_id>/transaction', methods=['POST'])
def create_user_transaction(user_id):
    """Create transaction for a user via API"""
    try:
        # Validate API key
        api_key = request.headers.get('X-API-Key')
        if api_key != os.getenv('INTERNAL_API_KEY', 'default_key'):
            return jsonify({
                'success': False,
                'error': 'Invalid API key'
            }), 401
        
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data received'
            }), 400
        
        # Get user wallet
        users = load_users()
        if user_id not in users:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        user = users[user_id]
        from_address = user['wallet_address']
        
        # Required fields
        required_fields = ['to_address', 'amount']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        to_address = data['to_address']
        amount = float(data['amount'])
        
        # Create transaction
        result = transaction_handler.send_transaction(from_address, to_address, amount)
        
        if result['success']:
            # Optional: Call webhook for transaction confirmation
            webhook_url = data.get('webhook_url')
            if webhook_url:
                try:
                    webhook_data = {
                        'user_id': user_id,
                        'transaction_hash': result.get('tx_hash'),
                        'from_address': from_address,
                        'to_address': to_address,
                        'amount': amount,
                        'status': 'completed',
                        'timestamp': datetime.now().isoformat()
                    }
                    requests.post(webhook_url, json=webhook_data, timeout=5)
                except Exception as e:
                    app.logger.warning(f"Transaction webhook failed: {str(e)}")
        
        return jsonify(result)
        
    except Exception as e:
        app.logger.error(f"API transaction error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Internal server error during transaction: {str(e)}'
        }), 500

@app.route('/api/users/batch-register', methods=['POST'])
def batch_register_users():
    """Batch register multiple users via API"""
    try:
        # Validate API key
        api_key = request.headers.get('X-API-Key')
        if api_key != os.getenv('INTERNAL_API_KEY', 'default_key'):
            return jsonify({
                'success': False,
                'error': 'Invalid API key'
            }), 401
        
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data received'
            }), 400
        
        users_list = data.get('users', [])
        if not users_list:
            return jsonify({
                'success': False,
                'error': 'No users provided'
            }), 400
        
        results = {
            'successful': [],
            'failed': []
        }
        
        # Initialize wallet system if needed
        master_password = os.getenv('WALLET_MASTER_PASSWORD', 'default_master_password_123')
        if not wallet_manager.fernet:
            if not wallet_manager.initialize_wallet_system(master_password):
                return jsonify({
                    'success': False,
                    'error': 'Failed to initialize wallet system'
                }), 500
        
        for user_data in users_list:
            try:
                user_id = user_data.get('user_id')
                username = user_data.get('username')
                email = user_data.get('email')
                
                if not all([user_id, username, email]):
                    results['failed'].append({
                        'user_data': user_data,
                        'error': 'Missing required fields'
                    })
                    continue
                
                # Check if user already exists
                users = load_users()
                if user_id in users:
                    existing_user = users[user_id]
                    results['successful'].append({
                        'user_id': user_id,
                        'username': username,
                        'wallet_address': existing_user['wallet_address'],
                        'existing': True
                    })
                    continue
                
                # Create wallet
                wallet_name = user_data.get('wallet_name', f"{username}'s Wallet")
                wallet_address = wallet_manager.create_wallet(wallet_name)
                
                if wallet_address:
                    # Save user
                    users[user_id] = {
                        'user_id': user_id,
                        'username': username,
                        'email': email,
                        'wallet_address': wallet_address,
                        'wallet_name': wallet_name,
                        'registered_via_api': True,
                        'created_at': datetime.now().isoformat()
                    }
                    save_users(users)
                    
                    results['successful'].append({
                        'user_id': user_id,
                        'username': username,
                        'wallet_address': wallet_address,
                        'existing': False
                    })
                else:
                    results['failed'].append({
                        'user_data': user_data,
                        'error': 'Failed to create wallet'
                    })
                    
            except Exception as e:
                results['failed'].append({
                    'user_data': user_data,
                    'error': str(e)
                })
        
        return jsonify({
            'success': True,
            'message': f"Processed {len(users_list)} users",
            'results': results
        })
        
    except Exception as e:
        app.logger.error(f"Batch registration error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Internal server error during batch registration: {str(e)}'
        }), 500

# Add environment configuration
@app.before_first_request
def setup():
    """Setup environment"""
    os.makedirs('data', exist_ok=True)
    os.makedirs('logs', exist_ok=True)
    
    # Load wallet system on startup if master password is set
    master_password = os.getenv('WALLET_MASTER_PASSWORD')
    if master_password and os.path.exists(wallet_manager.key_file):
        wallet_manager.load_wallet_system(master_password)

# Add this import at the top
from datetime import datetime

if __name__ == '__main__':
    app.logger.info("Starting Africoin API server...")
    app.run(host='0.0.0.0', port=5000, debug=True)