import argparse
import asyncio
import json
import os
import random
import ssl
import sys
import time
import urllib.parse
from collections import defaultdict
from datetime import datetime


# Sample data
NETUIDS = [18, 5, 119, 277]
HOTKEYS = [
    "5FFApaS75bv5pJHfAp2FVLBj9ZaXuFDjEypsaBNc1wCfe52v",
    "5GrwvaEF5zXb26HamNNkHZryQoydSiMhPT3N6A8UJFDgZLGy",
    "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty",
]

# Statistics
stats = {
    "total_requests": 0,
    "successful_requests": 0,
    "failed_requests": 0,
    "cached_responses": 0,
    "non_cached_responses": 0,
    "response_times": [],
    "status_codes": defaultdict(int),
    "errors": defaultdict(int),
    "start_time": None,
    "end_time": None,
}


def get_api_key_from_config():
    """Load API_AUTH_TOKEN from project config."""
    try:
        # First try importing directly
        sys.path.insert(0, os.path.abspath("."))
        try:
            from src.config import settings

            return settings.API_AUTH_TOKEN.get_secret_value()
        except (ImportError, AttributeError):
            pass

        # Then try loading from .env file
        env_file = ".env"
        if os.path.exists(env_file):
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        key, value = line.split("=", 1)
                        if key.strip() == "API_AUTH_TOKEN":
                            return value.strip().strip("\"'")

        print("Could not load API_AUTH_TOKEN from config or .env file")
        return None
    except Exception as e:
        print(f"Error loading API key from config: {e}")
        return None


async def make_request(host, path, api_key, user_id):
    """Make a single request to the API."""
    import http.client
    from urllib.parse import urlparse

    parsed_url = urlparse(host)
    hostname = parsed_url.netloc
    is_https = parsed_url.scheme == "https"

    # Generate random parameters
    netuid = random.choice(NETUIDS)
    hotkey = random.choice(HOTKEYS)
    use_trade = random.random() < 0.1  # 10% of requests use trade=true

    # Build query string
    query_params = {
        "netuid": netuid,
        "hotkey": hotkey,
    }

    if use_trade:
        query_params["trade"] = "true"

    query_string = urllib.parse.urlencode(query_params)
    full_path = f"{path}?{query_string}"

    # Set headers
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": f"LoadTest/1.0 (User-{user_id})",
        "Accept": "application/json",
    }

    start_time = time.time()

    try:
        if is_https:
            conn = http.client.HTTPSConnection(
                hostname, context=ssl._create_unverified_context()
            )
        else:
            conn = http.client.HTTPConnection(hostname)

        conn.request("GET", full_path, headers=headers)
        response = conn.getresponse()

        status_code = response.status
        stats["status_codes"][status_code] += 1

        response_data = response.read().decode("utf-8")

        end_time = time.time()
        response_time = (end_time - start_time) * 1000  # Convert to ms
        stats["response_times"].append(response_time)
        stats["total_requests"] += 1

        if 200 <= status_code < 300:
            stats["successful_requests"] += 1

            try:
                data = json.loads(response_data)
                if isinstance(data, dict) and data.get("cached", False):
                    stats["cached_responses"] += 1
                else:
                    stats["non_cached_responses"] += 1
            except json.JSONDecodeError:
                pass
        else:
            stats["failed_requests"] += 1
            print(
                f"Request failed: Status {status_code}, "
                f"Response: {response_data[:100]}..."
            )

        conn.close()
        return status_code, response_time

    except Exception as e:
        end_time = time.time()
        response_time = (end_time - start_time) * 1000  # Convert to ms
        stats["response_times"].append(response_time)
        stats["total_requests"] += 1
        stats["failed_requests"] += 1
        stats["errors"][str(e)] += 1
        print(f"Error making request: {e}")
        return None, response_time


async def run_load_test(host, path, api_key, num_users, spawn_rate, duration):
    """Run a load test with the given parameters."""
    print(f"Starting load test with {num_users} users against {host}{path}")
    print(
        f"Spawning at {spawn_rate} users/second, "
        f"running for {duration} seconds"
    )

    stats["start_time"] = datetime.now()

    # Calculate how many users to spawn in each batch
    users_per_batch = max(1, min(50, spawn_rate))
    sleep_time = users_per_batch / spawn_rate

    # Track active tasks
    tasks = []
    spawned_users = 0

    # Start time for test duration
    test_start_time = time.time()

    while (
        time.time() - test_start_time < duration and spawned_users < num_users
    ):
        # Spawn a batch of users
        batch_size = min(users_per_batch, num_users - spawned_users)

        for i in range(batch_size):
            user_id = spawned_users + i
            task = asyncio.create_task(
                make_request(host, path, api_key, user_id)
            )
            tasks.append(task)

        spawned_users += batch_size
        print(f"Spawned {spawned_users}/{num_users} users...")

        # Sleep before spawning next batch
        await asyncio.sleep(sleep_time)

        # Check for completed tasks and remove them
        tasks = [t for t in tasks if not t.done()]

    # Wait for all remaining tasks to complete
    if tasks:
        print(f"Waiting for {len(tasks)} remaining requests to complete...")
        await asyncio.gather(*tasks)

    stats["end_time"] = datetime.now()
    print_results()


def print_results():
    """Print the test results."""
    test_duration = (stats["end_time"] - stats["start_time"]).total_seconds()

    print("\n==== Load Test Results ====")
    print(f"Test duration: {test_duration:.2f} seconds")
    print(f"Total requests: {stats['total_requests']}")
    print(f"Successful requests: {stats['successful_requests']}")
    print(f"Failed requests: {stats['failed_requests']}")

    if stats["successful_requests"] > 0:
        print(
            f"Cached responses: {stats['cached_responses']} "
            f"({stats['cached_responses']/stats['successful_requests']*100:.2f}%)"
        )

    if stats["response_times"]:
        avg_response_time = sum(stats["response_times"]) / len(
            stats["response_times"]
        )
        min_response_time = min(stats["response_times"])
        max_response_time = max(stats["response_times"])

        print(f"Average response time: {avg_response_time:.2f} ms")
        print(f"Min response time: {min_response_time:.2f} ms")
        print(f"Max response time: {max_response_time:.2f} ms")

    print("\nStatus code distribution:")
    for status_code, count in sorted(stats["status_codes"].items()):
        print(
            f"  {status_code}: {count} ({count/stats['total_requests']*100:.2f}%)"
        )

    if stats["errors"]:
        print("\nErrors:")
        for error, count in stats["errors"].items():
            print(f"  {error}: {count}")

    rps = stats["total_requests"] / test_duration
    print(f"\nRequests per second: {rps:.2f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Load test for Tao Dividends API"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="http://localhost:8000",
        help="API host URL",
    )
    parser.add_argument(
        "--path",
        type=str,
        default="/api/v1/tao_dividends",
        help="API endpoint path",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="API key for authentication (optional, will try to load from config)",
    )
    parser.add_argument(
        "--users", type=int, default=1000, help="Number of concurrent users"
    )
    parser.add_argument(
        "--spawn-rate", type=int, default=50, help="Users to spawn per second"
    )
    parser.add_argument(
        "--duration", type=int, default=60, help="Test duration in seconds"
    )

    args = parser.parse_args()

    # Auto-import API key if not provided
    api_key = args.api_key
    if not api_key:
        api_key = get_api_key_from_config()
        if api_key:
            print(f"Loaded API key from config")
        else:
            print("No API key provided and couldn't load from config")
            sys.exit(1)

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(
        run_load_test(
            args.host,
            args.path,
            api_key,
            args.users,
            args.spawn_rate,
            args.duration,
        )
    )
