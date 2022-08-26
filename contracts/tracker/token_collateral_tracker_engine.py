import smartpy as sp

import utils.error_codes as Errors
import utils.constants as Constants

from utils.contract_utils import Utils
from utils.fa2 import LedgerKey, AdministrableMixin

from contracts.tracker.governance_token import Stake


class Settlement:
    """Parameter used in settle_with_vault"""

    def get_type():
        """Returns a single Settlement type, layouted

        Returns:
            sp.TRecord: the layouted settlement
        """
        return sp.TRecord(
            vault_owner=sp.TAddress, token_amount=sp.TNat, recipient=sp.TAddress
        ).layout(("vault_owner", ("token_amount", "recipient")))

    def make(vault_owner, token_amount, recipient):
        """Makes an instance of an settlement

        Args:
            vault_owner (sp.address): vault_owner
            token_amount (sp.nat): token_amount
            recipient (sp.address): recipient of the settlement tez

        Returns:
            Settlement: the settlement record
        """
        return sp.set_type_expr(
            sp.record(
                vault_owner=vault_owner, token_amount=token_amount, recipient=recipient
            ),
            Settlement.get_type(),
        )


class Liquidation:
    """Parameter used in liquidate"""

    def get_type():
        """Returns a single Liquidation type, layouted

        Returns:
            sp.TRecord: the layouted liquidation
        """
        return sp.TRecord(vault_owner=sp.TAddress, token_amount=sp.TNat).layout(
            ("vault_owner", "token_amount")
        )

    def make(vault_owner, token_amount):
        """Makes an instance of an liquidation

        Args:
            vault_owner (sp.address): vault_owner
            token_amount (sp.nat): token_amount

        Returns:
            Liquidation: the liquidation record
        """
        return sp.set_type_expr(
            sp.record(vault_owner=vault_owner, token_amount=token_amount),
            Liquidation.get_type(),
        )


