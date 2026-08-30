import requests
import json
from datetime import datetime

class AfricoinRPC:
    def __init__(self):
        self.rpc_url = "http://localhost:8332"  # Default Africoin RPC port
        self.rpc_user = "africoinrpc"
        self.rpc_password = "your_password_here"
        self.timeout = 30
    
    def rpc_call(self, method, params=None):
        """Make JSON-RPC call to Africoin node"""
        try:
            payload = {
                "jsonrpc": "1.0",
                "id": "africoin_dashboard",
                "method": method,
                "params": params or []
            }
            
            response = requests.post(
                self.rpc_url,
                auth=(self.rpc_user, self.rpc_password),
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'error' in result and result['error'] is not None:
                    raise Exception(f"RPC Error: {result['error']}")
                return result['result']
            else:
                raise Exception(f"HTTP Error: {response.status_code}")
                
        except Exception as e:
            print(f"Africoin RPC Error ({method}): {e}")
            return None
    
    def get_block_count(self):
        """Get current block height"""
        return self.rpc_call("getblockcount")
    
    def get_blockchain_info(self):
        """Get comprehensive blockchain info"""
        return self.rpc_call("getblockchaininfo")
    
    def get_network_info(self):
        """Get network information"""
        return self.rpc_call("getnetworkinfo")
    
    def get_block_hash(self, height):
        """Get block hash by height"""
        return self.rpc_call("getblockhash", [height])
    
    def get_block(self, block_hash):
        """Get block data by hash"""
        return self.rpc_call("getblock", [block_hash])
    
    def get_difficulty(self):
        """Get current difficulty"""
        return self.rpc_call("getdifficulty")
    
    def get_connection_count(self):
        """Get number of connections"""
        return self.rpc_call("getconnectioncount")

# Global instance
africoin_rpc = AfricoinRPC()