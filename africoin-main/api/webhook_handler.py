# webhook_handler.py
from flask import Flask, request, jsonify
import logging

app = Flask(__name__)

@app.route('/webhooks/wallet-created', methods=['POST'])
def handle_wallet_created():
    """Handle wallet creation webhook"""
    try:
        data = request.get_json()
        
        # Process the webhook data
        user_id = data.get('user_id')
        wallet_address = data.get('wallet_address')
        status = data.get('status')
        
        logging.info(f"Wallet created for user {user_id}: {wallet_address}")
        
        # Update your external database, send notification, etc.
        
        return jsonify({'success': True})
        
    except Exception as e:
        logging.error(f"Webhook handling error: {str(e)}")
        return jsonify({'success': False}), 500

if __name__ == '__main__':
    app.run(port=8000)