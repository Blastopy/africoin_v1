import requests
import time
import threading
from datetime import datetime, timedelta
from web.extensions import db
from models import BlockchainStats, Transaction
from .africoin_rpc import africoin_rpc

class AfricoinBlockchainService:
    def __init__(self):
        self.current_height = 0
        self.is_running = False
        self.update_interval = 60  # Update every minute
    
    def start_background_updates(self):
        """Start background thread for blockchain updates"""
        if not self.is_running:
            self.is_running = True
            thread = threading.Thread(target=self._update_loop, daemon=True)
            thread.start()
            print("Africoin blockchain service started")
    
    def _update_loop(self):
        """Background update loop for Africoin blockchain"""
        while self.is_running:
            try:
                self.update_africoin_stats()
                time.sleep(self.update_interval)
            except Exception as e:
                print(f"Error in Africoin blockchain update: {e}")
                time.sleep(30)
    
    def update_africoin_stats(self):
        """Update Africoin blockchain statistics"""
        try:
            # Get data from Africoin node
            blockchain_info = africoin_rpc.get_blockchain_info()
            network_info = africoin_rpc.get_network_info()
            difficulty = africoin_rpc.get_difficulty()
            connection_count = africoin_rpc.get_connection_count()
            
            if not blockchain_info:
                # Fallback to incremental growth if node is unavailable
                self._update_with_fallback()
                return
            
            # Calculate block time (average of last 100 blocks)
            block_time = self._calculate_africoin_block_time()
            
            # Get or create stats record
            stats = BlockchainStats.query.first()
            if not stats:
                stats = BlockchainStats()
                db.session.add(stats)
            
            # Update with real Africoin data
            stats.block_height = blockchain_info.get('blocks', 0)
            stats.network_hash_rate = self._calculate_africoin_hash_rate(difficulty, block_time)
            stats.difficulty = f"{difficulty:.2f}" if isinstance(difficulty, (int, float)) else str(difficulty)
            stats.total_transactions = blockchain_info.get('txcount', Transaction.query.count())
            stats.total_volume_afc = self._calculate_africoin_total_volume()
            stats.active_nodes = connection_count or network_info.get('connections', 0)
            stats.block_time_seconds = block_time
            stats.last_updated = datetime.utcnow()
            
            db.session.commit()
            self.current_height = stats.block_height
            
            print(f"Africoin blockchain updated: Height {stats.block_height}, Connections: {stats.active_nodes}")
            
        except Exception as e:
            print(f"Error updating Africoin stats: {e}")
            db.session.rollback()
            self._update_with_fallback()
    
    def _calculate_africoin_block_time(self):
        """Calculate average block time for Africoin"""
        try:
            # Get recent blocks to calculate average block time
            current_height = africoin_rpc.get_block_count()
            if not current_height or current_height < 10:
                return 150  # Default 2.5 minutes
            
            # Get timestamps for last 10 blocks
            block_times = []
            for i in range(10):
                block_hash = africoin_rpc.get_block_hash(current_height - i)
                if block_hash:
                    block_data = africoin_rpc.get_block(block_hash)
                    if block_data and 'time' in block_data:
                        block_times.append(block_data['time'])
            
            if len(block_times) >= 2:
                total_time_diff = 0
                for i in range(1, len(block_times)):
                    total_time_diff += block_times[i-1] - block_times[i]
                avg_block_time = total_time_diff / (len(block_times) - 1)
                return max(avg_block_time, 60)  # Minimum 1 minute
                
        except Exception as e:
            print(f"Error calculating block time: {e}")
        
        return 150  # Fallback: 2.5 minutes
    
    def _calculate_africoin_hash_rate(self, difficulty, block_time):
        """Calculate Africoin network hash rate"""
        try:
            if isinstance(difficulty, (int, float)) and block_time > 0:
                # Hash rate = difficulty * 2^32 / block_time
                hash_rate = (difficulty * (2**32)) / block_time
                
                # Convert to appropriate units
                if hash_rate >= 1e12:  # Terra hashes
                    return f"{hash_rate / 1e12:.2f} TH/s"
                elif hash_rate >= 1e9:  # Giga hashes
                    return f"{hash_rate / 1e9:.2f} GH/s"
                elif hash_rate >= 1e6:  # Mega hashes
                    return f"{hash_rate / 1e6:.2f} MH/s"
                else:
                    return f"{hash_rate:.2f} H/s"
        except:
            pass
        
        return "Calculating..."
    
    def _calculate_africoin_total_volume(self):
        """Calculate total AFC volume from confirmed transactions"""
        try:
            result = db.session.query(db.func.sum(Transaction.amount)).filter(
                Transaction.status == 'confirmed'
            ).scalar()
            return float(result) if result else 0.0
        except:
            return 0.0
    
    def _update_with_fallback(self):
        """Fallback update when Africoin node is unavailable"""
        try:
            stats = BlockchainStats.query.first()
            if not stats:
                stats = BlockchainStats()
                db.session.add(stats)
            
            # Incremental growth based on time
            if stats.last_updated:
                hours_since_update = (datetime.utcnow() - stats.last_updated).total_seconds() / 3600
                blocks_to_add = int(hours_since_update * 24)  # 24 blocks per hour (2.5 min blocks)
            else:
                blocks_to_add = 1
            
            stats.block_height = (stats.block_height or 100000) + blocks_to_add
            stats.network_hash_rate = "15.2 TH/s"
            stats.difficulty = "12.45 T"
            stats.total_transactions = Transaction.query.count()
            stats.total_volume_afc = self._calculate_africoin_total_volume()
            stats.active_nodes = max((stats.active_nodes or 500) - 1, 100)  # Gradual decrease
            stats.block_time_seconds = 150
            stats.last_updated = datetime.utcnow()
            
            db.session.commit()
            self.current_height = stats.block_height
            
        except Exception as e:
            print(f"Error in fallback update: {e}")
            db.session.rollback()
    
    def get_africoin_stats(self):
        """Get current Africoin blockchain statistics"""
        stats = BlockchainStats.query.first()
        if stats:
            return stats.to_dict()
        else:
            # Return default Africoin stats
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
africoin_blockchain = AfricoinBlockchainService()