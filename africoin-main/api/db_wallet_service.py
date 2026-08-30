import logging
from typing import Optional, Dict, Any
import os, sys
from flask import current_app

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from models import User
from web.extensions import db


class DBWalletService:
    def __init__(self):
        self.logger = logging.getLogger('Africoin')
        # No need to initialize self.db since we're using Flask-SQLAlchemy
    
    def get_wallet_by_address(self, address: str) -> Dict[str, Any]:
        """Get wallet by address using SQLAlchemy"""
        try:
            self.logger.info(f"Searching for wallet: {address}")
            
            # Use SQLAlchemy query instead of MongoDB
            wallet = User.query.filter_by(address=address).first()
            self.logger.info(f"Database query result: {wallet}")
            
            if wallet:
                wallet_data = {
                    'id': wallet.id,
                    'address': wallet.address,
                    'name': wallet.name,
                    'balance': float(wallet.balance),
                    'user_id': wallet.user_id,
                    'is_active': wallet.is_active,
                    'created_at': wallet.created_at.isoformat() if wallet.created_at else None
                }
                
                self.logger.info(f"Wallet found: {wallet.address} with balance: {wallet.balance}")
                return {
                    'success': True,
                    'wallet': wallet_data
                }
            else:
                self.logger.warning(f"No wallet found for address: {address}")
                return {'success': False, 'error': 'Wallet not found'}
                
        except Exception as e:
            self.logger.error(f"Database error in get_wallet_by_address: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_all_wallets(self, user_id: str = None) -> Dict[str, Any]:
        """Get all wallets, optionally filtered by user_id"""
        try:
            if user_id:
                wallets = User.query.filter_by(user_id=user_id, is_active=True).all()
            else:
                wallets = User.query.filter_by(is_active=True).all()
            
            wallet_list = []
            for wallet in wallets:
                wallet_list.append({
                    'id': wallet.id,
                    'address': wallet.address,
                    'name': wallet.name,
                    'balance': float(wallet.balance),
                    'user_id': wallet.user_id,
                    'created_at': wallet.created_at.isoformat() if wallet.created_at else None
                })
            
            return {'success': True, 'wallets': wallet_list}
            
        except Exception as e:
            self.logger.error(f"Error getting all wallets: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    # Keep your existing methods (they're already using SQLAlchemy)
    def get_user_wallets(self, user_id):
        """Get all wallets for a user"""
        try:
            wallets = User.query.filter_by(user_id=user_id, is_active=True).all()
            wallet_list = []
            
            for wallet in wallets:
                wallet_list.append({
                    'id': wallet.id,
                    'address': wallet.address,
                    'name': wallet.name,
                    'balance': float(wallet.balance),
                    'created_at': wallet.created_at.isoformat() if wallet.created_at else None
                })
            
            return {'success': True, 'wallets': wallet_list}
            
        except Exception as e:
            self.logger.error(f"Error getting user wallets: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def update_wallet_balance(self, address, new_balance):
        """Update wallet balance in database"""
        try:
            wallet = User.query.filter_by(address=address).first()
            if wallet:
                old_balance = wallet.balance
                wallet.balance = new_balance
                db.session.commit()
                
                self.logger.info(f"Updated balance for {address}: {old_balance} -> {new_balance}")
                return {'success': True}
            else:
                return {'success': False, 'error': 'Wallet not found'}
                
        except Exception as e:
            self.logger.error(f"Error updating wallet balance: {str(e)}")
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    def create_wallet_record(self, user_id, address, name, balance=0.0):
        """Create a new wallet record in database"""
        try:
            # Check if wallet already exists
            existing_wallet = User.query.filter_by(address=address).first()
            if existing_wallet:
                return {'success': False, 'error': 'Wallet already exists'}
            
            wallet = User(
                address=address,
                name=name,
                balance=balance,
                user_id=user_id,
                is_active=True
            )
            
            db.session.add(wallet)
            db.session.commit()
            
            self.logger.info(f"Created wallet record: {address} for user {user_id}")
            return {'success': True, 'wallet_id': wallet.id}
            
        except Exception as e:
            self.logger.error(f"Error creating wallet record: {str(e)}")
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    def get_wallet_with_user(self, address):
        """Get wallet with user information"""
        try:
            wallet = User.query.filter_by(address=address).join(User).first()
            if wallet:
                return {
                    'success': True,
                    'wallet': {
                        'address': wallet.address,
                        'name': wallet.name,
                        'balance': float(wallet.balance),
                        'user': {
                            'id': wallet.owner.id,
                            'username': wallet.owner.username,
                            'email': wallet.owner.email
                        }
                    }
                }
            else:
                return {'success': False, 'error': 'Wallet not found'}
                
        except Exception as e:
            self.logger.error(f"Error getting wallet with user: {str(e)}")
            return {'success': False, 'error': str(e)}