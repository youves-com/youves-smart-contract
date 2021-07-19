import smartpy as sp

import tracker.errors as Errors
import tracker.constants as Constants
from tracker.utils import Utils, InternalMixin
from tracker.vault import Vault, TransferAmount
from tracker.fa2 import AdministrableMixin, LedgerKey
from tracker.governance_token import Stake


class Settlement:
    """Parameter used in settle_with_vault
    """
    def get_type():
        """Returns a single Settlement type, layouted

        Returns:
            sp.TRecord: the layouted settlement
        """
        return sp.TRecord(vault_owner=sp.TAddress, token_amount=sp.TNat, recipient=sp.TAddress).layout(("vault_owner", ("token_amount", "recipient")))

    def make(vault_owner, token_amount, recipient):
        """Makes an instance of an settlement

        Args:
            vault_owner (sp.address): vault_owner
            token_amount (sp.nat): token_amount
            recipient (sp.address): recipient of the settlement tez

        Returns:
            Settlement: the settlement record
        """
        return sp.set_type_expr(sp.record(vault_owner=vault_owner, token_amount=token_amount, recipient=recipient), Settlement.get_type())

class Liquidation:
    """Parameter used in liquidate
    """
    def get_type():
        """Returns a single Liquidation type, layouted

        Returns:
            sp.TRecord: the layouted liquidation
        """
        return sp.TRecord(vault_owner=sp.TAddress, token_amount=sp.TNat).layout(("vault_owner", "token_amount"))

    def make(vault_owner, token_amount):
        """Makes an instance of an liquidation

        Args:
            vault_owner (sp.address): vault_owner
            token_amount (sp.nat): token_amount

        Returns:
            Liquidation: the liquidation record
        """
        return sp.set_type_expr(sp.record(vault_owner=vault_owner, token_amount=token_amount), Liquidation.get_type())

