# Tao Dividends API Service

An asynchronous API service that provides authenticated endpoints to query Tao dividends from the Bittensor blockchain, with sentiment-based stake/unstake operations.

## Features

- 🔑 **Authenticated FastAPI Endpoint**: Secure endpoints for querying Tao dividends
- 🏭 **Asynchronous Architecture**: Built with asyncio and FastAPI for high concurrency
- 💾 **Redis Caching**: Caches blockchain query results for 2 minutes
- 🔄 **Background Processing**: Celery workers handle async blockchain and sentiment tasks
- 📊 **Twitter Sentiment Analysis**: Analyzes tweets for sentiment-based trading decisions
- 🔗 **Blockchain Integration**: Stakes or unstakes TAO based on sentiment score
- 🛢️ **Database Persistence**: Stores transaction and dividend history
- 🐳 **Docker Deployment**: Easy deployment with Docker Compose

## Architecture

This service follows modern async patterns:

- **FastAPI** handles HTTP requests
- **Redis** serves as cache and message broker
- **Celery** workers process background tasks
- **PostgreSQL** with async SQLAlchemy stores results
- **Docker** containers orchestrate all components

## Prerequisites

- Docker and Docker Compose
- A Bittensor wallet with testnet tokens
- API keys for Datura.ai and Chutes.ai

## Quick Start

1. Clone the repository:
   ```bash
   git clone https://github.com/millerserhii/Datura-ai-FastAPI-Task.git
   cd Datura-ai-FastAPI-Task
   ```

2. Create a `.env` file from the template:
   ```bash
   cp .env.example .env
   ```

3. Update the `.env` file with your settings:
   ```
   # API
   API_AUTH_TOKEN=your_api_token_here

   # Database
   DB_USER=user
   DB_PASSWORD=password
   DB_NAME=app

   # Redis
   REDIS_PASSWORD=password

   # Bittensor
   BT_NETWORK=testnet
   BT_WALLET_NAME=my_wallet
   BT_WALLET_HOTKEY=my_hotkey
   BT_WALLET_SEED=your_wallet_seed_phrase_here

   # Default parameters
   DEFAULT_NETUID=18
   DEFAULT_HOTKEY=<your_default_hotkey_here>

   # External APIs
   DATURA_API_KEY=<your_datura_api_key_here>
   CHUTES_API_KEY=<your_chutes_api_key_here>
   ```

4. Start the services:
   ```bash
   docker-compose up --build
   ```

5. Access the API at http://localhost:8000/api/v1/tao_dividends

## API Documentation

Once the server is running, visit:
- Interactive documentation: http://localhost:8000/docs
- ReDoc documentation: http://localhost:8000/redoc

### Endpoints

#### GET /api/v1/tao_dividends

Returns Tao dividends data for a given subnet and hotkey.

**Query Parameters:**
- `netuid` (optional): Network UID (subnet ID)
- `hotkey` (optional): Account public key
- `trade` (optional, default=false): When true, triggers sentiment analysis and stake/unstake operations

**Headers:**
- `Authorization`: Bearer token for authentication

**Example Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/tao_dividends?netuid=18&hotkey=5FFApaS75bv5pJHfAp2FVLBj9ZaXuFDjEypsaBNc1wCfe52v" \
     -H "Authorization: Bearer your_token_here"
```

**Example Response:**
```json
{
  "netuid": 18,
  "hotkey": "5FFApaS75bv5pJHfAp2FVLBj9ZaXuFDjEypsaBNc1wCfe52v",
  "dividend": 123456789,
  "cached": false,
  "stake_tx_triggered": false,
  "tx_hash": null
}
```

**Example Batch Response:**
```json
{
  "dividends": [
    {
      "netuid": 18,
      "hotkey": "5FFApaS75bv5pJHfAp2FVLBj9ZaXuFDjEypsaBNc1wCfe52v",
      "dividend": 123456789,
      "cached": false,
      "stake_tx_triggered": true,
      "tx_hash": null
    },
    {
      "netuid": 18,
      "hotkey": "5G4mxrN8msvc4jjwp7xoBrtAejTfAMLCMTFGCivY5inmySbq",
      "dividend": 987654321,
      "cached": false,
      "stake_tx_triggered": true,
      "tx_hash": null
    }
  ],
  "cached": false,
  "stake_tx_triggered": true
}
```
