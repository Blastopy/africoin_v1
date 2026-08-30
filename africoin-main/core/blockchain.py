#!/usr/bin/env python3
"""
Africoin - A Production-Ready Cryptocurrency System
Core Blockchain Engine
"""

import hashlib
import json
import time
import secrets
import threading
import asyncio
import socket
import pickle
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, asdict
from enum import Enum
import logging
from logging.handlers import RotatingFileHandler
import sqlite3
import os
from contextlib import contextmanager
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature
import secrets

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('africoin.log', maxBytes=10*1024*1024, backupCount=5),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Africoin")

class TransactionStatus(Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"

@dataclass
class UTXO:
    """Unspent Transaction Output"""
    tx_hash: str
    output_index: int
    address: str
    amount: float
    script_pubkey: str

@dataclass
class TransactionInput:
    tx_hash: str
    output_index: int
    signature: str
    public_key: str

@dataclass
class TransactionOutput:
    address: str
    amount: float
    script_pubkey: str

class AfricoinTransaction:
    def __init__(self, version: int = 1):
        self.version = version
        self.inputs: List[TransactionInput] = []
        self.outputs: List[TransactionOutput] = []
        self.locktime = 0
        self.tx_hash = None
        self.fee = 0.0
        self.timestamp = time.time()
    
    def calculate_hash(self) -> str:
        """Calculate transaction hash using proper merkle tree structure"""
        tx_data = {
            'version': self.version,
            'inputs': [(inp.tx_hash, inp.output_index) for inp in self.inputs],
            'outputs': [(out.address, out.amount) for out in self.outputs],
            'locktime': self.locktime,
            'timestamp': self.timestamp
        }
        return hashlib.sha256(json.dumps(tx_data, sort_keys=True).encode()).hexdigest()
    
    def sign(self, private_key: ec.EllipticCurvePrivateKey):
        """Sign transaction with ECDSA"""
        self.tx_hash = self.calculate_hash()
        
        # Sign the transaction hash
        signature = private_key.sign(
            self.tx_hash.encode(),
            ec.ECDSA(hashes.SHA256())
        )
        
        # Add signature to inputs
        for tx_input in self.inputs:
            public_key = private_key.public_key()
            public_key_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            tx_input.public_key = public_key_bytes.hex()
            tx_input.signature = signature.hex()
    
    def verify_signature(self) -> bool:
        """Verify ECDSA signatures"""
        for tx_input in self.inputs:
            try:
                public_key = serialization.load_pem_public_key(
                    bytes.fromhex(tx_input.public_key),
                    backend=default_backend()
                )
                
                public_key.verify(
                    bytes.fromhex(tx_input.signature),
                    self.tx_hash.encode(),
                    ec.ECDSA(hashes.SHA256())
                )
            except (InvalidSignature, ValueError) as e:
                logger.error(f"Signature verification failed: {e}")
                return False
        return True
    
    def calculate_fee(self, utxos: List[UTXO]) -> float:
        """Calculate transaction fee"""
        input_amount = sum(utxo.amount for utxo in utxos)
        output_amount = sum(output.amount for output in self.outputs)
        return max(0.0, input_amount - output_amount)

class AfricoinBlock:
    def __init__(self, index: int, previous_hash: str, difficulty: int):
        self.version = 1
        self.index = index
        self.previous_hash = previous_hash
        self.timestamp = time.time()
        self.transactions: List[AfricoinTransaction] = []
        self.nonce = 0
        self.merkle_root = None
        self.difficulty = difficulty
        self.hash = None
    
    def calculate_merkle_root(self) -> str:
        """Calculate Merkle root of transactions"""
        if not self.transactions:
            return "0" * 64
            
        transaction_hashes = [tx.tx_hash for tx in self.transactions]
        
        while len(transaction_hashes) > 1:
            new_hashes = []
            for i in range(0, len(transaction_hashes), 2):
                if i + 1 < len(transaction_hashes):
                    combined = transaction_hashes[i] + transaction_hashes[i + 1]
                else:
                    combined = transaction_hashes[i] + transaction_hashes[i]
                new_hashes.append(hashlib.sha256(combined.encode()).hexdigest())
            transaction_hashes = new_hashes
        
        return transaction_hashes[0]
    
    def calculate_hash(self) -> str:
        """Calculate block hash"""
        self.merkle_root = self.calculate_merkle_root()
        
        block_data = {
            'version': self.version,
            'index': self.index,
            'previous_hash': self.previous_hash,
            'timestamp': self.timestamp,
            'merkle_root': self.merkle_root,
            'nonce': self.nonce,
            'difficulty': self.difficulty
        }
        return hashlib.sha256(json.dumps(block_data, sort_keys=True).encode()).hexdigest()
    
    def mine_block(self):
        """Proof of Work mining with dynamic difficulty"""
        logger.info(f"Mining block {self.index} with difficulty {self.difficulty}")
        start_time = time.time()
        hash_rate = 0
        start_nonce = self.nonce
        
        while True:
            self.hash = self.calculate_hash()
            hash_rate += 1
            
            if self.hash[:self.difficulty] == '0' * self.difficulty:
                mining_time = time.time() - start_time
                hashes_tried = self.nonce - start_nonce
                actual_hash_rate = hashes_tried / mining_time if mining_time > 0 else 0
                
                logger.info(f"Block {self.index} mined! "
                           f"Hash: {self.hash}, "
                           f"Nonce: {self.nonce}, "
                           f"Time: {mining_time:.2f}s, "
                           f"Hash Rate: {actual_hash_rate:.0f} H/s")
                break
            
            self.nonce += 1
            
            # Log progress every million hashes
            if self.nonce % 1000000 == 0:
                logger.debug(f"Mining... Nonce: {self.nonce}, Current hash: {self.hash}")

class DatabaseManager:
    def __init__(self, db_path: str = "africoin.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database with required tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Blocks table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS blocks (
                    hash TEXT PRIMARY KEY,
                    previous_hash TEXT NOT NULL,
                    block_index INTEGER NOT NULL,
                    timestamp REAL NOT NULL,
                    nonce INTEGER NOT NULL,
                    difficulty INTEGER NOT NULL,
                    merkle_root TEXT NOT NULL,
                    version INTEGER NOT NULL
                )
            ''')
            
            # Transactions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    tx_hash TEXT PRIMARY KEY,
                    block_hash TEXT,
                    version INTEGER NOT NULL,
                    locktime INTEGER NOT NULL,
                    fee REAL NOT NULL,
                    timestamp REAL NOT NULL,
                    status TEXT NOT NULL,
                    FOREIGN KEY (block_hash) REFERENCES blocks (hash)
                )
            ''')
            
            # UTXO table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS utxos (
                    tx_hash TEXT NOT NULL,
                    output_index INTEGER NOT NULL,
                    address TEXT NOT NULL,
                    amount REAL NOT NULL,
                    script_pubkey TEXT NOT NULL,
                    spent BOOLEAN DEFAULT FALSE,
                    PRIMARY KEY (tx_hash, output_index)
                )
            ''')
            
            # Transaction inputs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transaction_inputs (
                    tx_hash TEXT NOT NULL,
                    input_index INTEGER NOT NULL,
                    previous_tx_hash TEXT NOT NULL,
                    previous_output_index INTEGER NOT NULL,
                    signature TEXT NOT NULL,
                    public_key TEXT NOT NULL,
                    PRIMARY KEY (tx_hash, input_index)
                )
            ''')
            
            # Transaction outputs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transaction_outputs (
                    tx_hash TEXT NOT NULL,
                    output_index INTEGER NOT NULL,
                    address TEXT NOT NULL,
                    amount REAL NOT NULL,
                    script_pubkey TEXT NOT NULL,
                    PRIMARY KEY (tx_hash, output_index)
                )
            ''')
            
            # Network peers table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS peers (
                    address TEXT PRIMARY KEY,
                    port INTEGER NOT NULL,
                    last_seen REAL NOT NULL,
                    reputation INTEGER DEFAULT 100
                )
            ''')
            
            conn.commit()
    
    @contextmanager
    def get_connection(self):
        """Database connection context manager"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

class NetworkManager:
    def __init__(self, host: str = '0.0.0.0', port: int = 8333):
        self.host = host
        self.port = port
        self.peers: Set[tuple] = set()
        self.message_handlers = {}
        self.is_running = False
    
    async def start_server(self):
        """Start P2P network server"""
        self.is_running = True
        server = await asyncio.start_server(
            self.handle_connection, self.host, self.port
        )
        
        logger.info(f"Africoin node started on {self.host}:{self.port}")
        
        async with server:
            await server.serve_forever()
    
    async def handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle incoming peer connections"""
        try:
            while self.is_running:
                data = await reader.read(4096)
                if not data:
                    break
                
                message = pickle.loads(data)
                await self.handle_message(message, writer)
                
        except Exception as e:
            logger.error(f"Connection error: {e}")
        finally:
            writer.close()
    
    async def handle_message(self, message: Dict, writer: asyncio.StreamWriter):
        """Handle different message types"""
        message_type = message.get('type')
        
        if message_type in self.message_handlers:
            await self.message_handlers[message_type](message, writer)
    
    def register_message_handler(self, message_type: str, handler):
        """Register message handler"""
        self.message_handlers[message_type] = handler
    
    async def broadcast_message(self, message: Dict):
        """Broadcast message to all peers"""
        for peer in self.peers.copy():
            try:
                await self.send_message_to_peer(peer, message)
            except Exception as e:
                logger.error(f"Failed to send to {peer}: {e}")
                self.peers.remove(peer)
    
    async def send_message_to_peer(self, peer: tuple, message: Dict):
        """Send message to specific peer"""
        reader, writer = await asyncio.open_connection(peer[0], peer[1])
        try:
            writer.write(pickle.dumps(message))
            await writer.drain()
        finally:
            writer.close()

