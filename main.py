import functions_framework
from web3 import Web3
from eth_utils import to_checksum_address
import json
from google.cloud import storage
from google.cloud import scheduler_v1
from datetime import datetime
import os
import requests

# Environment variables
RPC_URL = os.environ.get('RPC_URL')

NATIVE_TOKEN = to_checksum_address('0x039e2fB66102314Ce7b64Ce5Ce3E5183bc94aD38') # Sonic native token (S)
USDC_TOKEN = to_checksum_address('0x29219dd400f2Bf60E5a23d13Be72B486D4038894') # USDC token address on Sonic

LBP_CA = to_checksum_address(os.environ.get('LBP_CA'))                   # Liquidity book pair contract
LBROUTER_CA = to_checksum_address(os.environ.get('LBROUTER_CA'))         # Liquidity router contract
REWARDER_CA  = to_checksum_address(os.environ.get('REWARDER_CA'))        # Pair rewarder contract

REWARD_WALLET = to_checksum_address(os.environ.get('REWARD_WALLET'))

PRIVATE_KEY = os.environ.get('PRIVATE_KEY')

REWARD_CONF = float(os.environ.get('REWARD_CONF'))  # 0 = transfer rewards, 1 = trade rewards for USDC

PROJECT_ID = os.environ.get('PROJECT_ID')
BUCKET_NAME = os.environ.get('BUCKET_NAME')
SCHEDULER_LOCATION = os.environ.get('SCHEDULER_LOCATION')
SCHEDULER_JOB_NAME = os.environ.get('SCHEDULER_JOB_NAME')

LOWER_LIM = float(os.environ.get('LOWER_LIM'))
UPPER_LIM = float(os.environ.get('UPPER_LIM'))
MAX_CHANGE = float(os.environ.get('MAX_CHANGE'))

PUSHOVER_TOKEN = os.environ.get('PUSHOVER_TOKEN')
PUSHOVER_USER = os.environ.get('PUSHOVER_USER')

