import smartpy as sp

import utils.constants as Constants
import utils.fa2 as fa2

from utils.contract_utils import Utils

from contracts.tracker.staking_pool import StakingPool


class DummyEngine(sp.Contract):
    def __init__(self, token_address):
        self.init(
            accrual_update_timestamp=sp.timestamp(0),
            pool_contract=Constants.DEFAULT_ADDRESS,
            token_address=token_address,
        )

    @sp.entry_point
    def set_pool_contract(
        self, pool_contract
    ):  # need to have more than one entrypoint...
        self.data.pool_contract = pool_contract

    @sp.entry_point
    def update(self):
        Utils.execute_token_mint(
            self.data.token_address,
            self.data.pool_contract,
            sp.nat(0),
            sp.as_nat(sp.now - self.data.accrual_update_timestamp),
        )
        self.data.accrual_update_timestamp = sp.now


class DummyFA2(fa2.AdministrableFA2):
    @sp.entry_point
    def mint(self, recipient_token_amount):
        sp.set_type(recipient_token_amount, fa2.RecipientTokenAmount.get_type())
        with sp.if_(
            self.data.ledger.contains(
                fa2.LedgerKey.make(
                    recipient_token_amount.token_id, recipient_token_amount.owner
                )
            )
        ):
            self.data.ledger[
                fa2.LedgerKey.make(
                    recipient_token_amount.token_id, recipient_token_amount.owner
                )
            ] += recipient_token_amount.token_amount
        with sp.else_():
            self.data.ledger[
                fa2.LedgerKey.make(
                    recipient_token_amount.token_id, recipient_token_amount.owner
                )
            ] = recipient_token_amount.token_amount


