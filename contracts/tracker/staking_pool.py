import smartpy as sp

import utils.constants as Constants
import utils.error_codes as Errors 
import utils.fa2 as fa2
import utils.error_codes as Errors

from utils.contract_utils import Utils
from utils.internal_mixin import InternalMixin


class StakingPool(sp.Contract, InternalMixin):
    """The staking pool contract allows users to stake a token and then receive rewards in another token. This means that the stake remains always the same regardless of the
    rewards. It's using the same distribution method with "distribution_factors" like the governance token contract and the savings pool contract for the tez distribution.

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

        storage["dist_factors"] = sp.big_map(tkey=sp.TAddress, tvalue=sp.TNat)
        storage["total_stake"] = sp.nat(0)
        storage["stakes"] = sp.big_map(tkey=sp.TAddress, tvalue=sp.TNat)
        storage["dist_factor"] = sp.nat(0)

        storage["reward_token_address"] = self.reward_token_address
        storage["reward_token_id"] = self.reward_token_id

        storage["stake_token_address"] = self.stake_token_address
        storage["stake_token_id"] = self.stake_token_id

        storage["engine_address"] = self.engine_address
        storage["sender"] = Constants.DEFAULT_ADDRESS

        storage["last_reward_balance"] = sp.nat(0)
        storage["current_reward_balance"] = sp.nat(0)

        return storage

    def __init__(
        self,
        engine_address,
        stake_token_address,
        stake_token_id,
        reward_token_address,
        reward_token_id,
    ):
        """takes as arguments the engine address (used to call the update function) as well as the staking and reward token.

        Args:
            engine_address (sp.address): the engine address used to call the update function
            stake_token_address (sp.address): the token to be staked
            stake_token_id (sp.nat): the token to be staked
            reward_token_address (sp.address): the token to be rewarded
            reward_token_id (sp.nat): the token to be rewarded
        """
        self.engine_address = engine_address
        self.reward_token_address = reward_token_address
        self.reward_token_id = reward_token_id
        self.stake_token_address = stake_token_address
        self.stake_token_id = stake_token_id
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
        Utils.execute_update(self.data.engine_address)
        Utils.execute_get_own_balance(
            self.data.reward_token_address,
            self.data.reward_token_id,
            "set_reward_balance",
        )

    @sp.private_lambda(with_storage="read-write", with_operations=True, wrap_call=True)
    def sub_distribute(self, unit):
        """sub entrypoint which updates the discount factor based on the received reward.

        Pre: storage.total_stake > 0
        Post: storage.dist_factor += ((storage.current_reward_balance - storage.last_reward_balance)*10**12)/storage.total_stake
        Post: storage.last_reward_balance = storage.current_reward_balance

        Args:
            unit (sp.unit): nothing
        """
        with sp.if_(self.data.total_stake > 0):
            reward = sp.as_nat(
                self.data.current_reward_balance - self.data.last_reward_balance
            )
            self.data.dist_factor += (
                reward * Constants.PRECISION_FACTOR / self.data.total_stake
            )
            self.data.last_reward_balance = self.data.current_reward_balance

    @sp.private_lambda(with_storage="read-write", with_operations=True, wrap_call=True)
    def sub_claim(self, unit):
        """sub entrypoint which claims the rewards for the sender stored in "sender". This means this can only be called by "internal_" entrypoints where
        the sender is set correctly.

        Pre: storage.stakes[storage.sender] > 0
        Post: transfer reward tokens from self_address to storage.sender
        Post: storage.last_reward_balance -= storage.stakes[storage.sender] * (storage.dist_factor-self.data.dist_factors[self.data.sender])/10**12
        Post: storage.dist_factors[storage.sender] = storage.current_reward_balance

        Args:
            unit (sp.unit): nothing
        """
        with sp.if_(self.data.stakes.contains(self.data.sender)):
            reward_token_amount = sp.local(
                "reward_token_amount",
                self.data.stakes[self.data.sender]
                * sp.as_nat(
                    self.data.dist_factor - self.data.dist_factors[self.data.sender]
                )
                / Constants.PRECISION_FACTOR,
            )
            Utils.execute_fa2_token_transfer(
                self.data.reward_token_address,
                sp.self_address,
                self.data.sender,
                self.data.reward_token_id,
                reward_token_amount.value,
            )

            self.data.last_reward_balance = sp.as_nat(
                self.data.last_reward_balance - reward_token_amount.value
            )
            self.data.dist_factors[self.data.sender] = self.data.dist_factor

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_reward_balance(self, balance_of_response):
        """called by the token contract to set the apropriate balance.

        Args:
            balance_of_response (sp.nat): fa2 balance_of response used to set the current_reward_balance
        """
        sp.set_type(balance_of_response, fa2.BalanceOf.get_response_type())
        sp.verify(sp.sender == self.data.reward_token_address, message=Errors.INVALID_SENDER)
        with sp.match_cons(balance_of_response) as matched_balance_of_response:
            sp.verify(
                matched_balance_of_response.head.request.owner == sp.self_address,
                message=Errors.INVALID_BALANCE_REQUEST,
            )
            self.data.current_reward_balance = matched_balance_of_response.head.balance

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

        Pre: verify_internal()
        Post: sub_distribute()
        Post: sub_claim()
        Post: transfer token_amount tokens fron sp.sender to sp.self_address
        Post: storage.stakes[storage.sender] += token_amount
        Post: storage.dist_factors[storage.sender] = self.data.dist_factor
        Post: storage.total_stake += token_amount

        Args:
            token_amount (sp.nat): the amount of tokens
        """
        self.verify_internal(sp.unit)
        self.sub_distribute(sp.unit)
        self.sub_claim(sp.unit)

        Utils.execute_fa2_token_transfer(
            self.data.stake_token_address,
            self.data.sender,
            sp.self_address,
            self.data.stake_token_id,
            token_amount,
        )
        self.data.dist_factors[self.data.sender] = self.data.dist_factor
        with sp.if_(self.data.stakes.contains(self.data.sender)):
            self.data.stakes[self.data.sender] += token_amount
        with sp.else_():
            self.data.stakes[self.data.sender] = token_amount
        self.data.total_stake += token_amount

    @sp.entry_point(check_no_incoming_transfer=True)
    def claim(self):
        """external entrypoint for a user to claim her/his rewards. The actual logic is in internal_deposit.

        Post: storage.sender = sp.sender
        Post: fetch_reward_balance()
        Post: calls self.internal_claim
        """
        self.data.sender = sp.sender
        self.fetch_reward_balance(sp.unit)
        sp.transfer(sp.unit, sp.mutez(0), sp.self_entry_point("internal_claim"))

    @sp.entry_point(check_no_incoming_transfer=True)
    def internal_claim(self):
        """internal entrypoint to claim a senders rewards.

        Pre: verify_internal()
        Post: sub_distribute()
        Post: sub_claim()
        """
        self.verify_internal(sp.unit)
        self.sub_distribute(sp.unit)
        self.sub_claim(sp.unit)

    @sp.entry_point(check_no_incoming_transfer=True)
    def withdraw(self):
        """external entrypoint for a user to claim her/his rewards and withdraw her/his stake. The actual logic is in internal_withdraw.

        Post: storage.sender = sp.sender
        Post: fetch_reward_balance()
        Post: calls self.internal_withdraw
        """
        self.data.sender = sp.sender
        self.fetch_reward_balance(sp.unit)
        sp.transfer(sp.unit, sp.mutez(0), sp.self_entry_point("internal_withdraw"))

    @sp.entry_point(check_no_incoming_transfer=True)
    def internal_withdraw(self):
        """internal entrypoint to claim a senders rewards and withdraw the stake.

        Pre: verify_internal()
        Post: sub_distribute()
        Post: sub_claim()
        Post: transfer token_amount tokens fron sp.self_address to sp.sender
        Post: storage.total_stake -= storage.stakes[storage.sender]
        Post: del storage.stakes[storage.sender]
        Post: del storage.dist_factors[storage.sender]
        """
        self.verify_internal(sp.unit)
        self.sub_distribute(sp.unit)
        self.sub_claim(sp.unit)

        stake = sp.local("stake", self.data.stakes[self.data.sender])
        Utils.execute_fa2_token_transfer(
            self.data.stake_token_address,
            sp.self_address,
            self.data.sender,
            self.data.stake_token_id,
            stake.value,
        )
        self.data.total_stake = sp.as_nat(self.data.total_stake - stake.value)
        del self.data.stakes[self.data.sender]
        del self.data.dist_factors[self.data.sender]

    @sp.entry_point(check_no_incoming_transfer=True)
    def default(self, unit):
        sp.set_type(unit, sp.TUnit)