class TrackerEngine(sp.Contract, AdministrableMixin,  InternalMixin):
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

        storage['reference_interest_rate'] = Constants.SECONDS_INTEREST_MINIMUM
        storage['compound_interest_rate'] = Constants.PRECISION_FACTOR

        storage['last_update_timestamp'] = sp.timestamp(0)
        storage['accrual_update_timestamp'] = sp.timestamp(0)

        storage['total_supply'] = sp.nat(0)

        storage['target_price_oracle'] = Constants.DEFAULT_ADDRESS
        storage['observed_price_oracle'] = Constants.DEFAULT_ADDRESS
        storage['reward_pool_contract'] = Constants.DEFAULT_ADDRESS
        storage['savings_pool_contract'] = Constants.DEFAULT_ADDRESS
        storage['governance_token_contract'] = Constants.DEFAULT_ADDRESS
        storage['options_contract'] = Constants.DEFAULT_ADDRESS

        storage['token_contract'] = self.token_contract
        storage['token_id'] = self.token_id

        storage['target_price'] = sp.nat(0)
        storage['observed_price'] = sp.nat(0)
        storage['sender'] = Constants.DEFAULT_ADDRESS


        storage['vault_contexts'] = sp.big_map(tkey=sp.TAddress, tvalue = sp.TRecord(address=sp.TAddress, minted=sp.TNat, is_being_liquidated=sp.TBool, balance=sp.TMutez))
        storage['vault_lookup'] = sp.big_map(tkey=sp.TAddress, tvalue = sp.TAddress)

        storage['administrators'] = sp.set_type_expr(self.administrators,sp.TBigMap(LedgerKey.get_type(), sp.TUnit))

        return storage

    def __init__(self, token_contract, token_id, administrators={}):
        """init to set the token and administrators, in order to be fully operational set_contracts need to be called first.
        Args:
            token_contract (sp.address): token address
            token_id (sp.nat): token id
            administrators (dict, optional): the administrators allowed to set the contracts. Defaults to {}.
        """
        self.token_contract = token_contract
        self.token_id = token_id
        self.administrators = administrators
        self.init(**self.get_init_storage())

    @sp.sub_entry_point
    def fetch_target_price(self, unit):
        """sub entrypoint which triggers a price fetch for the price to be set using the callback on the "set_target_price" entrypoint

        Args:
            unit (sp.unit): nothing
        """
        Utils.execute_get(self.data.target_price_oracle, "get_price", "set_target_price")

    @sp.sub_entry_point
    def fetch_observed_price(self, unit):
        """sub entrypoint which triggers a price fetch for the price to be set using the callback on the "set_observed_price" entrypoint

        Args:
            unit (sp.unit): nothing
        """
        Utils.execute_get(self.data.observed_price_oracle, "get_price", "set_observed_price")

    @sp.sub_entry_point
    def update_accrual(self, unit):
        """sub entrypoint which updates the accrual based on the interest rate and timedelta.

        Post: storage.accrual_update_timestamp = sp.now

        Args:
            unit (sp.unit): nothing
        """
        timedelta_since_last_update = sp.local("timedelta_since_last_update",sp.as_nat(
            sp.now-self.data.accrual_update_timestamp))
        with sp.if_(timedelta_since_last_update.value > 0):
            asset_accrual = sp.local("asset_accrual", (self.data.reference_interest_rate * \
                timedelta_since_last_update.value*self.data.total_supply)/Constants.PRECISION_FACTOR)
            spread_accrual = sp.local("spread_accrual",(Constants.SECONDS_INTEREST_SPREAD* \
                timedelta_since_last_update.value*self.data.total_supply)/Constants.PRECISION_FACTOR)

            compound_interest_rate = Constants.PRECISION_FACTOR + (self.data.reference_interest_rate+Constants.SECONDS_INTEREST_SPREAD) * timedelta_since_last_update.value

            self.data.compound_interest_rate = self.data.compound_interest_rate*compound_interest_rate/Constants.PRECISION_FACTOR

            Utils.execute_token_mint(self.data.token_contract, self.data.savings_pool_contract, self.data.token_id, asset_accrual.value)
            Utils.execute_token_mint(self.data.token_contract, self.data.reward_pool_contract, self.data.token_id, spread_accrual.value)

            self.data.total_supply += asset_accrual.value + spread_accrual.value

            self.data.accrual_update_timestamp = sp.now

    @sp.sub_entry_point
    def update_governance_stake(self, stake):
        """sub entrypoint to call "update_stake" on the governance token contract

        Post: governance_token.update_stake(stake)

        Args:
            stake (Stake): Address and amount
        """
        sp.set_type(stake, Stake.get_type())
        governance_token_contract = sp.contract(Stake.get_type(), self.data.governance_token_contract, entry_point="update_stake").open_some()
        sp.transfer(stake, sp.mutez(0), governance_token_contract)

    @sp.entry_point
    def set_vault_balance(self, vault_balance):
        """entrypoint used by the vault to set its balance
        Post: storage.vault_contexts[storage.vault_lookup[sp.sender]] = vault_balance
        Args:
            vault_balance (sp.mutez): vault balance
        """
        sp.set_type(vault_balance, sp.TMutez)
        self.data.vault_contexts[self.data.vault_lookup[sp.sender]].balance = vault_balance

    @sp.entry_point
    def set_target_price(self, target_price):
        """entrypoint used by the oracle to set the price
        Pre: sp.sender == storage.target_price_oracle
        Post: storage.target_price = target_price
        Args:
            target_price (sp.nat): price provided by the oracle
        """
        sp.set_type(target_price, sp.TNat)
        sp.verify(sp.sender == self.data.target_price_oracle)
        self.data.target_price = target_price

    @sp.entry_point
    def set_observed_price(self, observed_price):
        """entrypoint used by the oracle to set the price
        Pre: sp.sender == storage.observed_price_oracle
        Post: storage.observed_price = observed_price
        Args:
            observed_price (sp.nat): price provided by the oracle
        """
        sp.set_type(observed_price, sp.TNat)
        sp.verify(sp.sender == self.data.observed_price_oracle)
        self.data.observed_price = observed_price

    @sp.entry_point
    def set_contracts(self, target_price_oracle, observed_price_oracle, reward_pool_contract, savings_pool_contract, governance_token_contract, options_contract):
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
        self.data.observed_price_oracle = observed_price_oracle
        self.data.reward_pool_contract = reward_pool_contract
        self.data.savings_pool_contract = savings_pool_contract
        self.data.governance_token_contract = governance_token_contract
        self.data.options_contract = options_contract

    @sp.entry_point
    def interest_rate_update(self):
        """this entrypoint allows anyone to request for a referecne_interest update. Can only be once every week. The actual logic can be found in "internal_interest_rate_update".
        Post: fetch_target_price()
        Post: fetch_observed_price
        Post: calls self.internal_interest_rate_update
        """
        self.fetch_target_price(sp.unit)
        self.fetch_observed_price(sp.unit)
        sp.transfer(sp.unit, sp.mutez(0), sp.self_entry_point(
            "internal_interest_rate_update"))

    @sp.entry_point
    def internal_interest_rate_update(self):
        """updates the reference interest rate if it was not updated yet in this cycle. The minimum and maximum weekly interest rates set the upper and lower boundary of the interest rate.
        Inv: storage.reference_interest_rate >= Constants.SECONDS_INTEREST_MINIMUM
        Inv: storage.reference_interest_rate <= Constants.SECONDS_INTEREST_MAXIMUM
        Pre: sp.now/7days > storage.last_update_timestamp/7days
        Pre: verify_internal()
        Post: update_accrual()
        Post: storage.last_update_timestamp = sp.now
        Post: storage.reference_interest_rate is set according to documentation based on observed/target price difference.
        """
        self.verify_internal(sp.unit)

        last_cycle = sp.as_nat(self.data.last_update_timestamp -
                               sp.timestamp(0))//Constants.REFERENCE_INTEREST_UPDATE_INTERVAL
        current_cycle = sp.as_nat(
            sp.now-sp.timestamp(0))//Constants.REFERENCE_INTEREST_UPDATE_INTERVAL

        sp.verify(current_cycle > last_cycle, message=Errors.TOO_EARLY)

        price_difference = sp.local("price_difference", self.data.observed_price - self.data.target_price)
        stable_token_difference = sp.min(
            abs(price_difference.value), self.data.target_price >> Constants.MAX_STABLE_TOKEN_BITSHIFT)
        normalised_stable_token_difference = (
            stable_token_difference*Constants.FX_MULTIPLIER)/self.data.target_price
        target_step = sp.local("target_step", (sp.as_nat((1 << (normalised_stable_token_difference >>
                       Constants.SCALING_FACTOR_ONE))-1)*Constants.PRECISION_FACTOR) >> Constants.SCALING_FACTOR_TWO)

        self.update_accrual(sp.unit)

        with sp.if_(price_difference.value > 0):
            self.data.reference_interest_rate = sp.as_nat(
                sp.max(self.data.reference_interest_rate-target_step.value, Constants.SECONDS_INTEREST_MINIMUM))
        with sp.else_():
            self.data.reference_interest_rate = sp.min(
                self.data.reference_interest_rate+target_step.value, Constants.SECONDS_INTEREST_MAXIMUM)

        self.data.last_update_timestamp = sp.now

    @sp.entry_point
    def create_vault(self, baker, contract_address_callback):
        """originates a new vault for the sender, sets the deleage and returns the address in the callback

        Args:
            baker (sp.TOption(sp.TKeyHash)): delegate to set
            contract_address_callback (sp.TContract(sp.TAddress)): callback to receive the adress of the originated vault
        """
        sp.set_type(contract_address_callback, sp.TContract(sp.TAddress))
        sp.set_type(baker, sp.TOption(sp.TKeyHash))

        with sp.if_(~self.data.vault_contexts.contains(sp.sender)):
            vault_contract_address = sp.create_contract(Vault(sp.self_address), amount=sp.amount, baker=baker)
            vault_context = sp.record(address=vault_contract_address, minted=sp.nat(0), is_being_liquidated=False, balance=sp.amount)
            self.data.vault_contexts[sp.sender] = vault_context
            self.data.vault_lookup[vault_contract_address] = sp.sender
        with sp.else_():
            sp.send(self.data.vault_contexts[sp.sender].address, sp.amount)

        sp.transfer(self.data.vault_contexts[sp.sender].address, sp.mutez(0), contract_address_callback)

    @sp.entry_point
    def set_vault_delegate(self, baker):
        """external entrypoint called by a vault owner to set the delegate for her/his vault.

        Pre: storage.vault_contexts.contains(storage.sender)
        Post: delegate set on vault

        Args:
            baker (sp.TOption(sp.TKeyHash)): delegate to set
        """
        sp.set_type(baker, sp.TOption(sp.TKeyHash))

        set_vault_delegate = sp.contract(sp.TOption(sp.TKeyHash), self.data.vault_contexts[sp.sender].address, entry_point="set_delegate").open_some()
        sp.transfer(baker, sp.amount, set_vault_delegate)

    @sp.entry_point
    def mint(self, token_amount):
        """entrypoint called by a vault owner allows to mint new tokens. The actual logic is in "internal_mint".

        Post: fetch_target_price()
        Post: update_accrual()
        Post: storage.sender = sp.sender
        Post: call self.internal_mint

        Args:
            token_amount (sp.nat): token amoun to mint
        """
        sp.set_type(token_amount, sp.TNat)
        self.fetch_target_price(sp.unit)
        self.update_accrual(sp.unit)
        self.data.sender = sp.sender
        sp.transfer(token_amount, sp.mutez(0), sp.self_entry_point('internal_mint'))

    @sp.entry_point
    def internal_mint(self, token_amount):
        """internal entrypoint to mint a certain token amount given the current price and balance of a vault.

        Pre: verify_internal()
        Pre: token_amount > 10**9
        Pre: storage.vault_contexts.contains(storage.sender)
        Pre: storage.vault_contexts[storage.sender].balance*10**12 >= 3 * storage.target_price * (token_amount + storage.vault_contexts[storage.sender].minted*storage.compound_interest_rate/10**12)
        Post: token.mint(storage.sender, token_amount * 0.984375)
        Post: token.mint(storage.reward_pool, token_amount * 0.015625)
        Post: storage.total_supply += token_amount
        Post: storage.vault_contexts[storage.sender].minted += token_amount*10**12/storage.compound_interest_rate
        Post: update_governance_stake(sender, storage.target_price * (token_amount + storage.vault_contexts[storage.sender].minted*storage.compound_interest_rate/10**12))

        Args:
            token_amount (sp.nat): token amoun to mint
        """
        sp.set_type(token_amount, sp.TNat)
        self.verify_internal(sp.unit)
        sp.verify(token_amount >= Constants.MIN_TOKEN_AMOUNT_THRESHOLD, message=Errors.AMOUNT_TOO_SMALL)

        vault_context = sp.local("vault_context", self.data.vault_contexts[self.data.sender])

        balance_as_nat = sp.utils.mutez_to_nat(vault_context.value.balance)
        current_token_amount = sp.local("current_token_amount", (vault_context.value.minted*self.data.compound_interest_rate)/Constants.PRECISION_FACTOR)
        market_price_amount = sp.local("market_price_amount", (current_token_amount.value+token_amount) * self.data.target_price)

        required_balance = market_price_amount.value*Constants.TARGET_COLLATERALIZATION_FACTOR
        sp.verify(balance_as_nat*Constants.PRECISION_FACTOR >=
                  required_balance, message=Errors.NOT_ENOUGH_COLLATERAL)

        minting_fee = token_amount >> Constants.MINTING_FEE_BITSHIFT
        owner_amount = sp.as_nat(token_amount - minting_fee)

        vault_context.value.minted += (token_amount * Constants.PRECISION_FACTOR)/self.data.compound_interest_rate
        self.data.vault_contexts[self.data.sender] = vault_context.value

        Utils.execute_token_mint(self.data.token_contract, self.data.sender, self.data.token_id, owner_amount)
        Utils.execute_token_mint(self.data.token_contract, self.data.reward_pool_contract, self.data.token_id, minting_fee)

        self.data.total_supply += token_amount
        self.update_governance_stake(Stake.make(self.data.sender, market_price_amount.value))

    @sp.entry_point
    def burn(self, token_amount):
        """entrypoint called by a vault owner allows to burn tokens. The actual logic is in "internal_burn".

        Post: fetch_target_price()
        Post: update_accrual()
        Post: storage.sender = sp.sender
        Post: call self.internal_burn

        Args:
            token_amount (sp.nat): token amoun to burn
        """
        sp.set_type(token_amount, sp.TNat)
        self.fetch_target_price(sp.unit)
        self.update_accrual(sp.unit)
        self.data.sender = sp.sender
        sp.transfer(token_amount, sp.mutez(0), sp.self_entry_point('internal_burn'))

    @sp.entry_point
    def internal_burn(self, token_amount):
        """internal entrypoint to burn a certain token amount given the current price and balance of a vault.

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
        self.verify_internal(sp.unit)
        sp.verify(token_amount >= Constants.MIN_TOKEN_AMOUNT_THRESHOLD, message=Errors.AMOUNT_TOO_SMALL)

        vault_context = sp.local("vault_context", self.data.vault_contexts[self.data.sender])

        current_token_amount = sp.local("current_token_amount", (vault_context.value.minted*self.data.compound_interest_rate) / Constants.PRECISION_FACTOR)
        market_price_amount = sp.local("market_price_amount", sp.as_nat(current_token_amount.value - token_amount) * self.data.target_price)
        vault_context.value.minted = sp.as_nat(current_token_amount.value-token_amount) * Constants.PRECISION_FACTOR/self.data.compound_interest_rate
        self.data.vault_contexts[self.data.sender] = vault_context.value

        Utils.execute_token_burn(self.data.token_contract, self.data.sender, self.data.token_id, token_amount)

        self.data.total_supply = sp.as_nat(self.data.total_supply-token_amount)
        self.update_governance_stake(Stake.make(self.data.sender, market_price_amount.value))

    @sp.entry_point
    def liquidate(self, liquidation):
        """ entrypoint that can be called by anyone to liquidate a vault with too little collateral (<2x). The actual logic can be found in internal_liquidate.

        Post: fetch_target_price()
        Post: update_accrual()
        Post: storage.sender = sp.sender
        Post: call self.internal_liquidate

        Args:
            liquidation (Liquidation): liquidation parameter include address and amount to liquidate
        """

        sp.set_type(liquidation, Liquidation.get_type())
        self.fetch_target_price(sp.unit)
        self.update_accrual(sp.unit)
        self.data.sender = sp.sender

        sp.transfer(liquidation, sp.mutez(0), sp.self_entry_point("internal_liquidate"))

    @sp.entry_point
    def internal_liquidate(self, liquidation):
        """internal entrypoint to liquidate a vault back to the target collateralisation level (with a 5% threshold) (3x). Can only be executed if the vault was below
        emergency collateralisation (2x) or the liquidation started and did not manage to get to >target-5%.

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
        self.verify_internal(sp.unit)

        vault_context = sp.local('vault_context', self.data.vault_contexts[liquidation.vault_owner])

        balance_as_nat = sp.local("balance_as_nat", sp.utils.mutez_to_nat(vault_context.value.balance)*Constants.PRECISION_FACTOR)
        current_token_amount = (vault_context.value.minted*self.data.compound_interest_rate)/Constants.PRECISION_FACTOR

        sp.verify((balance_as_nat.value < current_token_amount*self.data.target_price*
                  Constants.EMERGENCY_COLLATERALIZATION_FACTOR) | vault_context.value.is_being_liquidated, message=Errors.NOT_BELOW_EMERGENCY)

        vault_context.value.is_being_liquidated = True

        token_amount_market_value = liquidation.token_amount*self.data.target_price
        liquidation_reward = token_amount_market_value >> Constants.LIQUIDATION_REWARD_BITSHIFT
        liquidation_payout_amount = sp.local('liquidation_payout_amount', (token_amount_market_value + liquidation_reward))
        liquidation_payout_amount_mutez = sp.local('liquidation_payout_amount_mutez', sp.utils.nat_to_mutez(liquidation_payout_amount.value/Constants.PRECISION_FACTOR))
        market_price_amount = sp.local('market_price_amount', sp.as_nat(current_token_amount-liquidation.token_amount) * self.data.target_price)

        sp.verify(sp.as_nat(balance_as_nat.value - liquidation_payout_amount.value) < market_price_amount.value*Constants.TARGET_COLLATERALIZATION_FACTOR, message=Errors.TOO_MUCH_LIQUIDATION)
        sp.verify(liquidation_payout_amount_mutez.value >= Constants.MIN_AMOUNT_THRESHOLD, message=Errors.AMOUNT_TOO_SMALL)

        with sp.if_(sp.as_nat(balance_as_nat.value - liquidation_payout_amount.value)*105 >= market_price_amount.value*Constants.TARGET_COLLATERALIZATION_FACTOR*100):
            vault_context.value.is_being_liquidated = False

        Utils.execute_token_burn(self.data.token_contract, self.data.sender, self.data.token_id, liquidation.token_amount)

        self.data.total_supply = sp.as_nat(self.data.total_supply-liquidation.token_amount)

        vault_context.value.minted = sp.as_nat(current_token_amount-liquidation.token_amount) * Constants.PRECISION_FACTOR/self.data.compound_interest_rate
        vault_context.value.balance -=  liquidation_payout_amount_mutez.value

        self.data.vault_contexts[liquidation.vault_owner] = vault_context.value

        self.update_governance_stake(Stake.make(liquidation.vault_owner, market_price_amount.value))

        withdraw_from_vault = sp.contract(TransferAmount.get_type(), vault_context.value.address, entry_point="withdraw").open_some()
        sp.transfer(TransferAmount.make(self.data.sender, liquidation_payout_amount_mutez.value), sp.mutez(0), withdraw_from_vault)

    @sp.entry_point
    def withdraw(self, amount):
        """entrypoint called by a vault owner allows to withdraw excess collateral. The actual logic is in "internal_withdraw".

        Post: fetch_target_price()
        Post: update_accrual()
        Post: storage.sender = sp.sender
        Post: call self.internal_withdraw

        Args:
            amount (sp.mutez): the mutez amount to withdraw
        """

        sp.set_type(amount, sp.TMutez)
        self.fetch_target_price(sp.unit)
        self.update_accrual(sp.unit)
        self.data.sender = sp.sender

        sp.transfer(amount, sp.mutez(0), sp.self_entry_point("internal_withdraw"))

    @sp.entry_point
    def internal_withdraw(self, amount):
        """internal entrypoint that allows to withdraw excess collateral. Excess collateral is defined as tez amount which is more than the 3x as the compounded minted
        liability.

        Pre: verify_internal()
        Pre: storage.vault_contexts.contains(storage.sender)
        Pre: (storage.vault_contexts[storage.sender].balance-amount)*10**12 >= 3 * storage.target_price * (storage.vault_contexts[liquidation.vault_owner].minted*storage.compound_interest_rate/10**12)
        Post: vault.withdraw(liquidation.vault_owner, amount)

        Args:
            amount (sp.mutez): the mutez amount to withdraw
        """
        sp.set_type(amount, sp.TMutez)
        self.verify_internal(sp.unit)

        vault_context = sp.local("vault_context", self.data.vault_contexts[self.data.sender])

        balance_as_nat = sp.utils.mutez_to_nat(vault_context.value.balance-amount)
        current_token_amount = vault_context.value.minted*self.data.compound_interest_rate

        sp.verify(balance_as_nat*Constants.PRECISION_FACTOR*Constants.PRECISION_FACTOR >= current_token_amount*
                  self.data.target_price*Constants.TARGET_COLLATERALIZATION_FACTOR, message=Errors.NOT_ENOUGH_COLLATERAL)
        vault_context.value.balance -= amount

        self.data.vault_contexts[self.data.sender] = vault_context.value

        withdraw_from_vault = sp.contract(TransferAmount.get_type(), vault_context.value.address, entry_point="withdraw").open_some()
        sp.transfer(TransferAmount.make(self.data.sender, amount), sp.mutez(0), withdraw_from_vault)

    @sp.entry_point
    def settle_with_vault(self, settlement):
        """entrypoint called by the options_contract to execute an intent. The actual logic is in "internal_settle_with_vault".

        Post: fetch_target_price()
        Post: update_accrual()
        Post: storage.sender = sp.sender
        Post: call self.internal_settle_with_vault

        Args:
            settlement (Settlement): the settlement includes the vault_owner, the token_amount and the recipient of the tez
        """
        sp.set_type(settlement, Settlement.get_type())
        self.fetch_target_price(sp.unit)
        self.update_accrual(sp.unit)
        self.data.sender = sp.sender

        sp.transfer(settlement, sp.mutez(0), sp.self_entry_point("internal_settle_with_vault"))

    @sp.entry_point
    def internal_settle_with_vault(self, settlement):
        """internal entrypoint to settle a certain token amount against a vault (at a premium of 6.25%). The tokens are directly burned on the
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
        self.verify_internal(sp.unit)
        sp.verify(self.data.sender == self.data.options_contract,
                  message=Errors.NOT_ADMIN)

        vault_context = sp.local("vault_context", self.data.vault_contexts[settlement.vault_owner])

        market_price_amount = sp.local("market_price_amount", settlement.token_amount*self.data.target_price)
        fee_amount = market_price_amount.value >> Constants.BID_FEE_BITSHIFT
        payout_amount = sp.local("payout_amount", sp.utils.nat_to_mutez(sp.as_nat(market_price_amount.value-fee_amount)/Constants.PRECISION_FACTOR))
        sp.verify(payout_amount.value >= Constants.MIN_AMOUNT_THRESHOLD, message=Errors.AMOUNT_TOO_SMALL)


        current_token_amount = sp.local("current_token_amount", (
            vault_context.value.minted*self.data.compound_interest_rate)/Constants.PRECISION_FACTOR)

        vault_context.value.minted = sp.as_nat(current_token_amount.value-settlement.token_amount) * Constants.PRECISION_FACTOR/self.data.compound_interest_rate
        vault_context.value.balance -= payout_amount.value

        self.data.vault_contexts[settlement.vault_owner] = vault_context.value

        self.update_governance_stake(sp.record(address=settlement.vault_owner, amount=sp.as_nat(current_token_amount.value-settlement.token_amount)*self.data.target_price))

        withdraw_from_vault = sp.contract(TransferAmount.get_type(), vault_context.value.address, entry_point="withdraw").open_some()
        sp.transfer(TransferAmount.make(settlement.recipient, payout_amount.value), sp.mutez(0), withdraw_from_vault)

        Utils.execute_token_burn(self.data.token_contract, self.data.sender, self.data.token_id, settlement.token_amount)
        self.data.total_supply = sp.as_nat(self.data.total_supply-settlement.token_amount)

    @sp.entry_point
    def bailout(self, token_amount):
        """entrypoint called by a vault owner to burn minted tokens from the savings pool at a given premium (25%) over market price. This basically means the
        vault owner who has locked in her/his collateral can unlock it by paying this premium over market price.

        Post: fetch_target_price()
        Post: update_accrual()
        Post: storage.sender = sp.sender
        Post: call savings_pool.bailout
        Post: call self.internal_bailout

        Args:
            token_amount (sp.nat): token amount the vault owner wishes to bail out (cannot be larger than the outstanding liability)
        """
        sp.set_type(token_amount, sp.TNat)
        self.fetch_target_price(sp.unit)
        self.update_accrual(sp.unit)
        self.data.sender = sp.sender

        savings_bailout = sp.contract(sp.TNat, self.data.savings_pool_contract, entry_point="bailout").open_some()
        sp.transfer(token_amount, sp.mutez(0), savings_bailout)
        sp.transfer(token_amount, sp.mutez(0), sp.self_entry_point("internal_bailout"))

    @sp.entry_point
    def internal_bailout(self, token_amount):
        """internal entrypoint to bail out the liability of a given vault at a premium over market price (25%). The liability is taken out of the savings pool.

        Pre: verify_internal()
        Pre: token_amount > 10**9
        Pre: storage.vault_contexts.contains(storage.sender)

        Post: storage.vault_contexts[storage.sender].minted -= settlement.token_amount*10**12/storage.compound_interest_rate
        Post: token.burn(storage.savings_pool_contract, token_amount)
        Post: storage.total_supply -= token_amount

        Post: update_governance_stake(settlement.vault_owner, storage.target_price * ((storage.vault_contexts[storage.sender].minted*storage.compound_interest_rate/10**12)-token_amount))
        Post: vault.withdraw(storage.savings_pool_contract, token_amount*storage.target_price * 1.25/10**12)

        Args:
            token_amount (sp.nat): token amount the vault owner wishes to bail out (cannot be larger than the outstanding liability)
        """
        sp.set_type(token_amount, sp.TNat)
        self.verify_internal(sp.unit)

        vault_context = sp.local("vault_context", self.data.vault_contexts[self.data.sender])

        market_price_amount = sp.local("market_price_amount", token_amount*self.data.target_price)
        fee_amount = market_price_amount.value >> Constants.ASK_FEE_BITSHIFT
        payout_amount = sp.local("payout_amount", sp.utils.nat_to_mutez((market_price_amount.value+fee_amount)/Constants.PRECISION_FACTOR))
        sp.verify(payout_amount.value >= Constants.MIN_AMOUNT_THRESHOLD, message=Errors.AMOUNT_TOO_SMALL)

        current_token_amount = sp.local("current_token_amount", (
            vault_context.value.minted*self.data.compound_interest_rate)/Constants.PRECISION_FACTOR)
        vault_context.value.minted = sp.as_nat(current_token_amount.value-token_amount) * Constants.PRECISION_FACTOR/self.data.compound_interest_rate
        vault_context.value.balance -=  payout_amount.value
        self.data.vault_contexts[self.data.sender] = vault_context.value

        self.update_governance_stake(sp.record(address=self.data.sender, amount=sp.as_nat(current_token_amount.value-token_amount)*self.data.target_price))

        withdraw_from_vault = sp.contract(TransferAmount.get_type(), vault_context.value.address, entry_point="withdraw").open_some()
        sp.transfer(TransferAmount.make(self.data.savings_pool_contract, payout_amount.value), sp.mutez(0), withdraw_from_vault)

        Utils.execute_token_burn(self.data.token_contract, self.data.savings_pool_contract, self.data.token_id, token_amount)
        self.data.total_supply = sp.as_nat(self.data.total_supply-token_amount)

    @sp.entry_point
    def update(self):
        """triggers the contract to update the accrual
        Post: update_accrual()
        """
        self.update_accrual(sp.unit)

if __name__=="__main__":
    from tracker.oracle import DummyOracle
    from tracker.viewer import Viewer
    import tracker.fa2 as fa2
    from tracker.savings_pool import SavingsPool
    from tracker.staking_pool import StakingPool
    from tracker.options_listing import OptionsListing
    from tracker.governance_token import GovernanceToken
    MAXMIMUM_RESPONSE = 1833
    
    @sp.add_test(name="Interest Rate Response")
    def test():
        scenario = sp.test_scenario()
        scenario.add_flag("protocol", "florence")
        scenario.h1("Interest Rate Response Test")
        scenario.table_of_contents()

        scenario.h2("Bootstrapping")
        administrator = sp.test_account("Administrator")
        alice = sp.test_account("Alice")
        bob = sp.test_account("Robert")
        dan = sp.test_account("Dan")
        scenario.h2("Accounts")
        scenario.show([administrator, alice, bob, dan])

        target_oracle = DummyOracle()
        scenario += target_oracle
        observed_oracle = DummyOracle()
        scenario += observed_oracle
        viewer = Viewer()
        scenario += viewer

        token_id = 0

        synth = fa2.AdministrableFA2({fa2.LedgerKey.make(0, administrator.address):sp.unit})
        scenario += synth

        tracker_engine = TrackerEngine(synth.address, sp.nat(0), administrators=sp.big_map({LedgerKey.make(sp.nat(0), administrator.address):sp.unit}))
        scenario += tracker_engine
        scenario += synth.set_administrator(token_id=token_id, administrator_to_set=tracker_engine.address).run(sender=administrator)
        scenario += synth.set_token_metadata(
            sp.record(token_id=token_id, token_info=sp.map())).run(sender=tracker_engine.address)

        scenario.p("Governance Token")
        governance_token = GovernanceToken(tracker_engine.address, {fa2.LedgerKey.make(0, tracker_engine.address):sp.unit})
        scenario += governance_token

        scenario.p("Options Listing")
        options_listing = OptionsListing(synth.address, token_id, tracker_engine.address, target_oracle.address)
        scenario += options_listing

        scenario.p("Reward Pool")
        rewards_pool = StakingPool(tracker_engine.address, governance_token.address, token_id, synth.address, token_id)
        scenario += rewards_pool

        scenario.p("Savings Pool")
        savings_pool = SavingsPool(tracker_engine.address, synth.address, sp.nat(0))
        scenario += savings_pool
        scenario += tracker_engine.set_contracts(target_price_oracle = target_oracle.address, observed_price_oracle = observed_oracle.address, reward_pool_contract = rewards_pool.address, savings_pool_contract = savings_pool.address, governance_token_contract = governance_token.address, options_contract = options_listing.address).run(sender=administrator)

        scenario.h3("Update Interest Rate on track")
        scenario.p("Will fail if called prematurely")
        scenario += tracker_engine.interest_rate_update().run(sender=alice, valid=False)
        now = sp.timestamp(Constants.SECONDS_PER_WEEK)

        scenario.p("Will not change if observed and target are same")
        scenario += tracker_engine.interest_rate_update().run(sender=alice, now=now)
        scenario.verify_equal(tracker_engine.data.reference_interest_rate, Constants.SECONDS_INTEREST_MINIMUM)

        scenario.p("Cannot call in same epoch...")
        scenario += tracker_engine.interest_rate_update().run(sender=alice, now=now, valid=False)

        scenario.h3("Price of synth too low")
        observed_price = 500000 
        now = sp.timestamp(2*Constants.SECONDS_PER_WEEK)
        scenario += observed_oracle.set_price(observed_price)
        
        
        scenario.p("The price of the synth half of what it should be")
        scenario += tracker_engine.interest_rate_update().run(sender=alice, now=now)
        new_reference_interest_rate = Constants.SECONDS_INTEREST_MINIMUM+MAXMIMUM_RESPONSE #1833 is the max response step
        scenario.verify_equal(tracker_engine.data.reference_interest_rate, new_reference_interest_rate)

        responses = {
            760000:1833,
            770000:902,
            800000:902,
            810000:436,
            840000:436,
            850000:203,
            880000:203,
            890000:87,
            920000:87,
            930000:29,
            960000:29,
            970000:0,
            1030000:0,
            1040000:-29,
            1070000:-29,
            1080000:-87,
            1110000:-87,
            1120000:-203,
            1150000:-203,
            1160000:-436,
            1190000:-436,
            1200000:-902,
            1230000:-902,
            1240000:-1833,
        }
        
        for observed_price, value in responses.items():
            scenario.p("The price of the synth is {} %% off target".format((1000000-observed_price)/10000))
            now = now.add_seconds(Constants.SECONDS_PER_WEEK)
            scenario += observed_oracle.set_price(observed_price) 
            scenario += tracker_engine.interest_rate_update().run(sender=alice, now=now)
            new_reference_interest_rate += value 
            scenario.verify_equal(tracker_engine.data.reference_interest_rate, new_reference_interest_rate)

        scenario.p("test minimum interest rate boundary")
        now = now.add_seconds(Constants.SECONDS_PER_WEEK)
        scenario += observed_oracle.set_price(10**20) # super high price
        scenario += tracker_engine.interest_rate_update().run(sender=alice, now=now)
        new_reference_interest_rate += -MAXMIMUM_RESPONSE # max response 
        scenario.verify_equal(tracker_engine.data.reference_interest_rate, new_reference_interest_rate)
        scenario.verify_equal(Constants.SECONDS_INTEREST_MINIMUM, new_reference_interest_rate)
        
        now = now.add_seconds(Constants.SECONDS_PER_WEEK)
        scenario += observed_oracle.set_price(10**20) # super high price
        scenario += tracker_engine.interest_rate_update().run(sender=alice, now=now)
        scenario.verify_equal(tracker_engine.data.reference_interest_rate, Constants.SECONDS_INTEREST_MINIMUM)

        scenario.p("test maximum interest rate boundary")
        while True: 
            now = now.add_seconds(Constants.SECONDS_PER_WEEK)
            scenario += observed_oracle.set_price(0) # super low price
            scenario += tracker_engine.interest_rate_update().run(sender=alice, now=now)
            new_reference_interest_rate += MAXMIMUM_RESPONSE
            scenario.verify_equal(tracker_engine.data.reference_interest_rate, min(new_reference_interest_rate, Constants.SECONDS_INTEREST_MAXIMUM))
            if new_reference_interest_rate >= Constants.SECONDS_INTEREST_MAXIMUM:
                break
        now = now.add_seconds(Constants.SECONDS_PER_WEEK)
        scenario += observed_oracle.set_price(0) # super low price
        scenario += tracker_engine.interest_rate_update().run(sender=alice, now=now)
        scenario.verify_equal(tracker_engine.data.reference_interest_rate, Constants.SECONDS_INTEREST_MAXIMUM)
    
        
        





    @sp.add_test(name="Tracker Engine")
    def test():
        scenario = sp.test_scenario()
        scenario.add_flag("protocol", "florence")
        scenario.h1("Tracker Engine Unit Test")
        scenario.table_of_contents()

        scenario.h2("Bootstrapping")
        administrator = sp.test_account("Administrator")
        alice = sp.test_account("Alice")
        bob = sp.test_account("Robert")
        dan = sp.test_account("Dan")
        scenario.h2("Accounts")
        scenario.show([administrator, alice, bob, dan])

        target_oracle = DummyOracle()
        scenario += target_oracle
        observed_oracle = DummyOracle()
        scenario += observed_oracle
        viewer = Viewer()
        scenario += viewer

        token_id = 0

        synth = fa2.AdministrableFA2({fa2.LedgerKey.make(0, administrator.address):sp.unit})
        scenario += synth

        tracker_engine = TrackerEngine(synth.address, sp.nat(0), administrators=sp.big_map({LedgerKey.make(sp.nat(0), administrator.address):sp.unit}))
        scenario += tracker_engine
        scenario += synth.set_administrator(token_id=token_id, administrator_to_set=tracker_engine.address).run(sender=administrator)
        scenario += synth.set_token_metadata(
            sp.record(token_id=token_id, token_info=sp.map())).run(sender=tracker_engine.address)

        scenario.p("Governance Token")
        governance_token = GovernanceToken(tracker_engine.address, {fa2.LedgerKey.make(0, tracker_engine.address):sp.unit})
        scenario += governance_token

        scenario.p("Options Listing")
        options_listing = OptionsListing(synth.address, token_id, tracker_engine.address, target_oracle.address)
        scenario += options_listing

        scenario.p("Reward Pool")
        rewards_pool = StakingPool(tracker_engine.address, governance_token.address, token_id, synth.address, token_id)
        scenario += rewards_pool

        scenario.p("Savings Pool")
        savings_pool = SavingsPool(tracker_engine.address, synth.address, sp.nat(0))
        scenario += savings_pool
        scenario += tracker_engine.set_contracts(target_price_oracle = target_oracle.address, observed_price_oracle = observed_oracle.address, reward_pool_contract = rewards_pool.address, savings_pool_contract = savings_pool.address, governance_token_contract = governance_token.address, options_contract = options_listing.address).run(sender=administrator)

        scenario.h3("Alice creates Vault")
        return_contract = sp.contract(
            sp.TAddress, viewer.address, entry_point="set_address").open_some()
        scenario += tracker_engine.create_vault(token_id=token_id, baker=sp.some(
            administrator.public_key_hash), contract_address_callback=return_contract).run(sender=alice, amount=sp.tez(100))

        scenario.h3("Mint")
        tokens_to_mint = sp.nat(33*Constants.PRECISION_FACTOR)
        tokens_fee = tokens_to_mint >> Constants.MINTING_FEE_BITSHIFT
        received_tokens = sp.as_nat(tokens_to_mint-tokens_fee)
        scenario += tracker_engine.mint(sp.nat(33*Constants.PRECISION_FACTOR)).run(sender=alice)
        scenario.verify_equal(tracker_engine.data.vault_contexts[alice.address].minted, tokens_to_mint)
        scenario.verify_equal(synth.data.ledger[LedgerKey.make(token_id, alice.address)], received_tokens)
        scenario.verify_equal(synth.data.ledger[LedgerKey.make(token_id, rewards_pool.address)], tokens_fee)

        scenario.h3(
            "Liquidation with no interest rate impact (everything happens at now 0)")
        scenario.p("Transfer Tokens to Bob")
        scenario += synth.transfer([sp.record(from_=alice.address, txs=[
                                                        sp.record(to_=bob.address, amount=received_tokens, token_id=token_id)])]).run(sender=alice)


        scenario.p("Bob liquidates alice in one go")
        tokens_to_liquidate = sp.nat(26*Constants.PRECISION_FACTOR)
        one_token = sp.nat(1*Constants.PRECISION_FACTOR)
        current_price = sp.nat(2000000)
        initial_balance = sp.mutez(100000000)
        scenario += target_oracle.set_price(current_price)
        scenario += tracker_engine.liquidate(vault_owner=alice.address, token_amount=tokens_to_liquidate).run(sender=bob)
        scenario.p("Cannot liquidate more")
        scenario += tracker_engine.liquidate(vault_owner=alice.address,  token_amount=one_token).run(sender=bob, valid=False)

        remaining_tokens_in_vault = sp.as_nat(received_tokens-tokens_to_liquidate)
        liquidation_reward = tokens_to_liquidate>>Constants.LIQUIDATION_REWARD_BITSHIFT
        scenario.verify_equal(tracker_engine.data.vault_contexts[alice.address].minted, sp.as_nat(tokens_to_mint-tokens_to_liquidate))
        scenario.verify_equal(synth.data.ledger[LedgerKey.make(token_id, bob.address)], remaining_tokens_in_vault)

        scenario.h1("Interest Rate Calculations")
        scenario.h3("Phase 1")
        minted_t0 = 7000000000000
        now = sp.timestamp(Constants.SECONDS_PER_WEEK)
        scenario += tracker_engine.update().run(now=now)

        minted_t1 = minted_t0*(tracker_engine.data.compound_interest_rate)/Constants.PRECISION_FACTOR
        asset_accrual = minted_t0*(tracker_engine.data.reference_interest_rate*Constants.SECONDS_PER_WEEK)//Constants.PRECISION_FACTOR
        spread_accrual = minted_t0*(Constants.SECONDS_INTEREST_SPREAD*Constants.SECONDS_PER_WEEK)//Constants.PRECISION_FACTOR+tokens_fee

        scenario.verify_equal(minted_t1, tracker_engine.data.total_supply)
        scenario.verify_equal(asset_accrual, synth.data.ledger[LedgerKey.make(token_id, savings_pool.address)])
        scenario.verify_equal(spread_accrual, synth.data.ledger[LedgerKey.make(token_id, rewards_pool.address)])


        scenario.h3("Phase 2")
        now = sp.timestamp(Constants.SECONDS_PER_WEEK*2)
        scenario += tracker_engine.update().run(now=now)

        minted_t2 = minted_t0*(tracker_engine.data.compound_interest_rate)/Constants.PRECISION_FACTOR
        asset_accrual += minted_t1*(tracker_engine.data.reference_interest_rate*Constants.SECONDS_PER_WEEK)//Constants.PRECISION_FACTOR
        spread_accrual += minted_t1*(Constants.SECONDS_INTEREST_SPREAD*Constants.SECONDS_PER_WEEK)//Constants.PRECISION_FACTOR
        scenario.show(minted_t2)
        scenario.show(asset_accrual)
        scenario.show(spread_accrual)
        #scenario.verify_equal(minted_t2, tracker_engine.data.total_supply)
        #scenario.verify_equal(asset_accrual, synth.data.ledger[LedgerKey.make(token_id, savings_pool.address)])
        #scenario.verify_equal(spread_accrual, synth.data.ledger[LedgerKey.make(token_id, rewards_pool.address)])

        scenario.h1("Bailout")
        scenario.p("Bob joins the savings pool")
        scenario += synth.update_operators([sp.variant("add_operator", sp.record(
            owner=bob.address,
            operator=savings_pool.address,
            token_id=token_id
        ))]).run(sender=bob, now=now)
        scenario += savings_pool.deposit(Constants.PRECISION_FACTOR).run(sender=bob, now=now)
        scenario.p("Alice bails out")
        scenario += tracker_engine.bailout(Constants.PRECISION_FACTOR).run(sender=alice, now=now)

        scenario.h1("Options settlement")
        scenario.p("Bob advertises intent")
        scenario += synth.update_operators([sp.variant("add_operator", sp.record(
            owner=bob.address,
            operator=options_listing.address,
            token_id=token_id
        ))]).run(sender=bob, now=now)

        scenario += options_listing.advertise_intent(Constants.PRECISION_FACTOR).run(sender=bob, now=now)
        now = sp.timestamp(Constants.SECONDS_PER_WEEK*2+24*60*60)
        scenario += options_listing.execute_intent(address=alice.address, token_amount=Constants.PRECISION_FACTOR).run(sender=bob, now=now)

       #scenario.verify_equal(interest_rate.data.spread_accrual+interest_rate.data.asset_accrual, sp.as_nat((interest_rate.data.compound_interest_rate*1999373212485/PRECISION_FACTOR)-1*PRECISION_FACTOR))
#        3'880'325'421'007
#          940'770'936'000

#                   1941'495'255'943'84 # corrected liability
#                    941'084'526'312'000 # accrued liability
#            1'881'148'7'64

#            1.9993732125
#1'000.373212485 * 1940770936000

#
# 3193817455761
# 2194505003376


#    2508722496
#    2508132832
#  1.0002351008
#    3135903120
#    3135116902
#
