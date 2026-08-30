from flask import Flask, jsonify, request, make_response
from flask_restx import Api, Resource, fields
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import jwt
import datetime
from functools import wraps
import json
import sys
import os
import logging
from wallet_manager import WalletManager
from transaction_handler import TransactionHandler
from flask_sqlalchemy import SQLAlchemy
from flask import current_app
import logging
import os
import secrets
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('Africoin')

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.blockchain import AfricoinBlockchain
from core.smart_contracts import SmartContractEngine
from web.extensions import db
from models import User
from config import settings as Config


def create_app():
    app = Flask(__name__, template_folder='web/templates', static_folder='web/static')
    
    # Set the absolute database path first
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATABASE_PATH = os.path.join(BASE_DIR, '../instance', 'users.db')
    
    # Create instance directory if it doesn't exist
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    
    # Default configuration - ensure database URI is always set
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DATABASE_PATH}'
    app.config['SECRET_KEY'] = 'Africoin2025bymainnet'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['WALLET_MASTER_PASSWORD'] = 'default_master_password_123'
    app.config['WALLET_API_URL'] = 'http://localhost:5000'
    app.config['DEBUG'] = True
    
    # Try to load from Config, but keep our defaults as fallback
    try:
        app.config.from_object(Config)
        logger.info("Configuration loaded successfully from Config")
        
        # Ensure database URI is set even if Config doesn't have it
        if not app.config.get('SQLALCHEMY_DATABASE_URI'):
            app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DATABASE_PATH}'
            logger.info("Database URI set to fallback path")
            
    except Exception as e:
        logger.error(f"Failed to load configuration from Config: {e}")
        logger.info("Using default configuration")

    # Initialize extensions
    db.init_app(app)

    with app.app_context():
        initialize_wallet_system(app)
        db.create_all()
        logger.info(f"Database initialized at: {DATABASE_PATH}")

    return app


def initialize_wallet_system(app):
    """Initialize wallet system within app context"""
    try:
        from wallet_manager import WalletManager
        from api.transaction_handler import TransactionHandler
        
        # Initialize wallet manager
        wallet_manager = WalletManager()
        transaction_handler = TransactionHandler(wallet_manager)
        
        # Store in app context for access in routes
        app.wallet_manager = wallet_manager
        app.transaction_handler = transaction_handler
        
        # Initialize wallet system
        master_password = app.config.get('WALLET_MASTER_PASSWORD', 'default_master_password_123')
        if wallet_manager.initialize_wallet_system(master_password):
            logging.info("Wallet system initialized successfully")
        else:
            logging.error("Failed to initialize wallet system")
            
    except Exception as e:
        logging.error(f"Error initializing wallet system: {str(e)}")


app = create_app()

# Enable CORS
CORS(app,
     resources={r"/*": {"origins": ["http://localhost:7070", "http://127.0.0.1:7070"]}},
     supports_credentials=True)

# Rate limiting
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
)

# Initialize REST API
api = Api(app, 
          version='1.0', 
          title='Africoin API',
          description='Enterprise Blockchain Platform API',
          doc='/api/docs/',
          serve_challenge_on_401=False
         )

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Namespaces
ns_blockchain = api.namespace('blockchain', description='Blockchain operations')
ns_wallet = api.namespace('wallet', description='Wallet operations')
ns_contracts = api.namespace('contracts', description='Smart contracts')
ns_mining = api.namespace('mining', description='Mining operations')
ns_bridge = api.namespace('bridge', description='Cross-chain operations')

# Initialize blockchain
blockchain = AfricoinBlockchain()
contract_engine = SmartContractEngine()

# Initialize managers
wallet_manager = WalletManager()
transaction_handler = TransactionHandler(wallet_manager)

# ... rest of your routes and endpoints remain the same ...


