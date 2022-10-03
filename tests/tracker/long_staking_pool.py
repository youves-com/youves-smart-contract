import smartpy as sp

import utils.constants as Constants
import utils.fa2 as fa2
from utils.administrable_mixin import AdministratorState

from contracts.tracker.long_staking_pool import LongStakingPool


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


@sp.add_test(name="Normal Staking Pool")
def test_normal_staking_pool():
    scenario = sp.test_scenario()
    scenario.h1("Staking Pool Unit Test")
    scenario.table_of_contents()

    scenario.h2("Bootstrapping")
    token_id = sp.nat(0)

    administrator = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob = sp.test_account("Robert")
    charlie = sp.test_account("Charlie")
    dan = sp.test_account("Dan")

    reward_token = DummyFA2({fa2.LedgerKey.make(0, administrator.address): sp.unit})
    staking_token = DummyFA2({fa2.LedgerKey.make(0, administrator.address): sp.unit})

    scenario += reward_token
    scenario += staking_token

    scenario += reward_token.set_token_metadata(
        sp.record(token_id=token_id, token_info=sp.map())
    ).run(sender=administrator)

    scenario += staking_token.set_token_metadata(
        sp.record(token_id=token_id, token_info=sp.map())
    ).run(sender=administrator)

    scenario.h1("Long Staking with release of 0")
    staking_pool = LongStakingPool(
        staking_token.address,
        token_id,
        Constants.TOKEN_TYPE_FA2,
        reward_token.address,
        token_id,
        180 * 24 * 60 * 60,
        sp.big_map({administrator.address: AdministratorState.SET}),
    )
    scenario += staking_pool

    scenario += staking_token.mint(
        owner=alice.address,
        token_id=token_id,
        token_amount=10 * Constants.PRECISION_FACTOR,
    )
    scenario += staking_token.mint(
        owner=bob.address,
        token_id=token_id,
        token_amount=10 * Constants.PRECISION_FACTOR,
    )
    scenario += staking_token.mint(
        owner=charlie.address,
        token_id=token_id,
        token_amount=10 * Constants.PRECISION_FACTOR,
    )
    scenario += staking_token.mint(
        owner=dan.address,
        token_id=token_id,
        token_amount=10 * Constants.PRECISION_FACTOR,
    )
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
    scenario += staking_token.update_operators(
        [
            sp.variant(
                "add_operator",
                sp.record(
                    owner=charlie.address,
                    operator=staking_pool.address,
                    token_id=token_id,
                ),
            )
        ]
    ).run(sender=charlie.address)
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
    alice_ledger_key = fa2.LedgerKey.make(0, alice.address)
    bob_ledger_key = fa2.LedgerKey.make(0, bob.address)
    charlie_ledger_key = fa2.LedgerKey.make(0, charlie.address)
    dan_ledger_key = fa2.LedgerKey.make(0, dan.address)

    scenario.h2("Start staking")
    now = sp.timestamp(0)
    scenario += staking_pool.deposit(1 * Constants.PRECISION_FACTOR).run(
        sender=alice, now=now
    )

    scenario.h2("Claim after a reward has been paid ")
    now = now.add_seconds(sp.to_int(staking_pool.data.max_release_period))
    reward_amount = 1 * Constants.PRECISION_FACTOR
    alice_reward = reward_amount
    bob_reward = 0
    scenario.p("pay reward")
    scenario += reward_token.mint(
        owner=staking_pool.address, token_id=token_id, token_amount=reward_amount
    )
    scenario.p("alice claims as only user -> gets full reward")
    scenario += staking_pool.claim().run(sender=alice, now=now)
    scenario.verify_equal(reward_token.data.ledger[alice_ledger_key], alice_reward)
    scenario.p("Multiclaim yields nothing")
    scenario += staking_pool.claim().run(sender=alice, now=now)
    scenario.verify_equal(reward_token.data.ledger[alice_ledger_key], alice_reward)

    scenario.h2("Bob joins before a reward payout")
    scenario += staking_pool.deposit(1 * Constants.PRECISION_FACTOR).run(
        sender=bob, now=now
    )
    now = now.add_seconds(sp.to_int(staking_pool.data.max_release_period))
    scenario.p("pay reward")
    alice_reward += reward_amount // 2
    bob_reward += reward_amount // 2
    scenario += reward_token.mint(
        owner=staking_pool.address, token_id=token_id, token_amount=reward_amount
    )
    scenario.p("both claim, both get same reward")
    scenario += staking_pool.claim().run(sender=alice, now=now)
    scenario += staking_pool.claim().run(sender=bob, now=now)
    scenario.verify_equal(reward_token.data.ledger[alice_ledger_key], alice_reward)
    scenario.verify_equal(reward_token.data.ledger[bob_ledger_key], bob_reward)

    scenario.h2("Alice Increases Stake")
    scenario += staking_pool.deposit(1 * Constants.PRECISION_FACTOR).run(
        sender=alice, now=now
    )
    now = now.add_seconds(sp.to_int(staking_pool.data.max_release_period))
    scenario.p("pay reward")
    alice_reward += reward_amount * 2 // 3
    bob_reward += reward_amount // 3
    scenario += reward_token.mint(
        owner=staking_pool.address, token_id=token_id, token_amount=reward_amount
    )
    scenario.p("both claim, alice gets 2/3 and bob 1/3")
    scenario += staking_pool.claim().run(sender=alice, now=now)
    scenario += staking_pool.claim().run(sender=bob, now=now)
    scenario.verify_equal(reward_token.data.ledger[alice_ledger_key], alice_reward)
    scenario.verify_equal(reward_token.data.ledger[bob_ledger_key], bob_reward)

    scenario.h2("Fixed rewards randomly flies in")
    scenario += reward_token.mint(
        owner=staking_pool.address, token_id=token_id, token_amount=reward_amount
    ).run(now=now)
    alice_reward += reward_amount * 2 // 3
    bob_reward += reward_amount // 3
    dan_reward = 0

    scenario.p("Dan joins late (not ellegible for fixed reward")
    now = now.add_seconds(sp.to_int(staking_pool.data.max_release_period))
    scenario += staking_pool.deposit(1 * Constants.PRECISION_FACTOR).run(
        sender=dan, now=now
    )

    scenario += staking_pool.claim().run(sender=alice, now=now)
    scenario += staking_pool.claim().run(sender=bob, now=now)
    scenario += staking_pool.claim().run(sender=dan, now=now)

    scenario.verify_equal(reward_token.data.ledger[alice_ledger_key], alice_reward)
    scenario.verify_equal(reward_token.data.ledger[bob_ledger_key], bob_reward)

    scenario.h2("Dan leaves after reward")
    scenario += reward_token.mint(
        owner=staking_pool.address, token_id=token_id, token_amount=reward_amount
    ).run(now=now)

    alice_reward += reward_amount * 2 // 4
    bob_reward += reward_amount // 4
    dan_reward += reward_amount // 4

    now = now.add_seconds(sp.to_int(staking_pool.data.max_release_period))
    scenario += staking_pool.withdraw().run(sender=dan, now=now)

    scenario.p("Dan Rejoins (after a new reward)")
    scenario += reward_token.mint(
        owner=staking_pool.address, token_id=token_id, token_amount=reward_amount
    ).run(now=now)
    now = now.add_seconds(sp.to_int(staking_pool.data.max_release_period))

    alice_reward += reward_amount * 2 // 3
    bob_reward += reward_amount // 3

    scenario += staking_pool.deposit(1 * Constants.PRECISION_FACTOR).run(
        sender=dan, now=now
    )
    scenario += staking_pool.claim().run(sender=alice, now=now)
    scenario += staking_pool.claim().run(sender=bob, now=now)
    scenario += staking_pool.claim().run(sender=dan, now=now)

    scenario.verify_equal(reward_token.data.ledger[alice_ledger_key], alice_reward)
    scenario.verify_equal(reward_token.data.ledger[bob_ledger_key], bob_reward)
    scenario.verify_equal(reward_token.data.ledger[dan_ledger_key], dan_reward)


