import smartpy as sp

import utils.constants as Constants
import utils.fa2 as fa2

from utils.contract_utils import Utils
from contracts.tracker.governance_token import Stake


class LiquidityFarm(sp.Contract, fa2.AdministrableMixin):
    """The Liquidity Farm will allow people to lock up FA2 "stake tokens" i.e. LP tokens and in return they receive a "weight" in the governance token distribution.
    The weight is determined by the amount of LP tokens and the 'incentive' factor.

    Args:
        (sp.Contract): this is a smartpy contract
    """

    def get_init_storage(self):
        """Returns the initial storage of the contract used for inheritance of smartpy contracts

        Returns:
            dict: initial storage of the contract
        """
        storage = {}

        storage["stakes"] = sp.big_map(tkey=sp.TAddress, tvalue=sp.TNat)
        storage["incentive_factor"] = sp.nat(Constants.PRECISION_FACTOR)

        storage["stake_token_address"] = self.stake_token_address
        storage["stake_token_id"] = self.stake_token_id

        storage["stake_manager_address"] = self.stake_manager_address

        storage["administrators"] = sp.set_type_expr(
            self.administrators, sp.TMap(fa2.LedgerKey.get_type(), sp.TUnit)
        )

        return storage

    def __init__(
        self, stake_token_address, stake_token_id, stake_manager_address, administrators
    ):
        """ """

        self.stake_token_address = stake_token_address
        self.stake_token_id = stake_token_id
        self.stake_manager_address = stake_manager_address
        self.administrators = administrators

        self.init(**self.get_init_storage())

    @sp.private_lambda(with_storage="read-write", with_operations=True, wrap_call=True)
    def update_stake(self, stake):
        """sub entrypoint to call "update_stake" on the stake manager contract

        Post: stake_manager.update_stake(stake)

        Args:
            stake (Stake): Address and amount
        """
        sp.set_type(stake, Stake.get_type())
        stake_manager_contract = sp.contract(
            Stake.get_type(),
            self.data.stake_manager_address,
            entry_point="update_stake",
        ).open_some()
        sp.transfer(stake, sp.mutez(0), stake_manager_contract)

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_incentive_factor(self, incentive_factor):
        """entrypoint to set the incentive factor used for the weight calculation. Only admin can call this

        Args:
            incentive_factor (sp.nat): the new incentive factor
        """
        sp.set_type(incentive_factor, sp.TNat)

        self.verify_is_admin(Constants.DEFAULT_TOKEN_ID)
        self.data.incentive_factor = incentive_factor

    @sp.entry_point(check_no_incoming_transfer=True)
    def deposit(self, token_amount):
        """external entrypoint to deposit a certain amount of tokens (requires you to have called update_operators to allow this contract first).

        token_amount (sp.nat): the amount of tokens
        """
        sp.set_type(token_amount, sp.TNat)

        Utils.execute_fa2_token_transfer(
            self.data.stake_token_address,
            sp.sender,
            sp.self_address,
            self.data.stake_token_id,
            token_amount,
        )

        with sp.if_(self.data.stakes.contains(sp.sender)):
            self.data.stakes[sp.sender] += token_amount
        with sp.else_():
            self.data.stakes[sp.sender] = token_amount

        self.update_stake(
            Stake.make(
                sp.sender,
                self.data.stakes[sp.sender]
                * self.data.incentive_factor
                / Constants.PRECISION_FACTOR,
            )
        )

    @sp.entry_point(check_no_incoming_transfer=True)
    def withdraw(self):
        """external entrypoint for a user to withdraw her/his stake."""
        Utils.execute_fa2_token_transfer(
            self.data.stake_token_address,
            sp.self_address,
            sp.sender,
            self.data.stake_token_id,
            self.data.stakes[sp.sender],
        )

        del self.data.stakes[sp.sender]

        self.update_stake(Stake.make(sp.sender, 0))