# Authentication decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):

        if request.method == "OPTIONS":
            return make_response("", 200)
        
        token = request.headers.get('Authorization')
        
        if not token:
            return {'message': 'Token is missing'}, 401
        
        try:
            token = token.replace('Bearer ', '')
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = data['user_id']
        except:
            return {'message': 'Token is invalid'}, 401
        
        return f(current_user, *args, **kwargs)
    
    return decorated

# API Models
transaction_model = api.model('Transaction', {
    'from_address': fields.String(required=True),
    'to_address': fields.String(required=True),
    'amount': fields.Float(required=True),
    'fee': fields.Float(default=0.001)
})

contract_model = api.model('Contract', {
    'template': fields.String(required=True),
    'parameters': fields.Raw(required=True),
    'gas_limit': fields.Integer(default=1000000)
})



# wallet ops
@app.before_request
def initialize_wallet_system_on_startup():
    """Initialize wallet system when the app starts"""
    try:
        logging.info("Initializing wallet system on app startup...")
        
        master_password = current_app.config.get('WALLET_MASTER_PASSWORD', 'default_master_password_123')
        logging.info(f"Using master password: {'*' * len(master_password)}")
        
        # Try to load existing wallet system first
        if not wallet_manager.load_wallet_system(master_password):
            logging.info("No existing wallet system found, initializing new one...")
            if wallet_manager.initialize_wallet_system(master_password):
                logging.info("Wallet system initialized successfully on startup")
            else:
                logging.error("Failed to initialize wallet system on startup")
        else:
            logging.info("Wallet system loaded successfully on startup")
            
        # Log wallet system status
        logging.info(f"Wallet system initialized: {wallet_manager.fernet is not None}")
        logging.info(f"Number of wallets: {len(wallet_manager.list_wallets())}")
        
    except Exception as e:
        logging.error(f"Wallet system initialization error on startup: {str(e)}")
    # Don't return anything - this is a before_request handler

# Make sure this runs before any wallet operations
@app.before_request
def ensure_wallet_system_loaded():
    """Ensure wallet system is loaded before handling wallet requests"""
    if request.endpoint and 'wallet' in request.endpoint:
        if not wallet_manager.fernet:
            logging.warning("Wallet system not loaded, attempting to load...")
            master_password = current_app.config.get('WALLET_MASTER_PASSWORD', 'default_master_password_123')
            if not wallet_manager.load_wallet_system(master_password):
                logging.error("Failed to load wallet system for wallet operation")
                # Return a proper response instead of letting the function continue
                return jsonify({'success': False, 'error': 'Wallet system not loaded'}), 500
    # Don't return anything if no wallet operation
            
@app.route('/wallet/init', methods=['POST'])
def wallet_init():
    """Initialize wallet system with master password"""
    try:
        data = request.get_json()
        password = data.get('password', 'default_master_password_123')
        
        logging.info(f"Wallet init endpoint called with password length: {len(password)}")
        
        # Check if already initialized
        if wallet_manager.fernet is not None:
            return jsonify({
                'success': True,
                'message': 'Wallet system already initialized',
                'already_initialized': True
            })
        
        if wallet_manager.initialize_wallet_system(password):
            return jsonify({
                'success': True,
                'message': 'Wallet system initialized successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to initialize wallet system'
            }), 500
            
    except Exception as e:
        app.logger.error(f"Wallet initialization error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }), 500
    
@app.route('/wallet/load', methods=['POST'])
def load_wallet_system():
    """Load existing wallet system"""
    try:
        data = request.get_json()
        password = data.get('password')
        
        if not password:
            return jsonify({
                'success': False,
                'error': 'Password is required'
            }), 400
        
        if wallet_manager.load_wallet_system(password):
            return jsonify({
                'success': True,
                'message': 'Wallet system loaded successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to load wallet system - check password'
            }), 401
            
    except Exception as e:
        app.logger.error(f"Wallet load error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error during wallet load'
        }), 500

        