class SonicConnection:
    def __init__(self):
        # Connect to Sonic
        self.web3 = Web3(Web3.HTTPProvider(RPC_URL))
        self.lbp_contract = None
        self.lbrouter_contract = None
        self.rewarder_contract = None

        # Load Sonic account
        self.account = self.web3.eth.account.from_key(PRIVATE_KEY)
        self.wallet_address = self.account.address

        # Load contract ABIs
        with open('lbp_contract_abi.json', 'r') as f:
            self.lbp_abi = json.load(f)
        with open('lbrouter_contract_abi.json', 'r') as f:
            self.lbrouter_abi = json.load(f)
        with open('erc20_contract_abi.json', 'r') as f:
            self.erc20_contract_abi = json.load(f)
        with open('rewarder_contract_abi.json', 'r') as f:
            self.rewarder_abi = json.load(f)
        
        # Initialize contracts
        self.lbp_contract = self.web3.eth.contract(
            address = LBP_CA,
            abi = self.lbp_abi
            )
        self.lbrouter_contract = self.web3.eth.contract(
            address = LBROUTER_CA,
            abi = self.lbrouter_abi
            )
        self.rewarder_contract = self.web3.eth.contract(
            address = REWARDER_CA,
            abi = self.rewarder_abi
        )
        
        # Get current METRO token address
        self.metro_token_address = self.web3.to_checksum_address(self.rewarder_contract.functions.getRewardToken().call())

        # Find bin steps
        self.bin_step = self.lbp_contract.functions.getBinStep().call()
    
    # Check for successful connection
    def is_connected(self):
        return self.web3.is_connected()
    
    def get_token_addresses(self) -> tuple:
        """Get the token addresses from the LBP contract"""
        try:
            token_x = self.lbp_contract.functions.getTokenX().call()
            token_y = self.lbp_contract.functions.getTokenY().call()
            return token_x, token_y

        except Exception as e:
            print("Failed to get token addresses")
            raise Exception(f"Failed to get token addresses: {e}")

    def get_token_decimals(self, token_address):
        """Get the token decimals from the LBP contract"""
        try:
            token_contract = self.web3.eth.contract(
                address = self.web3.to_checksum_address(token_address),
                abi = self.erc20_contract_abi
            )
            decimals = token_contract.functions.decimals().call()
            return decimals

        except Exception as e:
            print("Failed to get token decimals")
            raise Exception(f"Failed to get token decimals: {e}")

    def get_token_symbol(self, token_address):
        """Get the token symbol from the LBP contract"""
        try:
            token_contract = self.web3.eth.contract(
                address = self.web3.to_checksum_address(token_address),
                abi = self.erc20_contract_abi
            )
            symbol = token_contract.functions.symbol().call()
            return symbol

        except Exception as e:
            print("Failed to get token symbol")
            raise Exception(f"Failed to get token symbol: {e}")

    def get_pair_symbols(self) -> tuple:
        """Get the token symbols for file naming"""
        try:
            token_x, token_y = self.get_token_addresses()
            symbol_x = self.get_token_symbol(token_x)
            symbol_y = self.get_token_symbol(token_y)
            return symbol_x, symbol_y
        except Exception as e:
            print(f"Failed to get pair symbols: {e}")
            return "UNKNOWN", "UNKNOWN"
    
    def get_file_prefix(self) -> str:
        """Generate file prefix based on token pair"""
        symbol_x, symbol_y = self.get_pair_symbols()
        return f"{symbol_x}_{symbol_y}"

    def get_token_balance(self, token_address) -> tuple:
        """Get chosen token balance"""
        try:
            # Create token contract instance
            token_contract = self.web3.eth.contract(
                address = self.web3.to_checksum_address(token_address),
                abi = self.erc20_contract_abi
            )

            symbol = token_contract.functions.symbol().call()
            decimals = token_contract.functions.decimals().call()
            balance_wei = token_contract.functions.balanceOf(self.wallet_address).call()
            balance = balance_wei / (10 ** decimals)

            return symbol, decimals, balance_wei, balance

        except Exception as e:
            print("Failed to get token balance")
            raise Exception(f"Failed to get token balance: {e}")
    
    def get_native_balance(self) -> tuple:
        """Get native token balance"""
        try:
            symbol = "S"
            ### ADD CONTRACT ADDRESS HERE
            decimals = 18
            balance_s_wei = self.web3.eth.get_balance(self.wallet_address)
            balance_s = float(self.web3.from_wei(balance_s_wei, 'ether'))

            return symbol, decimals, balance_s_wei, balance_s

        except Exception as e:
            print("Failed to get native balance")
            raise Exception(f"Failed to get native balance: {e}")
    
    def get_current_price(self):
        """Get the active bin price"""
        token_x, token_y = self.get_token_addresses()
        decimals_x = self.get_token_decimals(token_x)
        decimals_y = self.get_token_decimals(token_y)

        active_id = self.lbp_contract.functions.getActiveId().call()
        raw_price = self.lbp_contract.functions.getPriceFromId(active_id).call()
        price = (raw_price / (2**128)) * (10**(decimals_x - decimals_y))
        return{
            "price": price,
            "token_x": token_x,
            "token_y": token_y
        }
    
    def gas_optimizer(self, transaction, fallback_gas, buffer_factor=1.2):
        """
        Estimate and optimize gas for a transaction and add a safety buffer

        Args:
            transaction: The built transaction dictionary
            buffer_factor: Safety factor to multiply the gas estimate by (default 1.2)

        Returns:
            int: Estimated gas with buffer applied
        """
        try:
            # Get base estimate from network
            estimated_gas = self.web3.eth.estimate_gas(transaction)
            # Apply buffer
            optimized_gas = int(estimated_gas * buffer_factor)
            return optimized_gas

        except Exception as e:
            print(f"Gas estimation failed: {e}")
            return fallback_gas

    def check_token_approval(self, token_address: str, spender_address: str) -> bool:
        """Check token approval status"""
        token_contract = self.web3.eth.contract(
                address = self.web3.to_checksum_address(token_address),
                abi = self.erc20_contract_abi
            )
        
        symbol = token_contract.functions.symbol().call()
        decimals = token_contract.functions.decimals().call()
        allowance = token_contract.functions.allowance(self.wallet_address, spender_address).call()
        allowance_readable = allowance / (10**decimals)

        allowance_sufficient = allowance > (10**decimals * 1000000)

        print(f"{symbol} {allowance_readable}")
        return allowance_sufficient

    def approve_token(self, token_address: str, spender_address: str) -> bool:
        """Approve token spending"""
        try:
            token_contract = self.web3.eth.contract(
                address = self.web3.to_checksum_address(token_address),
                abi = self.erc20_contract_abi
            )

            symbol = token_contract.functions.symbol().call()

            # Max uint256 value (2^256 -1)
            max_amount = (2**256) - 1

            # Build approval transaction
            approve_tx = token_contract.functions.approve(
                spender_address, max_amount
            ).build_transaction(
                {
                    'from': self.wallet_address,
                    'gasPrice': self.web3.eth.gas_price,
                    'nonce': self.web3.eth.get_transaction_count(self.wallet_address)
                }
            )

            # Estimate and optimize gas
            optimized_gas = self.gas_optimizer(approve_tx, 100000)

            # Add gas to transaction
            approve_tx['gas'] = optimized_gas

            # Sign and send transaction
            signed_tx = self.web3.eth.account.sign_transaction(
                approve_tx, self.account._private_key
            )
            
            # Transaction hash
            tx_hash = self.web3.eth.send_raw_transaction(
                signed_tx.rawTransaction
            )

            # Wait for the transaction receipt
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)

            if receipt.status == 1:
                print(f"{symbol} APPROVED")
                return True
            else:
                print(f"Falied to approve {symbol}")
                return False
        except Exception as e:
            print(f"Failed to approve token: {e}")
            return False

    def add_liquidity(self):
        """Add liquididity to the contract"""
        try:
            # Get active ID
            active_id = self.lbp_contract.functions.getActiveId().call()

            # Get token addresses
            token_x, token_y = self.get_token_addresses()
            symbol_x, decimals_x, balance_x_wei, balance_x = self.get_token_balance(token_x)
            symbol_y, decimals_y, balance_y_wei, balance_y = self.get_token_balance(token_y)

            # Approve token spending if required
            if not self.check_token_approval(token_x, LBROUTER_CA):
                token_x_approved = self.approve_token(token_x, LBROUTER_CA)
            
            if not self.check_token_approval(token_y, LBROUTER_CA):
                token_y_approved = self.approve_token(token_y, LBROUTER_CA)

            def position_amount(symbol, balance):
                if balance == 0:
                    print(f"No {symbol} available for liquidity")
                    return 0
                elif balance <= 1:
                    return balance * 0.1
                else:
                    return balance - 1

            # Calculate amounts
            amount_x = position_amount(symbol_x, balance_x)
            amount_y = position_amount(symbol_y, balance_y)

            amount_x_wei = int(amount_x * 10**decimals_x)
            amount_y_wei = int(amount_y * 10**decimals_y)

            if amount_x == 0 or amount_y == 0:
                return

            # Prepare liquidity parameters
            add_params = (
                token_x,                # tokenX
                token_y,                # tokenY
                self.bin_step,          # binStep
                amount_x_wei,           # amountX
                amount_y_wei,           # amountY
                0,                      # amountXMin
                0,                      # amountYMin
                active_id,              # activeIdDesired
                10,                     # idSlippage
                [0],                    # deltaIds
                [1000000000000000000],  # distributionX
                [1000000000000000000],  # distributionY
                self.wallet_address,    # to
                self.wallet_address,    # refundTo
                int(datetime.now().timestamp()) + 3600  # deadline
            )

            # Build transaction
            add_tx = self.lbrouter_contract.functions.addLiquidity(
                add_params
            ).build_transaction(
                {
                    'from': self.wallet_address,
                    'gasPrice': self.web3.eth.gas_price,
                    'nonce': self.web3.eth.get_transaction_count(self.wallet_address),
                }
            )

            # Estimate and optimize gas
            optimized_gas = self.gas_optimizer(add_tx, 500000)

            # Add gas to transaction
            add_tx['gas'] = optimized_gas

            # Sign and send transaction
            signed_tx = self.web3.eth.account.sign_transaction(
                add_tx, self.account._private_key
            )

            tx_hash = self.web3.eth.send_raw_transaction(
                signed_tx.rawTransaction
            )

            # Wait for transaction receipt
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)

            if receipt.status == 1:
                new_position = {
                    "bin_id": active_id,
                    "token_x": token_x,
                    "token_y": token_y,
                    "size_x": amount_x,
                    "size_y": amount_y,
                    "to_address": self.wallet_address
                }
                print("Liquidity sucessfully added")
                return new_position
            else:
                print("Add liquidity transaction failed")
                return False

        except Exception as e:
            print(f"Failed to add liquidity: {e}")
            return False

    def remove_liquidity(self, position) -> bool:
        """Withdraw liquididity from the contract"""
        try:
            token_x, token_y = self.get_token_addresses()
            bin_id = int(position["bin_id"])

            # Get previous bin amount
            amount = self.lbp_contract.functions.balanceOf(
                self.wallet_address,
                bin_id
            ).call()

            if amount == 0:
                return True

            # Prepare liquidity parameters
            remove_params = (
                token_x,
                token_y,
                self.bin_step,
                0,  # amountXMin
                0,  # amountYMin
                [bin_id],  # ids array
                [amount],  # amounts array
                self.wallet_address,
                int(datetime.now().timestamp()) + 3600
            )

            # Build transaction
            remove_tx = self.lbrouter_contract.functions.removeLiquidity(
                *remove_params
            ).build_transaction(
                {
                    'from': self.wallet_address,
                    'gasPrice': self.web3.eth.gas_price,
                    'nonce': self.web3.eth.get_transaction_count(self.wallet_address),
                }
            )

            # Estimate and optimize gas
            optimized_gas = self.gas_optimizer(remove_tx, 1000000)

            # Add gas to transaction
            remove_tx['gas'] = optimized_gas

            # Sign and send transaction
            signed_tx = self.web3.eth.account.sign_transaction(
                remove_tx, self.account._private_key
            )

            tx_hash = self.web3.eth.send_raw_transaction(
                signed_tx.rawTransaction
            )

            # Wait for transaction receipt
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)

            print(f"Liquidity sucessfully removed from bin {bin_id}")

            return receipt.status == 1
        
        except Exception as e:
            print(f"Failed to remove liquidity: {e}")
            return False
        
    def claim_rewards(self, position):
        """Claim any pending rewards for the specified bin"""
        try:
            bin_id = int(position["bin_id"])

            pending_rewards_wei = self.rewarder_contract.functions.getPendingRewards(
                self.wallet_address,
                [bin_id]
            ).call()

            pending_rewards = pending_rewards_wei / (10 ** 18)

            if pending_rewards > 0:
                claim_tx = self.rewarder_contract.functions.claim(
                    self.wallet_address,
                    [bin_id]
                ).build_transaction({
                    'from': self.wallet_address,
                    'gas': 200000,
                    'gasPrice': self.web3.eth.gas_price,
                    'nonce': self.web3.eth.get_transaction_count(self.wallet_address),
                })

                 # Sign and send transaction
                signed_tx = self.web3.eth.account.sign_transaction(
                    claim_tx, self.account._private_key
                )

                tx_hash = self.web3.eth.send_raw_transaction(
                    signed_tx.rawTransaction
                )

                # Wait for transaction receipt
                receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)

                if receipt.status == 1:
                    print("Successfully claimed rewards")
                    return True
                else:
                    print("Failed to claim rewards")
                    return False
            else:
                print("No rewards to claim")
                return True

        except Exception as e:
            print("Failed to claim rewards")
            return False
    
    def transfer_rewards(self):
        """Send all reward tokens to central rewards wallet"""
        try:
            # Instantiate metro contract
            metro_contract = self.web3.eth.contract(
                address = self.web3.to_checksum_address(self.metro_token_address),
                abi = self.erc20_contract_abi
            )

            # Check current metro balance
            symbol, decimals, balance_wei, balance = self.get_token_balance(self.metro_token_address)

            if balance_wei <= 0:
                print("No METRO tokens to send")
                return True
            
            transfer_tx = metro_contract.functions.transfer(
                REWARD_WALLET,
                balance_wei
            ).build_transaction(
                {
                    'from': self.wallet_address,
                    'gasPrice': self.web3.eth.gas_price,
                    'nonce': self.web3.eth.get_transaction_count(self.wallet_address),
                }
            )

            # Estimate and optimize gas
            optimized_gas = self.gas_optimizer(transfer_tx, 500000)

            # Add gas to transaction
            transfer_tx['gas'] = optimized_gas

            # Sign and send transaction
            signed_tx = self.web3.eth.account.sign_transaction(
                transfer_tx, self.account._private_key
            )

            tx_hash = self.web3.eth.send_raw_transaction(
                signed_tx.rawTransaction
            )

            # Wait for transaction receipt
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)

            if receipt.status == 1:
                print("METRO successfully transferred")
                return True
            else:
                print("METRO transfer failed")
                return False
            
        except Exception as e:
            print("Failed to transfer rewards")
            return False

    def trade_metro_to_usdc(self):
        """
        Trade METRO rewards for USDC or S

        Args:
            None
        
        Returns:
            bool: True if trade successful, False otherwise
        """

        try:
            # Get input token details
            token_x = self.metro_token_address
            symbol_x, decimals_x, balance_x_wei, balance_x = self.get_token_balance(token_x)
            amount_in_x_wei = balance_x_wei   # Trade all available METRO
            
            # Check that there is something to trade
            if amount_in_x_wei == 0:
                print("No METRO tokens to trade")
                return True
            
            # Check native S balance
            symbol_s, decimals_s, balance_s_wei, balance_s = self.get_native_balance()

            # Check that the token is approved for spending by the LBRouter contract, and if not approve it
            if not self.check_token_approval(token_x, LBROUTER_CA):
                token_x_approved = self.approve_token(token_x, LBROUTER_CA)

            # Set trade parameters based on gas balance, if balance is low then trade to S first
            if balance_s > 5:
                token_y = USDC_TOKEN
                symbol_y, decimals_y, balance_y_wei, balance_y = self.get_token_balance(token_y)

                amount_in_x_wei = balance_x_wei
                trade_function = self.lbrouter_contract.functions.swapExactTokensForTokens    
                path = (
                    [0, 4],                             # Bin steps for each hop    [METRO->S, S->USDC]
                    [0, 2],                             # Versions for each hop     [METRO->S, S->USDC]
                    [token_x, NATIVE_TOKEN, token_y]    # Token path (2 hops)
                )
                
            else:
                token_y = NATIVE_TOKEN
                symbol_y = symbol_s

                amount_in_x_wei = min(balance_x_wei, 50 * (10 ** decimals_x))  # Trade enough METRO to get 5 S
                trade_function = self.lbrouter_contract.functions.swapExactTokensForNATIVE
                path = (
                    [0],                                # Bin steps for each hop    [METRO->USDC]
                    [0],                                # Versions for each hop     [METRO->USDC]
                    [token_x, token_y]                  # Token path (1 hop)
                )
            
            # Set minimum output amount
            amount_min_y_wei = 1  ### This can be optimised later with slippage control and output simulation using the lbp contract getLBPairInformation information

            trade_params = (
                    amount_in_x_wei,                        # Amount token x in
                    amount_min_y_wei,                       # Amount token y out min
                    path,                                   # Path
                    self.wallet_address,                    # To address must be payable so requires checksum
                    int(datetime.now().timestamp()) + 3600  # Deadline
            )

            trade_tx = trade_function(
                *trade_params
            ).build_transaction(
                {
                    'from': self.wallet_address,
                    'gasPrice': self.web3.eth.gas_price,
                    'nonce': self.web3.eth.get_transaction_count(self.wallet_address),
                }
            )

            # Estimate and optimize gas
            optimized_gas = self.gas_optimizer(trade_tx, 500000)

            # Add gas to transaction
            trade_tx['gas'] = optimized_gas

            # Sign and send transaction
            signed_tx = self.web3.eth.account.sign_transaction(
                trade_tx, self.account._private_key
            )

            tx_hash = self.web3.eth.send_raw_transaction(
                signed_tx.rawTransaction
            )

            # Wait for transaction receipt
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)

            # Logging details
            amount_in_x = amount_in_x_wei / (10 ** decimals_x)

            if receipt.status == 1:
                print(f"{amount_in_x} {symbol_x} successfully traded for {symbol_y}")
                return True
            else:
                print("METRO to USDC trade failed")
                return False

        except Exception as e:
            print(f"Failed to trade METRO to USDC: {e}")
            return False
            
