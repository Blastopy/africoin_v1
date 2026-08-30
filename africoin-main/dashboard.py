from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, make_response
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import secrets
import json
from datetime import datetime, timedelta
from models import Contract, Transaction
from sqlalchemy import func, or_
import threading
import time
from web.data_entry import (RegistrationForms, LoginForm, UpdateProfileForm, ChangePasswordForm, PreferencesForm, ResetPasswordRequestForm, ResetPasswordForm)
from web.extensions import db
from models import User
from urllib.parse import urlparse
import jwt
import requests
import logging
from services.wallet_service import WalletService
from api.wallet_manager import WalletManager
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.fernet import Fernet
import os
import hashlib

# Any outbound HTTP call (exchange rate, wallet API) must never be allowed to
# hang forever on a single-threaded/low-worker deployment - it would freeze
# the whole site for every visitor. Keep this short and always pass it.
HTTP_TIMEOUT = 5

logging.basicConfig(level=logging.INFO)
login_manager = LoginManager()


# ---------------------------------------------------------------------------
# Exchange rate cache
# A blocking network call to api.frankfurter.app on every /profile and /wallet
# request is slow and, worse, has no timeout - if that API is briefly slow,
# every request to those pages stalls. Cache the rate for a while and always
# fall back to the last known-good value (or a sane default) on failure.
# ---------------------------------------------------------------------------
_exchange_rate_cache = {'rate': 18.0, 'fetched_at': 0}
EXCHANGE_RATE_TTL = 3600  # 1 hour


def get_usd_zar_rate():
    """Return the USD->ZAR rate, cached for EXCHANGE_RATE_TTL seconds."""
    now = time.time()
    if now - _exchange_rate_cache['fetched_at'] < EXCHANGE_RATE_TTL:
        return _exchange_rate_cache['rate']

    try:
        r = requests.get('https://api.frankfurter.app/latest?from=USD', timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        rate = r.json()['rates']['ZAR']
        _exchange_rate_cache['rate'] = rate
        _exchange_rate_cache['fetched_at'] = now
    except Exception as e:
        logging.warning(f"Exchange rate fetch failed, using cached/default value: {e}")

    return _exchange_rate_cache['rate']


def create_app():
    app = Flask(__name__, template_folder='web/templates', static_folder='web/static')
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATABASE_PATH = os.path.join(BASE_DIR, 'instance', 'users.db')
    # Create instance directory if it doesn't exist
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DATABASE_PATH}'
    # Allow overriding the secret key in production via env var, fall back to
    # the existing default so local/dev behaviour is unchanged.
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'Africoin2025bymainnet')
    db.init_app(app)

    bcrypt = Bcrypt(app)
    login_manager.init_app(app)
    login_manager.login_view = 'login'


    with app.app_context():
        db.create_all()

    return app

