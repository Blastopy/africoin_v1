import os
from dataclasses import dataclass
from typing import Dict, Any
from datetime import timedelta

@dataclass
class AfricoinConfig:
    # Network Settings
    NETWORK_ID: str = "africoin_mainnet_2024"
    DEFAULT_PORT: int = 8333
    API_PORT: int = 5000
    DASHBOARD_PORT: int = 8080
    
    # Blockchain Settings
    BLOCK_TIME: int = 600  # 10 minutes
    DIFFICULTY_ADJUSTMENT_INTERVAL: int = 2016  # ~2 weeks
    BLOCK_REWARD: float = 50.0
    HALVING_INTERVAL: int = 210000  # ~4 years
    MAX_SUPPLY: float = 21_000_000.0
    
    # Security Settings
    MAX_TRANSACTION_SIZE: int = 1_000_000  # 1MB
    MAX_BLOCK_SIZE: int = 4_000_000  # 4MB
    MIN_TRANSACTION_FEE: float = 0.0001
    
    # Mining Settings
    POOL_FEE: float = 0.01  # 1%
    PAYOUT_THRESHOLD: float = 0.01
    SHARE_DIFFICULTY: int = 1000
    
    # API Settings
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD: int = 3600  # 1 hour
    JWT_EXPIRY_DAYS: int = 30
    
    # Cross-chain Settings
    SUPPORTED_CHAINS: tuple = ('ethereum', 'bitcoin', 'binance')
    BRIDGE_FEE: float = 0.001
    
    # Database Settings
    DATABASE_PATH: str = "users.db"
    BACKUP_INTERVAL: int = 86400  # 24 hours

    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///instance/users.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session settings
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    WALLET_API_URL = os.environ.get('WALLET_API_URL', 'http://localhost:5000')
    WALLET_API_KEY = os.environ.get('WALLET_API_KEY', 'your_internal_api_key_456')
    WALLET_MASTER_PASSWORD = os.environ.get('WALLET_MASTER_PASSWORD', 'default_master_password_123')
    
    # Email settings
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.googlemail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    
    @classmethod
    def from_env(cls):
        """Create config from environment variables"""
        config = cls()
        
        # Override with environment variables
        for field in cls.__dataclass_fields__:
            env_value = os.getenv(f"AFRICOIN_{field}")
            if env_value is not None:
                # Convert to appropriate type
                field_type = cls.__dataclass_fields__[field].type
                if field_type == int:
                    setattr(config, field, int(env_value))
                elif field_type == float:
                    setattr(config, field, float(env_value))
                elif field_type == bool:
                    setattr(config, field, env_value.lower() == 'true')
                else:
                    setattr(config, field, env_value)
        
        return config

# Global configuration instance
config = AfricoinConfig.from_env()