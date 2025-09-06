import functions_framework
from web3 import Web3
import json
from google.cloud import storage
from google.cloud import scheduler_v1
from datetime import datetime
import os
import requests

# Environment variables
RPC_URL = os.environ.get('RPC_URL')
LBP_CA = os.environ.get('LBP_CA')           # Liquidity book pair contract
LBROUTER_CA = os.environ.get('LBROUTER_CA')      # Liquidity router contract
PRIVATE_KEY = os.environ.get('PRIVATE_KEY')

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
        
        # Initialize contracts
        self.lbp_contract = self.web3.eth.contract(
            address = self.web3.to_checksum_address(LBP_CA),
            abi = self.lbp_abi
            )
        self.lbrouter_contract = self.web3.eth.contract(
            address = self.web3.to_checksum_address(LBROUTER_CA),
            abi = self.lbrouter_abi
            )
        
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
            decimals = 18
            balance_wei = self.web3.eth.get_balance(self.wallet_address)
            balance_s = float(self.web3.from_wei(balance_wei, 'ether'))

            return symbol, decimals, balance_wei, balance_s

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
                    'gas': 100000,
                    'gasPrice': self.web3.eth.gas_price,
                    'nonce': self.web3.eth.get_transaction_count(self.wallet_address)
                }
            )

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
            symbol_x, decimals_x, balance_wei_x, balance_x = self.get_token_balance(token_x)
            symbol_y, decimals_y, balance_wei_y, balance_y = self.get_token_balance(token_y)

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
            ).build_transaction({
                'from': self.wallet_address,
                'gas': 500000,
                'gasPrice': self.web3.eth.gas_price,
                'nonce': self.web3.eth.get_transaction_count(self.wallet_address),
            })

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

            print(f"bin_step: {self.bin_step} (type: {type(self.bin_step).__name__})")
            print(f"bin_id: {bin_id} (type: {type(bin_id).__name__})")
            print(f"amount: {amount} (type: {type(amount).__name__})")

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

            print(f"Remove liquidity parameters:")
            print(f"  token_x: {remove_params[0]}")
            print(f"  token_y: {remove_params[1]}")
            print(f"  bin_step: {remove_params[2]}")
            print(f"  amountXMin: {remove_params[3]}")
            print(f"  amountYMin: {remove_params[4]}")
            print(f"  ids: {remove_params[5]}")
            print(f"  amounts: {remove_params[6]}")
            print(f"  to: {remove_params[7]}")
            print(f"  deadline: {remove_params[8]}")

            # Build transaction
            remove_tx = self.lbrouter_contract.functions.removeLiquidity(
                *remove_params
            ).build_transaction({
                'from': self.wallet_address,
                'gas': 1000000,
                'gasPrice': self.web3.eth.gas_price,
                'nonce': self.web3.eth.get_transaction_count(self.wallet_address),
            })

            # Sign and send transaction
            signed_tx = self.web3.eth.account.sign_transaction(
                remove_tx, self.account._private_key
            )

            tx_hash = self.web3.eth.send_raw_transaction(
                signed_tx.rawTransaction
            )

            # Wait for transaction receipt
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)

            return receipt.status == 1
        except Exception as e:
            print(f"Failed to remove liquidity: {e}")
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

        """
        message = f"USDT/USDC price Change! New price: {current_price['price']:.6f}\nBin ID: {current_price['active_bin_id']}"
        message += f"\nPrevious: {previous_data['price']:.6f}"
        message += f"\nChange: {result['price_change_percent']:.3f}%" 
        
        pushover_data = {
            'token': PUSHOVER_TOKEN,
            'user': PUSHOVER_USER,
            'message': message,
            'title': 'Metro Price Alert'
        }

        # Send notification
        requests.post("https://api.pushover.net/1/messages.json", data=pushover_data)
        """

        # Generate filenames
        file_prefix = sonic.get_file_prefix()
        price_file = f"{file_prefix}_price.json"
        position_file = f"{file_prefix}_position.json"

        # Initialize variables
        first_run = False
        current_position = None
        last_position = None
        valid_position = False
        change_acceptable = False

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

        print(f"Current price: {current_price}")
        print(f"Last price: {last_price}")
        print(f"Price difference: {current_price - last_price}")
        print(f"Price difference percentage: {price_diff_pc}%")
        print(f"Change acceptable: {change_acceptable}")


        if valid_position and not first_run:
            
            print("Test: Entering managment logic")

            if price_changed:
                try:

                    print("Test: Attempting to remove liquidity")

                    if sonic.remove_liquidity(last_position):

                        print("Test: Liquidity removed sucessfully")

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