app = create_app()
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class AfricoinDashboard:
    def __init__(self, api_url=None):
        # Read from env so this can point at a real deployed blockchain API
        # service in production instead of a hardcoded localhost URL.
        self.api_url = (api_url or os.environ.get('WALLET_API_URL', 'http://localhost:5000')).rstrip('/')
        self.cache = {}
        self.cache_timeout = 30  # seconds
        self.last_update = 0
        
    def get_blockchain_stats(self):
        """Get blockchain statistics"""
        if time.time() - self.last_update < self.cache_timeout:
            return self.cache.get('stats', {})
        
        try:
            response = requests.get(f"{self.api_url}/blockchain/status", timeout=HTTP_TIMEOUT)
            response.raise_for_status()
            stats = response.json()
            
            self.cache['stats'] = stats
            self.last_update = time.time()

            return stats
        except Exception as e:
            logging.warning(f"get_blockchain_stats failed: {e}")
            # Serve last known-good cached stats (if any) rather than an error
            # blob the template isn't expecting, and don't hammer a dead API
            # on every single request.
            self.last_update = time.time()
            return self.cache.get('stats', {})
    
    def get_recent_blocks(self, limit=10):
        """Get recent blocks"""
        try:
            response = requests.get(f"{self.api_url}/blockchain/blocks", params={'limit': limit}, timeout=HTTP_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.warning(f"get_recent_blocks failed: {e}")
            return []
    
    def get_network_info(self):
        """Get network information"""
        try:
            # Mock network data - in production, this would come from multiple nodes
            return {
                'node_count': 42,
                'peer_count': 156,
                'network_hashrate': '15.2 TH/s',
                'avg_block_time': '9.8s',
                'transaction_volume_24h': '1,250,000 AFC'
            }
        except Exception as e:
            return {'error': str(e)}

# Dashboard routes
# dashboard = AfricoinDashboard()

@app.route('/')
def index():
    """Main dashboard page"""
    dashboard = AfricoinDashboard()
    stats = dashboard.get_blockchain_stats()
    recent_blocks = dashboard.get_recent_blocks(5)
    network_info = dashboard.get_network_info()
    
    return render_template('index.html',
                         stats=stats,
                         recent_blocks=recent_blocks,
                         network_info=network_info)

@app.route('/blocks')
def blocks_page():
    """Blocks explorer page"""
    dashboard = AfricoinDashboard()
    blocks = dashboard.get_recent_blocks(50)
    return render_template('blocks.html', blocks=blocks)

@app.route('/transactions')
def transactions_page():
    """Transactions page"""
    return render_template('transactions.html')


@app.route('/mining')
def mining_page():
    """Mining dashboard page"""
    return render_template('mining.html')


# @app.route('/api/dashboard/stats')
# def api_dashboard_stats():
#     """API endpoint for dashboard statistics"""
#     stats = dashboard.get_blockchain_stats()
#     return jsonify(stats)

@app.route('/api/dashboard/blocks')
def api_dashboard_blocks():
    """API endpoint for blocks data"""
    limit = request.args.get('limit', 10, type=int)
    # NOTE: previously referenced an undefined module-level `dashboard`
    # object and 500'd on every call - instantiate one here instead.
    dashboard_obj = AfricoinDashboard()
    blocks = dashboard_obj.get_recent_blocks(limit)
    return jsonify(blocks)


# ---------------------------------------------------------------------------
# Real transactions API - backs the Transactions Explorer page.
# Replaces the client-side generateMockTransactions() fake data with actual
# rows from the Transaction table, paginated and filtered server-side so the
# browser never has to generate/hold thousands of fake records.
# ---------------------------------------------------------------------------
def _tx_to_dict(tx):
    return {
        'hash': tx.tx_hash or f'pending-{tx.id}',
        'from': tx.from_address or 'unknown',
        'to': tx.to_address or 'unknown',
        'amount': tx.amount or 0.0,
        'fee': tx.fee or 0.0,
        'status': tx.status or 'pending',
        'confirmations': tx.confirmations or 0,
        'block': tx.block_height,
        'timestamp': int(tx.created_at.timestamp() * 1000) if tx.created_at else None,
        'type': tx.type or 'transfer',
    }


@app.route('/api/transactions')
def api_transactions():
    """Paginated, filterable, real transaction data."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 15, type=int), 500)
    status = request.args.get('status', 'all')
    tx_type = request.args.get('type', 'all')
    time_range = request.args.get('time_range', 'all')
    search = request.args.get('search', '').strip()
    min_amount = request.args.get('min_amount', type=float)
    max_amount = request.args.get('max_amount', type=float)

    query = Transaction.query

    if status != 'all':
        query = query.filter(Transaction.status == status)
    if tx_type != 'all':
        query = query.filter(Transaction.type == tx_type)

    if time_range != 'all':
        deltas = {
            '1h': timedelta(hours=1),
            '24h': timedelta(hours=24),
            '7d': timedelta(days=7),
            '30d': timedelta(days=30),
        }
        if time_range in deltas:
            query = query.filter(Transaction.created_at >= datetime.utcnow() - deltas[time_range])

    if min_amount is not None:
        query = query.filter(Transaction.amount >= min_amount)
    if max_amount is not None:
        query = query.filter(Transaction.amount <= max_amount)

    if search:
        like = f'%{search}%'
        query = query.filter(or_(
            Transaction.tx_hash.ilike(like),
            Transaction.from_address.ilike(like),
            Transaction.to_address.ilike(like),
        ))

    query = query.order_by(Transaction.created_at.desc())

    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()

    return jsonify({
        'transactions': [_tx_to_dict(tx) for tx in items],
        'page': page,
        'per_page': per_page,
        'total': total,
        'total_pages': max(1, (total + per_page - 1) // per_page),
    })


@app.route('/api/transactions/stats')
def api_transactions_stats():
    """Aggregate stats + hourly buckets for the Transactions Explorer charts."""
    now = datetime.utcnow()
    day_ago = now - timedelta(hours=24)

    total_count = db.session.query(func.count(Transaction.id)).scalar() or 0
    count_24h = db.session.query(func.count(Transaction.id)).filter(
        Transaction.created_at >= day_ago).scalar() or 0
    total_volume = db.session.query(func.coalesce(func.sum(Transaction.amount), 0.0)).scalar() or 0.0
    avg_fee = db.session.query(func.coalesce(func.avg(Transaction.fee), 0.0)).scalar() or 0.0
    pending_count = db.session.query(func.count(Transaction.id)).filter(
        Transaction.status == 'pending').scalar() or 0

    # Bucket the last 24h of transactions into 4-hour windows for the charts.
    bucket_hours = 4
    num_buckets = 24 // bucket_hours
    volume_buckets = [0.0] * num_buckets
    fee_sums = [0.0] * num_buckets
    fee_counts = [0] * num_buckets

    recent_txs = Transaction.query.filter(Transaction.created_at >= day_ago).all()
    for tx in recent_txs:
        if not tx.created_at:
            continue
        hours_ago = (now - tx.created_at).total_seconds() / 3600
        bucket_idx = num_buckets - 1 - min(int(hours_ago // bucket_hours), num_buckets - 1)
        bucket_idx = max(0, min(bucket_idx, num_buckets - 1))
        volume_buckets[bucket_idx] += tx.amount or 0.0
        fee_sums[bucket_idx] += tx.fee or 0.0
        fee_counts[bucket_idx] += 1

    fee_buckets = [
        (fee_sums[i] / fee_counts[i]) if fee_counts[i] else 0.0
        for i in range(num_buckets)
    ]

    return jsonify({
        'total_transactions': total_count,
        'transactions_24h': count_24h,
        'avg_fee': avg_fee,
        'total_volume': total_volume,
        'pending_count': pending_count,
        'volume_buckets': volume_buckets,
        'fee_buckets': fee_buckets,
    })



# Routes
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = RegistrationForms()
    if form.validate_on_submit():
        try:
            wallet_service = WalletService()       
            
            user_data = {
                'first_name': form.first_name.data,
                'last_name': form.last_name.data,
                'username': form.username.data,
                'email': form.email.data,
                'wallet_name': f"{form.first_name.data} {form.last_name.data}'s Wallet"
            }

            api_result = wallet_service.create_wallet_for_user(user_data)
            if api_result['success']:
                wallet_address = api_result['address']
                api_user_id = f"user_{secrets.token_hex(8)}"
                private_key = secrets.token_hex(32)
                public_key = hashlib.sha256(private_key.encode()).hexdigest()
                key = Fernet.generate_key()      # this is your secret encryption key
                fernet = Fernet(key)

                # Encrypt private key
                encrypted_private_key = fernet.encrypt(private_key.encode()).decode()

                # Create user with wallet info
                user = User(
                    first_name=form.first_name.data,
                    last_name=form.last_name.data,
                    username=form.username.data,
                    email=form.email.data,
                    phone=form.phone.data,
                    country=form.country.data,
                    password_hash=generate_password_hash(form.password.data),
                    wallet_address=wallet_address,
                    encrypted_private_key=encrypted_private_key,
                    public_key=public_key,
                    wallet_name=f"{form.first_name.data} {form.last_name.data}'s Wallet",
                    wallet_balance=0.0,
                    api_user_id=api_user_id,
                    created_at=datetime.utcnow()
                )
                
                db.session.add(user)
                db.session.commit()
                
                logging.info(f"User created successfully: {user.username} with wallet: {wallet_address}")
                
                flash('Your account has been created with a secure wallet! You can now log in.', 'success')
                return redirect(url_for('login'))
            else:
                flash(f'Wallet creation failed: {api_result.get("error", "Unknown error")}', 'danger')
                return render_template('register.html', form=form)
        except Exception as e:
            db.session.rollback()
            logging.error(f"Registration error: {str(e)}")
            flash('An unexpected error occurred. Please try again.', 'danger')
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        # Check if input is email or username
        user = User.query.filter(
            (User.email == form.email.data) | (User.username == form.email.data)
        ).first()
        
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user, remember=form.remember.data)
            user.last_login = datetime.utcnow()
            db.session.commit()

            token = jwt.encode(
            {
                "user_id": user.id,
                "exp": datetime.utcnow() + timedelta(hours=5)
            },
                app.config['SECRET_KEY'],
                algorithm="HS256"
            )

            # resp = make_response(jsonify({"message": "Login successful"}))
            resp = redirect('/dashboard')
    # Save token as cookie
            resp.set_cookie(
                "authToken",
                token,
                max_age=5 * 60 * 60,     # 5 hours
                httponly=False,          # frontend JS needs to read it
                secure=False,            # set True if using HTTPS
                samesite="Lax"
            )
            return resp
            next_page = request.args.get('next')
            if not next_page or urlparse(next_page).netloc != '':
                next_page = url_for('dashboard')

            return redirect('/dashboard')
            # flash('Login successful!', 'success')
            # return redirect(next_page)
        else:
            flash('Login unsuccessful. Please check email/username and password.', 'danger')
    
    return render_template('login.html', form=form)

@app.route('/dashboard')
@login_required
def dashboard():
    dashboard = AfricoinDashboard()
    stats = dashboard.get_blockchain_stats()
    recent_blocks = dashboard.get_recent_blocks(5)
    network_info = dashboard.get_network_info()   
    # Get user stats
    # Get wallet balance from API
    total_contracts = Contract.query.filter_by(user_id=current_user.id).count()
    active_contracts = Contract.query.filter_by(user_id=current_user.id, status='Active').count()
    return render_template('index.html',
                         stats=stats,
                         recent_blocks=recent_blocks,
                         network_info=network_info,
                         total_contracts=total_contracts,
                         active_contracts=active_contracts)

    
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/profile')
@login_required
def profile():
    form = UpdateProfileForm()
    password_form = ChangePasswordForm()
    preferences_form = PreferencesForm()
    
    # Populate form data
    form.first_name.data = current_user.first_name
    form.last_name.data = current_user.last_name
    form.username.data = current_user.username
    form.email.data = current_user.email
    form.phone.data = current_user.phone
    form.country.data = current_user.country
    
    # Mock data for demonstration
    recent_transactions = [
        {'date': datetime.utcnow(), 'type': 'received', 'amount': 1.5, 'status': 'confirmed'},
        {'date': datetime.utcnow(), 'type': 'sent', 'amount': 0.5, 'status': 'confirmed'}
    ]

    exchange_rate = get_usd_zar_rate()

    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.created_at.desc()).limit(10).all()

    return render_template('profile.html', 
                         form=form,
                         transactions=transactions,
                         password_form=password_form,
                         preferences_form=preferences_form,
                         recent_transactions=recent_transactions,
                         exchange_rate=exchange_rate)  # Mock exchange rate

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    form = UpdateProfileForm()
    if form.validate_on_submit():
        current_user.first_name = form.first_name.data
        current_user.last_name = form.last_name.data
        current_user.username = form.username.data
        current_user.email = form.email.data
        current_user.phone = form.phone.data
        current_user.country = form.country.data
        
        db.session.commit()
        flash('Your profile has been updated!', 'success')
    else:
        flash('Please correct the errors in the form.', 'danger')
    
    return redirect(url_for('profile'))

@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if check_password_hash(current_user.password_hash, form.current_password.data):
            current_user.password_hash = generate_password_hash(form.new_password.data)
            db.session.commit()
            flash('Your password has been updated!', 'success')
        else:
            flash('Current password is incorrect.', 'danger')
    else:
        flash('Please correct the errors in the form.', 'danger')
    
    return redirect(url_for('profile'))

@app.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            # Here you would typically send a password reset email
            # For now, we'll just show a message
            flash('Check your email for instructions to reset your password.', 'info')
            return redirect(url_for('login'))
        else:
            flash('Email not found.', 'danger')
    
    return render_template('reset_password_request.html', form=form)

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    # In a real app, you would verify the token here
    # For demonstration, we'll assume it's valid
    form = ResetPasswordForm()
    if form.validate_on_submit():
        # Find user by token (in real app, you'd decode the token)
        # For now, we'll use a dummy implementation
        flash('Your password has been reset! You can now log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('reset_password.html', form=form)

@app.route('/contracts')
@login_required
def contracts():
    user_contracts = Contract.query.filter_by(user_id=current_user.id).all()
    return render_template('contracts.html', contracts=user_contracts)

@app.route('/wallet')
@login_required
def wallet():
    exchange_rate = get_usd_zar_rate()
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.created_at.desc()).limit(10).all()
    return render_template('wallet.html', transactions=transactions, exchange_rate=exchange_rate)

# API endpoints
@app.route('/api/dashboard_stats')
@login_required
def api_dashboard_stats():
    stats = {
        'balance': current_user.wallet_balance,
        'total_contracts': Contract.query.filter_by(user_id=current_user.id).count(),
        'active_contracts': Contract.query.filter_by(user_id=current_user.id, status='Active').count(),
        'pending_transactions': Transaction.query.filter_by(user_id=current_user.id, status='pending').count()
    }
    return jsonify(stats)

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500


@app.errorhandler(403)
def forbidden_error(error):
    return render_template('403.html')

@app.route('/admin/sync-wallets')
def admin_sync_wallets():
    """Sync wallets between wallet system and database"""
    try:
        from models import User
        from services.wallet_service import DBWalletService
        
        db_wallet_service = DBWalletService()
        wallet_service = WalletService()
        
        # Get all wallets from wallet system
        wallets_response = wallet_service.get_all_wallets()
        
        if not wallets_response.get('success'):
            return jsonify({'success': False, 'error': 'Could not get wallets from wallet system'})
        
        wallet_addresses = wallets_response.get('addresses', [])
        results = []
        
        for address in wallet_addresses:
            try:
                # Check if wallet exists in database
                db_result = db_wallet_service.get_wallet_by_address(address)
                
                if not db_result['success']:
                    # Wallet doesn't exist in DB, find user by address
                    user = User.query.filter_by(wallet_address=address).first()
                    
                    if user:
                        # Create wallet record
                        wallet_name = f"{user.first_name} {user.last_name}'s Wallet"
                        create_result = db_wallet_service.create_wallet_record(
                            user.id, address, wallet_name
                        )
                        
                        if create_result['success']:
                            results.append({
                                'address': address,
                                'action': 'created',
                                'user': user.username
                            })
                        else:
                            results.append({
                                'address': address,
                                'action': 'failed',
                                'error': create_result.get('error')
                            })
                    else:
                        results.append({
                            'address': address,
                            'action': 'skipped',
                            'reason': 'No user found for this wallet'
                        })
                else:
                    results.append({
                        'address': address,
                        'action': 'exists',
                        'user': db_result['wallet']['owner_username']
                    })
                    
            except Exception as e:
                results.append({
                    'address': address,
                    'action': 'error',
                    'error': str(e)
                })
        
        return jsonify({
            'success': True,
            'message': f"Processed {len(wallet_addresses)} wallets",
            'results': results
        })
        
    except Exception as e:
        logging.error(f"Wallet sync error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    # Only used for local development. In production Render starts this via
    # gunicorn (see Procfile) which is multi-worker/threaded and won't lock
    # up the whole site on one slow request the way this dev server does.
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    port = int(os.environ.get('PORT', 7070))
    app.run(host='0.0.0.0', port=port, debug=debug_mode)