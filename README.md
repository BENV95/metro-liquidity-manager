# Metropolis DEX Liquidity Manager

Automated DLMM liquidity management bot for Metropolis Exchange on Sonic EVM Layer-1 blockchain. Developed for cloud deployment.

## Features
- Dynamic liquidity rebalancing based on price movements
- Automated reward claiming and trading
- Gas optimization with dynamic estimation
- Comprehensive logging and monitoring
- Emergency stop mechanism with Pushover alerts

## Architecture

This bot is designed to run as a **Google Cloud Function** triggered by **Cloud Scheduler**.

### Components
- **Cloud Function**: Main bot logic
- **Cloud Storage**: Stores position/price data between runs
- **Cloud Scheduler**: Triggers function every minute
- **Cloud Logging**: Structured logging and monitoring
- **Secret Manager**: Secure credential storage

## Security

🔒 **All sensitive credentials are stored in Google Cloud Secret Manager**, never in code:
- Private keys
- API tokens
- RPC URLs (if private)

The code contains only public contract addresses which are visible on-chain anyway.

## Prerequisites

- Google Cloud Platform account with billing enabled
- `gcloud` CLI installed and configured
- Python 3.11
- Sonic RPC access

## Deployment

### 1. Set up Google Cloud Project

Enable the following services
- Cloud functions
- Cloud scheduler
- Secret manager
- Cloud storage

### 2. Create secrets in Secret Manager

### 3. Create cloud Storage Bucket

### 4. Deploy Cloud Function

### 5. Set up Cloud Sceduler

## Configuration

### Environment variables
| Variable | Description | Example |
|----------|-------------|---------|
| `LBP_CA` | Liquidity pool contract address | `0x...` |
| `LBROUTER_CA` | Router contract address | `0x...` |
| `REWARDER_CA` | Rewarder contract address | `0x...` |
| `REWARD_WALLET` | Destination for rewards | `0x...` |
| `REWARD_CONF` | 0=transfer, 1=trade to USDC | `1` |
| `LOWER_LIM` | Lower price boundary | `0.95` |
| `UPPER_LIM` | Upper price boundary | `1.05` |
| `MAX_CHANGE` | Max price change % per cycle | `2` |
| `PROJECT_ID` | GCP project ID | `my-project` |
| `BUCKET_NAME` | Storage bucket name | `my-bucket` |

### Secrets
Set via Secret Manager
- `PRIVATE_KEY`: Wallet private key
- `RPC_URL`: Sonic RPC endpoint
- `PUSHOVER_TOKEN`: Pushover API token
- `PUSHOVER_USER`: Pushover user key

## ⚠️ Financial Disclaimer

This software is provided for educational and informational purposes only.

**IMPORTANT:**
- This bot manages real cryptocurrency funds
- Past performance does not guarantee future results  
- You may lose some or all of your investment
- No warranty or guarantee of profitability
- Use at your own risk
- The authors are not financial advisors
- The authors are not liable for any financial losses

**Always:**
- Test with small amounts first
- Understand the code before running it
- Monitor your positions regularly
- Only invest what you can afford to lose

By using this software, you acknowledge these risks.

## License

MIT License - See LICENSE file