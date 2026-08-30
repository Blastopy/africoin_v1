import requests
import time
import threading
from datetime import datetime, timedelta
from web.extensions import db
from models import BlockchainStats, Transaction


class BlockchainService:
    def __init__(self):
        self.current_height = 0
        self.is_running = False
        self.update_interval = 60  # seconds
    
    def start_background_updates(self):
        """Start background thread for blockchain updates"""
        if not self.is_running:
            self.is_running = True
            thread = threading.Thread(target=self._update_loop, daemon=True)
            thread.start()
    
    def _update_loop(self):
        """Background update loop"""
        while self.is_running:
            try:
                self.update_blockchain_stats()
                time.sleep(self.update_interval)
            except Exception as e:
                print(f"Error in blockchain update loop: {e}")
                time.sleep(30)  # Wait longer on error
    
    def update_blockchain_stats(self):
        """Update blockchain statistics in database"""
        try:
            # Get current stats from various sources
            stats = self._fetch_blockchain_data()
            
            # Create or update blockchain stats record
            blockchain_stats = BlockchainStats.query.first()
            if not blockchain_stats:
                blockchain_stats = BlockchainStats()
                db.session.add(blockchain_stats)
            
            # Update fields
            blockchain_stats.block_height = stats['block_height']
            blockchain_stats.network_hash_rate = stats['network_hash_rate']
            blockchain_stats.difficulty = stats['difficulty']
            blockchain_stats.total_transactions = stats['total_transactions']
            blockchain_stats.total_volume_afc = stats['total_volume_afc']
            blockchain_stats.active_nodes = stats['active_nodes']
            blockchain_stats.block_time_seconds = stats['block_time_seconds']
            blockchain_stats.last_updated = datetime.utcnow()
            
            db.session.commit()
            self.current_height = stats['block_height']
            
            print(f"Blockchain stats updated: Height {stats['block_height']}")
            
        except Exception as e:
            print(f"Error updating blockchain stats: {e}")
            db.session.rollback()
    
    def _fetch_blockchain_data(self):
        """Fetch real blockchain data from APIs"""
        # For Africoin, you would use your own blockchain node API
        # For now, we'll simulate growth and use real Bitcoin data as reference
        
        # Try to get real Bitcoin data first
        bitcoin_height = self._get_bitcoin_height()
        
        if bitcoin_height:
            # Use Bitcoin data scaled for Africoin
            base_africoin_height = 100000  # Starting point for Africoin
            current_africoin_height = base_africoin_height + (bitcoin_height - 800000) // 10
            
            stats = {
                'block_height': current_africoin_height,
                'network_hash_rate': self._calculate_hash_rate(current_africoin_height),
                'difficulty': self._calculate_difficulty(current_africoin_height),
                'total_transactions': Transaction.query.count(),
                'total_volume_afc': self._calculate_total_volume(),
                'active_nodes': self._estimate_active_nodes(current_africoin_height),
                'block_time_seconds': 150  # 2.5 minutes for Africoin
            }
        else:
            # Fallback: incremental growth based on last known height
            last_stats = BlockchainStats.query.order_by(BlockchainStats.last_updated.desc()).first()
            if last_stats:
                new_height = last_stats.block_height + 24  # ~1 block per 2.5 minutes over 1 hour
            else:
                new_height = 100000  # Starting height
            
            stats = {
                'block_height': new_height,
                'network_hash_rate': '15.2 TH/s',
                'difficulty': '12.45 T',
                'total_transactions': Transaction.query.count(),
                'total_volume_afc': self._calculate_total_volume(),
                'active_nodes': 892,
                'block_time_seconds': 150
            }
        
        return stats
    
    def _get_bitcoin_height(self):
        """Get current Bitcoin block height"""
        try:
            response = requests.get('https://blockchain.info/q/getblockcount', timeout=10)
            if response.status_code == 200:
                return int(response.text)
        except:
            pass
        return None
    
    def _calculate_hash_rate(self, height):
        """Calculate simulated hash rate based on block height"""
        base_hash = 10.0  # TH/s at height 100,000
        growth_factor = (height - 100000) / 10000  # Growth per 10,000 blocks
        current_hash = base_hash * (1 + growth_factor * 0.1)
        return f"{current_hash:.1f} TH/s"
    
    def _calculate_difficulty(self, height):
        """Calculate simulated difficulty"""
        base_diff = 10.0  # T at height 100,000
        growth_factor = (height - 100000) / 5000  # Adjustment every 5,000 blocks
        current_diff = base_diff * (1 + growth_factor * 0.05)
        return f"{current_diff:.2f} T"
    
    def _calculate_total_volume(self):
        """Calculate total AFC volume from transactions"""
        result = db.session.query(db.func.sum(Transaction.amount)).filter(
            Transaction.status == 'confirmed'
        ).scalar()
        return float(result) if result else 0.0
    
    def _estimate_active_nodes(self, height):
        """Estimate active nodes based on block height"""
        base_nodes = 500
        growth = (height - 100000) // 1000  # +1 node per 1000 blocks
        return base_nodes + growth * 10
    
    def get_current_stats(self):
        """Get current blockchain statistics"""
        stats = BlockchainStats.query.first()
        if stats:
            return stats.to_dict()
        else:
            # Return default stats if none in database
            return {
                'block_height': 100000,
                'network_hash_rate': '10.0 TH/s',
                'difficulty': '10.00 T',
                'total_transactions': 0,
                'total_volume_afc': 0.0,
                'active_nodes': 500,
                'block_time_seconds': 150,
                'last_updated': datetime.utcnow().isoformat()
            }

# Global instance
blockchain_service = BlockchainService()