import smartpy as sp

import utils.constants as Constants
import utils.error_codes as Errors
import utils.fa2 as fa2

from utils.contract_utils import Utils
from utils.internal_mixin import InternalMixin

import contracts.tracker.vester as vester


class SavingsPool(sp.Contract, InternalMixin, fa2.AdministrableMixin):
    """The savings pool allows a user to lock their tokens and then get a reward on the same token type like was locked. This means that there are compounding
    effects and we cannot "simply" use the method used in "StakingPool". 

    Args:
        (sp.Contract): this is a smartpy contract
        (InternalMixin): mixin used whenever we need external data and hence have to trigger an internal call (to process after we received said external data)
    """

    def get_init_storage(self):
        """Returns the initial storage of the contract used for inheritance of smartpy contracts

        Returns:
            dict: initial storage of the contract
        """
        storage = {}

        storage["total_stake"] = sp.nat(0)  # total stake
        storage["disc_factor"] = sp.nat(Constants.PRECISION_FACTOR)
        storage["dist_factor"] = sp.nat(0)

        storage["dist_factors"] = sp.big_map(tkey=sp.TAddress, tvalue=sp.TNat)
        storage["stakes"] = sp.big_map(tkey=sp.TAddress, tvalue=sp.TNat)

        storage["token_address"] = self.token_address
        storage["token_id"] = self.token_id

        storage["sender"] = Constants.DEFAULT_ADDRESS

        storage["last_balance"] = sp.nat(0)
        storage["current_balance"] = sp.nat(0)

        storage["vesting_contract"] = Constants.DEFAULT_ADDRESS
        storage["vesting_duration_in_seconds"] = sp.nat(0)
        storage["administrators"] = sp.big_map(
            l=self.administrators, tkey=fa2.LedgerKey.get_type(), tvalue=sp.TUnit
        )

        return storage

    def __init__(self, token_address, token_id, administrators):
        """specifies the token used for staking and the administrators.

        Args:
            token_address (sp.address): token address
            token_id (sp.nat): token id
        """
        self.token_address = token_address
        self.token_id = token_id
        self.administrators = administrators
        self.init(**self.get_init_storage())

    @sp.private_lambda(with_storage="read-write", with_operations=True, wrap_call=True)
    def fetch_reward_balance(self, unit):
        """sub entrypoint which triggers a own token balance fetch to be set using the callback on the "set_balance" entrypoint.
        Furthermore this sub entrypoint calls the update function on the engine such that if a new accrual happened we get it.
        The order is reversed because in sub entrypoints the operation stack returned is processed as a stack (execute_update is processed before).

        Post: get token balance
        Post: call update on engine
        Args:
            unit (sp.unit): nothing
        """
        Utils.execute_get_own_balance(
            self.data.token_address, self.data.token_id, "set_balance"
        )

    @sp.private_lambda(with_storage="read-write", with_operations=True, wrap_call=True)
    def sub_update_factor(self, unit):
        """sub entrypoint which updates the discount factor based on the received reward.

        Pre: storage.total_stake > 0
        Post: storage.last_balance = storage.current_balance
        Post: storage.disc_fator += ((storage.current_balance - storage.last_balance)*10**12)/storage.total_stake

        Args:
            unit (sp.unit): nothing
        """
        with sp.if_(self.data.total_stake > 0):
            reward = sp.as_nat(self.data.current_balance - self.data.last_balance)
            self.data.disc_factor += (
                reward * Constants.PRECISION_FACTOR / self.data.total_stake
            )
            self.data.last_balance = self.data.current_balance

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_balance(self, balance_of_response):
        """called by the token contract to set the apropriate balance.

        Args:
            balance_of_response (sp.nat): fa2 balance_of response used to set the current_balance
        """
        sp.set_type(balance_of_response, fa2.BalanceOf.get_response_type())
        sp.verify(sp.sender == self.data.token_address, message=Errors.INVALID_SENDER)
        with sp.match_cons(balance_of_response) as matched_balance_of_response:
            sp.verify(
                matched_balance_of_response.head.request.owner == sp.self_address,
                message=Errors.INVALID_BALANCE_REQUEST,
            )
            self.data.current_balance = matched_balance_of_response.head.balance

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
        self.data.sender = sp.sender
        self.fetch_reward_balance(sp.unit)
        sp.transfer(token_amount, sp.mutez(0), sp.self_entry_point("internal_deposit"))

    @sp.entry_point(check_no_incoming_transfer=True)
    def internal_deposit(self, token_amount):
        """internal entrypoint to deposit a certain token amount to the contract and calculate the stake and distribution factor.
        The stakes are discounted to the t=0 point in time, such that we store for every participant the t=0 stake. Also if the
        participant is ellegible for a tez distribution this call will send the ellegible amount to the sender.

        Pre: verify_internal()
        Post: sub_update_factor()
        Post: transfer token_amount tokens fron sp.sender to sp.self_address
        Post: storage.stakes[storage.sender] += token_amount*10**12/storage.disc_factor
        Post: send (storage.stakes[storage.sender]*storage.dist_factor - storage.dist_factors[storage.sender])/10**12) to storage.sender
        Post: storage.dist_factors[storage.sender] = self.data.dist_factor
        Post: storage.last_balance += token_amount
        Post: storage.total_stake += token_amount*10**12/storage.disc_factor
        Args:
            token_amount (sp.nat): the amount of tokens
        """
        sp.set_type(token_amount, sp.TNat)
        self.verify_internal(sp.unit)
        self.sub_update_factor(sp.unit)

        Utils.execute_fa2_token_transfer(
            self.data.token_address,
            self.data.sender,
            sp.self_address,
            self.data.token_id,
            token_amount,
        )

        discounted_amount = sp.local(
            "discounted_amount",
            token_amount * Constants.PRECISION_FACTOR / self.data.disc_factor,
        )

        with sp.if_(
            self.data.dist_factors.contains(self.data.sender)
            & (self.data.dist_factors[self.data.sender] < self.data.dist_factor)
        ):
            ellegible_amount = (
                self.data.stakes[self.data.sender]
                * sp.as_nat(
                    self.data.dist_factor - self.data.dist_factors[self.data.sender]
                )
                / Constants.PRECISION_FACTOR
            )
            with sp.if_(ellegible_amount > 0):
                sp.send(self.data.sender, sp.utils.nat_to_mutez(ellegible_amount))
        with sp.if_(self.data.stakes.contains(self.data.sender)):
            self.data.stakes[self.data.sender] += discounted_amount.value
        with sp.else_():
            self.data.stakes[self.data.sender] = discounted_amount.value

        self.data.dist_factors[self.data.sender] = self.data.dist_factor
        self.data.total_stake += discounted_amount.value
        self.data.last_balance += token_amount

    @sp.entry_point(check_no_incoming_transfer=True)
    def withdraw(self):
        """withdraws the total stake and reward, if there was a tez payout that as well. The actual logic is in internal_withdraw.

        Post: storage.sender = sp.sender
        Post: fetch_reward_balance()
        Post: calls self.internal_withdraw
        """
        self.data.sender = sp.sender
        self.fetch_reward_balance(sp.unit)
        sp.transfer(sp.unit, sp.mutez(0), sp.self_entry_point("internal_withdraw"))

    @sp.entry_point(check_no_incoming_transfer=True)
    def internal_withdraw(self):
        """internal entrypoint to withdraw the own stake and any distributed tez reward the user is ellegible to receive.
        Pre: verify_internal()
        Pre: storage.stake.contains(storage.sender)
        Post: sub_update_factor()
        Post: transfer token_amount tokens fron sp.self_address to sp.sender
        Post: send (storage.stakes[storage.sender]*storage.dist_factor - storage.dist_factors[storage.sender])/10**12) to storage.sender
        Post: storage.last_balance -= storage.stakes[storage.sender]*storage.disc_factor/10**12
        Post: storage.total_stake -= storage.stakes[storage.sender]
        Post: del storage.stakes[storage.sender]
        Post: del storage.dist_factors[storage.sender]
        """
        self.verify_internal(sp.unit)
        sp.verify(
            self.data.vesting_contract != Constants.DEFAULT_ADDRESS,
            message=Errors.NO_VESTER_SET,
        )
        self.sub_update_factor(sp.unit)

        current_amount = sp.local(
            "current_amount",
            self.data.stakes[self.data.sender]
            * self.data.disc_factor
            / Constants.PRECISION_FACTOR,
        )

        # Send it to the vesting contract.
        vest_entry_point = sp.contract(
            vester.VestingOperation.get_batch_type(),
            self.data.vesting_contract,
            entry_point="vest",
        ).open_some()
        deadline = sp.local(
            "deadline",
            sp.now.add_seconds(sp.to_int(self.data.vesting_duration_in_seconds)),
        )
        vest_payload = [
            vester.VestingOperation.make(
                self.data.sender, current_amount.value, deadline.value
            )
        ]
        sp.transfer(vest_payload, sp.mutez(0), vest_entry_point)

        with sp.if_(self.data.dist_factors[self.data.sender] < self.data.dist_factor):
            ellegible_amount = (
                self.data.stakes[self.data.sender]
                * sp.as_nat(
                    self.data.dist_factor - self.data.dist_factors[self.data.sender]
                )
                / Constants.PRECISION_FACTOR
            )
            sp.send(self.data.sender, sp.utils.nat_to_mutez(ellegible_amount))

        self.data.last_balance = sp.as_nat(
            self.data.last_balance - current_amount.value
        )
        self.data.total_stake = sp.as_nat(
            self.data.total_stake - self.data.stakes[self.data.sender]
        )

        del self.data.stakes[self.data.sender]
        del self.data.dist_factors[self.data.sender]

    @sp.entry_point
    def default(self):
        """entrypoint used to accept tez payments. Will distribute these evenly among the pool using the dist_factor methodology.
        Pre: storage.total_stake > 0
        Post: storage.dist_factor += sp.amount*10**12/storage.total_stake
        """
        self.data.dist_factor += (
            sp.utils.mutez_to_nat(sp.amount)
            * Constants.PRECISION_FACTOR
            // self.data.total_stake
        )

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_vesting_contract(self, params):
        sp.set_type(
            params,
            sp.TRecord(contract=sp.TAddress, duration_in_seconds=sp.TNat).layout(
                ("contract", "duration_in_seconds")
            ),
        )
        self.verify_is_admin(self.data.token_id)

        self.data.vesting_contract = params.contract
        self.data.vesting_duration_in_seconds = params.duration_in_seconds

        update_operators_payload = [
            sp.variant(
                "add_operator",
                sp.record(
                    owner=sp.self_address,
                    operator=params.contract,
                    token_id=self.data.token_id,
                ),
            )
        ]
        update_operators_token_contract = sp.contract(
            fa2.UpdateOperator.get_batch_type(),
            self.data.token_address,
            entry_point="update_operators",
        ).open_some()
        sp.transfer(
            update_operators_payload, sp.mutez(0), update_operators_token_contract
        )