@sp.add_test(name="Staking Pool")
def test():
    scenario = sp.test_scenario()
    scenario.add_flag("protocol", "ithaca")
    scenario.h1("Staking Pool Unit Test")
    scenario.table_of_contents()

    scenario.h2("Bootstrapping")
    token_id = sp.nat(0)

    administrator = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob = sp.test_account("Robert")
    dan = sp.test_account("Dan")

    scenario.show([administrator, alice, bob, dan])

    reward_token = DummyFA2({fa2.LedgerKey.make(0, administrator.address): sp.unit})
    scenario += reward_token
    staking_token = DummyFA2({fa2.LedgerKey.make(0, administrator.address): sp.unit})
    scenario += staking_token
    tracker_engine = DummyEngine(reward_token.address)
    scenario += tracker_engine

    scenario += reward_token.set_token_metadata(
        sp.record(token_id=token_id, token_info=sp.map())
    ).run(sender=administrator)

    scenario += staking_token.set_token_metadata(
        sp.record(token_id=token_id, token_info=sp.map())
    ).run(sender=administrator)

    staking_pool = StakingPool(
        tracker_engine.address,
        staking_token.address,
        token_id,
        reward_token.address,
        token_id,
    )
    scenario += staking_pool
    scenario += tracker_engine.set_pool_contract(staking_pool.address)

    scenario += staking_token.mint(
        owner=alice.address,
        token_id=token_id,
        token_amount=1 * Constants.PRECISION_FACTOR,
    )
    scenario += staking_token.mint(
        owner=bob.address,
        token_id=token_id,
        token_amount=1 * Constants.PRECISION_FACTOR,
    )
    scenario += staking_token.mint(
        owner=dan.address,
        token_id=token_id,
        token_amount=1 * Constants.PRECISION_FACTOR,
    )

    scenario.h2("Start staking")
    scenario += staking_token.update_operators(
        [
            sp.variant(
                "add_operator",
                sp.record(
                    owner=alice.address,
                    operator=staking_pool.address,
                    token_id=token_id,
                ),
            )
        ]
    ).run(sender=alice.address)
    scenario += staking_pool.deposit(1 * Constants.PRECISION_FACTOR).run(sender=alice)

    scenario.h2("Claim after a week")
    now = sp.timestamp(Constants.SECONDS_PER_WEEK)

    scenario += staking_pool.claim().run(sender=alice, now=now)
    scenario.verify_equal(
        reward_token.data.ledger[fa2.LedgerKey.make(0, alice.address)],
        Constants.SECONDS_PER_WEEK,
    )

    scenario.p("Multiclaim yields nothing")
    scenario += staking_pool.claim().run(sender=alice, now=now)
    scenario.verify_equal(
        reward_token.data.ledger[fa2.LedgerKey.make(0, alice.address)],
        Constants.SECONDS_PER_WEEK,
    )

    scenario.h2("Bob joins after a week")
    now = sp.timestamp(Constants.SECONDS_PER_WEEK * 2)

    scenario += staking_token.update_operators(
        [
            sp.variant(
                "add_operator",
                sp.record(
                    owner=bob.address, operator=staking_pool.address, token_id=token_id
                ),
            )
        ]
    ).run(sender=bob.address)
    scenario += staking_pool.deposit(1 * Constants.PRECISION_FACTOR).run(
        sender=bob, now=now
    )

    scenario.p("Both claim after 3 weeks")
    now = sp.timestamp(Constants.SECONDS_PER_WEEK * 3)

    scenario += staking_pool.claim().run(sender=alice, now=now)
    scenario += staking_pool.claim().run(sender=bob, now=now)
    scenario.verify_equal(
        reward_token.data.ledger[fa2.LedgerKey.make(0, alice.address)],
        Constants.SECONDS_PER_WEEK * 2 + Constants.SECONDS_PER_WEEK // 2,
    )
    scenario.verify_equal(
        reward_token.data.ledger[fa2.LedgerKey.make(0, bob.address)],
        Constants.SECONDS_PER_WEEK // 2,
    )

    scenario.h2("Fixed rewards randomly flies in")
    scenario += reward_token.mint(
        owner=staking_pool.address,
        token_id=token_id,
        token_amount=1 * Constants.PRECISION_FACTOR,
    ).run(now=now)

    scenario.p("Dan joins late (not ellegible for fixed reward")
    now = sp.timestamp(Constants.SECONDS_PER_WEEK * 4)
    scenario += staking_token.update_operators(
        [
            sp.variant(
                "add_operator",
                sp.record(
                    owner=dan.address, operator=staking_pool.address, token_id=token_id
                ),
            )
        ]
    ).run(sender=dan.address)
    scenario += staking_pool.deposit(1 * Constants.PRECISION_FACTOR).run(
        sender=dan, now=now
    )

    scenario.p("All claim after 5 weeks")
    now = sp.timestamp(Constants.SECONDS_PER_WEEK * 5)

    scenario += staking_pool.claim().run(sender=alice, now=now)
    scenario += staking_pool.claim().run(sender=bob, now=now)
    scenario += staking_pool.claim().run(sender=dan, now=now)
    scenario.verify_equal(
        reward_token.data.ledger[fa2.LedgerKey.make(0, alice.address)],
        Constants.SECONDS_PER_WEEK * 2
        + 2 * Constants.SECONDS_PER_WEEK // 2
        + 1 * Constants.PRECISION_FACTOR // 2
        + Constants.SECONDS_PER_WEEK // 3,
    )
    scenario.verify_equal(
        reward_token.data.ledger[fa2.LedgerKey.make(0, bob.address)],
        2 * Constants.SECONDS_PER_WEEK // 2
        + 1 * Constants.PRECISION_FACTOR // 2
        + Constants.SECONDS_PER_WEEK // 3,
    )
    scenario.verify_equal(
        reward_token.data.ledger[fa2.LedgerKey.make(0, dan.address)],
        Constants.SECONDS_PER_WEEK // 3,
    )

    scenario.h2("Dan leaves after 6 weeks and rejoins after 7")
    now = sp.timestamp(Constants.SECONDS_PER_WEEK * 6)

    scenario += staking_pool.withdraw().run(sender=dan, now=now)

    scenario.p("Rejoins")
    now = sp.timestamp(Constants.SECONDS_PER_WEEK * 7)

    scenario += staking_pool.deposit(1 * Constants.PRECISION_FACTOR).run(
        sender=dan, now=now
    )
    scenario += staking_pool.claim().run(sender=alice, now=now)
    scenario += staking_pool.claim().run(sender=bob, now=now)
    scenario += staking_pool.claim().run(sender=dan, now=now)

    scenario.verify_equal(
        reward_token.data.ledger[fa2.LedgerKey.make(0, alice.address)],
        Constants.SECONDS_PER_WEEK * 2
        + 3 * Constants.SECONDS_PER_WEEK // 2
        + 1 * Constants.PRECISION_FACTOR // 2
        + Constants.SECONDS_PER_WEEK // 3 * 2,
    )
    scenario.verify_equal(
        reward_token.data.ledger[fa2.LedgerKey.make(0, bob.address)],
        3 * Constants.SECONDS_PER_WEEK // 2
        + 1 * Constants.PRECISION_FACTOR // 2
        + Constants.SECONDS_PER_WEEK // 3 * 2,
    )
    scenario.verify_equal(
        reward_token.data.ledger[fa2.LedgerKey.make(0, dan.address)],
        Constants.SECONDS_PER_WEEK // 3 * 2,
    )
