import smartpy as sp

import utils.constants as Constants
import utils.error_codes as Errors
import utils.fa2 as fa2

from utils.contract_utils import Utils
from utils.internal_mixin import InternalMixin
from utils.administrable_mixin import SingleAdministrableMixin


class LongStakingPool(sp.Contract, InternalMixin, SingleAdministrableMixin):
    """The long staking pool contract follows the same distribution logic as the staking pool. The big difference lies in the release of said rewards. During
    max_release_period the rewards are being distributed linearly. The intuition is that long-term staking is rewarded more that short-term.

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

        storage["total_stake"] = sp.nat(0)

        storage["max_release_period"] = self.max_release_period

        storage["stakes"] = sp.big_map(
            tkey=sp.TAddress,
            tvalue=sp.TRecord(
                stake=sp.TNat, dist_factor=sp.TNat, age_timestamp=sp.TTimestamp
            ),
        )
        storage["dist_factor"] = sp.nat(0)

        storage["reward_token_address"] = self.reward_token_address
        storage["reward_token_id"] = self.reward_token_id

        storage["stake_token_address"] = self.stake_token_address
        storage["stake_token_id"] = self.stake_token_id

        storage["sender"] = Constants.DEFAULT_ADDRESS

        storage["last_reward_balance"] = sp.nat(0)
        storage["current_reward_balance"] = sp.nat(0)
        storage["administrators"] = sp.set_type_expr(
            self.administrators, sp.TBigMap(sp.TAddress, sp.TNat)
        )

        return storage

    def __init__(
        self,
        stake_token_address,
        stake_token_id,
        stake_token_type,
        reward_token_address,
        reward_token_id,
        max_release_period=180 * 24 * 60 * 60,
        administrators=sp.big_map({}),
    ):
        """takes as arguments the engine address (used to call the update function) as well as the staking and reward token.

        Args:
            stake_token_address (sp.address): the token to be staked
            stake_token_id (sp.nat): the token to be staked
            stake_token_type (string): used to at compile time include the right transfer logic, this can be Constants.TOKEN_TYPE_FA1 or Constants.TOKEN_TYPE_FA2
            reward_token_address (sp.address): the token to be rewarded
            reward_token_id (sp.nat): the token to be rewarded
            max_release_period (sp.nat): the time on which the rewards are linearly unlocked
        """
        self.reward_token_address = reward_token_address
        self.reward_token_id = reward_token_id
        self.stake_token_type = stake_token_type
        self.stake_token_address = stake_token_address
        self.stake_token_id = stake_token_id
        self.administrators = administrators
        self.max_release_period = max_release_period
        self.init(**self.get_init_storage())

    @sp.private_lambda(with_storage="read-only", with_operations=True, wrap_call=True)
    def fetch_reward_balance(self, unit):
        """sub entrypoint which triggers a own token balance fetch to be set using the callback on the "set_balance" entrypoint.
        The order is reversed because in sub entrypoints the operation stack returned is processed as a stack (execute_update is processed before).

        Post: get token balance
        Args:
            unit (sp.unit): nothing
        """
        Utils.execute_get_own_balance(
            self.data.reward_token_address,
            self.data.reward_token_id,
            "set_reward_balance",
        )

    @sp.private_lambda(with_storage="read-write", with_operations=False, wrap_call=True)
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
                reward * Constants.PRECISION_FACTOR // self.data.total_stake
            )
            self.data.last_reward_balance = self.data.current_reward_balance

    @sp.private_lambda(with_storage="read-write", with_operations=True, wrap_call=True)
    def sub_claim(self, unit):
        """sub entrypoint which claims the rewards for the sender stored in "sender". This means this can only be called by "internal_" entrypoints where
        the sender is set correctly. This sub-claim also contains the logic of linear release. Based on the stake age a fraction of the reward is
        released to the sender, the rest is redistributed among the other pool participants.

        Args:
            unit (sp.unit): nothing
        """
        with sp.if_(self.data.stakes.contains(self.data.sender)):
            stake = sp.local("stake", self.data.stakes[self.data.sender])
            stake_age = sp.min(
                sp.as_nat(sp.now - stake.value.age_timestamp),
                self.data.max_release_period,
            )

            reward_token_amount = sp.local(
                "reward_token_amount",
                stake.value.stake
                * sp.as_nat(self.data.dist_factor - stake.value.dist_factor)
                // Constants.PRECISION_FACTOR,
            )
            timed_reward_token_amount = sp.local(
                "timed_reward_token_amount",
                reward_token_amount.value * stake_age // self.data.max_release_period,
            )

            Utils.execute_fa2_token_transfer(
                self.data.reward_token_address,
                sp.self_address,
                sp.self_address,
                self.data.reward_token_id,
                sp.as_nat(reward_token_amount.value - timed_reward_token_amount.value),
            )  # this self-transfer is just for indexing purposes and not required for functionality. It can be removed if gas matters.
            Utils.execute_fa2_token_transfer(
                self.data.reward_token_address,
                sp.self_address,
                self.data.sender,
                self.data.reward_token_id,
                timed_reward_token_amount.value,
            )

            self.data.last_reward_balance = sp.as_nat(
                self.data.last_reward_balance - reward_token_amount.value
            )
            self.data.stakes[self.data.sender].dist_factor = self.data.dist_factor

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
    def set_max_release_period(self, new_max_release_period):
        """Only an existing admin can call this entrypoint. This sets the the max_release_period for the contract.
        Pre: verify_is_admin(token_id)

        Args:
            new_max_release_period(sp.nat): the new max_release_period
        """
        sp.set_type(new_max_release_period, sp.TNat)
        self.verify_is_admin()
        self.data.max_release_period = new_max_release_period

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
        """internal entrypoint to deposit a certain token amount to the contract and calculate the stake and distribution factor. This method also allows
        for increasing an existing deposit. Since an increase in deposit affects also the age, what happens is that based on the age and weight of the existing stake the
        new age is calculated, such that there is no difference if you would have 2 seperate stakes on this aggregated one.

        Args:
            token_amount (sp.nat): the amount of tokens
        """
        self.verify_internal(sp.unit)
        self.sub_distribute(sp.unit)

        if self.stake_token_type == Constants.TOKEN_TYPE_FA2:
            Utils.execute_fa2_token_transfer(
                self.data.stake_token_address,
                self.data.sender,
                sp.self_address,
                self.data.stake_token_id,
                token_amount,
            )
        elif self.stake_token_type == Constants.TOKEN_TYPE_FA1:
            Utils.execute_fa1_token_transfer(
                self.data.stake_token_address,
                self.data.sender,
                sp.self_address,
                token_amount,
            )

        with sp.if_(self.data.stakes.contains(self.data.sender)):
            stake = sp.local("stake", self.data.stakes[self.data.sender])
            stake_age = sp.min(
                sp.as_nat(sp.now - stake.value.age_timestamp),
                self.data.max_release_period,
            )  # for calculations can never be older than max_release
            sender_dist_factor = stake.value.dist_factor
            current_reward_token_amount = sp.local(
                "current_reward_token_amount",
                stake.value.stake
                * sp.as_nat(self.data.dist_factor - sender_dist_factor)
                // Constants.PRECISION_FACTOR,
            )

            new_stake = stake.value.stake + token_amount
            new_sender_dist_factor = sp.local(
                "new_sender_dist_factor",
                sp.as_nat(
                    self.data.dist_factor
                    - current_reward_token_amount.value
                    * Constants.PRECISION_FACTOR
                    // new_stake
                ),
            )
            new_age_timestamp = sp.now.add_seconds(
                -1 * sp.to_int((stake.value.stake * stake_age // new_stake))
            )  # this is negative addition == substraction because no "remove_seconds" exists in smartpy

            self.data.stakes[self.data.sender] = sp.record(
                stake=new_stake,
                dist_factor=new_sender_dist_factor.value,
                age_timestamp=new_age_timestamp,
            )
        with sp.else_():
            self.data.stakes[self.data.sender] = sp.record(
                stake=token_amount,
                dist_factor=self.data.dist_factor,
                age_timestamp=sp.now,
            )
        self.data.total_stake += token_amount

    @sp.entry_point(check_no_incoming_transfer=True)
    def claim(self):
        """external entrypoint for a user to claim her/his rewards. The actual logic is in internal_claim.

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
        """
        self.verify_internal(sp.unit)
        self.sub_distribute(sp.unit)
        self.sub_claim(sp.unit)

        stake = sp.local("stake", self.data.stakes[self.data.sender])
        if self.stake_token_type == Constants.TOKEN_TYPE_FA2:
            Utils.execute_fa2_token_transfer(
                self.data.stake_token_address,
                sp.self_address,
                self.data.sender,
                self.data.stake_token_id,
                stake.value.stake,
            )
        elif self.stake_token_type == Constants.TOKEN_TYPE_FA1:
            Utils.execute_fa1_token_transfer(
                self.data.stake_token_address,
                sp.self_address,
                self.data.sender,
                stake.value.stake,
            )
        self.data.total_stake = sp.as_nat(self.data.total_stake - stake.value.stake)
        del self.data.stakes[self.data.sender]
