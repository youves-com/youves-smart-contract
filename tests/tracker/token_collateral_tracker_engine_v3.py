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

    scenario.h3("Mint")
    scenario += tracker_engine.create_vault(sp.none).run(sender=alice)
    scenario += tracker_engine.deposit(sp.nat(100 * Constants.PRECISION_FACTOR)).run(
        sender=alice
    )
    tokens_to_mint = sp.nat(33 * Constants.PRECISION_FACTOR)
    tokens_fee = tokens_to_mint >> Constants.MINTING_FEE_BITSHIFT
    received_tokens = sp.as_nat(tokens_to_mint - tokens_fee)

    scenario += tracker_engine.mint(sp.nat(33 * Constants.PRECISION_FACTOR)).run(
        sender=alice
    )
    scenario.verify_equal(
        tracker_engine.data.vault_contexts[alice.address].minted, tokens_to_mint
    )
    scenario.verify_equal(
        synth.data.ledger[LedgerKey.make(token_id, alice.address)], received_tokens
    )
    scenario.verify_equal(
        synth.data.ledger[LedgerKey.make(token_id, rewards_pool.address)], tokens_fee
    )

    scenario.h3(
        "Liquidation with no interest rate impact (everything happens at now 0)"
    )
    scenario.p("Transfer Tokens to Bob")
    scenario += synth.transfer(
        [
            sp.record(
                from_=alice.address,
                txs=[
                    sp.record(
                        to_=bob.address, amount=received_tokens, token_id=token_id
                    )
                ],
            )
        ]
    ).run(sender=alice)

    scenario.p("Bob liquidates alice in one go")
    tokens_to_liquidate = sp.nat(
        int(
            liquidation_helper_calculator(33, 100, 0.5, 2.0, 0.125)
            * Constants.PRECISION_FACTOR
        )
        - 1
    )
    one_token = sp.nat(1 * Constants.PRECISION_FACTOR)
    current_price = sp.nat(2000000)
    scenario += target_oracle.set_price(current_price)
    scenario += tracker_engine.liquidate(
        vault_owner=alice.address, token_amount=tokens_to_liquidate
    ).run(sender=bob)
    scenario.p("Cannot liquidate more")
    scenario += tracker_engine.liquidate(
        vault_owner=alice.address, token_amount=one_token
    ).run(sender=bob, valid=False)

    remaining_tokens_in_vault = sp.as_nat(received_tokens - tokens_to_liquidate)
    whole_liquidation_reward = (
        tokens_to_liquidate * 2
    ) >> Constants.LIQUIDATION_REWARD_BITSHIFT
    platform_liquidation_reward = (
        whole_liquidation_reward >> Constants.LIQUIDATION_REWARD_BITSHIFT
    )
    individual_liquidiation_reward = (tokens_to_liquidate * 2) + sp.as_nat(
        whole_liquidation_reward - platform_liquidation_reward
    )

    scenario.verify_equal(
        tracker_engine.data.vault_contexts[alice.address].minted,
        sp.as_nat(tokens_to_mint - tokens_to_liquidate),
    )
    scenario.verify_equal(
        synth.data.ledger[LedgerKey.make(token_id, bob.address)],
        remaining_tokens_in_vault,
    )

    scenario.show(whole_liquidation_reward)
    scenario.show(platform_liquidation_reward)
    scenario.show(individual_liquidiation_reward)
    scenario.verify_equal(
        synth.data.ledger[LedgerKey.make(collateral_token_id, rewards_pool.address)],
        platform_liquidation_reward,
    )
    scenario.verify_equal(
        synth.data.ledger[LedgerKey.make(collateral_token_id, bob.address)],
        STARTING_BALANCE + individual_liquidiation_reward,
    )

    scenario.h1("Interest Rate Calculations")
    scenario.h3("Phase 1")
    minted_t0 = 14714285714287
    now = sp.timestamp(Constants.SECONDS_PER_WEEK)
    scenario += tracker_engine.update().run(now=now)

    minted_t1 = (
        minted_t0
        * (tracker_engine.data.compound_interest_rate)
        // Constants.PRECISION_FACTOR
    )
    asset_accrual = (
        minted_t0
        * (tracker_engine.data.reference_interest_rate * Constants.SECONDS_PER_WEEK)
        // Constants.PRECISION_FACTOR
    )
    spread_accrual = (
        minted_t0
        * (tracker_engine.data.spread_rate * Constants.SECONDS_PER_WEEK)
        // Constants.PRECISION_FACTOR
        + tokens_fee
    )
    scenario.show(minted_t1)
    scenario.show(asset_accrual)
    scenario.show(spread_accrual)

    scenario.verify_equal(minted_t1, tracker_engine.data.total_supply)
    scenario.verify_equal(
        asset_accrual, synth.data.ledger[LedgerKey.make(token_id, savings_pool.address)]
    )
    scenario.verify_equal(
        spread_accrual,
        synth.data.ledger[LedgerKey.make(token_id, rewards_pool.address)],
    )

    scenario.h3("Phase 2")
    now = sp.timestamp(Constants.SECONDS_PER_WEEK * 2)
    minted_t1 = 14718236959087  # we need to do this because otherwise we end up in a situation where minted_t1 is computed with the new compound interest rate
    scenario += tracker_engine.update().run(now=now)

    minted_t2 = (
        minted_t0
        * (tracker_engine.data.compound_interest_rate)
        // Constants.PRECISION_FACTOR
    )
    asset_accrual += (
        minted_t1
        * (tracker_engine.data.reference_interest_rate * Constants.SECONDS_PER_WEEK)
        // Constants.PRECISION_FACTOR
    )
    spread_accrual += (
        minted_t1
        * (tracker_engine.data.spread_rate * Constants.SECONDS_PER_WEEK)
        // Constants.PRECISION_FACTOR
    )
    scenario.show(minted_t2)
    scenario.show(asset_accrual)
    scenario.show(spread_accrual)
    scenario.verify_equal(minted_t2, tracker_engine.data.total_supply)
    scenario.verify_equal(
        asset_accrual, synth.data.ledger[LedgerKey.make(token_id, savings_pool.address)]
    )
    scenario.verify_equal(
        spread_accrual,
        synth.data.ledger[LedgerKey.make(token_id, rewards_pool.address)],
    )

    scenario.p("Bob joins the savings pool")
    scenario += synth.update_operators(
        [
            sp.variant(
                "add_operator",
                sp.record(
                    owner=bob.address, operator=savings_pool.address, token_id=token_id
                ),
            )
        ]
    ).run(sender=bob, now=now)
    scenario += savings_pool.deposit(Constants.PRECISION_FACTOR).run(
        sender=bob, now=now
    )

    scenario.h1("Options settlement")
    scenario.p("Bob advertises intent")
    scenario += synth.update_operators(
        [
            sp.variant(
                "add_operator",
                sp.record(
                    owner=bob.address,
                    operator=options_listing.address,
                    token_id=token_id,
                ),
            )
        ]
    ).run(sender=bob, now=now)

    scenario += options_listing.advertise_intent(Constants.PRECISION_FACTOR).run(
        sender=bob, now=now
    )
    now = sp.timestamp(Constants.SECONDS_PER_WEEK * 2 + 24 * 60 * 60)
    current_price = sp.nat(1000000)
    scenario += target_oracle.set_price(current_price)

    scenario.p("Don't allow execution on well collateralised vault")
    scenario += tracker_engine.liquidate(
        vault_owner=alice.address, token_amount=one_token
    ).run(sender=bob, valid=False)
    scenario += options_listing.execute_intent(
        address=alice.address, token_amount=Constants.PRECISION_FACTOR
    ).run(sender=bob, now=now, valid=False)

    scenario.p(
        "After price drop we get into the threshold for conversions but no liquidations"
    )
    current_price = sp.nat(2000000)
    scenario += target_oracle.set_price(current_price)
    scenario += tracker_engine.liquidate(
        vault_owner=alice.address, token_amount=one_token
    ).run(sender=bob, valid=False)
    scenario += options_listing.execute_intent(
        address=alice.address, token_amount=Constants.PRECISION_FACTOR
    ).run(sender=bob, now=now)

    scenario.h1("Ratio updates")

    scenario.p("Collateral ratio update")
    scenario += tracker_engine.set_collateral_ratio(Ratio.make(4, 1)).run(
        sender=alice, valid=False
    )
    scenario += tracker_engine.set_collateral_ratio(Ratio.make(4, 1)).run(
        sender=administrator
    )
    scenario.verify_equal(tracker_engine.data.collateral_ratio, Ratio.make(4, 1))

    scenario.p("Settlement ratio update")
    scenario += tracker_engine.set_settlement_ratio(Ratio.make(4, 1)).run(
        sender=alice, valid=False
    )
    scenario += tracker_engine.set_settlement_ratio(Ratio.make(4, 1)).run(
        sender=administrator
    )
    scenario.verify_equal(tracker_engine.data.settlement_ratio, Ratio.make(4, 1))

    scenario.p("Minting fee ratio update")
    scenario += tracker_engine.set_minting_fee_ratio(Ratio.make(2, 100)).run(
        sender=alice, valid=False
    )
    scenario += tracker_engine.set_minting_fee_ratio(Ratio.make(2, 100)).run(
        sender=administrator
    )
    scenario.verify_equal(tracker_engine.data.minting_fee_ratio, Ratio.make(2, 100))

    scenario.p("Introducer ratio update")
    scenario += tracker_engine.set_introducer_ratio(Ratio.make(18, 100)).run(
        sender=alice, valid=False
    )
    scenario += tracker_engine.set_introducer_ratio(Ratio.make(18, 100)).run(
        sender=administrator
    )
    scenario.verify_equal(tracker_engine.data.introducer_ratio, Ratio.make(18, 100))

    scenario.p("Settlement reward fee ratio update")
    scenario += tracker_engine.set_settlement_reward_fee_ratio(Ratio.make(20, 100)).run(
        sender=alice, valid=False
    )
    scenario += tracker_engine.set_settlement_reward_fee_ratio(Ratio.make(20, 100)).run(
        sender=administrator
    )
    scenario.verify_equal(
        tracker_engine.data.settlement_reward_fee_ratio, Ratio.make(20, 100)
    )

    scenario.p("Settlement payout ratio update")
    scenario += tracker_engine.set_settlement_payout_ratio(Ratio.make(975, 1000)).run(
        sender=alice, valid=False
    )
    scenario += tracker_engine.set_settlement_payout_ratio(Ratio.make(975, 1000)).run(
        sender=administrator
    )
    scenario.verify_equal(
        tracker_engine.data.settlement_payout_ratio, Ratio.make(975, 1000)
    )

    scenario.p("Liquidation payout ratio update")
    scenario += tracker_engine.set_liquidation_payout_ratio(Ratio.make(120, 100)).run(
        sender=alice, valid=False
    )
    scenario += tracker_engine.set_liquidation_payout_ratio(Ratio.make(120, 100)).run(
        sender=administrator
    )
    scenario.verify_equal(
        tracker_engine.data.liquidation_payout_ratio, Ratio.make(120, 100)
    )
