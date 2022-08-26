import smartpy as sp

import utils.error_codes as Errors
import utils.constants as Constants
from utils.contract_utils import Ratio, Utils
from utils.fa2 import AdministrableMixin, LedgerKey
from contracts.tracker.vault import Vault, TransferAmount

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

    def get_internal_type():
        """Returns a single Settlement type, layouted

        Returns:
            sp.TRecord: the layouted settlement
        """
        return sp.TRecord(
            vault_owner=sp.TAddress,
            token_amount=sp.TNat,
            recipient=sp.TAddress,
            collateral_ratio=Ratio.get_type(),
            payout_ratio=Ratio.get_type(),
        ).layout(
            (
                "vault_owner",
                ("token_amount", ("recipient", ("collateral_ratio", "payout_ratio"))),
            )
        )

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

    def make_internal(
        vault_owner, token_amount, recipient, collateral_ratio, payout_ratio
    ):
        """Makes an instance of an settlement used internally by the contract.

        Args:
            vault_owner (sp.address): vault_owner
            token_amount (sp.nat): token_amount
            recipient (sp.address): recipient of the settlement tez
            collateral_ratio (Ratio): denominator and numerator of the collateral ratio
            payout_ratio (Ratio): denominator and numerator of the payout ratio

        Returns:
            Settlement: the settlement record
        """
        return sp.set_type_expr(
            sp.record(
                vault_owner=vault_owner,
                token_amount=token_amount,
                recipient=recipient,
                collateral_ratio=collateral_ratio,
                payout_ratio=payout_ratio,
            ),
            Settlement.get_internal_type(),
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


def ceil_div(ratio):
    """lambda used to return a rounded up division of the given ratio.

    Args:
        dividend (sp.nat): the number to be divided.
        divisor (sp.nat): the divisor.
    """
    sp.set_type(ratio, sp.TPair(sp.TNat, sp.TNat))
    (dividend, divisor) = sp.match_pair(ratio)

    returnVal = sp.local("returnVal", sp.nat(0))
    remainder = dividend % divisor
    with sp.if_(remainder == sp.nat(0)):
        returnVal.value = dividend // divisor
    with sp.else_():
        returnVal.value = dividend // divisor + 1
    
    sp.result(returnVal.value)


class BaseTrackerEngine(sp.Contract, AdministrableMixin):
    """This is the heartpiece of the entire project. The engine that orchestrates all other
    components. This contract is responsible for the interest rate/inflation of the
    liability/savings rate of the synthetic asset. This engine is built to create synthetic asset
    tokens that by getting data from an oracle the resulting synthetic asset will track that value.

    Args:
        (sp.Contract): this is a smartpy contract
        (AdministrableMixin): mixin used to add the administratble entrypoints
    """

    def get_init_storage(self):
        """Returns the initial storage of the contract used for inheritance of smartpy contracts

        Returns:
            dict: initial storage of the contract
        """
        storage = {}

        storage["administrators"] = self.administrators

        storage["accrual_update_timestamp"] = sp.timestamp(0)

        storage["reference_interest_rate"] = Constants.SECONDS_INTEREST_MINIMUM
        storage["compound_interest_rate"] = Constants.PRECISION_FACTOR
        
        # (1 + (316/10**12))**(60*60*24*365) --> approx 1% yearly
        storage["spread_rate"] = sp.nat(316)

        storage["total_supply"] = sp.nat(0)

        storage["target_price_oracle"] = Constants.DEFAULT_ADDRESS
        storage["reward_pool_contract"] = Constants.DEFAULT_ADDRESS
        storage["savings_pool_contract"] = Constants.DEFAULT_ADDRESS
        storage["governance_token_contract"] = Constants.DEFAULT_ADDRESS
        storage["options_contract"] = Constants.DEFAULT_ADDRESS
        storage["interest_rate_setter_contract"] = Constants.DEFAULT_ADDRESS

        storage["token_contract"] = self.token_contract
        storage["token_id"] = self.token_id

        storage["collateral_token_contract"] = self.collateral_token_contract
        storage["collateral_token_id"] = self.collateral_token_id

        storage["collateral_ratio"] = Ratio.make(2, 1)
        storage["settlement_ratio"] = Ratio.make(3, 1)
        storage["minting_fee_ratio"] = Ratio.make(15625, 1000000)  # 1.5625%
        storage["introducer_ratio"] = Ratio.make(125, 1000)  # 12.5%
        storage["settlement_reward_fee_ratio"] = Ratio.make(125, 1000)  # 12.5
        storage["settlement_payout_ratio"] = Ratio.make(9375, 10000)  # 100%-6.25% = 93.75%
        storage["liquidation_payout_ratio"] = Ratio.make(1125, 1000)

        return storage

    def __init__(
        self,
        token_contract,
        token_id,
        collateral_token_contract,
        collateral_token_id=0,
        price_extra_precision_factor=1,
        collateral_token_decimals = 6,
        token_decimals = 12,
        administrators={},
    ):
        """init to set the token and administrators, in order to be fully operational set_contracts
        need to be called first.

        Args:
            token_contract (sp.address): token address
            token_id (sp.nat): token id
            administrators (dict): the administrators allowed to set the contracts. Defaults to {}.
        """
        self.token_contract = token_contract
        self.token_id = token_id
        self.collateral_token_contract = collateral_token_contract
        self.collateral_token_id = collateral_token_id
        self.administrators = administrators
        self.price_extra_precision_factor = price_extra_precision_factor
        self.collateral_token_decimals = collateral_token_decimals
        self.token_decimals = token_decimals

        self.init(**self.get_init_storage())
    
    @sp.private_lambda(with_storage="read-write", with_operations=True, wrap_call=True)
    def update_accrual(self, unit):
        """lambda used to update the accrual based on the interest rate and timedelta.

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
                    self.data.spread_rate
                    * timedelta_since_last_update.value
                    * self.data.total_supply
                )
                / Constants.PRECISION_FACTOR,
            )

            compound_interest_rate = (
                Constants.PRECISION_FACTOR
                + (self.data.reference_interest_rate + self.data.spread_rate)
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
        interest_rate_setter_contract
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
        self.data.interest_rate_setter_contract = interest_rate_setter_contract

    @sp.private_lambda(with_storage="read-write", with_operations=True, wrap_call=True)
    def internal_settle_with_vault(self, settlement):
        """Used by liquidate and settle_with_vault entrypoint. Internally checks if the vault can
        be settled and if yes settles the vault by burning from sp.sender and sending the payout
        to recipient.
        """
        sp.set_type(settlement, Settlement.get_internal_type())

        target_price = sp.view(
            "get_price", self.data.target_price_oracle, sp.unit, t=sp.TNat
        ).open_some(Errors.INVALID_VIEW)

        vault_context = sp.local(
            "vault_context", self.data.vault_contexts[settlement.vault_owner]
        )
        balance_as_nat = sp.local("balance_as_nat", vault_context.value.balance)
        unnormalized_minted_amount = sp.local(
            "unnormalized_minted_amount", 
            vault_context.value.minted * self.data.compound_interest_rate)
        ceil_div_lambda = sp.compute(sp.build_lambda(ceil_div))
        current_minted_token_amount = sp.local(
            "current_minted_token_amount",
            ceil_div_lambda(sp.pair(unnormalized_minted_amount.value, Constants.PRECISION_FACTOR)))

        normalised_individual_collateral_numerator = (
            balance_as_nat.value
            * Constants.PRICE_PRECISION_FACTOR
            * Constants.PRICE_PRECISION_FACTOR
            * self.price_extra_precision_factor
            * (10**self.token_decimals)
        )
        normalised_individual_collateral_denominator = (
            current_minted_token_amount.value 
            * target_price 
            * (10**self.collateral_token_decimals)
        )
        normalised_individual_collateral_ratio = sp.local(
            "normalised_individual_collateral_ratio",
            normalised_individual_collateral_numerator 
            // normalised_individual_collateral_denominator
        )
        normalised_payout_ratio = (
            Constants.PRICE_PRECISION_FACTOR
            * settlement.payout_ratio.numerator
            // settlement.payout_ratio.denominator
        )
        normalised_collateral_ratio = (
            Constants.PRICE_PRECISION_FACTOR
            * settlement.collateral_ratio.numerator
            // settlement.collateral_ratio.denominator
        )

        sp.verify(
            normalised_individual_collateral_ratio.value
            < normalised_collateral_ratio,
            message=Errors.NOT_BELOW_EMERGENCY,
        )

        min_payout_ratio = sp.min(
            normalised_individual_collateral_ratio.value, normalised_payout_ratio)
        token_amount_market_value = (settlement.token_amount * target_price * 10**self.collateral_token_decimals) // (self.price_extra_precision_factor * Constants.PRICE_PRECISION_FACTOR * 10**self.token_decimals)

        payout_amount = sp.local(
            "payout_amount",
            (token_amount_market_value * min_payout_ratio)
            // Constants.PRICE_PRECISION_FACTOR,
        )
        reward_amount = sp.local(
            "reward_amount",
            sp.as_nat(sp.max(0, (payout_amount.value - token_amount_market_value)))
            * self.data.settlement_reward_fee_ratio.numerator
            // self.data.settlement_reward_fee_ratio.denominator,
        )

        new_minted_token_amount = sp.local(
            "new_minted_token_amount",
            sp.as_nat(current_minted_token_amount.value - settlement.token_amount),
        )
        new_market_price_amount = sp.local(
            "new_market_price_amount",
            (new_minted_token_amount.value * target_price)
            // self.price_extra_precision_factor,
        )

        sp.verify(
            sp.as_nat(balance_as_nat.value - payout_amount.value)  
            * Constants.PRICE_PRECISION_FACTOR * 10**self.token_decimals
            < new_market_price_amount.value 
            * 10**self.collateral_token_decimals * settlement.collateral_ratio.numerator
            // settlement.collateral_ratio.denominator,
            message=Errors.TOO_MUCH_SETTLEMENT,
        )
        sp.verify(
            payout_amount.value >= Constants.MIN_TOKEN_AMOUNT_THRESHOLD,
            message=Errors.AMOUNT_TOO_SMALL,
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

        vault_context.value.minted = (
            new_minted_token_amount.value
            * Constants.PRECISION_FACTOR
            // self.data.compound_interest_rate
        )
        vault_context.value.balance = sp.as_nat(
            balance_as_nat.value - payout_amount.value
        )

        self.data.vault_contexts[settlement.vault_owner] = vault_context.value

        if self.collateral_token_type == Constants.TOKEN_TYPE_TEZ:
            withdraw_from_vault = sp.contract(
                TransferAmount.get_type(),
                vault_context.value.address,
                entry_point="withdraw",
            ).open_some()
            sp.transfer(
                TransferAmount.make(
                    settlement.recipient,
                    sp.utils.nat_to_mutez(sp.as_nat(payout_amount.value - reward_amount.value))),
                sp.mutez(0),
                withdraw_from_vault,
            )
            sp.transfer(
                TransferAmount.make(
                    self.data.reward_pool_contract,
                    sp.utils.nat_to_mutez(reward_amount.value)),
                sp.mutez(0),
                withdraw_from_vault,
            )
        elif self.collateral_token_type == Constants.TOKEN_TYPE_FA2:
            Utils.execute_fa2_token_transfer(
                self.data.collateral_token_contract,
                sp.self_address,
                settlement.recipient,
                self.data.collateral_token_id,
                sp.as_nat(payout_amount.value - reward_amount.value),
            )
            Utils.execute_fa2_token_transfer(
                self.data.collateral_token_contract,
                sp.self_address,
                self.data.reward_pool_contract,
                self.data.collateral_token_id,
                reward_amount.value,
            )
        elif self.collateral_token_type == Constants.TOKEN_TYPE_FA1:
            Utils.execute_fa1_token_transfer(
                self.data.collateral_token_contract,
                sp.self_address,
                settlement.recipient,
                sp.as_nat(payout_amount.value - reward_amount.value),
            )
            Utils.execute_fa1_token_transfer(
                self.data.collateral_token_contract,
                sp.self_address,
                self.data.reward_pool_contract,
                reward_amount.value,
            )

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_reference_interest_rate(self, reference_interest_rate):
        sp.verify(
            sp.sender == self.data.interest_rate_setter_contract,
            message=Errors.NOT_ADMIN,
        )
        self.update_accrual(sp.unit)
        self.data.reference_interest_rate = reference_interest_rate

    @sp.entry_point(check_no_incoming_transfer=True)
    def mint(self, token_amount):
        """entrypoint called by a vault owner allows to mint new tokens.

        Pre: token_amount > 10**6
        Pre: storage.vault_contexts.contains(sp.sender)
        Pre: storage.vault_contexts[storage.sender].balance*10**12 * storage.collateral_ratio.denominator >= 
             storage.collateral_ratio.numerator * storage.target_price * (token_amount + storage.vault_contexts[storage.sender].minted*storage.compound_interest_rate/10**12)

        Post: update_accrual()
        Post: token.mint(storage.sender, token_amount - minting_fee)
        Post: token.mint(storage.reward_pool, minting_fee)
        Post: storage.total_supply += token_amount
        Post: storage.vault_contexts[storage.sender].minted += token_amount*10**12 / storage.compound_interest_rate
        Post: update_governance_stake(sender, storage.vault_contexts[sp.sender].minted))
        Post: update_governance_stake(introducer, storage.vault_contexts[sp.sender].minted * introducer_ratio)) if any.

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
        unnormalized_minted_amount = sp.local(
            "unnormalized_minted_amount", 
            vault_context.value.minted * self.data.compound_interest_rate)

        ceil_div_lambda = sp.compute(sp.build_lambda(ceil_div))
        current_minted_token_amount = sp.local(
            "current_minted_token_amount",
            ceil_div_lambda(sp.pair(unnormalized_minted_amount.value, Constants.PRECISION_FACTOR)))

        target_price = sp.view(
            "get_price", self.data.target_price_oracle, sp.unit, t=sp.TNat
        ).open_some(Errors.INVALID_VIEW)
        market_price_amount = sp.local(
            "market_price_amount",
            ((current_minted_token_amount.value + token_amount) * target_price)
            // self.price_extra_precision_factor,
        )

        required_balance = (
            market_price_amount.value
            * self.data.collateral_ratio.numerator
            // self.data.collateral_ratio.denominator
        )
        sp.verify(
            balance_as_nat * Constants.PRICE_PRECISION_FACTOR * 10**self.token_decimals
            >= required_balance * 10**self.collateral_token_decimals,
            message=Errors.NOT_ENOUGH_COLLATERAL,
        )  # because we want to avoid divisions we multiply the "other side" instead

        minting_fee = (
            token_amount
            * self.data.minting_fee_ratio.numerator
            // self.data.minting_fee_ratio.denominator
        )
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

        self.update_governance_stake(Stake.make(sp.sender, vault_context.value.minted))
        with sp.if_(vault_context.value.introducer.is_some()):
            self.update_governance_stake(
                Stake.make(
                    vault_context.value.introducer.open_some(
                        message=Errors.NO_INTRODUCER
                    ),
                    vault_context.value.minted
                    * self.data.introducer_ratio.numerator
                    // self.data.introducer_ratio.denominator,
                )
            )

    @sp.entry_point(check_no_incoming_transfer=True)
    def burn(self, token_amount):
        """entrypoint called by a vault owner allows to burn tokens. 

        Pre: token_amount > 10**6
        Pre: storage.vault_contexts.contains(sp.sender)

        Post: token.burn(storage.sender, token_amount)

        Post: storage.vault_contexts[storage.sender].minted -= token_amount*10**12/storage.compound_interest_rate
        Post: storage.total_supply -= token_amount
        Post: update_governance_stake(sender, storage.vault_contexts[sp.sender].minted)
        Post: update_governance_stake(introducer, storage.vault_contexts[sp.sender].minted * introducer_ratio)

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

        unnormalized_minted_amount = sp.local(
            "unnormalized_minted_amount", 
            vault_context.value.minted * self.data.compound_interest_rate)
        ceil_div_lambda = sp.compute(sp.build_lambda(ceil_div))
        current_minted_token_amount = sp.local(
            "current_minted_token_amount",
           ceil_div_lambda(sp.pair(unnormalized_minted_amount.value, Constants.PRECISION_FACTOR)))

        unnormalized_minted_amount_after_burn = sp.local(
            "unnormalized_minted_amount_after_burn",
            sp.as_nat(current_minted_token_amount.value - token_amount) * Constants.PRECISION_FACTOR)
        vault_context.value.minted = ceil_div_lambda(
            sp.pair(unnormalized_minted_amount_after_burn.value, self.data.compound_interest_rate))

        self.data.vault_contexts[sp.sender] = vault_context.value

        Utils.execute_token_burn(
            self.data.token_contract, sp.sender, self.data.token_id, token_amount
        )
        self.data.total_supply = sp.as_nat(self.data.total_supply - token_amount)

        self.update_governance_stake(Stake.make(sp.sender, vault_context.value.minted))
        with sp.if_(vault_context.value.introducer.is_some()):
            self.update_governance_stake(
                Stake.make(
                    vault_context.value.introducer.open_some(
                        message=Errors.NO_INTRODUCER
                    ),
                    vault_context.value.minted
                    * self.data.introducer_ratio.numerator
                    // self.data.introducer_ratio.denominator,
                )
            )

    @sp.entry_point(check_no_incoming_transfer=True)
    def liquidate(self, liquidation):
        """entrypoint that can be called by anyone to liquidate a vault with too little collateral. The actual logic can be found in internal_settle_with_vault.

        Post: update_accrual()
        Post: internal_settle_with_vault()
        Post: update_governance_stake(sender, storage.vault_contexts[sp.sender].minted)
        Post: update_governance_stake(introducer, storage.vault_contexts[sp.sender].minted * introducer_ratio)

        Args:
            liquidation (Liquidation): liquidation parameter include address and amount to liquidate
        """

        sp.set_type(liquidation, Liquidation.get_type())
        self.update_accrual(sp.unit)

        self.internal_settle_with_vault(
            Settlement.make_internal(
                liquidation.vault_owner,
                liquidation.token_amount,
                sp.sender,
                self.data.collateral_ratio,
                self.data.liquidation_payout_ratio,
            )
        )

        vault_context = sp.local(
            "vault_context", self.data.vault_contexts[liquidation.vault_owner]
        )
        self.update_governance_stake(
            Stake.make(liquidation.vault_owner, vault_context.value.minted)
        )
        with sp.if_(vault_context.value.introducer.is_some()):
            self.update_governance_stake(
                Stake.make(
                    vault_context.value.introducer.open_some(
                        message=Errors.NO_INTRODUCER
                    ),
                    vault_context.value.minted
                    * self.data.introducer_ratio.numerator
                    // self.data.introducer_ratio.denominator,
                )
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
        sp.verify(sp.sender == self.data.options_contract, message=Errors.NOT_ADMIN)
        self.update_accrual(sp.unit)

        self.internal_settle_with_vault(
            Settlement.make_internal(
                settlement.vault_owner,
                settlement.token_amount,
                settlement.recipient,
                self.data.settlement_ratio,
                self.data.settlement_payout_ratio,
            )
        )

        vault_context = sp.local(
            "vault_context", self.data.vault_contexts[settlement.vault_owner]
        )
        self.update_governance_stake(
            Stake.make(settlement.vault_owner, vault_context.value.minted)
        )
        with sp.if_(vault_context.value.introducer.is_some()):
            self.update_governance_stake(
                Stake.make(
                    vault_context.value.introducer.open_some(
                        message=Errors.NO_INTRODUCER
                    ),
                    vault_context.value.minted
                    * self.data.introducer_ratio.numerator
                    // self.data.introducer_ratio.denominator,
                )
            )

    @sp.entry_point(check_no_incoming_transfer=True)
    def withdraw(self, token_amount):
        """entrypoint that allows to withdraw excess collateral. Excess collateral is defined as tez amount which is more than the 3x as the compounded minted
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
        current_minted_token_amount = (
            vault_context.value.minted * self.data.compound_interest_rate
        )
        target_price = sp.view(
            "get_price", self.data.target_price_oracle, sp.unit, t=sp.TNat
        ).open_some(Errors.INVALID_VIEW)

        sp.verify(
            balance_as_nat 
            * Constants.PRECISION_FACTOR 
            * Constants.PRICE_PRECISION_FACTOR * self.price_extra_precision_factor
            * 10**self.token_decimals 
            * self.data.collateral_ratio.denominator >= current_minted_token_amount
            * target_price * self.data.collateral_ratio.numerator * 10**self.collateral_token_decimals,
            message=Errors.NOT_ENOUGH_COLLATERAL,
        )
        vault_context.value.balance = balance_as_nat

        self.data.vault_contexts[sp.sender] = vault_context.value

        if self.collateral_token_type == Constants.TOKEN_TYPE_TEZ:
            withdraw_from_vault = sp.contract(
                TransferAmount.get_type(),
                vault_context.value.address,
                entry_point="withdraw",
            ).open_some()

            sp.transfer(
                TransferAmount.make(sp.sender, sp.utils.nat_to_mutez(token_amount)),
                sp.mutez(0),
                withdraw_from_vault,
            )
        elif self.collateral_token_type == Constants.TOKEN_TYPE_FA2:
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
    def touch(self, addresses):
        """triggers the contract to update the minted weight of specified vaults
        Post: update_accrual()
        """
        sp.set_type(addresses, sp.TList(sp.TAddress))
        self.update_accrual(sp.unit)

        with sp.for_("address", addresses) as address:
            vault_context = sp.local(
                "vault_context", self.data.vault_contexts[address]
            )
            self.update_governance_stake(
                Stake.make(address, vault_context.value.minted)
            )
            with sp.if_(vault_context.value.introducer.is_some()):
                self.update_governance_stake(
                    Stake.make(
                        vault_context.value.introducer.open_some(
                            message=Errors.NO_INTRODUCER
                        ),
                        vault_context.value.minted
                        * self.data.introducer_ratio.numerator
                        // self.data.introducer_ratio.denominator,
                    )
                )

    @sp.entry_point(check_no_incoming_transfer=True)
    def update(self):
        """triggers the contract to update the accrual
        Post: update_accrual()
        """
        self.update_accrual(sp.unit)

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_collateral_ratio(self, ratio):
        """Updates the collateral ratio. Only an admin can call this entrypoint."""
        sp.set_type(ratio, Ratio.get_type())

        self.verify_is_admin(Constants.DEFAULT_TOKEN_ID)
        self.data.collateral_ratio = ratio

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_settlement_ratio(self, ratio):
        """Updates the settlement ratio. Only an admin can call this entrypoint."""
        sp.set_type(ratio, Ratio.get_type())

        self.verify_is_admin(Constants.DEFAULT_TOKEN_ID)
        self.data.settlement_ratio = ratio

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_minting_fee_ratio(self, ratio):
        """Updates the minting fee ratio. Only an admin can call this entrypoint."""
        sp.set_type(ratio, Ratio.get_type())

        self.verify_is_admin(Constants.DEFAULT_TOKEN_ID)
        self.data.minting_fee_ratio = ratio

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_introducer_ratio(self, ratio):
        """Updates the introducer ratio. Only an admin can call this entrypoint."""
        sp.set_type(ratio, Ratio.get_type())

        self.verify_is_admin(Constants.DEFAULT_TOKEN_ID)
        self.data.introducer_ratio = ratio

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_settlement_reward_fee_ratio(self, ratio):
        """Updates the settlement reward fee ratio. Only an admin can call this entrypoint."""
        sp.set_type(ratio, Ratio.get_type())

        self.verify_is_admin(Constants.DEFAULT_TOKEN_ID)
        self.data.settlement_reward_fee_ratio = ratio

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_settlement_payout_ratio(self, ratio):
        """Updates the settlement payout ratio. Only an admin can call this entrypoint."""
        sp.set_type(ratio, Ratio.get_type())

        self.verify_is_admin(Constants.DEFAULT_TOKEN_ID)
        self.data.settlement_payout_ratio = ratio

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_liquidation_payout_ratio(self, ratio):
        """Updates the liquidation payout ratio. Only an admin can call this entrypoint."""
        sp.set_type(ratio, Ratio.get_type())

        self.verify_is_admin(Constants.DEFAULT_TOKEN_ID)
        self.data.liquidation_payout_ratio = ratio

    ######################## ON CHAIN VIEWS ########################
    @sp.onchain_view()
    def accrual_update_timestamp(self):
        sp.result(self.data.accrual_update_timestamp)

    @sp.onchain_view()
    def reference_interest_rate(self):
        sp.result(self.data.reference_interest_rate)

    @sp.onchain_view()
    def compound_interest_rate(self):
        sp.result(self.data.compound_interest_rate)

    @sp.onchain_view()
    def spread_rate(self):
        sp.result(self.data.spread_rate)

    @sp.onchain_view()
    def total_supply(self):
        sp.result(self.data.total_supply)

    @sp.onchain_view()
    def target_price_oracle(self):
        sp.result(self.data.target_price_oracle)

    @sp.onchain_view()
    def reward_pool_contract(self):
        sp.result(self.data.reward_pool_contract)

    @sp.onchain_view()
    def savings_pool_contract(self):
        sp.result(self.data.savings_pool_contract)

    @sp.onchain_view()
    def governance_token_contract(self):
        sp.result(self.data.governance_token_contract)

    @sp.onchain_view()
    def options_contract(self):
        sp.result(self.data.options_contract)

    @sp.onchain_view()
    def interest_rate_setter_contract(self):
        sp.result(self.data.interest_rate_setter_contract)

    @sp.onchain_view()
    def token_contract(self):
        sp.result(self.data.token_contract)

    @sp.onchain_view()
    def token_id(self):
        sp.result(self.data.token_id)

    @sp.onchain_view()
    def collateral_token_contract(self):
        sp.result(self.data.collateral_token_contract)

    @sp.onchain_view()
    def collateral_token_id(self):
        sp.result(self.data.collateral_token_id)

    @sp.onchain_view()
    def collateral_ratio(self):
        sp.result(self.data.collateral_ratio)

    @sp.onchain_view()
    def settlement_ratio(self):
        sp.result(self.data.settlement_ratio)

    @sp.onchain_view()
    def minting_fee_ratio(self):
        sp.result(self.data.minting_fee_ratio)

    @sp.onchain_view()
    def introducer_ratio(self):
        sp.result(self.data.introducer_ratio)

    @sp.onchain_view()
    def settlement_reward_fee_ratio(self):
        sp.result(self.data.settlement_reward_fee_ratio)

    @sp.onchain_view()
    def settlement_payout_ratio(self):
        sp.result(self.data.settlement_payout_ratio)

    @sp.onchain_view()
    def liquidation_payout_ratio(self):
        sp.result(self.data.liquidation_payout_ratio)

    @sp.onchain_view()
    def is_admin(self, ledger_key):
        sp.result(self.data.administrators.contains(ledger_key))

    @sp.onchain_view()
    def vault_context(self, address):
        "Returns the vault context or none if the vault is not present."
        sp.set_type(address, sp.TAddress)

        with sp.if_(self.data.vault_contexts.contains(address)):
            sp.result(sp.some(self.data.vault_contexts[address]))
        with sp.else_():
            sp.result(sp.none)
