import smartpy as sp

import utils.constants as Constants

from utils.fa2 import LedgerKey
from utils.viewer import Viewer
import utils.fa2 as fa2

from contracts.oracle.dummy_oracle import DummyOracle
from contracts.tracker.savings_pool import SavingsPool
from contracts.tracker.staking_pool import StakingPool
from contracts.tracker.options_listing import OptionsListing
from contracts.tracker.governance_token import GovernanceToken
from contracts.tracker.tracker_engine import TrackerEngine
from contracts.tracker.tez_collateral_tracker_engine_v3 import (
    TezCollateralTrackerEngine,
)
from utils.contract_utils import Ratio

MAXMIMUM_RESPONSE = 1833


def liquidation_helper_calculator(
    minted, collateral, price, collateral_ratio, step_in_bonus
):
    return (collateral_ratio * minted - price * collateral) / (
        collateral_ratio - (1 + step_in_bonus)
    )


@sp.add_test(name="Settlement Premium")
def testSettlementPremium():
    scenario = sp.test_scenario()
    scenario.add_flag("protocol", "ithaca")
    scenario.h1("Settlement Premium Unit Test")
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

    synth = fa2.AdministrableFA2(
        {fa2.LedgerKey.make(0, administrator.address): sp.unit}
    )
    scenario += synth

    tracker_engine = TezCollateralTrackerEngine(
        token_contract=synth.address,
        token_id=sp.nat(0),
        collateral_token_contract=Constants.DEFAULT_ADDRESS,
        collateral_token_id=sp.nat(0),
        price_extra_precision_factor=sp.nat(1),
        token_decimals=12,
        collateral_token_decimals=6,
        administrators=sp.big_map(
            {fa2.LedgerKey.make(0, administrator.address): sp.unit}
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
        dan.address, {fa2.LedgerKey.make(0, tracker_engine.address): sp.unit}
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

    scenario.h3("Alice creates Vault (settlement on)")
    return_contract = sp.contract(
        sp.TAddress, viewer.address, entry_point="set_address"
    ).open_some()
    scenario += tracker_engine.create_vault(
        baker=sp.some(administrator.public_key_hash), introducer=sp.none
    ).run(sender=alice, amount=sp.tez(100))

    scenario.h3("Bob creates Vault (settlement off)")
    scenario += tracker_engine.create_vault(
        baker=sp.some(administrator.public_key_hash), introducer=sp.none
    ).run(sender=bob, amount=sp.tez(100))

    scenario.h3("Mint (settlement on)")
    tokens_to_mint = sp.nat(33 * Constants.PRECISION_FACTOR)
    tokens_fee = (
        tokens_to_mint
        * tracker_engine.data.minting_fee_ratio.numerator
        // tracker_engine.data.minting_fee_ratio.denominator
    )
    received_tokens = sp.as_nat(tokens_to_mint - tokens_fee)
    scenario += tracker_engine.mint(tokens_to_mint).run(sender=alice)
    scenario.verify_equal(
        tracker_engine.data.vault_contexts[alice.address].minted, tokens_to_mint
    )
    scenario.verify_equal(
        synth.data.ledger[LedgerKey.make(token_id, alice.address)], received_tokens
    )
    scenario.verify_equal(
        synth.data.ledger[LedgerKey.make(token_id, rewards_pool.address)], tokens_fee
    )

    scenario.h3("Mint (settlement off)")
    tokens_to_mint = sp.nat(33 * Constants.PRECISION_FACTOR)
    tokens_fee = (
        tokens_to_mint
        * tracker_engine.data.minting_fee_ratio.numerator
        // tracker_engine.data.minting_fee_ratio.denominator
    )
    received_tokens = sp.as_nat(tokens_to_mint - tokens_fee)
    scenario += tracker_engine.mint(sp.nat(33 * Constants.PRECISION_FACTOR)).run(
        sender=bob
    )
    scenario.verify_equal(
        tracker_engine.data.vault_contexts[bob.address].minted, tokens_to_mint
    )
    scenario.verify_equal(
        synth.data.ledger[LedgerKey.make(token_id, bob.address)], received_tokens
    )
    scenario.verify_equal(
        synth.data.ledger[LedgerKey.make(token_id, rewards_pool.address)],
        tokens_fee * 2,
    )

    now = sp.timestamp(Constants.SECONDS_PER_WEEK)

    scenario.h3("Claim Gov tokens after one week")

    gov_tokens_bob = 0
    gov_tokens_alice = (
        Constants.GOVERNANCE_TOKEN_ISSUANCE_RATE * Constants.SECONDS_PER_WEEK // 2
    )

    scenario += governance_token.claim().run(sender=alice, now=now)
    scenario += governance_token.claim().run(sender=bob, now=now)

    scenario.verify_equal(
        abs(
            governance_token.data.ledger[LedgerKey.make(token_id, alice.address)]
            - gov_tokens_alice
        )
        < 10**7,
        True,
    )
    scenario.verify_equal(
        governance_token.data.ledger.contains(LedgerKey.make(token_id, bob.address)),
        True,
    )

    scenario.h3("Can only settle on Alice")
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

    scenario += tracker_engine.set_settlement_ratio(Ratio.make(100, 1)).run(
        sender=administrator, now=now
    )
    scenario += options_listing.advertise_intent(11 * Constants.PRECISION_FACTOR).run(
        sender=bob, now=now
    )
    now = now.add_seconds(24 * 60 * 60)

    scenario.p("Bob settles on himself (and fails)")
    scenario += options_listing.execute_intent(
        address=bob.address, token_amount=5 * Constants.PRECISION_FACTOR
    ).run(sender=bob, now=now)

    scenario.p("Bob settles on alice (and succeeds")
    scenario += options_listing.execute_intent(
        address=alice.address, token_amount=6 * Constants.PRECISION_FACTOR
    ).run(sender=bob, now=now)

    scenario.p("claim after a settlement (after 1 week)")
    now = now.add_seconds(6 * 24 * 60 * 60)

    scenario += governance_token.claim().run(sender=alice, now=now)
    scenario += governance_token.claim().run(sender=bob, now=now)


@sp.add_test(name="Tracker Engine")
def testTrackerEngine():
    def lambda_delete_vault(param):
        sp.set_type(
            param,
            sp.TPair(
                sp.TAddress,
                sp.TBigMap(
                    sp.TAddress,
                    sp.TRecord(
                        address=sp.TAddress,
                        minted=sp.TNat,
                        balance=sp.TNat,
                        introducer=sp.TOption(sp.TAddress),
                    ),
                ),
            ),
        )

        with sp.if_(param.second.contains(param.first)):
            del param.second[param.first]

        sp.result(sp.unit)

    scenario = sp.test_scenario()
    scenario.add_flag("protocol", "ithaca")
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

    synth = fa2.AdministrableFA2(
        {fa2.LedgerKey.make(0, administrator.address): sp.unit}
    )
    scenario += synth

    tracker_engine = TezCollateralTrackerEngine(
        token_contract=synth.address,
        token_id=sp.nat(0),
        collateral_token_contract=Constants.DEFAULT_ADDRESS,
        collateral_token_id=sp.nat(0),
        price_extra_precision_factor=sp.nat(1),
        token_decimals=12,
        collateral_token_decimals=6,
        administrators=sp.big_map(
            {fa2.LedgerKey.make(0, administrator.address): sp.unit}
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
        tracker_engine.address, {fa2.LedgerKey.make(0, tracker_engine.address): sp.unit}
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

    scenario.h3("Alice creates Vault")
    return_contract = sp.contract(
        sp.TAddress, viewer.address, entry_point="set_address"
    ).open_some()
    scenario += tracker_engine.create_vault(
        baker=sp.some(administrator.public_key_hash), introducer=sp.none
    ).run(sender=alice, amount=sp.tez(100))

    scenario.h3("Mint")
    tokens_to_mint = sp.nat(33 * Constants.PRECISION_FACTOR)
    tokens_fee = (
        tokens_to_mint
        * tracker_engine.data.minting_fee_ratio.numerator
        // tracker_engine.data.minting_fee_ratio.denominator
    )
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

    scenario.h3("Burn")
    scenario += tracker_engine.burn(sp.nat(10)).run(
        sender=alice, valid=False
    )  # amount to small
    scenario += tracker_engine.burn(sp.nat(33 * Constants.PRECISION_FACTOR)).run(
        sender=alice, valid=False
    )  # amount to large
    scenario += tracker_engine.burn(received_tokens).run(sender=alice)

    scenario.verify_equal(
        synth.data.ledger.contains(LedgerKey.make(token_id, alice.address)), False
    )

    scenario.verify_equal(
        tracker_engine.data.vault_contexts[alice.address].minted, tokens_fee
    )

    scenario.h3("Withdraw")
    # Mint some small amount back
    tokens_to_mint = sp.nat(20 * Constants.PRECISION_FACTOR)
    tokens_fee = (
        tokens_to_mint
        * tracker_engine.data.minting_fee_ratio.numerator
        // tracker_engine.data.minting_fee_ratio.denominator
    )
    received_tokens = sp.as_nat(tokens_to_mint - tokens_fee)
    scenario += tracker_engine.mint(tokens_to_mint).run(sender=alice)

    scenario += tracker_engine.withdraw(60 * 10**6).run(
        sender=alice, valid=False
    )  # Trying to withdraw to much
    scenario += tracker_engine.withdraw(40 * 10**6).run(sender=alice)

    scenario.verify_equal(
        tracker_engine.data.vault_contexts[alice.address].balance, 60 * 10**6
    )

    # bring back the previous state
    return_contract = sp.contract(
        sp.TAddress, viewer.address, entry_point="set_address"
    ).open_some()
    scenario += tracker_engine.create_vault(
        baker=sp.some(administrator.public_key_hash), introducer=sp.none
    ).run(sender=alice, amount=sp.tez(40))
    scenario += tracker_engine.mint(13 * Constants.PRECISION_FACTOR).run(sender=alice)

    scenario.verify_equal(
        tracker_engine.data.vault_contexts[alice.address].balance, 100 * 10**6
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
        - 1000000
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
    # scenario.verify_equal(
    #     synth.data.ledger[LedgerKey.make(collateral_token_id, rewards_pool.address)],
    #     platform_liquidation_reward,
    # )
    # scenario.verify_equal(
    #     synth.data.ledger[LedgerKey.make(collateral_token_id, bob.address)],
    #     STARTING_BALANCE + individual_liquidiation_reward,
    # )

    scenario.h1("Interest Rate Calculations")
    scenario.h3("Phase 1")
    minted_t0 = 14714286714286
    now = sp.timestamp(Constants.SECONDS_PER_WEEK)
    scenario += tracker_engine.update().run(now=now)

    minted_t1 = (
        minted_t0
        * (tracker_engine.data.compound_interest_rate)
        / Constants.PRECISION_FACTOR
    )
    asset_accrual = (
        minted_t0
        * (tracker_engine.data.reference_interest_rate * Constants.SECONDS_PER_WEEK)
        // Constants.PRECISION_FACTOR
    )
    spread_accrual = (
        minted_t0
        * (Constants.SECONDS_INTEREST_SPREAD * Constants.SECONDS_PER_WEEK)
        // Constants.PRECISION_FACTOR
        + tokens_fee
    )

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
    scenario += tracker_engine.update().run(now=now)

    minted_t2 = (
        minted_t0
        * (tracker_engine.data.compound_interest_rate)
        / Constants.PRECISION_FACTOR
    )
    asset_accrual += (
        minted_t1
        * (tracker_engine.data.reference_interest_rate * Constants.SECONDS_PER_WEEK)
        // Constants.PRECISION_FACTOR
    )
    spread_accrual += (
        minted_t1
        * (Constants.SECONDS_INTEREST_SPREAD * Constants.SECONDS_PER_WEEK)
        // Constants.PRECISION_FACTOR
    )
    scenario.show(minted_t2)
    scenario.show(asset_accrual)
    scenario.show(spread_accrual)
    # scenario.verify_equal(minted_t2, tracker_engine.data.total_supply)
    # scenario.verify_equal(asset_accrual, synth.data.ledger[LedgerKey.make(token_id, savings_pool.address)])
    # scenario.verify_equal(spread_accrual, synth.data.ledger[LedgerKey.make(token_id, rewards_pool.address)])

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
    scenario += options_listing.execute_intent(
        address=alice.address, token_amount=Constants.PRECISION_FACTOR
    ).run(sender=bob, now=now)

    _lambda = sp.build_lambda(lambda_delete_vault)
    # sp.set_type(
    #    _lambda,
    #    sp.TLambda(
    #        sp.TPair(
    #            sp.TAddress,
    #            sp.TBigMap(
    #                sp.TAddress,
    #                sp.TRecord(
    #                    address=sp.TAddress,
    #                    minted=sp.TNat,
    #                    balance=sp.TNat,
    #                    introducer=sp.TOption(sp.TAddress)
    #                )
    #            )),
    #    sp.TUnit))
    scenario.show(_lambda)
    scenario.verify(tracker_engine.data.vault_contexts.contains(alice.address))
    scenario += tracker_engine.execute(alice.address, _lambda).run(sender=administrator)
    scenario.verify(~tracker_engine.data.vault_contexts.contains(alice.address))