class CloudStorageHandler:
    def __init__(self, bucket_name):
        self.storage_client = storage.Client()
        self.bucket = self.storage_client.bucket(bucket_name)

    def read_json_file(self, filename):
        # Generic method to read any JSON file from bucket
        try:
            blob = self.bucket.blob(filename)
            if not blob.exists():
                return None
            return json.loads(blob.download_as_text())
        except Exception as e:
            print(f"Error reading {filename}: {e}")
            return None
    
    def write_json_file(self, filename, data):
        # Generic method to write any JSON file to bucket
        try:
            blob = self.bucket.blob(filename)
            blob.upload_from_string(json.dumps(data, indent=2))
            return True
        except Exception as e:
            print(f"Error writing {filename}: {e}")
            return False 

# Global Sonic connection instance
sonic = SonicConnection()
data = CloudStorageHandler(BUCKET_NAME)

@functions_framework.http
def manage_liquidity(request):

    print("Function started")

    try:
        # Check Sonic connection
        if not sonic.is_connected():
            print("Failed to connect to Sonic network")
            return {"error": "Failed to connect to Sonic network"}

        # Generate filenames
        file_prefix = sonic.get_file_prefix()
        op_file = f"{file_prefix}_time.json"
        price_file = f"{file_prefix}_price.json"
        position_file = f"{file_prefix}_position.json"

        # Initialize variables
        first_run = False
        current_position = None
        last_position = None
        valid_position = False
        change_acceptable = False        

        # Read and initialize operational data
        last_op_data = data.read_json_file(op_file)

        current_op_data = {
            "timestamp": datetime.now().isoformat()
        }

        data.write_json_file(op_file, current_op_data)

        if last_op_data is None:
            last_op_data = current_op_data

        last_date = datetime.fromisoformat(last_op_data["timestamp"]).date()
        current_date = datetime.fromisoformat(current_op_data["timestamp"]).date()

        # Read and initialise price data
        last_price_data = data.read_json_file(price_file)

        current_price_data = sonic.get_current_price()
        current_price_data["timestamp"] = datetime.now().isoformat()

        if last_price_data is None:
            data.write_json_file(price_file, current_price_data)
            last_price_data = data.read_json_file(price_file)
            first_run = True
        
        last_price = last_price_data["price"]
        current_price = current_price_data["price"]

        in_limits = current_price > LOWER_LIM and current_price < UPPER_LIM

        if last_price > 0:
            price_diff = current_price - last_price
            price_diff_pc = (price_diff / last_price) * 100
            change_acceptable = abs(price_diff_pc) < MAX_CHANGE
        else:
            price_diff_pc = 0
            change_acceptable = True

        # Read previous position
        last_position = data.read_json_file(position_file)

        if last_position:
            valid_position = (
                last_position.get("bin_id") and
                last_position.get("token_x") and
                last_position.get("token_y")
            )

        if not in_limits or not change_acceptable:
            return {"status": "no_action", "reason": "Price out of limits"}
        
        price_changed = abs(current_price - last_price) > 0

        sonic.trade_metro_to_usdc()

        if valid_position and not first_run:

            # Claim and transfer rewards daily
            if current_date != last_date:
                if sonic.claim_rewards(last_position):
                    print("Daily METRO rewards claim successful")
                    if REWARD_CONF == 0:
                        if sonic.transfer_rewards():
                            print("Daily rewards transfer successful")
                        else:
                            print("Daily rewards transfer failed")
                    elif REWARD_CONF == 1:
                        if sonic.trade_metro_to_usdc():
                            print("Daily rewards trade successful")
                        else:
                            print("Daily rewards trade failed")
                else:
                    print("Daily METRO rewards claim failed")

            # Liquidity management
            if price_changed:
                try:
                    print("Test: Attempting to remove liquidity")

                    if sonic.remove_liquidity(last_position):
                        sonic.claim_rewards(last_position)
                        current_position = sonic.add_liquidity()

                        if current_position:
                            print("Test: Liquidity added successfully")

                        else:
                            failure_count(file_prefix)
                            return {"error": "Failed to add liquidity"}
                        
                    else:
                        failure_count(file_prefix)
                        return {"error": "Failed to remove liquidity"}

                except Exception as e:
                    return {"error": f"Liquidity operation failed: {e}"}

            else:
                return {"status": "no_action", "reason": "Position exists, no price change"}

        else:
            print("Test: Entering first time run logic")
            try:
                current_position = sonic.add_liquidity()
                if not current_position:
                    return {"error": "Failed to add initial liquidity"}

            except Exception as e:
                return {"error": f"Failed to add liquidity: {e}"}

        if current_position:
            data.write_json_file(position_file, current_position)
            data.write_json_file(price_file, current_price_data)
        
        return {"status": "success", "position": current_position}

    except Exception as e:
        print(f"error: Function failed: {str(e)}")
        return {"error": f"Function failed: {str(e)}"}

