from datetime import datetime
from flask_login import UserMixin
from web.extensions import db, login_manager
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import json
from sqlalchemy.orm import relationship


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), default='')  # Make optional with default
    country = db.Column(db.String(100), default='')  # Make optional with default
    password_hash = db.Column(db.String(128), nullable=False)
    
    # Wallet information
    wallet_address = db.Column(db.String(120), unique=True, nullable=False)
    wallet_name = db.Column(db.String(100), default='My Africoin Wallet')
    wallet_balance = db.Column(db.Float, default=0.0)
    encrypted_private_key = db.Column(db.Text)
    public_key = db.Column(db.Text)
    
    # User profile fields
    api_user_id = db.Column(db.String(50), unique=True)
    balance = db.Column(db.Float, default=0.0)
    is_verified = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    
    # Preferences
    language = db.Column(db.String(10), default='en')
    currency = db.Column(db.String(10), default='USD')
    email_notifications = db.Column(db.Boolean, default=True)
    sms_notifications = db.Column(db.Boolean, default=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime)

 
    # Relationships
    contracts = db.relationship('Contract', backref='owner', lazy='dynamic', cascade='all, delete-orphan')
    transactions = db.relationship('Transaction', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    password_reset_tokens = db.relationship('PasswordResetToken', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def generate_wallet_address(self):
        """Generate a unique wallet address for the user"""
        self.wallet_address = 'AFC' + secrets.token_hex(20)
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def update_balance(self, amount, transaction_type):
        """Update user balance based on transaction type"""
        if transaction_type == 'received':
            self.balance += amount
        elif transaction_type == 'sent':
            self.balance -= amount
        db.session.commit()
    
    def __repr__(self):
        return f'<User {self.username}>'


class WalletMeta(db.Model):
    __tablename__ = "wallet_meta"

    id = db.Column(db.Integer, primary_key=True)
    salt = db.Column(db.LargeBinary, nullable=False)
    iterations = db.Column(db.Integer, nullable=False)
    version = db.Column(db.Integer, nullable=False, default=1)
    
class Contract(db.Model):
    __tablename__ = 'contracts'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    client_name = db.Column(db.String(100), nullable=False)
    client_email = db.Column(db.String(120))
    client_phone = db.Column(db.String(20))
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    value = db.Column(db.Float, nullable=False)
    value_currency = db.Column(db.String(3), default='USD')
    status = db.Column(db.String(20), default='Draft')  # Draft, Active, Expired, Completed, Cancelled
    contract_type = db.Column(db.String(50))  # Service, Employment, Partnership, etc.
    payment_terms = db.Column(db.Text)
    special_conditions = db.Column(db.Text)
    
    # File attachments (paths to stored files)
    contract_file = db.Column(db.String(255))
    additional_files = db.Column(db.Text)  # JSON string of file paths
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    signed_at = db.Column(db.DateTime)
    
    # Foreign keys
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Relationships
    payments = db.relationship('ContractPayment', backref='contract', lazy='dynamic', cascade='all, delete-orphan')
    milestones = db.relationship('ContractMilestone', backref='contract', lazy='dynamic', cascade='all, delete-orphan')
    
    def is_active(self):
        return self.status == 'Active' and datetime.utcnow() <= self.end_date
    
    def days_remaining(self):
        if self.end_date and self.is_active():
            return (self.end_date - datetime.utcnow()).days
        return 0
    
    def total_paid(self):
        return sum(payment.amount for payment in self.payments.filter_by(status='completed'))
    
    def progress_percentage(self):
        if self.value == 0:
            return 0
        return (self.total_paid() / self.value) * 100
    
    def __repr__(self):
        return f'<Contract {self.title} - {self.client_name}>'

class ContractMilestone(db.Model):
    __tablename__ = 'contract_milestones'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.DateTime, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, completed, overdue
    completed_at = db.Column(db.DateTime)
    
    # Foreign keys
    contract_id = db.Column(db.Integer, db.ForeignKey('contracts.id'), nullable=False, index=True)
    
    def is_overdue(self):
        return self.status == 'pending' and datetime.utcnow() > self.due_date
    
    def __repr__(self):
        return f'<Milestone {self.title} - {self.status}>'

class ContractPayment(db.Model):
    __tablename__ = 'contract_payments'
    
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='USD')
    payment_method = db.Column(db.String(50))  # bank_transfer, cryptocurrency, mobile_money, etc.
    payment_date = db.Column(db.DateTime, nullable=False)
    due_date = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='pending')  # pending, completed, failed, refunded
    transaction_reference = db.Column(db.String(100))
    notes = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign keys
    contract_id = db.Column(db.Integer, db.ForeignKey('contracts.id'), nullable=False, index=True)
    
    def __repr__(self):
        return f'<Payment {self.amount} {self.currency} - {self.status}>'

