import logging
from typing import Any, Optional, Union

import bittensor
from bittensor.core.async_subtensor import AsyncSubtensor
from bittensor.core.chain_data import decode_account_id

from src.blockchain.schemas import StakeOperation, TaoDividend
from src.config import settings
from src.exceptions import BlockchainError


logger = logging.getLogger(__name__)


class BitensorClient:
    """Client for interacting with the Bittensor blockchain."""

    def __init__(self) -> None:
        """Initialize client."""
        self.network = settings.BT_NETWORK
        self.wallet_name = settings.BT_WALLET_NAME
        self.wallet_hotkey = settings.BT_WALLET_HOTKEY
        self.default_netuid = settings.DEFAULT_NETUID
        self.default_hotkey = settings.DEFAULT_HOTKEY.get_secret_value()
        self._subtensor: Optional[AsyncSubtensor] = None
        self._wallet: Optional[Any] = None

    async def connect(self) -> AsyncSubtensor:
        """Connect to the Bittensor blockchain."""
        if self._subtensor is None:
            try:
                self._subtensor = AsyncSubtensor(
                    network=self.network,
                    log_verbose=True,
                )

                logger.info(
                    "Created AsyncSubtensor client for %s",
                    self.network,
                )

            except Exception as e:
                logger.error("Failed to connect to Bittensor: %s", e)
                raise BlockchainError(
                    f"Failed to connect to Bittensor: {e}"
                ) from e
        return self._subtensor

    def get_wallet(self) -> Any:
        """Get Bittensor wallet and ensure it has funds."""
        if self._wallet is None:
            try:
                # Create or load the wallet
                self._wallet = bittensor.wallet(
                    name=self.wallet_name, hotkey=self.wallet_hotkey
                )

                # Ensure wallet is available with the given seed
                if settings.BT_WALLET_SEED:
                    mnemonic = settings.BT_WALLET_SEED.get_secret_value()
                    self._wallet.regenerate_hotkey(
                        mnemonic=mnemonic, hotkey=self.wallet_hotkey
                    )

                logger.info(
                    "Initialized wallet %s:%s",
                    self.wallet_name,
                    self.wallet_hotkey,
                )

            except Exception as e:
                logger.error("Failed to initialize wallet: %s", e)
                raise BlockchainError(
                    f"Failed to initialize wallet: {e}"
                ) from e
        return self._wallet

    async def get_tao_dividends(
        self, netuid: Optional[int] = None, hotkey: Optional[str] = None
    ) -> Union[TaoDividend, list[TaoDividend]]:
        """
        Get Tao dividends for the given netuid and hotkey.

        Args:
            netuid: Network UID (subnet ID)
            hotkey: Account public key

        Returns:
            TaoDividend or List[TaoDividend]: Dividend information
        """
        subtensor = await self.connect()

        # Use default values if not provided
        netuid = netuid if netuid is not None else self.default_netuid
        hotkey = hotkey if hotkey is not None else self.default_hotkey

        try:
            dividends = []
            netuids = [netuid] if netuid is not None else list(range(1, 51))

            for current_netuid in netuids:
                try:
                    # Query the map of all hotkeys for this netuid
                    query_map_result = await subtensor.query_map(
                        "SubtensorModule",
                        "TaoDividendsPerSubnet",
                        params=[current_netuid],
                    )

                    async for key, value in query_map_result:
                        decoded_key = decode_account_id(key)

                        # If hotkey was specified, only add that one
                        if hotkey is None or decoded_key == hotkey:
                            dividend_value = float(
                                value.value
                                if hasattr(value, "value")
                                else value
                            )
                            dividends.append(
                                TaoDividend(
                                    netuid=current_netuid,
                                    hotkey=decoded_key,
                                    dividend=dividend_value,
                                    cached=False,
                                )
                            )

                            # If we found the specific hotkey, break
                            if hotkey is not None:
                                break

                except (ValueError, AttributeError, TypeError) as ex:
                    logger.warning(
                        "Failed to get dividends for netuid %s: %s",
                        current_netuid,
                        ex,
                    )
                    # Continue with other netuids

            # If we have dividends, return them
            if dividends:
                # If hotkey was specified, return only the first dividend
                if hotkey is not None and len(dividends) == 1:
                    return dividends[0]
                return dividends

            # If we didn't find any dividends, return a default one
            if hotkey is not None:
                netuid_value = (
                    netuid if netuid is not None else self.default_netuid
                )
                return TaoDividend(
                    netuid=netuid_value,
                    hotkey=hotkey,
                    dividend=0,
                    cached=False,
                )
            return []  # type: ignore[unreachable]

        except Exception as e:
            logger.error(
                "Failed to get Tao dividends for netuid=%s, hotkey=%s: %s",
                netuid,
                hotkey,
                e,
            )
            raise BlockchainError(f"Failed to get Tao dividends: {e}") from e

    async def stake(
        self,
        amount: float,
        hotkey: Optional[str] = None,
        netuid: Optional[int] = None,
    ) -> StakeOperation:
        """
        Stake TAO to a hotkey.

        Args:
            amount: Amount to stake
            hotkey: Hotkey to stake to (default to wallet's hotkey)
            netuid: Network UID (subnet ID)

        Returns:
            StakeOperation: Result of stake operation
        """
        subtensor = await self.connect()
        wallet = self.get_wallet()

        # Use default values if not provided
        hotkey = hotkey if hotkey is not None else self.default_hotkey
        netuid = netuid if netuid is not None else self.default_netuid

        try:
            # Submit stake extrinsic
            success, tx_hash = await subtensor.add_stake(
                wallet=wallet,
                amount=amount,
                hotkey_ss58=hotkey,
                netuid=netuid,
            )

            if not success:
                raise BlockchainError(f"Failed to stake: {tx_hash}")

            logger.info(
                "Successfully staked %s TAO to %s on subnet %s. "
                "Transaction hash: %s",
                amount,
                hotkey,
                netuid,
                tx_hash,
            )

            return StakeOperation(
                hotkey=hotkey,
                amount=amount,
                operation_type="stake",
                tx_hash=tx_hash,
                success=success,
            )

        except (BlockchainError, ValueError, RuntimeError) as e:
            logger.error(
                "Failed to stake %s TAO to %s: %s",
                amount,
                hotkey,
                e,
            )
            return StakeOperation(
                hotkey=hotkey,
                amount=amount,
                operation_type="stake",
                success=False,
                error=str(e),
            )

    async def unstake(
        self,
        amount: float,
        hotkey: Optional[str] = None,
        netuid: Optional[int] = None,
    ) -> StakeOperation:
        """
        Unstake TAO from a hotkey.

        Args:
            amount: Amount to unstake
            hotkey: Hotkey to unstake from (default to wallet's hotkey)
            netuid: Network UID (subnet ID)

        Returns:
            StakeOperation: Result of unstake operation
        """
        subtensor = await self.connect()
        wallet = self.get_wallet()

        # Use default values if not provided
        hotkey = hotkey if hotkey is not None else self.default_hotkey
        netuid = netuid if netuid is not None else self.default_netuid

        try:
            # Submit unstake extrinsic
            success, tx_hash = await subtensor.unstake(
                wallet=wallet,
                amount=amount,
                hotkey_ss58=hotkey,
                netuid=netuid,
            )

            if not success:
                raise BlockchainError(f"Failed to unstake: {tx_hash}")

            logger.info(
                "Successfully unstaked %s TAO from %s on subnet %s. "
                "Transaction hash: %s",
                amount,
                hotkey,
                netuid,
                tx_hash,
            )

            return StakeOperation(
                hotkey=hotkey,
                amount=amount,
                operation_type="unstake",
                tx_hash=tx_hash,
                success=success,
            )

        except (BlockchainError, ValueError, RuntimeError) as e:
            logger.error(
                "Failed to unstake %s TAO from %s: %s",
                amount,
                hotkey,
                e,
            )
            return StakeOperation(
                hotkey=hotkey,
                amount=amount,
                operation_type="unstake",
                success=False,
                error=str(e),
            )


# Initialize global client
bittensor_client = BitensorClient()