class TokenTrackerEngine(sp.Contract, AdministrableMixin):
    """this is the heartpiece of the entire project. The engine that orchestrates all other components. This is also the contract responsible for the interest rate/inflation of the liability/savings rate of the
    synthetic asset. This engine is built to create synthetic asset tokens that by getting data from an oracle the resulting synthetic asset will track that value.

    Args:
        (sp.Contract): this is a smartpy contract
        (AdministrableMixin): mixin used to add the administratble entrypoints
        (InternalMixin): mixin used whenever we need external data and hence have to trigger an internal call (to process after we received said external data)
    """

    def get_init_storage(self):
        """Returns the initial storage of the contract used for inheritance of smartpy contracts

        Returns:
            dict: initial storage of the contract
        """
        storage = {}

        storage["reference_interest_rate"] = Constants.SECONDS_INTEREST_MINIMUM
        storage["compound_interest_rate"] = Constants.PRECISION_FACTOR

        storage["accrual_update_timestamp"] = sp.timestamp(0)

        storage["total_supply"] = sp.nat(0)

        storage["target_price_oracle"] = Constants.DEFAULT_ADDRESS
        storage["reward_pool_contract"] = Constants.DEFAULT_ADDRESS
        storage["savings_pool_contract"] = Constants.DEFAULT_ADDRESS
        storage["governance_token_contract"] = Constants.DEFAULT_ADDRESS
        storage["options_contract"] = Constants.DEFAULT_ADDRESS

        storage["token_contract"] = self.token_contract
        storage["token_id"] = self.token_id

        storage["collateral_token_contract"] = self.collateral_token_contract
        storage["collateral_token_id"] = self.collateral_token_id

        storage["vault_contexts"] = sp.big_map(
            tkey=sp.TAddress,
            tvalue=sp.TRecord(
                minted=sp.TNat,
                is_being_liquidated=sp.TBool,
                allows_settlement=sp.TBool,
                balance=sp.TNat,
            ),
        )

        storage["administrators"] = sp.set_type_expr(
            self.administrators, sp.TBigMap(LedgerKey.get_type(), sp.TUnit)
        )

        return storage

    def __init__(
        self,
        token_contract,
        token_id,
        collateral_token_contract,
        collateral_token_id=0,
        collateral_token_type=Constants.TOKEN_TYPE_FA2,
        price_extra_precision_factor=1,
        administrators={},
    ):
        """init to set the token and administrators, in order to be fully operational set_contracts need to be called first.
        Args:
            token_contract (sp.address): token address
            token_id (sp.nat): token id
            administrators (dict, optional): the administrators allowed to set the contracts. Defaults to {}.
        """
        self.token_contract = token_contract
        self.token_id = token_id
        self.collateral_token_contract = collateral_token_contract
        self.collateral_token_id = collateral_token_id
        self.administrators = administrators
        self.collateral_token_type = collateral_token_type
        self.price_extra_precision_factor = price_extra_precision_factor
        self.init(**self.get_init_storage())

    @sp.private_lambda(with_storage="read-write", with_operations=True, wrap_call=True)
    def update_accrual(self, unit):
        """sub entrypoint which updates the accrual based on the interest rate and timedelta.

        Post: storage.accrual_update_timestamp = sp.now

        Args:
            unit (sp.unit): nothing
        """
        timedelta_since_last_update = sp.local(
            "timedelta_since_last_update",
            sp.as_nat(sp.now - self.data.accrual_update_timestamp),
        )
        with sp.if_(timedelta_since_last_update.value > 0):
            asset_accrual = sp.local(
                "asset_accrual",
                (
                    self.data.reference_interest_rate
                    * timedelta_since_last_update.value
                    * self.data.total_supply
                )
                / Constants.PRECISION_FACTOR,
            )
            spread_accrual = sp.local(
                "spread_accrual",
                (
                    Constants.SECONDS_INTEREST_SPREAD
                    * timedelta_since_last_update.value
                    * self.data.total_supply
                )
                / Constants.PRECISION_FACTOR,
            )

            compound_interest_rate = (
                Constants.PRECISION_FACTOR
                + (
                    self.data.reference_interest_rate
                    + Constants.SECONDS_INTEREST_SPREAD
                )
                * timedelta_since_last_update.value
            )

            self.data.compound_interest_rate = (
                self.data.compound_interest_rate
                * compound_interest_rate
                / Constants.PRECISION_FACTOR
            )

            Utils.execute_token_mint(
                self.data.token_contract,
                self.data.savings_pool_contract,
                self.data.token_id,
                asset_accrual.value,
            )
            Utils.execute_token_mint(
                self.data.token_contract,
                self.data.reward_pool_contract,
                self.data.token_id,
                spread_accrual.value,
            )

            self.data.total_supply += asset_accrual.value + spread_accrual.value

            self.data.accrual_update_timestamp = sp.now

    @sp.private_lambda(with_storage="read-write", with_operations=True, wrap_call=True)
    def update_governance_stake(self, stake):
        """sub entrypoint to call "update_stake" on the governance token contract

        Post: governance_token.update_stake(stake)

        Args:
            stake (Stake): Address and amount
        """
        sp.set_type(stake, Stake.get_type())
        governance_token_contract = sp.contract(
            Stake.get_type(),
            self.data.governance_token_contract,
            entry_point="update_stake",
        ).open_some()
        sp.transfer(stake, sp.mutez(0), governance_token_contract)

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_contracts(
        self,
        target_price_oracle,
        reward_pool_contract,
        savings_pool_contract,
        governance_token_contract,
        options_contract,
    ):
        """entrypoint to set all helper contracts, only an admin of id=0 is allowed to do so.

        Args:
            target_price_oracle (sp.address): target oracle
            observed_price_oracle (sp.address): observer oracle
            reward_pool_contract (sp.address): rewards pool contract
            savings_pool_contract (sp.address): savings pool contract
            governance_token_contract (sp.address): governance token contract
            options_contract (sp.address): options listing contract
        """
        self.verify_is_admin(Constants.DEFAULT_TOKEN_ID)
        self.data.target_price_oracle = target_price_oracle
        self.data.reward_pool_contract = reward_pool_contract
        self.data.savings_pool_contract = savings_pool_contract
        self.data.governance_token_contract = governance_token_contract
        self.data.options_contract = options_contract

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_reference_interest_rate(self, reference_interest_rate):
        self.verify_is_admin(Constants.DEFAULT_TOKEN_ID)
        self.update_accrual(sp.unit)
        self.data.reference_interest_rate = reference_interest_rate

    @sp.entry_point(check_no_incoming_transfer=True)
    def create_vault(self, allows_settlement):
        """originates a new vault for the sender, sets the deleage and returns the address in the callback

        Args:
            baker (sp.TOption(sp.TKeyHash)): delegate to set
            contract_address_callback (sp.TContract(sp.TAddress)): callback to receive the adress of the originated vault
        """
        sp.set_type(allows_settlement, sp.TBool)

        with sp.if_(~self.data.vault_contexts.contains(sp.sender)):
            vault_context = sp.record(
                minted=sp.nat(0),
                is_being_liquidated=False,
                balance=0,
                allows_settlement=allows_settlement,
            )
            self.data.vault_contexts[sp.sender] = vault_context

    @sp.entry_point(check_no_incoming_transfer=True)
    def mint(self, token_amount):
        """entrypoint called by a vault owner allows to mint new tokens. The actual logic is in "internal_mint".

        Post: update_accrual()
        Post: storage.sender = sp.sender
        Post: call self.internal_mint

        Args:
            token_amount (sp.nat): token amoun to mint
        """
        sp.set_type(token_amount, sp.TNat)

        self.update_accrual(sp.unit)

        sp.verify(
            token_amount >= Constants.MIN_TOKEN_AMOUNT_THRESHOLD,
            message=Errors.AMOUNT_TOO_SMALL,
        )

        vault_context = sp.local("vault_context", self.data.vault_contexts[sp.sender])

        balance_as_nat = vault_context.value.balance
        current_token_amount = sp.local(
            "current_token_amount",
            (vault_context.value.minted * self.data.compound_interest_rate)
            / Constants.PRECISION_FACTOR,
        )

        target_price = sp.view(
            "get_price", self.data.target_price_oracle, sp.unit, t=sp.TNat
        ).open_some(Errors.INVALID_VIEW)
        market_price_amount = sp.local(
            "market_price_amount",
            ((current_token_amount.value + token_amount) * target_price)
            // self.price_extra_precision_factor,
        )

        required_balance = (
            market_price_amount.value * Constants.TARGET_COLLATERALIZATION_FACTOR
        )
        sp.verify(
            balance_as_nat * Constants.PRICE_PRECISION_FACTOR >= required_balance,
            message=Errors.NOT_ENOUGH_COLLATERAL,
        )  # because we want to avoid divisions we multiply the "other side" instead

        minting_fee = token_amount >> Constants.MINTING_FEE_BITSHIFT
        owner_amount = sp.as_nat(token_amount - minting_fee)

        vault_context.value.minted += (
            token_amount * Constants.PRECISION_FACTOR
        ) / self.data.compound_interest_rate

        self.data.vault_contexts[sp.sender] = vault_context.value

        Utils.execute_token_mint(
            self.data.token_contract, sp.sender, self.data.token_id, owner_amount
        )
        Utils.execute_token_mint(
            self.data.token_contract,
            self.data.reward_pool_contract,
            self.data.token_id,
            minting_fee,
        )

        self.data.total_supply += token_amount
        with sp.if_(vault_context.value.allows_settlement):
            self.update_governance_stake(
                Stake.make(sp.sender, market_price_amount.value)
            )

    @sp.entry_point(check_no_incoming_transfer=True)
    def burn(self, token_amount):
        """entrypoint called by a vault owner allows to burn tokens. The actual logic is in "internal_burn".

        Pre: verify_internal()
        Pre: token_amount > 10**9
        Pre: storage.vault_contexts.contains(storage.sender)

        Post: token.burn(storage.sender, token_amount)

        Post: storage.vault_contexts[storage.sender].minted -= token_amount*10**12/storage.compound_interest_rate
        Post: storage.total_supply -= token_amount
        Post: update_governance_stake(sender, storage.target_price * ((storage.vault_contexts[storage.sender].minted*storage.compound_interest_rate/10**12)-token_amount))

        Args:
            token_amount (sp.nat): token amoun to burn
        """
        sp.set_type(token_amount, sp.TNat)
        self.update_accrual(sp.unit)

        sp.verify(
            token_amount >= Constants.MIN_TOKEN_AMOUNT_THRESHOLD,
            message=Errors.AMOUNT_TOO_SMALL,
        )

        vault_context = sp.local("vault_context", self.data.vault_contexts[sp.sender])

        current_token_amount = sp.local(
            "current_token_amount",
            (vault_context.value.minted * self.data.compound_interest_rate)
            / Constants.PRECISION_FACTOR,
        )

        target_price = sp.view(
            "get_price", self.data.target_price_oracle, sp.unit, t=sp.TNat
        ).open_some(Errors.INVALID_VIEW)
        market_price_amount = sp.local(
            "market_price_amount",
            (sp.as_nat(current_token_amount.value - token_amount) * target_price)
            // self.price_extra_precision_factor,
        )

        vault_context.value.minted = (
            sp.as_nat(current_token_amount.value - token_amount)
            * Constants.PRECISION_FACTOR
            / self.data.compound_interest_rate
        )

        self.data.vault_contexts[sp.sender] = vault_context.value

        Utils.execute_token_burn(
            self.data.token_contract, sp.sender, self.data.token_id, token_amount
        )

        self.data.total_supply = sp.as_nat(self.data.total_supply - token_amount)
        with sp.if_(vault_context.value.allows_settlement):
            self.update_governance_stake(
                Stake.make(sp.sender, market_price_amount.value)
            )

    @sp.entry_point(check_no_incoming_transfer=True)
    def liquidate(self, liquidation):
        """entrypoint that can be called by anyone to liquidate a vault with too little collateral (<2x). The actual logic can be found in internal_liquidate.

        Pre: verify_internal()
        Pre: storage.vault_contexts.contains(liquidation.vault_owner)
        Pre: storage.vault_contexts[liquidation.vault_owner].balance*10**12 < 2 * storage.target_price * (token_amount + storage.vault_contexts[liquidation.vault_owner].minted*storage.compound_interest_rate/10**12) || storage.vault_contexts[storage.sender].is_being_liquidated
        Pre: storage.vault_contexts[liquidation.vault_owner].balance - liquidation.token_amount*storage.target_price * 1.125 < 3 * storage.target_price * ((storage.vault_contexts[storage.sender].minted*storage.compound_interest_rate/10**12) - liquidation.token_amount)
        Post: storage.vault_contexts[liquidation.vault_owner].is_being_liquidated = True
        Post: storage.vault_contexts[liquidation.vault_owner].minted -= liquidation.token_amount*10**12/storage.compound_interest_rate
        Post: token.burn(storage.sender, liquidation.token_amount)
        Post: storage.total_supply -= liquidation.token_amount
        Post: update_governance_stake(liquidation.vault_owner, storage.target_price * ((storage.vault_contexts[liquidation.vault_owner].minted*storage.compound_interest_rate/10**12)-token_amount))
        Post: vault.withdraw(liquidation.vault_owner, liquidation.token_amount*storage.target_price * 1.125/10**12)

        Args:
            liquidation (Liquidation): liquidation parameter include address and amount to liquidate
        """

        sp.set_type(liquidation, Liquidation.get_type())

        self.update_accrual(sp.unit)

        vault_context = sp.local(
            "vault_context", self.data.vault_contexts[liquidation.vault_owner]
        )

        balance_as_nat = sp.local("balance_as_nat", vault_context.value.balance)
        current_token_amount = (
            vault_context.value.minted * self.data.compound_interest_rate
        ) / Constants.PRECISION_FACTOR

        target_price = sp.view(
            "get_price", self.data.target_price_oracle, sp.unit, t=sp.TNat
        ).open_some(Errors.INVALID_VIEW)
        sp.verify(
            (
                balance_as_nat.value * Constants.PRICE_PRECISION_FACTOR
                < (
                    current_token_amount
                    * target_price
                    * Constants.EMERGENCY_COLLATERALIZATION_FACTOR
                )
                // self.price_extra_precision_factor
            )
            | vault_context.value.is_being_liquidated,
            message=Errors.NOT_BELOW_EMERGENCY,
        )  # because we want to avoid divisions we multiply the "other side" instead

        vault_context.value.is_being_liquidated = True

        token_amount_market_value = (
            liquidation.token_amount * target_price
        ) // self.price_extra_precision_factor
        liquidation_reward = (
            token_amount_market_value >> Constants.LIQUIDATION_REWARD_BITSHIFT
        )
        liquidation_payout_amount = sp.local(
            "liquidation_payout_amount",
            (token_amount_market_value + liquidation_reward)
            // Constants.PRICE_PRECISION_FACTOR,
        )

        market_price_amount = sp.local(
            "market_price_amount",
            (sp.as_nat(current_token_amount - liquidation.token_amount) * target_price)
            // self.price_extra_precision_factor,
        )

        sp.verify(
            sp.as_nat(balance_as_nat.value - liquidation_payout_amount.value)
            * Constants.PRICE_PRECISION_FACTOR
            < market_price_amount.value * Constants.TARGET_COLLATERALIZATION_FACTOR,
            message=Errors.TOO_MUCH_SETTLEMENT,
        )
        sp.verify(
            liquidation_payout_amount.value >= Constants.MIN_TOKEN_AMOUNT_THRESHOLD,
            message=Errors.AMOUNT_TOO_SMALL,
        )

        with sp.if_(
            sp.as_nat(balance_as_nat.value - liquidation_payout_amount.value)
            * Constants.PRICE_PRECISION_FACTOR
            * 105
            >= market_price_amount.value
            * Constants.TARGET_COLLATERALIZATION_FACTOR
            * 100
        ):
            vault_context.value.is_being_liquidated = False

        Utils.execute_token_burn(
            self.data.token_contract,
            sp.sender,
            self.data.token_id,
            liquidation.token_amount,
        )

        self.data.total_supply = sp.as_nat(
            self.data.total_supply - liquidation.token_amount
        )

        vault_context.value.minted = (
            sp.as_nat(current_token_amount - liquidation.token_amount)
            * Constants.PRECISION_FACTOR
            // self.data.compound_interest_rate
        )
        vault_context.value.balance = sp.as_nat(
            vault_context.value.balance - liquidation_payout_amount.value
        )

        self.data.vault_contexts[liquidation.vault_owner] = vault_context.value
        with sp.if_(vault_context.value.allows_settlement):
            self.update_governance_stake(
                Stake.make(liquidation.vault_owner, market_price_amount.value)
            )

        # the following statement is evaluated at compile time
        if self.collateral_token_type == Constants.TOKEN_TYPE_FA2:
            Utils.execute_fa2_token_transfer(
                self.data.collateral_token_contract,
                sp.self_address,
                sp.sender,
                self.data.collateral_token_id,
                liquidation_payout_amount.value,
            )
        elif self.collateral_token_type == Constants.TOKEN_TYPE_FA1:
            Utils.execute_fa1_token_transfer(
                self.data.collateral_token_contract,
                sp.self_address,
                sp.sender,
                liquidation_payout_amount.value,
            )

    @sp.entry_point(check_no_incoming_transfer=True)
    def deposit(self, token_amount):
        """external entrypoint to deposit a certain amount of tokens (requires you to have called update_operators to allow this contract first).
        The actual logic is in internal_deposit.

        Post: storage.sender = sp.sender
        Post: fetch_reward_balance()
        Post: calls self.internal_deposit

        Args:
            token_amount (sp.nat): the amount of tokens
        """

        sp.set_type(token_amount, sp.TNat)
        if self.collateral_token_type == Constants.TOKEN_TYPE_FA2:
            Utils.execute_fa2_token_transfer(
                self.data.collateral_token_contract,
                sp.sender,
                sp.self_address,
                self.data.collateral_token_id,
                token_amount,
            )
        elif self.collateral_token_type == Constants.TOKEN_TYPE_FA1:
            Utils.execute_fa1_token_transfer(
                self.data.collateral_token_contract,
                sp.sender,
                sp.self_address,
                token_amount,
            )
        self.data.vault_contexts[sp.sender].balance += token_amount

    @sp.entry_point(check_no_incoming_transfer=True)
    def withdraw(self, token_amount):
        """internal entrypoint that allows to withdraw excess collateral. Excess collateral is defined as tez amount which is more than the 3x as the compounded minted
        liability.

        Pre: verify_internal()
        Pre: storage.vault_contexts.contains(storage.sender)
        Pre: (storage.vault_contexts[storage.sender].balance-amount)*10**12 >= 3 * storage.target_price * (storage.vault_contexts[liquidation.vault_owner].minted*storage.compound_interest_rate/10**12)
        Post: vault.withdraw(liquidation.vault_owner, amount)

        Args:
            amount (sp.mutez): the mutez amount to withdraw
        """

        sp.set_type(token_amount, sp.TNat)

        self.update_accrual(sp.unit)

        vault_context = sp.local("vault_context", self.data.vault_contexts[sp.sender])

        balance_as_nat = sp.as_nat(vault_context.value.balance - token_amount)
        current_token_amount = (
            vault_context.value.minted * self.data.compound_interest_rate
        )
        target_price = sp.view(
            "get_price", self.data.target_price_oracle, sp.unit, t=sp.TNat
        ).open_some(Errors.INVALID_VIEW)

        sp.verify(
            balance_as_nat
            * Constants.PRECISION_FACTOR
            * Constants.PRICE_PRECISION_FACTOR
            >= (
                current_token_amount
                * target_price
                * Constants.TARGET_COLLATERALIZATION_FACTOR
            )
            // self.price_extra_precision_factor,
            message=Errors.NOT_ENOUGH_COLLATERAL,
        )
        vault_context.value.balance = balance_as_nat

        self.data.vault_contexts[sp.sender] = vault_context.value

        if self.collateral_token_type == Constants.TOKEN_TYPE_FA2:
            Utils.execute_fa2_token_transfer(
                self.data.collateral_token_contract,
                sp.self_address,
                sp.sender,
                self.data.collateral_token_id,
                token_amount,
            )
        elif self.collateral_token_type == Constants.TOKEN_TYPE_FA1:
            Utils.execute_fa1_token_transfer(
                self.data.collateral_token_contract,
                sp.self_address,
                sp.sender,
                token_amount,
            )

    @sp.entry_point(check_no_incoming_transfer=True)
    def settle_with_vault(self, settlement):
        """entrypoint to settle a certain token amount against a vault (at a premium of 6.25%). The tokens are directly burned on the
        options_contract address.

        Pre: verify_internal()
        Pre: storage.vault_contexts.contains(settlement.vault_owner)
        Pre: storage.sender == storage.options_contract

        Post: storage.vault_contexts[settlement.vault_owner].minted -= settlement.token_amount*10**12/storage.compound_interest_rate
        Post: token.burn(storage.sender, settlement.token_amount)
        Post: storage.total_supply -= settlement.token_amount

        Post: update_governance_stake(settlement.vault_owner, storage.target_price * ((storage.vault_contexts[settlement.vault_owner].minted*storage.compound_interest_rate/10**12)-settlement.token_amount))
        Post: vault.withdraw(settlement.vault_owner, settlement.token_amount*storage.target_price * 0.9375/10**12)

        Args:
            settlement (Settlement): the settlement includes the vault_owner, the token_amount and the recipient of the tez
        """
        sp.set_type(settlement, Settlement.get_type())
        self.update_accrual(sp.unit)

        sp.verify(sp.sender == self.data.options_contract, message=Errors.NOT_ADMIN)

        vault_context = sp.local(
            "vault_context", self.data.vault_contexts[settlement.vault_owner]
        )

        sp.verify(
            vault_context.value.allows_settlement, message=Errors.SETTLEMENT_NOT_ALLOWED
        )
        target_price = sp.view(
            "get_price", self.data.target_price_oracle, sp.unit, t=sp.TNat
        ).open_some(Errors.INVALID_VIEW)

        market_price_amount = sp.local(
            "market_price_amount",
            (settlement.token_amount * target_price)
            // self.price_extra_precision_factor,
        )
        fee_amount = market_price_amount.value >> Constants.BID_FEE_BITSHIFT
        payout_amount = sp.local(
            "payout_amount",
            sp.as_nat(market_price_amount.value - fee_amount)
            // Constants.PRICE_PRECISION_FACTOR,
        )
        sp.verify(
            payout_amount.value >= Constants.MIN_TOKEN_AMOUNT_THRESHOLD,
            message=Errors.AMOUNT_TOO_SMALL,
        )

        current_token_amount = sp.local(
            "current_token_amount",
            (vault_context.value.minted * self.data.compound_interest_rate)
            / Constants.PRECISION_FACTOR,
        )

        vault_context.value.minted = (
            sp.as_nat(current_token_amount.value - settlement.token_amount)
            * Constants.PRECISION_FACTOR
            / self.data.compound_interest_rate
        )
        vault_context.value.balance = sp.as_nat(
            vault_context.value.balance - payout_amount.value
        )

        self.data.vault_contexts[settlement.vault_owner] = vault_context.value

        with sp.if_(vault_context.value.allows_settlement):
            self.update_governance_stake(
                sp.record(
                    address=settlement.vault_owner,
                    amount=(
                        sp.as_nat(current_token_amount.value - settlement.token_amount)
                        * target_price
                    )
                    // self.price_extra_precision_factor,
                )
            )

        if self.collateral_token_type == Constants.TOKEN_TYPE_FA2:
            Utils.execute_fa2_token_transfer(
                self.data.collateral_token_contract,
                sp.self_address,
                settlement.recipient,
                self.data.collateral_token_id,
                payout_amount.value,
            )
        elif self.collateral_token_type == Constants.TOKEN_TYPE_FA1:
            Utils.execute_fa1_token_transfer(
                self.data.collateral_token_contract,
                sp.self_address,
                settlement.recipient,
                payout_amount.value,
            )

        Utils.execute_token_burn(
            self.data.token_contract,
            sp.sender,
            self.data.token_id,
            settlement.token_amount,
        )
        self.data.total_supply = sp.as_nat(
            self.data.total_supply - settlement.token_amount
        )

    @sp.entry_point(check_no_incoming_transfer=True)
    def touch(self, addresses):
        """triggers the contract to update the accrual
        Post: update_accrual()
        """
        sp.set_type(addresses, sp.TList(sp.TAddress))
        self.update_accrual(sp.unit)

        target_price = sp.view(
            "get_price", self.data.target_price_oracle, sp.unit, t=sp.TNat
        ).open_some(Errors.INVALID_VIEW)
        with sp.for_("address", addresses) as address:
            with sp.if_(self.data.vault_contexts[address].allows_settlement):
                self.update_governance_stake(
                    sp.record(
                        address=address,
                        amount=(
                            self.data.vault_contexts[address].minted
                            * self.data.compound_interest_rate
                            * target_price
                        )
                        // (
                            Constants.PRECISION_FACTOR
                            * self.price_extra_precision_factor
                        ),
                    )
                )

    @sp.entry_point(check_no_incoming_transfer=True)
    def update(self):
        """triggers the contract to update the accrual
        Post: update_accrual()
        """
        self.update_accrual(sp.unit)
