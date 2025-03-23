import json
from unittest.mock import patch

from fastapi import status

from src.blockchain.schemas import TaoDividend


class TestIntegrationFlow:
    """Integration tests for the full API flow."""

    def test_tao_dividends_with_trade_flow(
        self,
        client,
        mock_bittensor_client,
        mock_redis_client,
        mock_celery_task,
    ):
        """
        Test full flow: get dividends with trade=true to trigger sentiment analysis and stake.
        """
        # Arrange
        netuid = 18
        hotkey = "5FFApaS75bv5pJHfAp2FVLBj9ZaXuFDjEypsaBNc1wCfe52v"

        # Mock blockchain response
        dividend = TaoDividend(
            netuid=netuid,
            hotkey=hotkey,
            dividend=1000,
            cached=False,
        )
        mock_bittensor_client.get_tao_dividends.return_value = dividend

        # Act
        with patch(
            "src.blockchain.service.bittensor_client", mock_bittensor_client
        ):
            with patch(
                "src.blockchain.service.redis_client", mock_redis_client
            ):
                # Call the endpoint
                response = client.get(
                    f"/api/v1/tao_dividends?netuid={netuid}&hotkey={hotkey}&trade=true",
                )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["netuid"] == netuid
        assert data["hotkey"] == hotkey
        assert data["dividend"] == 1000
        assert data["stake_tx_triggered"] is True

        # Verify Celery task was triggered
        mock_celery_task.delay.assert_called_once()

    def test_concurrent_requests(
        self,
        client,
        mock_bittensor_client,
        mock_redis_client,
    ):
        """Test handling multiple concurrent requests."""
        # Arrange
        netuid = 18

        # Different hotkeys
        hotkeys = [
            "5FFApaS75bv5pJHfAp2FVLBj9ZaXuFDjEypsaBNc1wCfe52v",
            "5GrwvaEF5zXb26HamNNkHZryQoydSiMhPT3N6A8UJFDgZLGy",
            "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty",
        ]

        # Mock blockchain responses
        # Use side_effect to return different dividends for different calls
        mock_bittensor_client.get_tao_dividends.side_effect = [
            TaoDividend(
                netuid=netuid,
                hotkey=hotkey,
                dividend=1000 * (i + 1),
                cached=False,
            )
            for i, hotkey in enumerate(hotkeys)
        ]

        # Act - Make multiple requests
        responses = []
        with patch(
            "src.blockchain.service.bittensor_client", mock_bittensor_client
        ):
            with patch(
                "src.blockchain.service.redis_client", mock_redis_client
            ):
                for hotkey in hotkeys:
                    response = client.get(
                        f"/api/v1/tao_dividends?netuid={netuid}&hotkey={hotkey}"
                    )
                    responses.append(response)

        # Assert
        for i, response in enumerate(responses):
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["netuid"] == netuid
            assert data["hotkey"] == hotkeys[i]
            assert data["dividend"] == 1000 * (i + 1)

        # Verify all blockchain calls were made
        assert mock_bittensor_client.get_tao_dividends.call_count == len(
            hotkeys
        )

    def test_cache_effectiveness(
        self,
        client,
        mock_bittensor_client,
        mock_redis_client,
    ):
        """Test that caching works correctly for repeated requests."""
        # Arrange
        netuid = 18
        hotkey = "5FFApaS75bv5pJHfAp2FVLBj9ZaXuFDjEypsaBNc1wCfe52v"

        # Mock Redis cache behavior
        # First call: cache miss
        mock_redis_client.get.side_effect = [
            None,  # First call - cache miss
            json.dumps(
                {  # Second call - cache hit
                    "netuid": netuid,
                    "hotkey": hotkey,
                    "dividend": 1000,
                    "cached": True,
                }
            ),
        ]

        # Mock blockchain response
        dividend = TaoDividend(
            netuid=netuid,
            hotkey=hotkey,
            dividend=1000,
            cached=False,
        )
        mock_bittensor_client.get_tao_dividends.return_value = dividend

        # Act - Make two identical requests
        with patch(
            "src.blockchain.service.bittensor_client", mock_bittensor_client
        ):
            with patch(
                "src.blockchain.service.redis_client", mock_redis_client
            ):
                # First request (should hit blockchain)
                response1 = client.get(
                    f"/api/v1/tao_dividends?netuid={netuid}&hotkey={hotkey}",
                )

                # Second request (should hit cache)
                response2 = client.get(
                    f"/api/v1/tao_dividends?netuid={netuid}&hotkey={hotkey}",
                )

        # Assert
        assert response1.status_code == status.HTTP_200_OK
        data1 = response1.json()
        assert data1["cached"] is False

        assert response2.status_code == status.HTTP_200_OK
        data2 = response2.json()
        assert data2["cached"] is True

        # Verify blockchain was only called once
        assert mock_bittensor_client.get_tao_dividends.call_count == 1