def failure_count(file_prefix):
    """Simple failure counter with emergency stop at 3"""
    failure_file = f"{file_prefix}_failures.json"
    failure_data = data.read_json_file(failure_file) or {"count": 0}
    
    failure_data["count"] += 1
    failure_data["last_failure"] = datetime.now().isoformat()
    
    data.write_json_file(failure_file, failure_data)
    
    if failure_data["count"] >= 3:

        emergency_stop(file_prefix)

        failure_data["last_estop"] = datetime.now().isoformat()
        failure_data["count"] = 0

    return failure_data["count"]

def emergency_stop(file_prefix):
    """Pause the scheduler"""
    client = scheduler_v1.CloudSchedulerClient()
    job_path = client.job_path(PROJECT_ID, SCHEDULER_LOCATION, SCHEDULER_JOB_NAME)
    try:
        client.pause_job(request={"name": job_path})

        message = f"CRITICAL: {file_prefix} liquidity manager suspended after 3 consecutive failures. Scheduler paused."
        title = f"{file_prefix} Metro Auto DLMM"

        push_notification(
            message,
            title,
            1
        )

        print("Scheduler paused successfully")
        return True
    except Exception as e:
        print(f"Failed to pause scheduler: {e}")
        return False

def push_notification(message, title, priority):
    pushover_data = {
        'token': PUSHOVER_TOKEN,
        'user': PUSHOVER_USER,
        'message': message,
        'title': title,
        'priority': priority  # High priority
    }

    try:
        requests.post("https://api.pushover.net/1/messages.json", data=pushover_data)
        print("Emergency notification sent")
        return True
    except Exception as e:
        print(f"Failed to raise notification: {e}")
        return False