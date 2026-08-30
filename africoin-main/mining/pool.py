import asyncio
import json
import hashlib
import time
from typing import Dict, List, Any
from dataclasses import dataclass
from enum import Enum

class MinerStatus(Enum):
    CONNECTED = "connected"
    MINING = "mining"
    DISCONNECTED = "disconnected"

@dataclass
class Miner:
    address: str
    worker_name: str
    hashrate: float
    shares: int
    last_share: float
    status: MinerStatus

class AfricoinMiningPool:
    def __init__(self, blockchain):
        self.blockchain = blockchain
        self.miners: Dict[str, Miner] = {}
        self.shares: List[Dict] = []
        self.current_block = None
        self.pool_fee = 0.01  # 1% pool fee
        self.block_reward = 0
        self.payout_threshold = 0.01  # Minimum payout
        
    def add_miner(self, address: str, worker_name: str = "default") -> str:
        """Add miner to pool"""
        miner_id = f"{address}.{worker_name}"
        
        self.miners[miner_id] = Miner(
            address=address,
            worker_name=worker_name,
            hashrate=0,
            shares=0,
            last_share=time.time(),
            status=MinerStatus.CONNECTED
        )
        
        return miner_id
    
    def submit_share(self, miner_id: str, share_data: Dict) -> bool:
        """Submit mining share"""
        if miner_id not in self.miners:
            return False
        
        miner = self.miners[miner_id]
        
        # Validate share
        if self.validate_share(share_data):
            miner.shares += 1
            miner.last_share = time.time()
            miner.hashrate = self.calculate_hashrate(miner_id)
            
            self.shares.append({
                'miner_id': miner_id,
                'timestamp': time.time(),
                'difficulty': share_data.get('difficulty', 1)
            })
            
            return True
        
        return False
    
    def validate_share(self, share_data: Dict) -> bool:
        """Validate mining share"""
        # Implementation would validate share against current block
        return True
    
    def calculate_hashrate(self, miner_id: str) -> float:
        """Calculate miner hashrate"""
        miner_shares = [s for s in self.shares if s['miner_id'] == miner_id]
        recent_shares = [s for s in miner_shares if time.time() - s['timestamp'] < 3600]
        
        if not recent_shares:
            return 0
        
        total_difficulty = sum(s['difficulty'] for s in recent_shares)
        time_span = time.time() - min(s['timestamp'] for s in recent_shares)
        
        return total_difficulty / max(time_span, 1)
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """Get pool statistics"""
        total_hashrate = sum(miner.hashrate for miner in self.miners.values())
        active_miners = sum(1 for miner in self.miners.values() 
                          if miner.status == MinerStatus.MINING)
        
        return {
            'total_miners': len(self.miners),
            'active_miners': active_miners,
            'total_hashrate': total_hashrate,
            'pool_fee': self.pool_fee,
            'current_block': self.current_block.index if self.current_block else 0,
            'pending_payouts': self.calculate_pending_payouts()
        }
    
    def calculate_pending_payouts(self) -> Dict[str, float]:
        """Calculate pending payouts for miners"""
        total_shares = sum(miner.shares for miner in self.miners.values())
        if total_shares == 0:
            return {}
        
        # Calculate miner rewards based on shares
        payouts = {}
        for miner_id, miner in self.miners.items():
            share_ratio = miner.shares / total_shares
            reward = self.block_reward * share_ratio * (1 - self.pool_fee)
            
            if reward >= self.payout_threshold:
                payouts[miner.address] = payouts.get(miner.address, 0) + reward
        
        return payouts
    
    def process_block_reward(self, block_reward: float):
        """Process block reward distribution"""
        self.block_reward = block_reward
        payouts = self.calculate_pending_payouts()
        
        # Create payout transactions
        for address, amount in payouts.items():
            self.create_payout_transaction(address, amount)
        
        # Reset shares for new round
        for miner in self.miners.values():
            miner.shares = 0
    
    def create_payout_transaction(self, address: str, amount: float):
        """Create payout transaction"""
        # Implementation would create actual transaction
        print(f"Paying {amount} AFC to {address}")