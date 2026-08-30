from flask import Flask, request, jsonify
import jwt
import datetime
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'africoin-mobile-secret'

def mobile_token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token:
            return jsonify({'error': 'Token required'}), 401
        
        try:
            token = token.replace('Bearer ', '')
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            request.user_id = data['user_id']
        except:
            return jsonify({'error': 'Invalid token'}), 401
        
        return f(*args, **kwargs)
    return decorated

@app.route('/mobile/api/login', methods=['POST'])
def mobile_login():
    """Mobile app login"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    # Simplified authentication
    if username and password:
        token = jwt.encode({
            'user_id': username,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=30)
        }, app.config['SECRET_KEY'])
        
        return jsonify({
            'success': True,
            'token': token,
            'user': username
        })
    
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/mobile/api/wallet/balance', methods=['GET'])
@mobile_token_required
def mobile_balance():
    """Get mobile wallet balance"""
    # Implementation would connect to main API
    return jsonify({
        'balance': 100.0,
        'addresses': ['1ABC...'],
        'pending': 0.0
    })

@app.route('/mobile/api/wallet/send', methods=['POST'])
@mobile_token_required
def mobile_send():
    """Send transaction from mobile"""
    data = request.get_json()
    
    # Implementation would create and broadcast transaction
    return jsonify({
        'success': True,
        'tx_hash': '0x123...',
        'message': 'Transaction sent'
    })

@app.route('/mobile/api/wallet/qr', methods=['GET'])
@mobile_token_required
def generate_qr():
    """Generate QR code for address"""
    address = request.args.get('address')
    
    # Implementation would generate QR code
    return jsonify({
        'qr_data': f'africoin:{address}',
        'address': address
    })

# Push notifications for mobile
class MobilePushNotifications:
    def __init__(self):
        self.device_tokens = {}
    
    def register_device(self, user_id, device_token):
        """Register device for push notifications"""
        self.device_tokens[user_id] = device_token
    
    def send_transaction_notification(self, user_id, tx_hash, amount):
        """Send transaction notification"""
        device_token = self.device_tokens.get(user_id)
        if device_token:
            # Implementation would send push notification
            print(f"Sending notification to {user_id}: Received {amount} AFC")