@app.route('/wallet/create', methods=['POST'])
def create_wallet():
    """Create a new wallet"""
    try:
        data = request.get_json()
        wallet_name = data.get('name', 'My Africoin Wallet')
        
        # Ensure wallet system is loaded
        if not wallet_manager.fernet:
            master_password = current_app.config.get('WALLET_MASTER_PASSWORD', 'default_master_password_123')
            if not wallet_manager.initialize_wallet_system(master_password):
                return jsonify({
                    'success': False,
                    'error': 'Wallet system not loaded'
                }), 500
        
        address = wallet_manager.create_wallet(wallet_name)
        
        if address:
            return jsonify({
                'success': True,
                'address': address,
                'message': 'Wallet created successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to create wallet'
            }), 500
            
    except Exception as e:
        app.logger.error(f"Wallet creation error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Internal server error during wallet creation: {str(e)}'
        }), 500

@app.route('/wallet/import', methods=['POST'])
def import_wallet():
    """Import wallet from private key"""
    try:
        data = request.get_json()
        private_key = data.get('private_key')
        wallet_name = data.get('name', 'Imported Wallet')
        
        if not private_key:
            return jsonify({
                'success': False,
                'error': 'Private key is required'
            }), 400
        
        address = wallet_manager.import_wallet(private_key, wallet_name)
        
        if address:
            return jsonify({
                'success': True,
                'address': address,
                'message': 'Wallet imported successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to import wallet'
            }), 500
            
    except Exception as e:
        app.logger.error(f"Wallet import error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error during wallet import'
        }), 500

@app.route('/wallet/send', methods=['POST'])
def send_transaction():
    """Send transaction with comprehensive error handling"""
    try:
        # Ensure wallet system is loaded
        if not wallet_manager.fernet:
            master_password = current_app.config.get('WALLET_MASTER_PASSWORD', 'default_master_password_123')
            if not wallet_manager.initialize_wallet_system(master_password):
                return jsonify({
                    'success': False,
                    'error': 'Wallet system not loaded'
                }), 500
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['from_address', 'to_address', 'amount']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        result = transaction_handler.send_transaction(
            data['from_address'],
            data['to_address'],
            float(data['amount'])
        )
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        app.logger.error(f"Transaction error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error during transaction',
            'message': 'Please try again later'
        }), 500

@app.route('/wallet/addresses', methods=['GET'])
def list_addresses():
    """List all wallet addresses"""
    try:
        addresses = wallet_manager.list_wallets()
        return jsonify({
            'success': True,
            'addresses': addresses
        })
    except Exception as e:
        app.logger.error(f"Address list error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve wallet addresses'
        }), 500

@app.route('/wallet/status', methods=['GET'])
def wallet_status():
    """Check wallet system status"""
    try:
        addresses = wallet_manager.list_wallets()
        return jsonify({
            'success': True,
            'is_initialized': wallet_manager.fernet is not None,
            'wallet_count': len(addresses),
            'addresses': addresses
        })
    except Exception as e:
        app.logger.error(f"Status check error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to check wallet status'
        }), 500

