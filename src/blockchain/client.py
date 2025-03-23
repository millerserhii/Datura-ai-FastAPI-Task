import logging
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
        self.default_netuid = settings.DEFAULT_NETUID
        self.default_hotkey = settings.DEFAULT_HOTKEY.get_secret_value()
        self._subtensor: Optional[AsyncSubtensor] = None
        self._wallet: Optional[Any] = None
        self.connection_retries = 3
        self.retry_delay = 2  # seconds

    async def connect(self) -> AsyncSubtensor:
        """
        Connect to the Bittensor blockchain with retries.

        Returns:
            AsyncSubtensor: Connected subtensor client

        Raises:
            BlockchainError: If connection fails after retries
        """
        if self._subtensor is not None:
            return self._subtensor

        retries = 0
        last_error = None

        while retries <= self.connection_retries:
            try:
                logger.info(
                    f"Connecting to Bittensor {self.network} (attempt {retries+1}/{self.connection_retries+1})"
                )

                self._subtensor = AsyncSubtensor(
                    network=self.network,
                    log_verbose=False,
                )

                logger.info(
                    f"Connected to AsyncSubtensor client for {self.network}"
                )
                return self._subtensor

            except Exception as e:
                last_error = e
                retries += 1

                if retries <= self.connection_retries:
                    wait_time = self.retry_delay * retries
                    logger.warning(
                        f"Failed to connect to Bittensor: {e}. "
                        f"Retrying in {wait_time}s ({retries}/{self.connection_retries})"
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(
                        f"Failed to connect to Bittensor after {retries} attempts: {e}"
                    )

        # If we reach here, all retries failed
        error_msg = f"Failed to connect to Bittensor after {retries} attempts: {last_error}"
        logger.error(error_msg)
        raise BlockchainError(error_msg)

    def get_wallet(self) -> Any:
        """Get Bittensor wallet."""
        if self._wallet is None:
            try:
                # Simply load the wallet without extra config parameters
                self._wallet = bittensor.wallet(
                    name=self.wallet_name, hotkey=self.wallet_hotkey
                )

                logger.info(
                    f"Initialized wallet {self.wallet_name}:{self.wallet_hotkey}"
                )

            except Exception as e:
                logger.error(f"Failed to initialize wallet: {e}")
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
        try:
            subtensor = await self.connect()

            # Use default values if not provided
            netuid = netuid if netuid is not None else self.default_netuid
            hotkey = hotkey if hotkey is not None else self.default_hotkey

            dividends = []
            netuids = (
                [netuid] if netuid is not None else list(range(1, 21))
            )  # Limit to 20 netuids for performance

            for current_netuid in netuids:
                try:
                    # Query the map of all hotkeys for this netuid
                    logger.info(
                        f"Querying TaoDividendsPerSubnet for netuid={current_netuid}"
                    )
                    query_map_result = await subtensor.query_map(
                        "SubtensorModule",
                        "TaoDividendsPerSubnet",
                        params=[current_netuid],
                    )

                    if query_map_result is None:
                        logger.warning(
                            f"No dividend data found for netuid={current_netuid}"
                        )
                        continue

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

                except Exception as ex:
                    logger.warning(
                        f"Failed to get dividends for netuid {current_netuid}: {ex}"
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
            return []

        except BlockchainError as e:
            # Re-raise BlockchainError
            raise e
        except Exception as e:
            logger.error(
                f"Failed to get Tao dividends for netuid={netuid}, hotkey={hotkey}: {e}"
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

        tao_amount = Balance.from_tao(amount)

        # Use default values if not provided
        hotkey = hotkey if hotkey is not None else self.default_hotkey
        netuid = netuid if netuid is not None else self.default_netuid

        try:
            # Submit stake extrinsic
            success = await subtensor.add_stake(
                wallet=wallet,
                hotkey_ss58=hotkey,
                netuid=netuid,
                amount=tao_amount,
            )

            if not success:
                error_msg = "Failed to stake: Chain rejected transaction"
                logger.error(error_msg)
                return StakeOperation(
                    hotkey=hotkey,
                    amount=tao_amount,
                    operation_type="stake",
                    success=False,
                    error=error_msg,
                )

            logger.info(
                "Successfully staked %s TAO to %s on subnet %s",
                tao_amount,
                hotkey,
                netuid,
            )

            return StakeOperation(
                hotkey=hotkey,
                amount=amount,
                operation_type="stake",
                tx_hash="Transaction submitted",  # We don't have the actual hash
                success=success,
            )

        except Exception as e:
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
        amount: float,  # TAO amount
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

            if float(alpha_amount) < 0.001:
                error_msg = f"Converted alpha amount ({alpha_amount}) is too low for {tao_amount} TAO"
                logger.error(error_msg)
                return StakeOperation(
                    hotkey=hotkey,
                    amount=amount,
                    operation_type="unstake",
                    success=False,
                    error=error_msg,
                )

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
                        error_msg = f"Not enough stake: {current_stake} alpha tokens available, but trying to unstake {alpha_amount} alpha tokens"
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
                amount=alpha_amount,  # Already a Balance object
                hotkey_ss58=hotkey,
                netuid=netuid,
            )

            if not success:
                error_msg = "Failed to unstake: Chain rejected transaction"
                logger.error(error_msg)
                return StakeOperation(
                    hotkey=hotkey,
                    amount=amount,  # Return original TAO amount
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

            return StakeOperation(
                hotkey=hotkey,
                amount=amount,  # Return original TAO amount
                operation_type="unstake",
                tx_hash="Transaction submitted",
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