class Transaction(db.Model):
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(20), nullable=False)  # sent, received, exchange, mining_reward
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='AFC')
    fee = db.Column(db.Float, default=0.0)
    net_amount = db.Column(db.Float)  # amount - fee
    
    # Address information
    from_address = db.Column(db.String(42))
    to_address = db.Column(db.String(42))
    
    # Blockchain information
    tx_hash = db.Column(db.String(66), unique=True, index=True)
    block_height = db.Column(db.Integer)
    confirmations = db.Column(db.Integer, default=0)
    
    # Status and metadata
    status = db.Column(db.String(20), default='pending')  # pending, confirmed, failed, cancelled
    category = db.Column(db.String(50))  # payment, transfer, exchange, reward
    description = db.Column(db.Text)
    tx_metadata = db.Column(db.Text)  # Renamed from 'metadata' to avoid conflict
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    confirmed_at = db.Column(db.DateTime)
    
    # Foreign keys
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    contract_id = db.Column(db.Integer, db.ForeignKey('contracts.id'))  # Optional: link to contract
    
    def calculate_net_amount(self):
        """Calculate net amount after fees"""
        if self.type == 'sent':
            self.net_amount = self.amount - self.fee
        else:
            self.net_amount = self.amount
    
    def is_confirmed(self):
        return self.status == 'confirmed' and self.confirmations >= 3
    
    def get_metadata(self):
        """Get metadata as dictionary"""
        if self.tx_metadata:
            return json.loads(self.tx_metadata)
        return {}
    
    def set_metadata(self, data):
        """Set metadata from dictionary"""
        self.tx_metadata = json.dumps(data)
    
    def __repr__(self):
        return f'<Transaction {self.type} {self.amount} {self.currency} - {self.status}>'

class PasswordResetToken(db.Model):
    __tablename__ = 'password_reset_tokens'
    
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(100), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    used_at = db.Column(db.DateTime)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Foreign keys
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    def is_valid(self):
        return not self.is_used and datetime.utcnow() < self.expires_at
    
    def __repr__(self):
        return f'<PasswordResetToken {self.token} - {self.is_used}>'

class ExchangeRate(db.Model):
    __tablename__ = 'exchange_rates'
    
    id = db.Column(db.Integer, primary_key=True)
    from_currency = db.Column(db.String(3), nullable=False, index=True)
    to_currency = db.Column(db.String(3), nullable=False, index=True)
    rate = db.Column(db.Float, nullable=False)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<ExchangeRate {self.from_currency}/{self.to_currency}: {self.rate}>'

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(50))  # transaction, contract, system, security
    is_read = db.Column(db.Boolean, default=False)
    action_url = db.Column(db.String(500))  # URL for the notification action
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    read_at = db.Column(db.DateTime)
    
    # Foreign keys
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    def mark_as_read(self):
        self.is_read = True
        self.read_at = datetime.utcnow()
    
    def __repr__(self):
        return f'<Notification {self.title} - {self.is_read}>'

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(100), nullable=False)
    resource_type = db.Column(db.String(50))  # user, contract, transaction, etc.
    resource_id = db.Column(db.Integer)
    old_values = db.Column(db.Text)  # JSON string
    new_values = db.Column(db.Text)  # JSON string
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Foreign keys
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    def __repr__(self):
        return f'<AuditLog {self.action} by User {self.user_id}>'

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class BlockchainStats(db.Model):
    __tablename__ = 'blockchain_stats'
    
    id = db.Column(db.Integer, primary_key=True)
    block_height = db.Column(db.Integer, nullable=False)
    network_hash_rate = db.Column(db.String(50))
    difficulty = db.Column(db.String(50))
    total_transactions = db.Column(db.BigInteger)
    total_volume_afc = db.Column(db.Float)
    active_nodes = db.Column(db.Integer)
    block_time_seconds = db.Column(db.Float)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'block_height': self.block_height,
            'network_hash_rate': self.network_hash_rate,
            'difficulty': self.difficulty,
            'total_transactions': self.total_transactions,
            'total_volume_afc': self.total_volume_afc,
            'active_nodes': self.active_nodes,
            'block_time_seconds': self.block_time_seconds,
            'last_updated': self.last_updated.isoformat()
        }