@sp.add_test(name="Vesting Staking Pool")
def test_vesting_incentive():
    scenario = sp.test_scenario()
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
    staking_token = DummyFA2({fa2.LedgerKey.make(0, administrator.address): sp.unit})

    scenario += reward_token
    scenario += staking_token

    scenario += reward_token.set_token_metadata(
        sp.record(token_id=token_id, token_info=sp.map())
    ).run(sender=administrator)

    scenario += staking_token.set_token_metadata(
        sp.record(token_id=token_id, token_info=sp.map())
    ).run(sender=administrator)

    scenario.h1("Long Staking with release of 0")
    staking_pool = LongStakingPool(
        staking_token.address,
        token_id,
        Constants.TOKEN_TYPE_FA2,
        reward_token.address,
        token_id,
        180 * 24 * 60 * 60,
        sp.big_map({administrator.address: sp.unit}),
    )
    scenario += staking_pool

    scenario += staking_token.mint(
        owner=alice.address,
        token_id=token_id,
        token_amount=10 * Constants.PRECISION_FACTOR,
    )
    scenario += staking_token.mint(
        owner=bob.address,
        token_id=token_id,
        token_amount=10 * Constants.PRECISION_FACTOR,
    )
    scenario += staking_token.mint(
        owner=dan.address,
        token_id=token_id,
        token_amount=10 * Constants.PRECISION_FACTOR,
    )
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
    alice_ledger_key = fa2.LedgerKey.make(0, alice.address)
    bob_ledger_key = fa2.LedgerKey.make(0, bob.address)
    dan_ledger_key = fa2.LedgerKey.make(0, dan.address)

    scenario.h2("Start staking")
    now = sp.timestamp(0)
    scenario += staking_pool.deposit(1 * Constants.PRECISION_FACTOR).run(
        sender=alice, now=now
    )

    scenario.h2("Claim after a reward has been paid ")
    now = now.add_seconds(sp.to_int(staking_pool.data.max_release_period // 2))
    reward_amount = 1 * Constants.PRECISION_FACTOR
    alice_reward = reward_amount // 2
    bob_reward = 0
    scenario.p("pay reward")
    scenario += reward_token.mint(
        owner=staking_pool.address, token_id=token_id, token_amount=reward_amount
    )
    scenario.p("alice claims as only user -> gets full reward")
    scenario += staking_pool.claim().run(sender=alice, now=now)
    scenario.verify_equal(reward_token.data.ledger[alice_ledger_key], alice_reward)
    scenario.p("Multiclaim yields the re-distributed rewards")
    alice_reward += (reward_amount - alice_reward) // 2
    scenario += staking_pool.claim().run(sender=alice, now=now)
    scenario.verify_equal(reward_token.data.ledger[alice_ledger_key], alice_reward)

    scenario.h2("Bob joins before a reward payout")
    scenario += staking_pool.deposit(1 * Constants.PRECISION_FACTOR).run(
        sender=bob, now=now
    )
    now = now.add_seconds(sp.to_int(staking_pool.data.max_release_period // 2))
    scenario.p("pay reward")
    alice_reward += reward_amount // 2 + reward_amount // 4
    bob_reward += reward_amount // 4
    scenario += reward_token.mint(
        owner=staking_pool.address, token_id=token_id, token_amount=reward_amount
    )
    scenario.p("both claim, both get same reward")
    scenario += staking_pool.claim().run(sender=alice, now=now)
    scenario += staking_pool.claim().run(sender=bob, now=now)
    scenario.verify_equal(reward_token.data.ledger[alice_ledger_key], alice_reward)
    scenario.verify_equal(reward_token.data.ledger[bob_ledger_key], bob_reward)

    scenario.h2("Alice Increases Stake")
    scenario += staking_pool.deposit(1 * Constants.PRECISION_FACTOR).run(
        sender=alice, now=now
    )
    now = now.add_seconds(sp.to_int(staking_pool.data.max_release_period // 2))
    scenario.p("pay reward")
    alice_reward += (
        reward_amount * 2 // 3 + reward_amount // 4 // 2
    )  # time weighted own + bob's redistribution
    bob_reward += reward_amount // 3 + reward_amount // 4 // 2
    scenario += reward_token.mint(
        owner=staking_pool.address, token_id=token_id, token_amount=reward_amount
    )
    scenario.p("both claim, alice gets 2/3 and bob 1/3")
    scenario += staking_pool.claim().run(sender=alice, now=now)
    scenario += staking_pool.claim().run(sender=bob, now=now)
    scenario.verify_equal(reward_token.data.ledger[alice_ledger_key], alice_reward)
    scenario.verify_equal(reward_token.data.ledger[bob_ledger_key], bob_reward)

    scenario.h2("Fixed rewards randomly flies in")
    scenario += reward_token.mint(
        owner=staking_pool.address, token_id=token_id, token_amount=reward_amount
    ).run(now=now)
    alice_reward += reward_amount * 2 // 3
    bob_reward += reward_amount // 3
    dan_reward = 0

    scenario.p("Dan joins late (not ellegible for fixed reward")
    now = now.add_seconds(sp.to_int(staking_pool.data.max_release_period // 2))
    scenario += staking_pool.deposit(1 * Constants.PRECISION_FACTOR).run(
        sender=dan, now=now
    )

    scenario += staking_pool.claim().run(sender=alice, now=now)
    scenario += staking_pool.claim().run(sender=bob, now=now)
    scenario += staking_pool.claim().run(sender=dan, now=now)

    scenario.verify_equal(reward_token.data.ledger[alice_ledger_key], alice_reward)
    scenario.verify_equal(reward_token.data.ledger[bob_ledger_key], bob_reward)

    scenario.h2("Dan leaves after reward")
    scenario += reward_token.mint(
        owner=staking_pool.address, token_id=token_id, token_amount=reward_amount
    ).run(now=now)

    alice_reward += reward_amount * 2 // 4
    bob_reward += reward_amount // 4
    dan_reward += reward_amount // 4 // 2

    now = now.add_seconds(sp.to_int(staking_pool.data.max_release_period // 2))
    scenario += staking_pool.withdraw().run(sender=dan, now=now)

    scenario.p("Dan Rejoins (after a new reward)")
    scenario += reward_token.mint(
        owner=staking_pool.address, token_id=token_id, token_amount=reward_amount
    ).run(now=now)
    now = now.add_seconds(sp.to_int(staking_pool.data.max_release_period // 2))

    alice_reward += reward_amount * 2 // 3 + reward_amount * 2 // 4 // 2 // 3 + 1
    bob_reward += (
        reward_amount // 3 + reward_amount // 4 // 2 // 3 + 1
    )  # the +1 is because we have double truncated division

    scenario += staking_pool.deposit(1 * Constants.PRECISION_FACTOR).run(
        sender=dan, now=now
    )
    scenario += staking_pool.claim().run(sender=alice, now=now)
    scenario += staking_pool.claim().run(sender=bob, now=now)
    scenario += staking_pool.claim().run(sender=dan, now=now)

    scenario.verify_equal(reward_token.data.ledger[alice_ledger_key], alice_reward)
    scenario.verify_equal(reward_token.data.ledger[bob_ledger_key], bob_reward)
    scenario.verify_equal(reward_token.data.ledger[dan_ledger_key], dan_reward)
    now = now.add_seconds(sp.to_int(staking_pool.data.max_release_period // 2))
    scenario += staking_pool.claim().run(sender=alice, now=now)
    scenario += staking_pool.claim().run(sender=bob, now=now)

    # Admin tests
    scenario += staking_pool.propose_administrator(alice.address).run(
        sender=alice, now=now, valid=False
    )
    scenario += staking_pool.propose_administrator(alice.address).run(
        sender=administrator, now=now, valid=True
    )
    scenario.verify(staking_pool.data.administrators.contains(alice.address) == True)
    scenario.verify_equal(
        staking_pool.data.administrators[alice.address], AdministratorState.PROPOSED
    )

    scenario += staking_pool.set_administrator(sp.unit).run(
        sender=bob, now=now, valid=False
    )
    scenario += staking_pool.set_administrator(sp.unit).run(
        sender=alice, now=now, valid=True
    )
    scenario.verify(staking_pool.data.administrators.contains(alice.address) == True)
    scenario.verify_equal(
        staking_pool.data.administrators[alice.address], AdministratorState.SET
    )

    scenario += staking_pool.remove_administrator(alice.address).run(
        sender=bob, now=now, valid=False
    )
    scenario += staking_pool.remove_administrator(alice.address).run(
        sender=administrator, now=now, valid=True
    )
    scenario.verify(staking_pool.data.administrators.contains(alice.address) == False)

    scenario += staking_pool.set_max_release_period(360 * 24 * 60 * 60).run(
        sender=alice, now=now, valid=False
    )
    scenario += staking_pool.set_max_release_period(360 * 24 * 60 * 60).run(
        sender=administrator, now=now, valid=True
    )
    scenario.verify(staking_pool.data.max_release_period == 360 * 24 * 60 * 60)
