import hashlib
import json
import time
from typing import Dict, List, Any, Optional, Callable
from enum import Enum
import re

class ContractState(Enum):
    ACTIVE = "active"
    EXECUTED = "executed"
    FAILED = "failed"
    EXPIRED = "expired"

class AfricoinSmartContract:
    def __init__(self, contract_id: str, code: str, creator: str, gas_limit: int = 1000000):
        self.contract_id = contract_id
        self.code = code
        self.creator = creator
        self.gas_limit = gas_limit
        self.gas_used = 0
        self.state = ContractState.ACTIVE
        self.storage: Dict[str, Any] = {}
        self.created_at = time.time()
        self.updated_at = time.time()
        
    def execute(self, function: str, args: List[Any], caller: str, gas_price: float = 1.0) -> Dict[str, Any]:
        """Execute contract function with gas accounting"""
        start_gas = self.gas_used
        
        try:
            # Parse and execute contract code
            result = self._execute_function(function, args, caller)
            
            # Calculate gas cost
            gas_cost = self.gas_used - start_gas
            total_cost = gas_cost * gas_price
            
            return {
                'success': True,
                'result': result,
                'gas_used': gas_cost,
                'total_cost': total_cost
            }
            
        except Exception as e:
            self.state = ContractState.FAILED
            return {
                'success': False,
                'error': str(e),
                'gas_used': self.gas_used - start_gas
            }
    
    def _execute_function(self, function: str, args: List[Any], caller: str) -> Any:
        """Execute specific contract function"""
        self.gas_used += 100  # Base gas cost
        
        # Simple VM for contract execution
        if function == "transfer":
            return self._transfer(args, caller)
        elif function == "get_balance":
            return self._get_balance(args)
        elif function == "multi_sig":
            return self._multi_sig(args, caller)
        elif function == "time_lock":
            return self._time_lock(args, caller)
        else:
            raise ValueError(f"Unknown function: {function}")
    
    def _transfer(self, args: List[Any], caller: str) -> Dict[str, Any]:
        """Token transfer function"""
        if len(args) != 2:
            raise ValueError("Transfer requires 2 arguments: to, amount")
        
        to_address, amount = args
        
        # Check balances (simplified)
        sender_balance = self.storage.get(f"balance_{caller}", 0)
        if sender_balance < amount:
            raise ValueError("Insufficient balance")
        
        # Update balances
        self.storage[f"balance_{caller}"] = sender_balance - amount
        self.storage[f"balance_{to_address}"] = self.storage.get(f"balance_{to_address}", 0) + amount
        
        self.gas_used += 50
        return {"success": True, "from": caller, "to": to_address, "amount": amount}
    
    def _get_balance(self, args: List[Any]) -> Dict[str, Any]:
        """Get balance function"""
        if len(args) != 1:
            raise ValueError("Get_balance requires 1 argument: address")
        
        address = args[0]
        balance = self.storage.get(f"balance_{address}", 0)
        
        self.gas_used += 10
        return {"address": address, "balance": balance}
    
    def _multi_sig(self, args: List[Any], caller: str) -> Dict[str, Any]:
        """Multi-signature contract function"""
        if len(args) < 3:
            raise ValueError("Multi_sig requires at least 3 arguments: required_signatures, addresses, transaction_data")
        
        required_signatures, addresses, tx_data = args[0], args[1], args[2]
        
        # Initialize or update signature count
        tx_hash = hashlib.sha256(json.dumps(tx_data).encode()).hexdigest()
        current_signatures = self.storage.get(f"signatures_{tx_hash}", set())
        current_signatures.add(caller)
        self.storage[f"signatures_{tx_hash}"] = current_signatures
        
        self.gas_used += 30
        
        if len(current_signatures) >= required_signatures:
            # Execute the transaction
            return {"executed": True, "signatures": list(current_signatures)}
        else:
            return {"executed": False, "current_signatures": len(current_signatures), "required": required_signatures}
    
    def _time_lock(self, args: List[Any], caller: str) -> Dict[str, Any]:
        """Time-lock contract function"""
        if len(args) != 3:
            raise ValueError("Time_lock requires 3 arguments: release_time, recipient, amount")
        
        release_time, recipient, amount = args
        
        if time.time() < release_time:
            raise ValueError(f"Funds locked until {release_time}")
        
        # Check and transfer funds
        sender_balance = self.storage.get(f"balance_{caller}", 0)
        if sender_balance < amount:
            raise ValueError("Insufficient balance")
        
        self.storage[f"balance_{caller}"] = sender_balance - amount
        self.storage[f"balance_{recipient}"] = self.storage.get(f"balance_{recipient}", 0) + amount
        
        self.gas_used += 40
        return {"released": True, "amount": amount, "recipient": recipient}

class SmartContractEngine:
    def __init__(self):
        self.contracts: Dict[str, AfricoinSmartContract] = {}
        self.contract_templates: Dict[str, str] = {
            "token": self._load_template("token"),
            "multi_sig": self._load_template("multi_sig"),
            "time_lock": self._load_template("time_lock"),
            "decentralized_exchange": self._load_template("dex")
        }
    
    def deploy_contract(self, template: str, creator: str, parameters: Dict[str, Any]) -> str:
        """Deploy a new smart contract"""
        if template not in self.contract_templates:
            raise ValueError(f"Unknown contract template: {template}")
        
        contract_id = hashlib.sha256(f"{creator}{time.time()}".encode()).hexdigest()[:32]
        
        # Generate contract code from template
        contract_code = self._generate_contract_code(template, parameters)
        
        contract = AfricoinSmartContract(contract_id, contract_code, creator)
        self.contracts[contract_id] = contract
        
        return contract_id
    
    def execute_contract(self, contract_id: str, function: str, args: List[Any], caller: str) -> Dict[str, Any]:
        """Execute a contract function"""
        if contract_id not in self.contracts:
            raise ValueError(f"Contract not found: {contract_id}")
        
        contract = self.contracts[contract_id]
        return contract.execute(function, args, caller)
    
    def _load_template(self, template_name: str) -> str:
        """Load contract template (simplified)"""
        templates = {
            "token": """
                CONTRACT Token:
                    FUNC transfer(to, amount):
                        IF balance[msg.sender] >= amount:
                            balance[msg.sender] -= amount
                            balance[to] += amount
                            RETURN True
                        ELSE:
                            RETURN False
                    
                    FUNC get_balance(address):
                        RETURN balance[address]
            """,
            "multi_sig": """
                CONTRACT MultiSig:
                    FUNC approve(tx_data):
                        signatures[tx_hash].add(msg.sender)
                        IF len(signatures[tx_hash]) >= required_signatures:
                            EXECUTE tx_data
                            RETURN True
                        RETURN False
            """
        }
        return templates.get(template_name, "")
    
    def _generate_contract_code(self, template: str, parameters: Dict[str, Any]) -> str:
        """Generate contract code from template and parameters"""
        code = self.contract_templates[template]
        
        # Replace parameters in template
        for key, value in parameters.items():
            code = code.replace(f"${key}", str(value))
        
        return code