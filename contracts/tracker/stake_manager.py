import smartpy as sp

import utils.constants as Constants
from utils.fa2 import LedgerKey, AdministrableMixin

from contracts.tracker.governance_token import Stake


class ImportStake:
    """This type is what is used in the import_stake entrypoint"""

    def get_type():
        """Returns the stake type, layouted

        Returns:
            sp.TRecord: layouted type of an import stake record
        """
        return sp.TList(
            sp.TRecord(updater=sp.TAddress, owner=sp.TAddress, amount=sp.TNat).layout(
                ("updater", ("owner", "amount"))
            )
        )


class StakeManager(sp.Contract, AdministrableMixin):
    """The Stakemanager lives between engine (or other contracts that have the power to set stake) and the governance token
    This allows the stake manager to address shortcomings of the governance token, like i.e. having multiple engines setting
    the stake without an override. Another use case is to be able to specify incentive factors for certain sources/engines
    and/or have adresses with fixed stakes.

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

        storage["total_stake"] = sp.nat(0)
        storage["governance_token_contract"] = self.governance_token_contract

        storage["local_stakes"] = sp.big_map(
            tkey=sp.TPair(sp.TAddress, sp.TAddress), tvalue=sp.TNat
        )
        storage["global_stakes"] = sp.big_map(tkey=sp.TAddress, tvalue=sp.TNat)

        storage["stake_factors"] = sp.big_map(tkey=sp.TAddress, tvalue=sp.TNat)
        storage["fixed_stakes"] = sp.big_map(tkey=sp.TAddress, tvalue=sp.TNat)

        storage["administrators"] = sp.set_type_expr(
            self.administrators, sp.TBigMap(LedgerKey.get_type(), sp.TUnit)
        )

        return storage

    def __init__(self, governance_token_contract, administrators={}):
        """init to set the token and administrators.
        Args:
            governance_token_contract (sp.address): the actual governance token address
            administrators (dict, optional): the administrators allowed to set the contracts. Defaults to {}.
        """
        self.governance_token_contract = governance_token_contract
        self.administrators = administrators
        self.init(**self.get_init_storage())

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
    def update_stake(self, stake):
        """this entrypoint is called by an admin (i.e. engine) and sets the stake. If the local stake of that source is already available
        it will overwrite the stake amount, if it's not available yet it will add to the existing stake_amount for that user.  Only admin can call this.
        """
        sp.set_type(stake, Stake.get_type())
        self.verify_is_admin(Constants.DEFAULT_TOKEN_ID)

        local_stake_key = sp.local("stake_key", sp.pair(sp.sender, stake.address))
        local_stake = sp.local("local_stake", self.data.local_stakes.get(local_stake_key.value, sp.nat(0)))
        stake_amount = sp.local("stake_amount", stake.amount)

        with sp.if_(self.data.stake_factors.contains(sp.sender)):
            stake_amount.value = sp.fst(
                sp.ediv(
                    stake_amount.value * self.data.stake_factors[sp.sender],
                    Constants.PRECISION_FACTOR,
                ).open_some()
            )

        global_delta = sp.local("global_delta", stake_amount.value - local_stake.value)
        global_stake = sp.local("global_stake", self.data.global_stakes.get(stake.address, sp.nat(0)))

        global_stake.value = sp.as_nat(
            sp.to_int(global_stake.value) + global_delta.value
        )
        self.data.total_stake = sp.as_nat(
            sp.to_int(self.data.total_stake) + global_delta.value
        )

        with sp.if_(global_stake.value != 0):
            self.data.global_stakes[stake.address] = global_stake.value
        with sp.else_():
            del self.data.global_stakes[stake.address]

        with sp.if_(stake_amount.value != 0):
            self.data.local_stakes[local_stake_key.value] = stake_amount.value
        with sp.else_():
            del self.data.local_stakes[local_stake_key.value]

        self.update_governance_stake(Stake.make(stake.address, global_stake.value))

    @sp.entry_point(check_no_incoming_transfer=True)
    def update_fixed_stakes(self, addresses):
        """entrypoint used for "touching"/updating the fixed stakes. This is done here because we did not want to impact the gas cost of
        the update_stake method by sending "update_governance_stake" twice per "update_stake". Anyone can call this.
        """
        sp.set_type(addresses, sp.TList(sp.TAddress))
        with sp.for_("address", addresses) as address:
            self.update_governance_stake(
                sp.record(
                    address=address,
                    amount=self.data.total_stake
                    * self.data.fixed_stakes[address]
                    // Constants.PRECISION_FACTOR,
                )
            )

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_fixed_stake(self, address, ratio):
        """entrypoint used for by an admin to set a fixed stake for a specific address. Only admin can call this."""
        self.verify_is_admin(Constants.DEFAULT_TOKEN_ID)
        self.data.fixed_stakes[address] = ratio

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_stake_factor(self, address, factor):
        """entrypoint used for by an admin to set a stake factor for a specific source. Only admin can call this."""
        self.verify_is_admin(Constants.DEFAULT_TOKEN_ID)
        self.data.stake_factors[address] = factor

    @sp.entry_point(check_no_incoming_transfer=True)
    def import_stakes(self, stakes):
        """entrypoint used for by an admin to import local stakes, does not actually call update_governance_stake."""
        sp.set_type(stakes, ImportStake.get_type())
        self.verify_is_admin(Constants.DEFAULT_TOKEN_ID)
        with sp.for_("stake", stakes) as stake:
            with sp.if_(~self.data.global_stakes.contains(stake.owner)):
                local_stake_key = sp.pair(stake.updater, stake.owner)
                self.data.local_stakes[local_stake_key] = stake.amount
                self.data.global_stakes[stake.owner] = stake.amount
                self.data.total_stake += stake.amount