class WalletManager:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.private_keys: Dict[str, ec.EllipticCurvePrivateKey] = {}
        self.addresses: Set[str] = set()
    
    def generate_new_address(self) -> str:
        """Generate new wallet address"""
        private_key = ec.generate_private_key(ec.SECP256K1(), default_backend())
        public_key = private_key.public_key()
        
        # Create address from public key hash
        public_key_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint
        )
        
        # Double SHA256 hash
        sha256_hash = hashlib.sha256(public_key_bytes).digest()
        ripemd160_hash = hashlib.new('ripemd160', sha256_hash).digest()
        
        # Add version byte (0x00 for mainnet)
        version_byte = b'\x00'
        payload = version_byte + ripemd160_hash
        
        # Calculate checksum
        checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
        
        # Combine and encode as base58
        address_bytes = payload + checksum
        address = self.base58_encode(address_bytes)
        
        # Store the key
        self.private_keys[address] = private_key
        self.addresses.add(address)
        
        logger.info(f"Generated new address: {address}")
        return address
    
    def base58_encode(self, data: bytes) -> str:
        """Base58 encoding for addresses"""
        alphabet = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
        n = int.from_bytes(data, 'big')
        encoded = ''
        
        while n > 0:
            n, rem = divmod(n, 58)
            encoded = alphabet[rem] + encoded
        
        # Add leading '1's for zero bytes
        leading_zeros = len(data) - len(data.lstrip(b'\x00'))
        encoded = '1' * leading_zeros + encoded
        
        return encoded
    
    def get_balance(self, address: str) -> float:
        """Get balance for address from UTXOs"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT SUM(amount) FROM utxos 
                WHERE address = ? AND spent = FALSE
            ''', (address,))
            
            result = cursor.fetchone()
            return result[0] if result[0] is not None else 0.0
    
    def get_utxos(self, address: str) -> List[UTXO]:
        """Get UTXOs for address"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT tx_hash, output_index, address, amount, script_pubkey
                FROM utxos 
                WHERE address = ? AND spent = FALSE
            ''', (address,))
            
            return [UTXO(*row) for row in cursor.fetchall()]
    
    def create_transaction(self, from_address: str, to_address: str, amount: float, fee: float = 0.001) -> Optional[AfricoinTransaction]:
        """Create and sign a transaction"""
        if from_address not in self.private_keys:
            logger.error(f"No private key for address {from_address}")
            return None
        
        # Get available UTXOs
        utxos = self.get_utxos(from_address)
        if not utxos:
            logger.error(f"No UTXOs available for address {from_address}")
            return None
        
        # Select UTXOs to spend
        selected_utxos = []
        total_amount = 0.0
        
        for utxo in utxos:
            selected_utxos.append(utxo)
            total_amount += utxo.amount
            if total_amount >= amount + fee:
                break
        
        if total_amount < amount + fee:
            logger.error(f"Insufficient balance. Available: {total_amount}, Required: {amount + fee}")
            return None
        
        # Create transaction
        transaction = AfricoinTransaction()
        
        # Add inputs
        for utxo in selected_utxos:
            tx_input = TransactionInput(
                tx_hash=utxo.tx_hash,
                output_index=utxo.output_index,
                signature="",
                public_key=""
            )
            transaction.inputs.append(tx_input)
        
        # Add outputs
        transaction.outputs.append(TransactionOutput(
            address=to_address,
            amount=amount,
            script_pubkey=f"OP_DUP OP_HASH160 {to_address} OP_EQUALVERIFY OP_CHECKSIG"
        ))
        
        # Add change output if needed
        change = total_amount - amount - fee
        if change > 0:
            transaction.outputs.append(TransactionOutput(
                address=from_address,
                amount=change,
                script_pubkey=f"OP_DUP OP_HASH160 {from_address} OP_EQUALVERIFY OP_CHECKSIG"
            ))
        
        transaction.fee = fee
        
        # Sign transaction
        private_key = self.private_keys[from_address]
        transaction.sign(private_key)
        
        logger.info(f"Created transaction: {transaction.tx_hash}")
        return transaction

class AfricoinBlockchain:
    def __init__(self, db_path: str = "africoin.db"):
        self.db = DatabaseManager(db_path)
        self.wallet = WalletManager(self.db)
        self.network = NetworkManager()
        
        self.chain: List[AfricoinBlock] = []
        self.pending_transactions: List[AfricoinTransaction] = []
        self.utxo_set: Dict[str, UTXO] = {}
        
        # Consensus parameters
        self.difficulty = 4
        self.block_reward = 50.0
        self.halving_interval = 210000  # Approximately 4 years
        self.target_block_time = 600  # 10 minutes
        
        self.mining = False
        self.mining_thread = None
        
        self.setup_network_handlers()
        self.load_blockchain()
    
    def setup_network_handlers(self):
        """Setup P2P network message handlers"""
        self.network.register_message_handler('block', self.handle_block_message)
        self.network.register_message_handler('transaction', self.handle_transaction_message)
        self.network.register_message_handler('get_blocks', self.handle_get_blocks_message)
    
    async def handle_block_message(self, message: Dict, writer: asyncio.StreamWriter):
        """Handle incoming block messages"""
        block_data = message['block']
        block = self.deserialize_block(block_data)
        
        if self.validate_block(block):
            self.add_block(block)
            logger.info(f"Added new block {block.index} from peer")
    
    async def handle_transaction_message(self, message: Dict, writer: asyncio.StreamWriter):
        """Handle incoming transaction messages"""
        tx_data = message['transaction']
        transaction = self.deserialize_transaction(tx_data)
        
        if self.validate_transaction(transaction):
            self.pending_transactions.append(transaction)
            logger.info(f"Added pending transaction {transaction.tx_hash}")
    
    async def handle_get_blocks_message(self, message: Dict, writer: asyncio.StreamWriter):
        """Handle block sync requests"""
        pass  # Implement block synchronization logic

    def get_network_hashrate(self):
        blockchain_info = self._rpc_call("getblockchaininfo")
        try:
            if blockchain_info and 'difficulty' in blockchain_info:
                difficulty = blockchain_info['difficulty']
                # Hashrate = difficulty * 2^32 / block_time
                block_time = 150  # 2.5 minutes for Africoin
                hashrate_calculated = (difficulty * (2**32)) / block_time
                return self._format_hashrate(hashrate_calculated)
            
        except Exception as e:
            print(f"Error getting network hashrate: {e}")
    
    def load_blockchain(self):
        """Load blockchain from database"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM blocks ORDER BY block_index')
            
            for row in cursor.fetchall():
                block = AfricoinBlock(
                    index=row['block_index'],
                    previous_hash=row['previous_hash'],
                    difficulty=row['difficulty']
                )
                block.hash = row['hash']
                block.timestamp = row['timestamp']
                block.nonce = row['nonce']
                block.merkle_root = row['merkle_root']
                
                # Load transactions
                cursor.execute('''
                    SELECT t.* FROM transactions t
                    WHERE t.block_hash = ?
                ''', (block.hash,))
                
                for tx_row in cursor.fetchall():
                    transaction = self.load_transaction_from_db(tx_row['tx_hash'])
                    if transaction:
                        block.transactions.append(transaction)
                
                self.chain.append(block)
        
        if not self.chain:
            self.create_genesis_block()
        
        self.build_utxo_set()
        logger.info(f"Blockchain loaded with {len(self.chain)} blocks")
    
    def create_genesis_block(self):
        """Create the genesis block"""
        genesis_block = AfricoinBlock(0, "0" * 64, self.difficulty)
        
        # Create initial coinbase transaction
        coinbase_tx = AfricoinTransaction()
        coinbase_tx.outputs.append(TransactionOutput(
            address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",  # Satoshi's address homage
            amount=self.block_reward,
            script_pubkey="OP_DUP OP_HASH160 62e907b15cbf27d5425399ebf6f0fb50ebb88f18 OP_EQUALVERIFY OP_CHECKSIG"
        ))
        coinbase_tx.tx_hash = coinbase_tx.calculate_hash()
        
        genesis_block.transactions.append(coinbase_tx)
        genesis_block.mine_block()
        
        self.add_block(genesis_block)
        logger.info("Genesis block created and mined")
    
    def build_utxo_set(self):
        """Build UTXO set from blockchain"""
        self.utxo_set.clear()
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM utxos WHERE spent = FALSE')
            
            for row in cursor.fetchall():
                utxo = UTXO(
                    tx_hash=row['tx_hash'],
                    output_index=row['output_index'],
                    address=row['address'],
                    amount=row['amount'],
                    script_pubkey=row['script_pubkey']
                )
                self.utxo_set[f"{utxo.tx_hash}:{utxo.output_index}"] = utxo
    
    def validate_transaction(self, transaction: AfricoinTransaction) -> bool:
        """Validate transaction"""
        # Basic validation
        if not transaction.tx_hash or transaction.tx_hash != transaction.calculate_hash():
            return False
        
        # Verify signatures
        if not transaction.verify_signature():
            return False
        
        # Check for double spending
        for tx_input in transaction.inputs:
            utxo_key = f"{tx_input.tx_hash}:{tx_input.output_index}"
            if utxo_key not in self.utxo_set:
                return False
        
        # Verify input amount >= output amount
        input_amount = sum(self.utxo_set[f"{inp.tx_hash}:{inp.output_index}"].amount 
                          for inp in transaction.inputs)
        output_amount = sum(output.amount for output in transaction.outputs)
        
        if input_amount < output_amount:
            return False
        
        return True
    
    def validate_block(self, block: AfricoinBlock) -> bool:
        """Validate block"""
        # Check proof of work
        if block.hash[:block.difficulty] != '0' * block.difficulty:
            return False
        
        # Check block hash
        if block.hash != block.calculate_hash():
            return False
        
        # Check previous hash
        if block.index > 0 and block.previous_hash != self.chain[-1].hash:
            return False
        
        # Validate all transactions
        for transaction in block.transactions:
            if not self.validate_transaction(transaction):
                return False
        
        return True
    
    def add_block(self, block: AfricoinBlock):
        """Add validated block to blockchain"""
        self.chain.append(block)
        
        # Update UTXO set
        for transaction in block.transactions:
            self.process_transaction(transaction)
        
        # Save to database
        self.save_block_to_db(block)
        
        # Adjust difficulty periodically
        self.adjust_difficulty()
        
        logger.info(f"Block {block.index} added to blockchain")
    
    def process_transaction(self, transaction: AfricoinTransaction):
        """Process transaction and update UTXO set"""
        # Mark inputs as spent
        for tx_input in transaction.inputs:
            utxo_key = f"{tx_input.tx_hash}:{tx_input.output_index}"
            if utxo_key in self.utxo_set:
                del self.utxo_set[utxo_key]
        
        # Add new UTXOs from outputs
        for i, output in enumerate(transaction.outputs):
            utxo = UTXO(
                tx_hash=transaction.tx_hash,
                output_index=i,
                address=output.address,
                amount=output.amount,
                script_pubkey=output.script_pubkey
            )
            self.utxo_set[f"{transaction.tx_hash}:{i}"] = utxo
    
    def save_block_to_db(self, block: AfricoinBlock):
        """Save block to database"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Save block
            cursor.execute('''
                INSERT OR REPLACE INTO blocks 
                (hash, previous_hash, block_index, timestamp, nonce, difficulty, merkle_root, version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                block.hash, block.previous_hash, block.index, block.timestamp,
                block.nonce, block.difficulty, block.merkle_root, block.version
            ))
            
            # Save transactions
            for transaction in block.transactions:
                cursor.execute('''
                    INSERT OR REPLACE INTO transactions
                    (tx_hash, block_hash, version, locktime, fee, timestamp, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    transaction.tx_hash, block.hash, transaction.version,
                    transaction.locktime, transaction.fee, transaction.timestamp,
                    TransactionStatus.CONFIRMED.value
                ))
                
                # Save inputs
                for i, tx_input in enumerate(transaction.inputs):
                    cursor.execute('''
                        INSERT OR REPLACE INTO transaction_inputs
                        (tx_hash, input_index, previous_tx_hash, previous_output_index, signature, public_key)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        transaction.tx_hash, i, tx_input.tx_hash,
                        tx_input.output_index, tx_input.signature, tx_input.public_key
                    ))
                
                # Save outputs and UTXOs
                for i, output in enumerate(transaction.outputs):
                    cursor.execute('''
                        INSERT OR REPLACE INTO transaction_outputs
                        (tx_hash, output_index, address, amount, script_pubkey)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (
                        transaction.tx_hash, i, output.address,
                        output.amount, output.script_pubkey
                    ))
                    
                    cursor.execute('''
                        INSERT OR REPLACE INTO utxos
                        (tx_hash, output_index, address, amount, script_pubkey, spent)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        transaction.tx_hash, i, output.address,
                        output.amount, output.script_pubkey, False
                    ))
    
    def load_transaction_from_db(self, tx_hash: str) -> Optional[AfricoinTransaction]:
        """Load transaction from database"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM transactions WHERE tx_hash = ?', (tx_hash,))
            tx_row = cursor.fetchone()
            if not tx_row:
                return None
            
            transaction = AfricoinTransaction(version=tx_row['version'])
            transaction.tx_hash = tx_hash
            transaction.locktime = tx_row['locktime']
            transaction.fee = tx_row['fee']
            transaction.timestamp = tx_row['timestamp']
            
            # Load inputs
            cursor.execute('''
                SELECT * FROM transaction_inputs 
                WHERE tx_hash = ? ORDER BY input_index
            ''', (tx_hash,))
            
            for input_row in cursor.fetchall():
                tx_input = TransactionInput(
                    tx_hash=input_row['previous_tx_hash'],
                    output_index=input_row['previous_output_index'],
                    signature=input_row['signature'],
                    public_key=input_row['public_key']
                )
                transaction.inputs.append(tx_input)
            
            # Load outputs
            cursor.execute('''
                SELECT * FROM transaction_outputs 
                WHERE tx_hash = ? ORDER BY output_index
            ''', (tx_hash,))
            
            for output_row in cursor.fetchall():
                tx_output = TransactionOutput(
                    address=output_row['address'],
                    amount=output_row['amount'],
                    script_pubkey=output_row['script_pubkey']
                )
                transaction.outputs.append(tx_output)
            
            return transaction
    
    def adjust_difficulty(self):
        """Adjust mining difficulty based on block time"""
        if len(self.chain) % 2016 != 0:  # Every 2016 blocks (~2 weeks)
            return
        
        # Calculate actual block time for last 2016 blocks
        start_time = self.chain[-2016].timestamp
        end_time = self.chain[-1].timestamp
        actual_time = end_time - start_time
        target_time = 2016 * self.target_block_time
        
        # Adjust difficulty
        ratio = actual_time / target_time
        if ratio < 0.5:
            ratio = 0.5
        elif ratio > 2.0:
            ratio = 2.0
        
        new_difficulty = int(self.difficulty * ratio)
        self.difficulty = max(4, new_difficulty)  # Minimum difficulty
        
        logger.info(f"Difficulty adjusted to {self.difficulty} (ratio: {ratio:.2f})")
    
    def start_mining(self, miner_address: str):
        """Start mining new blocks"""
        self.mining = True
        self.mining_thread = threading.Thread(target=self._mine_loop, args=(miner_address,))
        self.mining_thread.daemon = True
        self.mining_thread.start()
        logger.info(f"Mining started with address: {miner_address}")
    
    def stop_mining(self):
        """Stop mining"""
        self.mining = False
        if self.mining_thread:
            self.mining_thread.join()
        logger.info("Mining stopped")
    
    def _mine_loop(self, miner_address: str):
        """Mining loop"""
        while self.mining:
            self.mine_new_block(miner_address)
    
    def mine_new_block(self, miner_address: str) -> bool:
        """Mine a new block with pending transactions"""
        if not self.pending_transactions:
            logger.info("No pending transactions to mine")
            return False
        
        # Create coinbase transaction
        coinbase_tx = AfricoinTransaction()
        coinbase_tx.outputs.append(TransactionOutput(
            address=miner_address,
            amount=self.get_block_reward(),
            script_pubkey=f"OP_DUP OP_HASH160 {miner_address} OP_EQUALVERIFY OP_CHECKSIG"
        ))
        coinbase_tx.tx_hash = coinbase_tx.calculate_hash()
        
        # Create new block
        previous_hash = self.chain[-1].hash
        new_block = AfricoinBlock(
            index=len(self.chain),
            previous_hash=previous_hash,
            difficulty=self.difficulty
        )
        
        # Add transactions (coinbase first)
        new_block.transactions.append(coinbase_tx)
        
        # Add pending transactions (validate first)
        valid_transactions = [tx for tx in self.pending_transactions if self.validate_transaction(tx)]
        new_block.transactions.extend(valid_transactions[:1000])  # Limit block size
        
        # Mine the block
        new_block.mine_block()
        
        # Add to blockchain
        if self.validate_block(new_block):
            self.add_block(new_block)
            self.pending_transactions = [tx for tx in self.pending_transactions if tx not in valid_transactions]
            
            # Broadcast new block
            asyncio.create_task(self.network.broadcast_message({
                'type': 'block',
                'block': self.serialize_block(new_block)
            }))
            
            return True
        
        return False
    
    def get_block_reward(self) -> float:
        """Calculate current block reward with halving"""
        halvings = len(self.chain) // self.halving_interval
        reward = self.block_reward / (2 ** halvings)
        return max(0, reward)
    
    def serialize_block(self, block: AfricoinBlock) -> Dict:
        """Serialize block for network transmission"""
        return {
            'version': block.version,
            'index': block.index,
            'previous_hash': block.previous_hash,
            'timestamp': block.timestamp,
            'transactions': [self.serialize_transaction(tx) for tx in block.transactions],
            'nonce': block.nonce,
            'merkle_root': block.merkle_root,
            'difficulty': block.difficulty,
            'hash': block.hash
        }
    
    def deserialize_block(self, data: Dict) -> AfricoinBlock:
        """Deserialize block from network data"""
        block = AfricoinBlock(
            index=data['index'],
            previous_hash=data['previous_hash'],
            difficulty=data['difficulty']
        )
        block.version = data['version']
        block.timestamp = data['timestamp']
        block.nonce = data['nonce']
        block.merkle_root = data['merkle_root']
        block.hash = data['hash']
        
        for tx_data in data['transactions']:
            block.transactions.append(self.deserialize_transaction(tx_data))
        
        return block
    
    def serialize_transaction(self, transaction: AfricoinTransaction) -> Dict:
        """Serialize transaction for network transmission"""
        return {
            'version': transaction.version,
            'inputs': [asdict(inp) for inp in transaction.inputs],
            'outputs': [asdict(out) for out in transaction.outputs],
            'locktime': transaction.locktime,
            'fee': transaction.fee,
            'timestamp': transaction.timestamp,
            'tx_hash': transaction.tx_hash
        }
    
    def deserialize_transaction(self, data: Dict) -> AfricoinTransaction:
        """Deserialize transaction from network data"""
        transaction = AfricoinTransaction(version=data['version'])
        transaction.locktime = data['locktime']
        transaction.fee = data['fee']
        transaction.timestamp = data['timestamp']
        transaction.tx_hash = data['tx_hash']
        
        for inp_data in data['inputs']:
            transaction.inputs.append(TransactionInput(**inp_data))
        
        for out_data in data['outputs']:
            transaction.outputs.append(TransactionOutput(**out_data))
        
        return transaction

class AfricoinCLI:
    """Command Line Interface for Africoin"""
    
    def __init__(self, blockchain: AfricoinBlockchain):
        self.blockchain = blockchain
        self.commands = {
            'help': self.show_help,
            'balance': self.get_balance,
            'address': self.generate_address,
            'send': self.send_transaction,
            'mine': self.start_mining,
            'stop': self.stop_mining,
            'status': self.show_status,
            'peers': self.list_peers,
            'exit': self.exit
        }
    
    def show_help(self):
        """Show available commands"""
        print("\nAfricoin CLI Commands:")
        print("  help     - Show this help message")
        print("  balance  - Show wallet balance")
        print("  address  - Generate new address")
        print("  send     - Send Africoin to address")
        print("  mine     - Start mining")
        print("  stop     - Stop mining")
        print("  status   - Show blockchain status")
        print("  peers    - List connected peers")
        print("  exit     - Exit Africoin CLI")
    
    def get_balance(self):
        """Show wallet balance"""
        total_balance = 0.0
        print("\nWallet Balances:")
        for address in self.blockchain.wallet.addresses:
            balance = self.blockchain.wallet.get_balance(address)
            total_balance += balance
            print(f"  {address}: {balance:.8f} AFC")
        print(f"Total: {total_balance:.8f} AFC")
    
    def generate_address(self):
        """Generate new wallet address"""
        address = self.blockchain.wallet.generate_new_address()
        print(f"\nNew address generated: {address}")
    
    def send_transaction(self):
        """Send transaction"""
        from_address = input("From address: ")
        to_address = input("To address: ")
        amount = float(input("Amount: "))
        fee = float(input("Fee (default 0.001): ") or "0.001")
        
        transaction = self.blockchain.wallet.create_transaction(from_address, to_address, amount, fee)
        if transaction:
            self.blockchain.pending_transactions.append(transaction)
            print(f"Transaction created: {transaction.tx_hash}")
            
            # Broadcast transaction
            asyncio.create_task(self.blockchain.network.broadcast_message({
                'type': 'transaction',
                'transaction': self.blockchain.serialize_transaction(transaction)
            }))
        else:
            print("Failed to create transaction")
    
    def start_mining(self):
        """Start mining"""
        if not self.blockchain.wallet.addresses:
            print("No addresses in wallet. Generate an address first.")
            return
        
        miner_address = list(self.blockchain.wallet.addresses)[0]
        self.blockchain.start_mining(miner_address)
        print(f"Mining started with address: {miner_address}")
    
    def stop_mining(self):
        """Stop mining"""
        self.blockchain.stop_mining()
        print("Mining stopped")
    
    def show_status(self):
        """Show blockchain status"""
        print(f"\nAfricoin Blockchain Status:")
        print(f"  Blocks: {len(self.blockchain.chain)}")
        print(f"  Difficulty: {self.blockchain.difficulty}")
        print(f"  Pending transactions: {len(self.blockchain.pending_transactions)}")
        print(f"  Block reward: {self.blockchain.get_block_reward():.8f} AFC")
        print(f"  Network: {len(self.blockchain.network.peers)} peers")
    
    def list_peers(self):
        """List connected peers"""
        print("\nConnected Peers:")
        for peer in self.blockchain.network.peers:
            print(f"  {peer[0]}:{peer[1]}")
    
    def exit(self):
        """Exit CLI"""
        self.blockchain.stop_mining()
        print("Goodbye!")
        return True
    
    def run(self):
        """Run CLI interface"""
        print("Welcome to Africoin!")
        print("Type 'help' for available commands")
        
        while True:
            try:
                command = input("\nafricoin> ").strip().lower()
                
                if command in self.commands:
                    if self.commands[command]():
                        break
                else:
                    print("Unknown command. Type 'help' for available commands.")
                    
            except KeyboardInterrupt:
                print("\nUse 'exit' to quit properly")
            except Exception as e:
                print(f"Error: {e}")

async def main():
    """Main function"""
    # Initialize Africoin blockchain
    blockchain = AfricoinBlockchain()
    
    # Start network in background
    network_task = asyncio.create_task(blockchain.network.start_server())
    
    # Start CLI
    cli = AfricoinCLI(blockchain)
    cli.run()
    
    # Cleanup
    blockchain.stop_mining()
    network_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())