@app.route('/wallet/debug', methods=['GET'])
def debug_wallets():
    """Debug endpoint to see all wallets"""
    try:
        # Check if wallet system is loaded
        if not wallet_manager.fernet:
            return jsonify({
                'success': False,
                'error': 'Wallet system not loaded. Call /wallet/init first.'
            }), 400
        
        # List all wallets
        wallets = wallet_manager.list_wallets()
        wallet_details = {}
        
        for address in wallets:
            wallet_info = wallet_manager.get_wallet_info(address)
            if wallet_info:
                wallet_details[address] = {
                    'name': wallet_info.get('name'),
                    'has_private_key': wallet_info.get('encrypted_private_key') is not None,
                    'balance': wallet_info.get('balance', 0)
                }
        
        return jsonify({
            'success': True,
            'total_wallets': len(wallets),
            'wallets': wallets,
            'wallet_details': wallet_details,
            'looking_for': 'AFC8b2a32e70aaae08b9f426ed471bab4884d05d007',
            'found': 'AFC8b2a32e70aaae08b9f426ed471bab4884d05d007' in wallets
        })
        
    except Exception as e:
        app.logger.error(f"Debug error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/wallet/check-address/<address>', methods=['GET'])
def check_specific_address(address):
    """Check if a specific address exists and is accessible"""
    try:
        if not wallet_manager.fernet:
            return jsonify({
                'success': False,
                'error': 'Wallet system not loaded'
            }), 400
        
        # Check if address exists
        wallets = wallet_manager.list_wallets()
        exists = address in wallets
        
        if exists:
            wallet_info = wallet_manager.get_wallet_info(address)
            private_key_accessible = wallet_manager.get_private_key(address) is not None
            
            return jsonify({
                'success': True,
                'exists': True,
                'accessible': private_key_accessible,
                'wallet_info': {
                    'name': wallet_info.get('name'),
                    'balance': wallet_info.get('balance', 0),
                    'has_encrypted_key': wallet_info.get('encrypted_private_key') is not None
                }
            })
        else:
            return jsonify({
                'success': True,
                'exists': False,
                'accessible': False,
                'message': f'Address {address} not found in wallet'
            })
            
    except Exception as e:
        app.logger.error(f"Address check error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Blockchain Endpoints
@ns_blockchain.route('/status')
class BlockchainStatus(Resource):
    @api.doc('get_blockchain_status')
    def get(self):
        """Get blockchain status"""
        status = {
            'block_height': len(blockchain.chain),
            'difficulty': blockchain.difficulty,
            'network_hashrate': blockchain.get_network_hashrate(),
            'pending_transactions': len(blockchain.pending_transactions),
            'block_reward': blockchain.get_block_reward(),
            'total_supply': blockchain.get_total_supply()
        }
        return jsonify(status)

@ns_blockchain.route('/blocks')
class BlockList(Resource):
    @api.doc('get_blocks')
    @api.param('limit', 'Number of blocks to return')
    def get(self):
        """Get recent blocks"""
        limit = min(int(request.args.get('limit', 10)), 100)
        blocks = blockchain.chain[-limit:]
        
        block_data = []
        for block in blocks:
            block_data.append({
                'index': block.index,
                'hash': block.hash,
                'previous_hash': block.previous_hash,
                'timestamp': block.timestamp,
                'transaction_count': len(block.transactions),
                'difficulty': block.difficulty
            })
        
        return jsonify(block_data)

@ns_blockchain.route('/blocks/<int:block_height>')
class BlockDetail(Resource):
    @api.doc('get_block')
    def get(self, block_height):
        """Get specific block"""
        if block_height >= len(blockchain.chain):
            return {'error': 'Block not found'}, 404
        
        block = blockchain.chain[block_height]
        transactions = []
        
        for tx in block.transactions:
            transactions.append({
                'hash': tx.tx_hash,
                'from': getattr(tx, 'sender', 'coinbase'),
                'to': tx.outputs[0].address if tx.outputs else '',
                'amount': tx.outputs[0].amount if tx.outputs else 0,
                'fee': getattr(tx, 'fee', 0)
            })
        
        return jsonify({
            'index': block.index,
            'hash': block.hash,
            'previous_hash': block.previous_hash,
            'timestamp': block.timestamp,
            'transactions': transactions,
            'nonce': block.nonce,
            'difficulty': block.difficulty
        })

@ns_blockchain.route('/transactions/<string:tx_hash>')
class TransactionDetail(Resource):
    @api.doc('get_transaction')
    def get(self, tx_hash):
        """Get transaction details"""
        transaction = blockchain.find_transaction(tx_hash)
        if not transaction:
            return {'error': 'Transaction not found'}, 404
        
        return jsonify({
            'hash': transaction.tx_hash,
            'block_height': transaction.block_height,
            'confirmations': len(blockchain.chain) - transaction.block_height,
            'inputs': [{'address': inp.address, 'amount': inp.amount} for inp in transaction.inputs],
            'outputs': [{'address': out.address, 'amount': out.amount} for out in transaction.outputs],
            'fee': transaction.fee,
            'timestamp': transaction.timestamp
        })

# Wallet Endpoints
@ns_wallet.route('/create')
class CreateWallet(Resource):
    @api.doc('create_wallet')
    @token_required
    def post(self, current_user):
        """Create new wallet"""
        address = blockchain.wallet.generate_new_address()
        return {
            'address': address,
            'message': 'Wallet created successfully'
        }

@ns_wallet.route('/balance/<string:address>')
class WalletBalance(Resource):
    @api.doc('get_balance')
    def get(self, address):
        """Get wallet balance"""
        balance = blockchain.wallet.get_balance(address)
        utxos = blockchain.wallet.get_utxos(address)
        
        return jsonify({
            'address': address,
            'balance': balance,
            'utxo_count': len(utxos),
            'utxos': [{
                'tx_hash': utxo.tx_hash,
                'amount': utxo.amount,
                'confirmations': blockchain.get_confirmations(utxo.tx_hash)
            } for utxo in utxos[:10]]  # Limit to 10 UTXOs
        })

@ns_wallet.route('/send', methods=['POST', 'OPTIONS'])
class SendTransaction(Resource):
    @api.doc('send_transaction')
    
    def options(self):
        return {}, 200
    
    @api.expect(transaction_model)
    @token_required
    def post(self, current_user):
        """Send transaction"""
        data = request.get_json()
        
        transaction = blockchain.wallet.create_transaction(
            data['from_address'],
            data['to_address'],
            data['amount'],
            data.get('fee', 0.001)
        )
        
        if transaction:
            blockchain.pending_transactions.append(transaction)
            
            # Broadcast to network
            blockchain.network.broadcast_transaction(transaction)
            
            return {
                'success': True,
                'tx_hash': transaction.tx_hash,
                'message': 'Transaction created and broadcasted'
            }
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to create transaction'
            }), 400

