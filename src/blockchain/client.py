import logging
import os
import time
from typing import Any, Optional, Union

import bittensor
from bittensor.core.async_subtensor import AsyncSubtensor
from bittensor.core.chain_data import decode_account_id
from bittensor.utils.balance import Balance

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
        self.wallet_path = settings.BT_WALLET_PATH
        self.default_netuid = settings.DEFAULT_NETUID
        self.default_hotkey = settings.DEFAULT_HOTKEY.get_secret_value()
        self._subtensor: Optional[AsyncSubtensor] = None
        self._wallet: Optional[Any] = None
        self._wallet_initialized = False

    def init_wallet(self) -> None:
        """Initialize wallet at application startup."""
        try:
            # Create or load the wallet
            self._wallet = bittensor.wallet(
                name=self.wallet_name,
                hotkey=self.wallet_hotkey,
                path=self.wallet_path,
            )

            hotkey_path = os.path.join(
                self.wallet_path,
                self.wallet_name,
                "hotkeys",
                self.wallet_hotkey,
            )

            if not os.path.exists(hotkey_path) and settings.BT_WALLET_SEED:
                mnemonic = settings.BT_WALLET_SEED.get_secret_value()
                self._wallet.regenerate_hotkey(
                    mnemonic=mnemonic,
                    hotkey=self.wallet_hotkey,
                    use_password=False,
                    overwrite=True,
                )

            logger.info(
                "Initialized wallet %s:%s from path %s",
                self.wallet_name,
                self.wallet_hotkey,
                self.wallet_path,
            )

            self._wallet_initialized = True

        except Exception as e:
            logger.error("Failed to initialize wallet: %s", e)

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
        """Get Bittensor wallet and ensure it's initialized."""
        if not self._wallet_initialized:
            self.init_wallet()

        if not self._wallet:
            raise BlockchainError(
                "Wallet not available. "
                "Make sure wallet files are mounted correctly."
            )

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

                            if hotkey is not None:
                                break

                except (ValueError, AttributeError, TypeError) as ex:
                    logger.warning(
                        "Failed to get dividends for netuid %s: %s",
                        current_netuid,
                        ex,
                    )

            if dividends:
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
            # Submit stake extrinsic - need to handle different return types
            logger.info(
                "Attempting to stake %s TAO to %s on subnet %s",
                amount,
                hotkey,
                netuid,
            )

            timestamp = int(time.time())

            result = await subtensor.add_stake(
                wallet=wallet,
                amount=amount,
                hotkey_ss58=hotkey,
                netuid=netuid,
            )

            # Handle different return types from add_stake
            if isinstance(result, tuple):
                success, tx_hash = result
            elif isinstance(result, bool):
                success = result
                tx_hash = f"tx-{timestamp}"
            else:
                raise BlockchainError(
                    f"Unexpected return type from add_stake: {type(result)}"
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

        except Exception as e:
            error_str = str(e)
            logger.error(
                "Failed to stake %s TAO to %s: %s",
                amount,
                hotkey,
                error_str,
            )

            # Handle "Transaction Already Imported" error specifically
            if "Transaction Already Imported" in error_str:
                return StakeOperation(
                    hotkey=hotkey,
                    amount=amount,
                    operation_type="stake",
                    tx_hash=f"duplicate-{int(time.time())}",
                    success=True,
                    error=(
                        "A similar transaction was already processed by "
                        "the blockchain. This usually means the operation "
                        "was already completed."
                    ),
                )

            return StakeOperation(
                hotkey=hotkey,
                amount=amount,
                operation_type="stake",
                success=False,
                error=error_str,
            )

    # Similarly update the unstake method to handle the same error
    async def unstake(
        self,
        amount: float,
        hotkey: Optional[str] = None,
        netuid: Optional[int] = None,
    ) -> StakeOperation:
        """
        Unstake TAO from a hotkey.

        Args:
            amount: Amount of TAO to unstake (will be converted to alpha)
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
            # Convert float TAO amount to Balance object
            tao_amount = Balance.from_tao(amount)

            # Get subnet info to convert TAO to alpha
            subnet_info = await subtensor.subnet(netuid)

            # Convert TAO amount to alpha amount
            alpha_amount = subnet_info.tao_to_alpha(tao_amount)

            logger.info(
                "Converting %s TAO to %s alpha tokens for unstaking from %s on subnet %s",
                tao_amount,
                alpha_amount,
                hotkey,
                netuid,
            )

            # Check current stake in alpha tokens
            try:
                stake_info_dict = (
                    await subtensor.get_stake_for_coldkey_and_hotkey(
                        coldkey_ss58=wallet.coldkeypub.ss58_address,
                        hotkey_ss58=hotkey,
                        netuids=[netuid],
                    )
                )

                # Extract the stake for the specified netuid
                if netuid in stake_info_dict:
                    stake_info = stake_info_dict[netuid]
                    current_stake = stake_info.stake
                    logger.info(
                        "Current stake: %s alpha tokens", current_stake
                    )

                    if float(current_stake) < float(alpha_amount):
                        error_msg = (
                            f"Not enough stake: {float(current_stake)} alpha tokens "
                            f"available, but trying to unstake {float(alpha_amount)} "
                            "alpha tokens"
                        )
                        logger.error(error_msg)
                        return StakeOperation(
                            hotkey=hotkey,
                            amount=amount,  # Return original TAO amount
                            operation_type="unstake",
                            success=False,
                            error=error_msg,
                        )
                else:
                    error_msg = f"No stake found for netuid {netuid}"
                    logger.error(error_msg)
                    return StakeOperation(
                        hotkey=hotkey,
                        amount=amount,
                        operation_type="unstake",
                        success=False,
                        error=error_msg,
                    )
            except Exception as e:
                logger.warning("Could not check current stake: %s", e)

            # Submit unstake extrinsic with the alpha amount
            logger.info(
                "Submitting unstake extrinsic: %s alpha tokens from %s on subnet %s",
                alpha_amount,
                hotkey,
                netuid,
            )

            success = await subtensor.unstake(
                wallet=wallet,
                amount=alpha_amount,
                hotkey_ss58=hotkey,
                netuid=netuid,
            )

            if not success:
                error_msg = "Failed to unstake: Chain rejected transaction"
                logger.error(error_msg)
                return StakeOperation(
                    hotkey=hotkey,
                    amount=amount,
                    operation_type="unstake",
                    success=False,
                    error=error_msg,
                )

            logger.info(
                "Successfully unstaked %s alpha tokens (%s TAO) from %s on subnet %s",
                alpha_amount,
                tao_amount,
                hotkey,
                netuid,
            )
            timestamp = int(time.time())

            return StakeOperation(
                hotkey=hotkey,
                amount=amount,
                operation_type="unstake",
                tx_hash=f"tx-{timestamp}",
                success=success,
            )

        except Exception as e:
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
