# Tao Dividends API Service

An asynchronous API service that provides authenticated endpoints to query Tao dividends from the Bittensor blockchain, with sentiment-based stake/unstake operations.

## Features

- 🔐 **Authenticated API**: Secure endpoints for querying Tao dividends
- ⚡ **Asynchronous Architecture**: Built with asyncio and FastAPI for high concurrency
- 🗄️ **Redis Caching**: Caches blockchain query results for 2 minutes
- 🔄 **Background Processing**: Celery workers handle async blockchain and sentiment tasks
- 📊 **Twitter Sentiment Analysis**: Analyzes tweets for sentiment-based trading decisions
- ⛓️ **Blockchain Integration**: Stakes or unstakes TAO based on sentiment score
- 💾 **Database Persistence**: Stores transaction and dividend history
- 🐳 **Docker Deployment**: Easy deployment with Docker Compose

## Prerequisites

- Docker and Docker Compose
- A Bittensor wallet with testnet tokens
- API keys for Datura.ai and Chutes.ai

## Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/millerserhii/Datura-ai-FastAPI-Task.git
cd Datura-ai-FastAPI-Task
```

### 2. Configure Environment Variables

> **⚠️ IMPORTANT:** You must copy the example environment file to create your own .env file.

```bash
cp .env.example .env
```

Edit the `.env` file to include your API keys and configuration:

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
BT_NETWORK=test
BT_WALLET_NAME=my_wallet
BT_WALLET_HOTKEY=my_hotkey
BT_WALLET_SEED=your_wallet_seed_phrase_here

# Default parameters
DEFAULT_NETUID=18
DEFAULT_HOTKEY='your_hotkey_here'

# External APIs
DATURA_API_KEY='your_datura_api_key_here'
CHUTES_API_KEY='your Chutes API key here'
```

### 3. Set Up Bittensor Wallets

> **⚠️ IMPORTANT:** You must copy your Bittensor wallets to the project directory.

Create a wallets directory and copy your Bittensor wallets:

```bash
mkdir -p wallets
cp -r ~/.bittensor/wallets/ .
```

You may need to adjust permissions:

```bash
chmod -R 755 wallets/
# Or assign to your user
chown -R $(whoami):$(whoami) wallets/
```

### 4. Start the Application

Build and start all services using Docker Compose:

```bash
docker-compose up --build
```

To run in the background:

```bash
docker-compose up --build -d
```

The application will be available at http://localhost:8000.

## API Documentation

Once the server is running, you can access the interactive API documentation:

- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

## Available Endpoints

### GET /api/v1/tao_dividends

Retrieves Tao dividends for the specified subnet and hotkey.

**Query Parameters:**
- `netuid` (optional): Network UID (subnet ID), defaults to value in .env
- `hotkey` (optional): Account public key, defaults to value in .env
- `trade` (optional, default: false): Triggers sentiment analysis and stake/unstake operations

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

### POST /api/v1/blockchain/stake

Stakes TAO to a hotkey.

**Request Body:**
```json
{
  "amount": 1.5,
  "netuid": 18,
  "hotkey": "5FFApaS75bv5pJHfAp2FVLBj9ZaXuFDjEypsaBNc1wCfe52v"
}
```

### POST /api/v1/blockchain/unstake

Unstakes TAO from a hotkey.

**Request Body:**
```json
{
  "amount": 1.5,
  "netuid": 18,
  "hotkey": "5FFApaS75bv5pJHfAp2FVLBj9ZaXuFDjEypsaBNc1wCfe52v"
}
```

### GET /api/v1/blockchain/dividend-history

Retrieves dividend history.

**Query Parameters:**
- `netuid` (optional): Filter by Network UID
- `hotkey` (optional): Filter by hotkey
- `limit` (optional, default: 100): Maximum records to return
- `offset` (optional, default: 0): Number of records to skip

### GET /api/v1/blockchain/stake-transaction-history

Retrieves stake transaction history.

**Query Parameters:**
- `netuid` (optional): Filter by Network UID
- `hotkey` (optional): Filter by hotkey
- `operation_type` (optional): Filter by operation type ("stake" or "unstake")
- `limit` (optional, default: 100): Maximum records to return
- `offset` (optional, default: 0): Number of records to skip

## Running Tests

To run the tests:

```bash
pytest
```

To run specific tests:

```bash
pytest tests/test_blockchain_service.py
```

## Health Checks

Check if the API is running:

```bash
curl http://localhost:8000/health
```

Check if Celery is working:

```bash
curl http://localhost:8000/celery-health
```

## Architecture

This service follows modern async patterns:

- **FastAPI** handles HTTP requests
- **Redis** serves as cache and message broker
- **Celery** workers process background tasks
- **PostgreSQL** with async SQLAlchemy stores results
- **Docker** containers orchestrate all components

## Troubleshooting

- **Database Connection Issues**: Check PostgreSQL logs with `docker-compose logs db`
- **Redis Connection Issues**: Verify Redis password in .env file
- **Wallet Access Problems**: Ensure wallets are copied correctly and have proper permissions
- **API Authorization Failures**: Verify API_AUTH_TOKEN in .env matches your request

## Shutting Down

```bash
docker-compose down
```

To remove volumes (will delete all data):

```bash
docker-compose down -v
```