# Smart Contract Endpoints
@ns_contracts.route('/deploy')
class DeployContract(Resource):
    @api.doc('deploy_contract')
    @api.expect(contract_model)
    @token_required
    def post(self, current_user):
        """Deploy smart contract"""
        data = request.get_json()
        
        try:
            contract_id = contract_engine.deploy_contract(
                data['template'],
                current_user,
                data['parameters']
            )
            
            return jsonify({
                'success': True,
                'contract_id': contract_id,
                'message': 'Contract deployed successfully'
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 400

@ns_contracts.route('/execute/<string:contract_id>')
class ExecuteContract(Resource):
    @api.doc('execute_contract')
    @api.param('function', 'Function to execute')
    @api.param('args', 'Function arguments as JSON array')
    @token_required
    def post(self, current_user, contract_id):
        """Execute contract function"""
        function = request.args.get('function')
        args = request.get_json()
        
        try:
            result = contract_engine.execute_contract(
                contract_id,
                function,
                args,
                current_user
            )
            
            return jsonify(result)
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 400

# Mining Endpoints
@ns_mining.route('/pool/join')
class JoinMiningPool(Resource):
    @api.doc('join_mining_pool')
    @api.param('address', 'Miner payout address')
    def post(self):
        """Join mining pool"""
        address = request.args.get('address')
        
        if not address:
            return {'error': 'Address required'}, 400
        
        pool_info = blockchain.mining_pool.add_miner(address)
        return jsonify(pool_info)

@ns_mining.route('/pool/stats')
class PoolStats(Resource):
    @api.doc('get_pool_stats')
    def get(self):
        """Get mining pool statistics"""
        stats = blockchain.mining_pool.get_stats()
        return jsonify(stats)

# Cross-chain Bridge Endpoints
@ns_bridge.route('/lock')
class LockFunds(Resource):
    @api.doc('lock_funds')
    @api.param('target_chain', 'Target blockchain')
    @api.param('amount', 'Amount to bridge')
    @token_required
    def post(self, current_user):
        """Lock funds for cross-chain transfer"""
        target_chain = request.args.get('target_chain')
        amount = float(request.args.get('amount'))
        
        try:
            result = blockchain.cross_chain_bridge.lock_funds(
                current_user,
                target_chain,
                amount
            )
            return jsonify(result)
        except Exception as e:
            return jsonify({'error': str(e)}), 400

@app.route('/fix-wallet/<address>')
def fix_specific_wallet(address):
    """Fix a specific wallet that's causing issues"""
    try:
        from models import User, Wallet
        
        wallet_manager = WalletManager()
        
        # Initialize wallet system
        master_password = current_app.config.get('WALLET_MASTER_PASSWORD', 'default_master_password_123')
        if not wallet_manager.load_wallet_system(master_password):
            return jsonify({'success': False, 'error': 'Failed to load wallet system'})
        
        # Check if wallet exists in wallet system
        wallets = wallet_manager.list_wallets()
        if address not in wallets:
            return jsonify({'success': False, 'error': f'Wallet {address} not found in wallet system'})
        
        # Check if already in database
        existing_wallet = Wallet.query.filter_by(address=address).first()
        if existing_wallet:
            return jsonify({'success': True, 'message': 'Wallet already exists in database', 'wallet': existing_wallet.address})
        
        # Find user by address
        user = User.query.filter_by(wallet_address=address).first()
        
        # Get wallet info
        wallet_info = wallet_manager.get_wallet_info(address)
        
        # Create wallet record
        wallet = Wallet(
            wallet_address=address,
            wallet_name=wallet_info.get('name', 'Fixed Wallet'),
            encrypted_private_key=None,
            public_key=wallet_info.get('public_key', ''),
            balance=wallet_info.get('balance', 0),
            user_id=user.id if user else None,
            is_active=True
        )
        
        db.session.add(wallet)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Wallet {wallet_address} synced successfully',
            'user': user.username if user else 'orphan'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    
@app.route('/debug/wallet-status')
def debug_wallet_status():
    """Debug route to check wallet system status"""
    status = {
        'wallet_system_initialized': wallet_manager.fernet is not None,
        'is_initialized_flag': wallet_manager.is_initialized,
        'master_password_set': bool(current_app.config.get('WALLET_MASTER_PASSWORD')),
        'total_wallets_in_db': User.query.filter_by(is_active=True).count(),
        'total_wallets_in_system': len(wallet_manager.list_wallets()),
        'config_keys': [key for key in current_app.config.keys() if 'WALLET' in key or 'PASSWORD' in key]
    }
    
    # Try to initialize if not initialized
    if not wallet_manager.fernet:
        master_password = current_app.config.get('WALLET_MASTER_PASSWORD', 'default_master_password_123')
        status['initialization_attempt'] = wallet_manager.initialize_wallet_system(master_password)
        status['initialized_after_attempt'] = wallet_manager.fernet is not None
    
    return jsonify(status)

@app.route('/debug/init-wallet')
def debug_init_wallet():
    """Debug route to manually initialize wallet system"""
    try:
        master_password = current_app.config.get('WALLET_MASTER_PASSWORD', 'default_master_password_123')
        
        if wallet_manager.initialize_wallet_system(master_password):
            return jsonify({
                'success': True,
                'message': 'Wallet system initialized successfully',
                'fernet_initialized': wallet_manager.fernet is not None
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to initialize wallet system'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/debug/test-wallet/<address>')
def debug_test_wallet(address):
    """Test a specific wallet"""
    try:
        # Ensure wallet system is loaded
        master_password = current_app.config.get('WALLET_MASTER_PASSWORD', 'default_master_password_123')
        if not wallet_manager.fernet:
            wallet_manager.initialize_wallet_system(master_password)
        
        wallet_info = wallet_manager.get_wallet_info(address)
        private_key_accessible = wallet_manager.get_private_key(address) is not None
        
        return jsonify({
            'success': True,
            'address': address,
            'wallet_info': wallet_info,
            'private_key_accessible': private_key_accessible,
            'fernet_initialized': wallet_manager.fernet is not None
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/debug/wallet-private-key/<address>')
def debug_wallet_private_key(address):
    """Debug private key access for a specific wallet"""
    try:
        # Get wallet from database
        wallet = User.query.filter_by(address=address).first()
        
        if not wallet:
            return jsonify({
                'success': False,
                'error': 'Wallet not found in database'
            })
        
        wallet_info = {
            'address': wallet.wallet_address,
            'name': wallet.wallet_name,
            'has_encrypted_private_key': bool(wallet.encrypted_private_key),
            'encrypted_private_key_length': len(wallet.encrypted_private_key) if wallet.encrypted_private_key else 0,
            'user_id': wallet.user_id,
            'balance': wallet.balance,
            'is_active': wallet.is_active
        }
        
        # Try to get private key
        try:
            private_key = wallet_manager.get_private_key(address)
            wallet_info['private_key_accessible'] = private_key is not None
            wallet_info['private_key_length'] = len(private_key) if private_key else 0
        except Exception as e:
            wallet_info['private_key_error'] = str(e)
            wallet_info['private_key_accessible'] = False
        
        return jsonify({
            'success': True,
            'wallet_info': wallet_info,
            'fernet_initialized': wallet_manager.fernet is not None
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/admin/fix-wallet-keys')
def admin_fix_wallet_keys():
    """Fix wallets that are missing encrypted private keys"""
    try:
        from models import User
        
        wallets_fixed = 0
        wallets_skipped = 0
        errors = []
        
        # Get all wallets from database
        all_wallets = User.query.all()
        
        for wallet in all_wallets:
            try:
                # Check if wallet has encrypted private key
                if not wallet.encrypted_private_key:
                    self.logger.warning(f"Wallet {wallet.address} missing encrypted private key")
                    
                    # Check if wallet exists in wallet system and we can access it
                    if wallet.address in wallet_manager.list_wallets():
                        # Try to get the private key (this will fail but we'll handle it)
                        try:
                            private_key = wallet_manager.get_private_key(wallet.address)
                            if private_key:
                                # Re-encrypt and store
                                encrypted_private_key = wallet_manager.fernet.encrypt(private_key.encode()).decode()
                                wallet.encrypted_private_key = encrypted_private_key
                                wallets_fixed += 1
                                self.logger.info(f"Fixed private key for: {wallet.address}")
                            else:
                                # Generate new private key for this wallet
                                new_private_key = secrets.token_hex(32)
                                encrypted_private_key = wallet_manager.fernet.encrypt(new_private_key.encode()).decode()
                                wallet.encrypted_private_key = encrypted_private_key
                                wallets_fixed += 1
                                self.logger.info(f"Generated new private key for: {wallet.address}")
                        except:
                            # Generate new private key
                            new_private_key = secrets.token_hex(32)
                            encrypted_private_key = wallet_manager.fernet.encrypt(new_private_key.encode()).decode()
                            wallet.encrypted_private_key = encrypted_private_key
                            wallets_fixed += 1
                            self.logger.info(f"Generated new private key for: {wallet.address}")
                    else:
                        # Wallet doesn't exist in wallet system, create new private key
                        new_private_key = secrets.token_hex(32)
                        encrypted_private_key = wallet_manager.fernet.encrypt(new_private_key.encode()).decode()
                        wallet.encrypted_private_key = encrypted_private_key
                        wallets_fixed += 1
                        self.logger.info(f"Generated new private key for missing wallet: {wallet.address}")
                else:
                    wallets_skipped += 1
                    
            except Exception as e:
                errors.append({
                    'wallet': wallet.address,
                    'error': str(e)
                })
                self.logger.error(f"Error fixing wallet {wallet.address}: {str(e)}")
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Fixed {wallets_fixed} wallets, skipped {wallets_skipped}',
            'errors': errors
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    
@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin")
    allowed = ["http://localhost:7070", "http://127.0.0.1:7070"]

    if origin in allowed:
        response.headers["Access-Control-Allow-Origin"] = origin

    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)