import smartpy as sp

import utils.constants as Constants
import utils.fa2 as fa2


class Stake:
    """This type is what is used in the update_stake entrypoint"""

    def get_type():
        """Returns the stake type, layouted

        Returns:
            sp.TRecord: layouted type of a stake record
        """
        return sp.TRecord(address=sp.TAddress, amount=sp.TNat).layout(
            ("address", "amount")
        )

    def make(address, amount):
        """Creates a typed ledger key

        Args:
            address (sp.address): address
            amount (sp.nat): amount


        Returns:
            sp.record: typed stake record
        """
        return sp.set_type_expr(
            sp.record(address=address, amount=amount), Stake.get_type()
        )


class GovernanceToken(fa2.BaseFA2, fa2.AdministrableMixin):
    """The governance token is a basic FA2 token contract with a single token (id 0) with a time dependent distribution/minting functionality.

    Args:
        fa2 (BaseFA2): [description]
        fa2 (Administrable): only the admin will be able to call "update_stake"
    """

    def get_init_storage(self):
        """Returns the initial storage of the contract used for inheritance of smartpy contracts

        Returns:
            dict: initial storage of the contract
        """
        storage = super().get_init_storage()

        storage["treasury_ledger_key"] = fa2.LedgerKey.make(
            Constants.GOVERNANCE_TOKEN_ID, self.treasury
        )
        storage["ledger"] = sp.big_map(
            l={fa2.LedgerKey.make(Constants.GOVERNANCE_TOKEN_ID, self.treasury): 0},
            tkey=fa2.LedgerKey.get_type(),
            tvalue=sp.TNat,
        )

        storage["dist_factors"] = sp.big_map(tkey=sp.TAddress, tvalue=sp.TNat)
        storage["total_stake"] = sp.nat(0)
        storage["stakes"] = sp.big_map(tkey=sp.TAddress, tvalue=sp.TNat)
        storage["dist_factor"] = sp.nat(0)
        storage["last_update_timestamp"] = sp.timestamp(0)
        storage["epoch_start_timestamp"] = sp.timestamp(0)
        storage["total_supply"] = sp.big_map(l={0: 0}, tkey=sp.TNat, tvalue=sp.TNat)
        storage["administrators"] = sp.big_map(
            l=self.administrators, tkey=fa2.LedgerKey.get_type(), tvalue=sp.TUnit
        )

        return storage

    def __init__(self, treasury, administrators={}):
        """Token engines will be the ones that are administrators of this contract. Treasury is where 12.5% of the minted tokens is sent to.

        Args:
            treasury (sp.address): address of the treasury, where 12.5% of tokens are sent.
            administrators (dict, optional): initial administrators to set. Defaults to {}.
        """
        self.add_flag("initial-cast")
        self.treasury = treasury
        self.administrators = administrators
        super().__init__()

    @sp.private_lambda(with_storage="read-write", with_operations=True, wrap_call=True)
    def sub_distribute(self, unit):
        """sub entry point that updates the distribution factor based on time. The rule is that we start with ~40k tokens (40k issuance + treasury reward) per week or ~0.066 token per second,
        every 365 days a new "phase" is started and this issuance number is halved. This method takes care of "cross" phase distribution.
        Pre: storage.total_stake > 0
        Post: storage.dist_factor += timedelta_since_last_udpate *
        Post: storage.last_update_timestamp = sp.now
        Post: storage.ledger[LedgerKey(storage.treasury, 0)] += ((storage.dist_factor-storage.dist_factors[address])*storage.stakes(address)/10**12)*0.125
        Post: storage.total_supply[0] += ((storage.dist_factor-storage.dist_factors[address])*storage.stakes(address)/10**12)*0.125
        Args:
            unit (sp.unit): does not mean anything
        """
        sp.set_type(unit, sp.TUnit)
        with sp.if_(self.data.total_stake > 0):
            start_phase = (
                sp.as_nat(
                    self.data.last_update_timestamp - self.data.epoch_start_timestamp
                )
                / Constants.ISSUANCE_PHASE_INTERVAL
            )
            end_phase = (
                sp.as_nat(sp.now - self.data.epoch_start_timestamp)
                / Constants.ISSUANCE_PHASE_INTERVAL
            )
            issuance = sp.local("issuance", 0)
            treasury_reward = sp.local("treasury_reward", 0)

            with sp.for_("phase", sp.range(start_phase, end_phase)) as phase:
                phase_end_timestamp = sp.local(
                    "phase_end_timestamp",
                    self.data.epoch_start_timestamp.add_seconds(
                        sp.to_int((phase + 1) * Constants.ISSUANCE_PHASE_INTERVAL)
                    ),
                )
                timedelta = sp.as_nat(
                    phase_end_timestamp.value - self.data.last_update_timestamp
                )
                issuance.value = timedelta * (
                    Constants.GOVERNANCE_TOKEN_ISSUANCE_RATE >> phase
                )
                treasury_reward.value += (
                    issuance.value >> Constants.TREASURY_REWARD_BITSHIFT
                )

                self.data.dist_factor += (
                    issuance.value * Constants.PRECISION_FACTOR / self.data.total_stake
                )
                self.data.last_update_timestamp = phase_end_timestamp.value

            timedelta = sp.as_nat(sp.now - self.data.last_update_timestamp)
            issuance.value = timedelta * (
                Constants.GOVERNANCE_TOKEN_ISSUANCE_RATE >> end_phase
            )
            treasury_reward.value += (
                issuance.value >> Constants.TREASURY_REWARD_BITSHIFT
            )

            self.data.ledger[self.data.treasury_ledger_key] += treasury_reward.value
            self.data.total_supply[
                Constants.GOVERNANCE_TOKEN_ID
            ] += treasury_reward.value

            self.data.dist_factor += (
                issuance.value * Constants.PRECISION_FACTOR / self.data.total_stake
            )
            self.data.last_update_timestamp = sp.now

    @sp.private_lambda(with_storage="read-write", with_operations=True, wrap_call=True)
    def sub_claim(self, address):
        """given an address this sub entrypoint will mint and assign to a specific address whatever was due. The distribution factor of the specific
        address will also be updated such that calling it multiple times will not result in multiple mints. 12.5% of the minted tokens are given to
        the treasury address.

        Pre: storage.stakes.contains(address)
        Post: storage.ledger[LedgerKey(address, 0)] += (storage.dist_factor-storage.dist_factors[address])*storage.stakes(address)/10**12
        Post: storage.total_supply[0] += (storage.dist_factor-storage.dist_factors[address])*storage.stakes(address)/10**12
        Post: storage.dist_factors[address] = storage.dist_factor

        Args:
            address (sp.address): the address that whishes to claim its ellegible tokens
        """
        sp.set_type(address, sp.TAddress)
        with sp.if_(self.data.stakes.contains(address)):
            reward_governance_token = sp.local(
                "reward_governance_token",
                self.data.stakes[address]
                * sp.as_nat(self.data.dist_factor - self.data.dist_factors[address])
                / Constants.PRECISION_FACTOR,
            )
            owner_ledger_key = fa2.LedgerKey.make(
                Constants.GOVERNANCE_TOKEN_ID, address
            )

            self.data.ledger[owner_ledger_key] = (
                self.data.ledger.get(owner_ledger_key, 0)
                + reward_governance_token.value
            )

            self.data.total_supply[
                Constants.GOVERNANCE_TOKEN_ID
            ] += reward_governance_token.value
            self.data.dist_factors[address] = self.data.dist_factor

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_treasury(self, treasury_ledger_key):
        """Only an admin for token id 0 can call this entrypoint. It will update the treasury ledger key, requires a non-zero balance of tokens!
        Pre: verify_is_admin(0)
        Post: storage.ledger.treasury_ledger_key = treasury_ledger_key

        Args:
            treasury_ledger_key (LedgerKey): the new treasury ledger key
        """
        sp.set_type(treasury_ledger_key, fa2.LedgerKey.get_type())
        self.verify_is_admin(Constants.GOVERNANCE_TOKEN_ID)
        with sp.if_(~self.data.ledger.contains(treasury_ledger_key)):
            self.data.ledger[treasury_ledger_key] = 0
        self.data.treasury_ledger_key = treasury_ledger_key

    @sp.entry_point(check_no_incoming_transfer=True)
    def update_stake(self, stake):
        """Only an admin for token id 0 can call this entrypoint. It will update the stake of a given address, after having distributed and claimed the stakes of that address.
        Pre: verify_is_admin(0)
        Pre: sub_distribute()
        Pre: sub_claim(stake.address)

        Args:
            stake (Stake): the stake
        """
        sp.set_type(stake, Stake.get_type())
        self.verify_is_admin(Constants.GOVERNANCE_TOKEN_ID)

        self.sub_distribute(sp.unit)
        self.sub_claim(stake.address)

        self.data.dist_factors[stake.address] = self.data.dist_factor
        stake_delta = stake.amount - self.data.stakes.get(stake.address, sp.nat(0))
        self.data.total_stake = sp.as_nat(
            sp.to_int(self.data.total_stake) + stake_delta
        )
        self.data.stakes[stake.address] = stake.amount

        with sp.if_(stake.amount == 0):
            del self.data.stakes[stake.address]
            del self.data.dist_factors[stake.address]

    @sp.entry_point(check_no_incoming_transfer=True)
    def claim(self):
        """entrypoint that allows a sender to claim it's rewards, it will also force a recalculation of the distribution factor before."""
        self.sub_distribute(sp.unit)
        self.sub_claim(sp.sender)
