import smartpy as sp

import utils.constants as Constants
from utils.contract_utils import Ratio
from utils.viewer import Viewer
from utils.fa2 import LedgerKey, RecipientTokenAmount, AdministrableFA2

from contracts.oracle.dummy_oracle import DummyOracle
from contracts.tracker.savings_pool import SavingsPool
from contracts.tracker.staking_pool import StakingPool
from contracts.tracker.options_listing import OptionsListing
from contracts.tracker.governance_token import GovernanceToken
from contracts.tracker.token_collateral_tracker_engine_v3 import TokenTrackerEngine

STARTING_BALANCE = 1000 * 10**12


def liquidation_helper_calculator(
    minted, collateral, price, collateral_ratio, step_in_bonus
):
    return (collateral_ratio * minted - price * collateral) / (
        collateral_ratio - (1 + step_in_bonus)
    )


@sp.add_test(name="FA2 Tracker Engine")
def test():
    scenario = sp.test_scenario()
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

    collateral_token_id = 1
    token_id = 0

    synth = AdministrableFA2({LedgerKey.make(0, administrator.address): sp.unit})
    scenario += synth

    scenario += synth.set_token_metadata(
        sp.record(token_id=collateral_token_id, token_info=sp.map())
    ).run(sender=administrator.address)
    scenario += synth.mint(
        RecipientTokenAmount.make(alice.address, collateral_token_id, STARTING_BALANCE)
    ).run(sender=administrator.address)
    scenario += synth.mint(
        RecipientTokenAmount.make(bob.address, collateral_token_id, STARTING_BALANCE)
    ).run(sender=administrator.address)
    scenario += synth.mint(
        RecipientTokenAmount.make(dan.address, collateral_token_id, STARTING_BALANCE)
    ).run(sender=administrator.address)

    tracker_engine = TokenTrackerEngine(
        synth.address,
        token_id,
        synth.address,
        collateral_token_id,
        administrators=sp.big_map(
            {LedgerKey.make(sp.nat(0), administrator.address): sp.unit}
        ),
    )
    scenario += tracker_engine
    scenario += synth.set_administrator(
        token_id=token_id, administrator_to_set=tracker_engine.address
    ).run(sender=administrator)
    scenario += synth.set_token_metadata(
        sp.record(token_id=token_id, token_info=sp.map())
    ).run(sender=tracker_engine.address)

    scenario.p("Governance Token")
    governance_token = GovernanceToken(
        tracker_engine.address, {LedgerKey.make(0, tracker_engine.address): sp.unit}
    )
    scenario += governance_token

    scenario.p("Options Listing")
    options_listing = OptionsListing(
        synth.address, token_id, tracker_engine.address, target_oracle.address
    )
    scenario += options_listing

    scenario.p("Reward Pool")
    rewards_pool = StakingPool(
        tracker_engine.address,
        governance_token.address,
        token_id,
        synth.address,
        token_id,
    )
    scenario += rewards_pool

    scenario.p("Savings Pool")
    savings_pool = SavingsPool(
        tracker_engine.address,
        synth.address,
        sp.nat(0),
        administrators={LedgerKey.make(sp.nat(0), administrator.address): sp.unit},
    )
    scenario += savings_pool
    scenario += tracker_engine.set_contracts(
        target_price_oracle=target_oracle.address,
        reward_pool_contract=rewards_pool.address,
        savings_pool_contract=savings_pool.address,
        governance_token_contract=governance_token.address,
        options_contract=options_listing.address,
        interest_rate_setter_contract=Constants.DEFAULT_ADDRESS,
    ).run(sender=administrator)

    scenario.h3("Update Operators")
    scenario += synth.update_operators(
        [
            sp.variant(
                "add_operator",
                sp.record(
                    owner=alice.address,
                    operator=tracker_engine.address,
                    token_id=collateral_token_id,
                ),
            )
        ]
    ).run(sender=alice.address)
    scenario += synth.update_operators(
        [
            sp.variant(
                "add_operator",
                sp.record(
                    owner=bob.address,
                    operator=tracker_engine.address,
                    token_id=collateral_token_id,
                ),
            )
        ]
    ).run(sender=bob.address)
    scenario += synth.update_operators(
        [
            sp.variant(
                "add_operator",
                sp.record(
                    owner=dan.address,
                    operator=tracker_engine.address,
                    token_id=collateral_token_id,
                ),
            )
        ]
    ).run(sender=dan.address)
