import smartpy as sp

import utils.constants as Constants
from utils.fa2 import AdministrableFA2, RecipientTokenAmount, LedgerKey, Transfer

from contracts.tracker.unified_staking_pool import (
    UnifiedStakingPool,
    ExchangeValue,
    ExchangeKey,
)


class DummyFA2(AdministrableFA2):
    @sp.entry_point
    def mint(self, recipient_token_amount):
        sp.set_type(recipient_token_amount, RecipientTokenAmount.get_type())
        with sp.if_(
            self.data.ledger.contains(
                LedgerKey.make(
                    recipient_token_amount.token_id, recipient_token_amount.owner
                )
            )
        ):
            self.data.ledger[
                LedgerKey.make(
                    recipient_token_amount.token_id, recipient_token_amount.owner
                )
            ] += recipient_token_amount.token_amount
        with sp.else_():
            self.data.ledger[
                LedgerKey.make(
                    recipient_token_amount.token_id, recipient_token_amount.owner
                )
            ] = recipient_token_amount.token_amount

    @sp.entry_point
    def burn(self, recipient_token_amount):
        sp.set_type(recipient_token_amount, RecipientTokenAmount.get_type())
        self.data.ledger[
            LedgerKey.make(
                recipient_token_amount.token_id, recipient_token_amount.owner
            )
        ] = sp.as_nat(
            self.data.ledger[
                LedgerKey.make(
                    recipient_token_amount.token_id, recipient_token_amount.owner
                )
            ]
            - recipient_token_amount.token_amount
        )


class DummyExchangeOracle(sp.Contract):
    @sp.entry_point
    def default(self):
        pass

    @sp.onchain_view()
    def get_min_out(self, token_amount):
        sp.set_type(token_amount, sp.TNat)
        sp.result(token_amount)


@sp.add_test(name="Unified Staking Pool")
def test():
    scenario = sp.test_scenario()
    scenario.h1("Unified Staking Pool Test")
    scenario.table_of_contents()

    scenario.h2("Bootstrapping")

    administrator = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob = sp.test_account("Robert")
    dan = sp.test_account("Dan")

    scenario.show([administrator, alice, bob, dan])

    token_id = sp.nat(0)
    staking_token = DummyFA2({LedgerKey.make(token_id, administrator.address): sp.unit})
    scenario += staking_token
    scenario += staking_token.set_token_metadata(
        token_id=token_id, token_info=sp.map()
    ).run(sender=administrator)
    staking_token_key = LedgerKey.make(0, staking_token.address)

    unified_staking_pool = UnifiedStakingPool(
        staking_token.address, token_id, 100, {administrator.address: 1}
    )
    scenario += unified_staking_pool

    initial_balance = 1000 * Constants.PRECISION_FACTOR

    scenario += staking_token.mint(
        owner=alice.address, token_id=token_id, token_amount=initial_balance
    )
    scenario += staking_token.mint(
        owner=bob.address, token_id=token_id, token_amount=initial_balance
    )
    scenario += staking_token.mint(
        owner=dan.address, token_id=token_id, token_amount=initial_balance
    )
    scenario += staking_token.update_operators(
        [
            sp.variant(
                "add_operator",
                sp.record(
                    owner=alice.address,
                    operator=unified_staking_pool.address,
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
                    owner=dan.address,
                    operator=unified_staking_pool.address,
                    token_id=token_id,
                ),
            )
        ]
    ).run(sender=dan.address)
    scenario += staking_token.update_operators(
        [
            sp.variant(
                "add_operator",
                sp.record(
                    owner=bob.address,
                    operator=unified_staking_pool.address,
                    token_id=token_id,
                ),
            )
        ]
    ).run(sender=bob.address)

    alice_ledger_key = LedgerKey.make(0, alice.address)
    bob_ledger_key = LedgerKey.make(0, bob.address)
    dan_ledger_key = LedgerKey.make(0, dan.address)
    unified_staking_pool_key = LedgerKey.make(0, unified_staking_pool.address)

    scenario.h2("Single User Flows")
    now = sp.timestamp(0)
    scenario.p("Alice stakes 1 token")
    alices_stake = 1 * Constants.PRECISION_FACTOR
    alices_balance = initial_balance
    scenario += unified_staking_pool.deposit(
        sp.record(token_amount=alices_stake, stake_id=0)
    ).run(sender=alice.address, now=now)
    scenario.p("Alice withdraws what she put in")
    scenario += unified_staking_pool.withdraw(
        sp.record(ratio_numerator=1, ratio_denominator=1, stake_id=1)
    ).run(sender=alice.address, now=now)
    scenario.verify_equal(staking_token.data.ledger[alice_ledger_key], alices_balance)

    scenario.p("Alice stakes 1 token")
    reward_payout = 1 * Constants.PRECISION_FACTOR
    total_reward = reward_payout
    scenario += unified_staking_pool.deposit(
        sp.record(token_amount=alices_stake, stake_id=0)
    ).run(sender=alice.address, now=now)
    scenario += staking_token.mint(
        owner=unified_staking_pool.address,
        token_id=token_id,
        token_amount=reward_payout,
    )

    scenario.p("Alice withdraws what she put in after reward")
    scenario += unified_staking_pool.withdraw(
        sp.record(ratio_numerator=1, ratio_denominator=1, stake_id=2)
    ).run(sender=alice.address, now=now)
    scenario.verify_equal(staking_token.data.ledger[alice_ledger_key], alices_balance)
    scenario.verify_equal(
        staking_token.data.ledger[unified_staking_pool_key], reward_payout
    )

    scenario.p("Alice stakes 1 token")
    scenario += unified_staking_pool.deposit(
        sp.record(token_amount=alices_stake, stake_id=0)
    ).run(sender=alice.address, now=now)
    scenario += staking_token.mint(
        owner=unified_staking_pool.address,
        token_id=token_id,
        token_amount=reward_payout,
    )

    scenario.p("Alice withdraws what she put in after reward after 1/10 of the time")
    now = now.add_seconds(10)
    total_reward += reward_payout
    alices_balance += total_reward // 10
    scenario += unified_staking_pool.withdraw(
        sp.record(ratio_numerator=1, ratio_denominator=1, stake_id=3)
    ).run(sender=alice.address, now=now)
    scenario.verify_equal(staking_token.data.ledger[alice_ledger_key], alices_balance)
    scenario.verify_equal(
        staking_token.data.ledger[unified_staking_pool_key], total_reward * 9 // 10
    )

    scenario.p("Alice stakes 1 token")
    scenario += unified_staking_pool.deposit(
        sp.record(token_amount=alices_stake, stake_id=0)
    ).run(sender=alice.address, now=now)
    scenario += staking_token.mint(
        owner=unified_staking_pool.address,
        token_id=token_id,
        token_amount=reward_payout,
    )

    scenario.p(
        "Alice withdraws what she put in after reward after 10/10 of the time, get full rewards"
    )
    now = now.add_seconds(100)
    total_reward = total_reward * 9 // 10 + reward_payout
    calculation_rest = 5
    alices_balance += total_reward - calculation_rest

    scenario += unified_staking_pool.withdraw(
        sp.record(ratio_numerator=1, ratio_denominator=1, stake_id=4)
    ).run(sender=alice.address, now=now)
    scenario.verify_equal(staking_token.data.ledger[alice_ledger_key], alices_balance)
    scenario.verify_equal(
        staking_token.data.ledger[unified_staking_pool_key], calculation_rest
    )

    scenario.p("Alice stakes 1 token")
    scenario += unified_staking_pool.deposit(
        sp.record(token_amount=alices_stake, stake_id=0)
    ).run(sender=alice.address, now=now)
    scenario += staking_token.mint(
        owner=unified_staking_pool.address,
        token_id=token_id,
        token_amount=reward_payout,
    )

    scenario.p("Alice withdraws half-time half of her stake")
    now = now.add_seconds(50)
    total_reward = reward_payout
    alices_balance += total_reward // 2 // 2 - (alices_stake // 2) - 4
    remaining_reward = (
        3 * total_reward // 4 + (alices_stake // 2) + 4 + calculation_rest
    )

    scenario += unified_staking_pool.withdraw(
        sp.record(ratio_numerator=1, ratio_denominator=2, stake_id=5)
    ).run(sender=alice.address, now=now)
    scenario.verify_equal(staking_token.data.ledger[alice_ledger_key], alices_balance)
    scenario.verify_equal(
        staking_token.data.ledger[unified_staking_pool_key], remaining_reward
    )

    scenario.p("Alice withdraws full-time the other half of her stake")
    now = now.add_seconds(50)
    alices_balance += 3 * total_reward // 4 + (alices_stake // 2) - 12
    remaining_reward = 4 + calculation_rest + 12
    scenario += unified_staking_pool.withdraw(
        sp.record(ratio_numerator=1, ratio_denominator=1, stake_id=5)
    ).run(sender=alice.address, now=now)
    scenario.verify_equal(staking_token.data.ledger[alice_ledger_key], alices_balance)
    scenario.verify_equal(
        staking_token.data.ledger[unified_staking_pool_key], remaining_reward
    )

    scenario.p("Alice stakes 1 token")
    scenario += unified_staking_pool.deposit(
        sp.record(token_amount=alices_stake, stake_id=0)
    ).run(sender=alice.address, now=now)
    scenario += staking_token.mint(
        owner=unified_staking_pool.address,
        token_id=token_id,
        token_amount=reward_payout,
    )

    scenario.p(
        "Alice adds 1 token to stake after half time, after reward her stake is currently 2:1"
    )
    now = now.add_seconds(50)
    scenario += unified_staking_pool.deposit(
        sp.record(token_amount=alices_stake, stake_id=6)
    ).run(sender=alice.address, now=now)
    scenario += staking_token.mint(
        owner=unified_staking_pool.address,
        token_id=token_id,
        token_amount=reward_payout,
    )

    scenario.p("Alice withdraws full after half time of the second deposit")
    now = now.add_seconds(50)
    total_reward = 2 * reward_payout
    # when alice deposits the second time, her stake has grown to 2x, this means we have 1x age of 0 and 2x age of 50 == an age of 33 days. Add the 50 days to that we end up at the 83 days used below.
    alices_balance += total_reward * 83 // 100 - 69
    remaining_reward = total_reward * 17 // 100 + 90
    scenario += unified_staking_pool.withdraw(
        sp.record(ratio_numerator=1, ratio_denominator=1, stake_id=6)
    ).run(sender=alice.address, now=now)
    scenario.verify_equal(staking_token.data.ledger[alice_ledger_key], alices_balance)
    scenario.verify_equal(
        staking_token.data.ledger[unified_staking_pool_key], remaining_reward
    )

    scenario.h2("Multi User Flows")
    scenario.p("create a new staking pool")
    now = sp.timestamp(0)
    bobs_stake = 1 * Constants.PRECISION_FACTOR
    bobs_balance = initial_balance

    unified_staking_pool = UnifiedStakingPool(
        staking_token.address, token_id, 100, {administrator.address: 1}
    )
    scenario += unified_staking_pool
    unified_staking_pool_key = LedgerKey.make(0, unified_staking_pool.address)
    scenario += staking_token.update_operators(
        [
            sp.variant(
                "add_operator",
                sp.record(
                    owner=alice.address,
                    operator=unified_staking_pool.address,
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
                    owner=dan.address,
                    operator=unified_staking_pool.address,
                    token_id=token_id,
                ),
            )
        ]
    ).run(sender=dan.address)
    scenario += staking_token.update_operators(
        [
            sp.variant(
                "add_operator",
                sp.record(
                    owner=bob.address,
                    operator=unified_staking_pool.address,
                    token_id=token_id,
                ),
            )
        ]
    ).run(sender=bob.address)

    scenario.p("Alice stakes 1 token")
    scenario += unified_staking_pool.deposit(
        sp.record(token_amount=alices_stake, stake_id=0)
    ).run(sender=alice.address, now=now)
    scenario.p("Reward is paid")
    scenario += staking_token.mint(
        owner=unified_staking_pool.address,
        token_id=token_id,
        token_amount=reward_payout,
    )
    scenario.p("Bob stakes 1 token")
    scenario += unified_staking_pool.deposit(
        sp.record(token_amount=bobs_stake, stake_id=0)
    ).run(sender=bob.address, now=now)
    scenario.p("Reward is paid")
    scenario += staking_token.mint(
        owner=unified_staking_pool.address,
        token_id=token_id,
        token_amount=reward_payout,
    )
    now = now.add_seconds(50)
    scenario.p("Bob exits after half time")
    scenario += unified_staking_pool.withdraw(
        sp.record(ratio_numerator=1, ratio_denominator=1, stake_id=2)
    ).run(sender=bob.address, now=now)
    bobs_balance += reward_payout // 3 // 2
    scenario.verify_equal(staking_token.data.ledger[bob_ledger_key], bobs_balance)

    scenario.p("Bob enters again after 50")
    now = now.add_seconds(50)
    scenario += unified_staking_pool.deposit(
        sp.record(token_amount=bobs_stake, stake_id=0)
    ).run(sender=bob.address, now=now)
    scenario.p("Reward is paid")
    scenario += staking_token.mint(
        owner=unified_staking_pool.address,
        token_id=token_id,
        token_amount=reward_payout,
    )
    now = now.add_seconds(50)
    scenario.p("Bob increases stake")
    scenario += unified_staking_pool.deposit(
        sp.record(token_amount=bobs_stake, stake_id=3)
    ).run(sender=bob.address, now=now)
    scenario += staking_token.mint(
        owner=unified_staking_pool.address,
        token_id=token_id,
        token_amount=reward_payout,
    )
    scenario.p("Bob exits half after half time")
    now = now.add_seconds(50)
    scenario += unified_staking_pool.withdraw(
        sp.record(ratio_numerator=1, ratio_denominator=2, stake_id=3)
    ).run(sender=bob.address, now=now)
    bobs_balance += (
        reward_payout * 6 * 77 // 23 // 100 // 2
    )  # alice has 2 + 5//6 weight to start -> 17//6 in total its 23//6 bob makes 6//6 of these. The rewards are then time adapted to: 77/100
    bobs_balance += (
        reward_payout * 312 * 77 // 805 // 100 // 2
    )  # after 50 alice has 17//6 + 17//23 == 493/138 and bob 1 + 6//23 + 1 == 52//23 ==> the total is 35//6. The rewards are then time adapted to:
    bobs_balance -= (
        bobs_stake + 4
    )  # one stake stays because only half is withdrawn, 4 is inacuracy.
    scenario.verify_equal(staking_token.data.ledger[bob_ledger_key], bobs_balance)
    scenario.p("Bob exits second half when time is up")
    now = now.add_seconds(50)
    scenario += unified_staking_pool.withdraw(
        sp.record(ratio_numerator=1, ratio_denominator=1, stake_id=3)
    ).run(sender=bob.address, now=now)
    scenario.p("Alice exits when time is up")
    scenario += unified_staking_pool.withdraw(
        sp.record(ratio_numerator=1, ratio_denominator=1, stake_id=1)
    ).run(sender=alice.address, now=now)
    scenario.verify_equal(
        staking_token.data.ledger[unified_staking_pool_key], 9
    )  # 9 is a rest...

    scenario.h2("Withdrawal Smurfing")
    scenario.p("create a new staking pool")
    now = sp.timestamp(0)
    dans_stake = 1 * Constants.PRECISION_FACTOR
    dans_balance = initial_balance

    unified_staking_pool = UnifiedStakingPool(
        staking_token.address, token_id, 100, {administrator.address: 1}
    )
    scenario += unified_staking_pool
    unified_staking_pool_key = LedgerKey.make(0, unified_staking_pool.address)
    scenario += staking_token.update_operators(
        [
            sp.variant(
                "add_operator",
                sp.record(
                    owner=alice.address,
                    operator=unified_staking_pool.address,
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
                    owner=dan.address,
                    operator=unified_staking_pool.address,
                    token_id=token_id,
                ),
            )
        ]
    ).run(sender=dan.address)
    scenario += staking_token.update_operators(
        [
            sp.variant(
                "add_operator",
                sp.record(
                    owner=bob.address,
                    operator=unified_staking_pool.address,
                    token_id=token_id,
                ),
            )
        ]
    ).run(sender=bob.address)

    scenario += unified_staking_pool.deposit(
        sp.record(token_amount=bobs_stake, stake_id=0)
    ).run(sender=bob.address, now=now)
    scenario += unified_staking_pool.deposit(
        sp.record(token_amount=dans_stake, stake_id=0)
    ).run(sender=dan.address, now=now)
    scenario += staking_token.mint(
        owner=unified_staking_pool.address,
        token_id=token_id,
        token_amount=reward_payout,
    )
    now = now.add_seconds(100)
    for i in range(10):
        scenario += unified_staking_pool.withdraw(
            sp.record(ratio_numerator=1, ratio_denominator=10, stake_id=2)
        ).run(sender=dan.address, now=now)
    scenario += unified_staking_pool.withdraw(
        sp.record(ratio_numerator=1, ratio_denominator=1, stake_id=2)
    ).run(sender=dan.address, now=now)
    dans_balance += reward_payout // 2
    scenario.verify_equal(staking_token.data.ledger[dan_ledger_key], dans_balance)
    scenario += unified_staking_pool.deposit(
        sp.record(token_amount=bobs_stake, stake_id=0)
    ).run(sender=alice.address, now=now)

    scenario.h2("Not allowed cases")
    scenario.p("cannot deposit in non-existing stake_id")
    scenario += unified_staking_pool.deposit(
        sp.record(token_amount=bobs_stake, stake_id=10)
    ).run(sender=bob.address, now=now, valid=False)
    scenario.p("cannot deposit in not-own stake_id")
    scenario += unified_staking_pool.deposit(
        sp.record(token_amount=bobs_stake, stake_id=3)
    ).run(sender=bob.address, now=now, valid=False)
    scenario.p("can only deposit in own stake_id")
    scenario += unified_staking_pool.deposit(
        sp.record(token_amount=bobs_stake, stake_id=1)
    ).run(sender=bob.address, now=now, valid=True)
    scenario += unified_staking_pool.deposit(
        sp.record(token_amount=bobs_stake, stake_id=3)
    ).run(sender=alice.address, now=now, valid=True)

    scenario.p("cannot withdraw in non-existing stake_id")
    scenario += unified_staking_pool.withdraw(
        sp.record(ratio_numerator=1, ratio_denominator=2, stake_id=10)
    ).run(sender=bob.address, now=now, valid=False)
    scenario.p("cannot deposit in not-own stake_id")
    scenario += unified_staking_pool.withdraw(
        sp.record(ratio_numerator=1, ratio_denominator=2, stake_id=3)
    ).run(sender=bob.address, now=now, valid=False)
    scenario.p("can only withdraw in own stake_id")
    scenario += unified_staking_pool.withdraw(
        sp.record(ratio_numerator=1, ratio_denominator=2, stake_id=1)
    ).run(sender=bob.address, now=now, valid=True)
    scenario += unified_staking_pool.withdraw(
        sp.record(ratio_numerator=1, ratio_denominator=2, stake_id=3)
    ).run(sender=alice.address, now=now, valid=True)

    scenario.p("cannot withdraw with ration >1")
    scenario += unified_staking_pool.withdraw(
        sp.record(ratio_numerator=11, ratio_denominator=10, stake_id=1)
    ).run(sender=bob.address, now=now, valid=False)
    scenario.p("can withdraw with ration ==1")
    scenario += unified_staking_pool.withdraw(
        sp.record(ratio_numerator=11, ratio_denominator=11, stake_id=1)
    ).run(sender=bob.address, now=now, valid=True)

    scenario.h2("Testing the transfer of stake")
    scenario.p("cannot transfer someone elses stake")
    scenario += unified_staking_pool.transfer(
        [
            Transfer.item(
                alice.address, [sp.record(to_=bob.address, token_id=3, amount=1)]
            )
        ]
    ).run(sender=bob.address, now=now, valid=False)
    scenario.p("cannot transfer not existing stake")
    scenario += unified_staking_pool.transfer(
        [
            Transfer.item(
                alice.address, [sp.record(to_=bob.address, token_id=30, amount=1)]
            )
        ]
    ).run(sender=bob.address, now=now, valid=False)
    scenario.p("cannot transfer zero")
    scenario += unified_staking_pool.transfer(
        [
            Transfer.item(
                alice.address, [sp.record(to_=bob.address, token_id=3, amount=0)]
            )
        ]
    ).run(sender=alice.address, now=now, valid=False)
    scenario.p("cannot transfer more than 1")
    scenario += unified_staking_pool.transfer(
        [
            Transfer.item(
                alice.address, [sp.record(to_=bob.address, token_id=3, amount=2)]
            )
        ]
    ).run(sender=alice.address, now=now, valid=False)
    scenario.p("can transfer to self")
    scenario += unified_staking_pool.transfer(
        [
            Transfer.item(
                alice.address, [sp.record(to_=alice.address, token_id=3, amount=1)]
            )
        ]
    ).run(sender=alice.address, now=now, valid=True)
    scenario.p("can transfer own")
    scenario += unified_staking_pool.transfer(
        [
            Transfer.item(
                alice.address, [sp.record(to_=bob.address, token_id=3, amount=1)]
            )
        ]
    ).run(sender=alice.address, now=now, valid=True)

    scenario.h2("Testing the operators")
    scenario.p("alice cannot transfer not owned")
    scenario += unified_staking_pool.transfer(
        [
            Transfer.item(
                alice.address, [sp.record(to_=alice.address, token_id=3, amount=1)]
            )
        ]
    ).run(sender=alice.address, now=now, valid=False)
    scenario.p("cannot add operators of not owned")
    scenario += unified_staking_pool.update_operators(
        [
            sp.variant(
                "add_operator",
                sp.record(owner=bob.address, operator=bob.address, token_id=3),
            )
        ]
    ).run(sender=alice.address, valid=False)
    scenario.p("can add operators when owned")
    scenario += unified_staking_pool.update_operators(
        [
            sp.variant(
                "add_operator",
                sp.record(owner=bob.address, operator=alice.address, token_id=3),
            )
        ]
    ).run(sender=bob.address, valid=True)
    scenario.p("cannot delete operator if not owner")
    scenario += unified_staking_pool.update_operators(
        [
            sp.variant(
                "remove_operator",
                sp.record(owner=bob.address, operator=alice.address, token_id=3),
            )
        ]
    ).run(sender=alice.address, valid=False)
    scenario.p("now alice can transfer on bobs behalf (self transfer)")
    scenario += unified_staking_pool.transfer(
        [Transfer.item(bob.address, [sp.record(to_=bob.address, token_id=3, amount=1)])]
    ).run(sender=alice.address, now=now, valid=True)
    scenario.p("can delete operator if owner")
    scenario += unified_staking_pool.update_operators(
        [
            sp.variant(
                "remove_operator",
                sp.record(owner=bob.address, operator=alice.address, token_id=3),
            )
        ]
    ).run(sender=bob.address, valid=True)
    scenario.p("after delete cannot transfer")
    scenario += unified_staking_pool.transfer(
        [
            Transfer.item(
                bob.address, [sp.record(to_=alice.address, token_id=3, amount=1)]
            )
        ]
    ).run(sender=alice.address, now=now, valid=False)
    scenario.p("now alice can transfer on bobs behalf (after readding)")
    scenario += unified_staking_pool.update_operators(
        [
            sp.variant(
                "add_operator",
                sp.record(owner=bob.address, operator=alice.address, token_id=3),
            )
        ]
    ).run(sender=bob.address, valid=True)
    scenario += unified_staking_pool.transfer(
        [
            Transfer.item(
                bob.address, [sp.record(to_=alice.address, token_id=3, amount=1)]
            )
        ]
    ).run(sender=alice.address, now=now, valid=True)
    scenario.p("cannot reclaim power")
    scenario += unified_staking_pool.update_operators(
        [
            sp.variant(
                "add_operator",
                sp.record(owner=alice.address, operator=bob.address, token_id=3),
            )
        ]
    ).run(sender=bob.address, valid=False)
    scenario += unified_staking_pool.transfer(
        [
            Transfer.item(
                alice.address, [sp.record(to_=bob.address, token_id=3, amount=1)]
            )
        ]
    ).run(sender=bob.address, now=now, valid=False)

    scenario.h2("Exchange functions")
    scenario.p("bootstrapping")
    exchange_oracle = DummyExchangeOracle()
    scenario += exchange_oracle
    scenario.verify(exchange_oracle.get_min_out(2) == 2)

    exchange_token = DummyFA2(
        {LedgerKey.make(token_id, administrator.address): sp.unit}
    )
    scenario += exchange_token
    scenario += exchange_token.set_token_metadata(
        token_id=token_id, token_info=sp.map()
    ).run(sender=administrator)
    scenario += exchange_token.mint(
        owner=unified_staking_pool.address,
        token_id=token_id,
        token_amount=initial_balance,
    )
    exchange_token_key = LedgerKey.make(0, exchange_token.address)

    def execute_fa2_token_transfer(token_address, to_, token_id, amount):
        transfer_token_contract = sp.contract(
            Transfer.get_batch_type(), token_address, entry_point="transfer"
        ).open_some()
        transfer_payload = [
            Transfer.item(
                sp.self_address, [sp.record(to_=to_, token_id=token_id, amount=amount)]
            )
        ]
        return sp.transfer_operation(
            transfer_payload, sp.mutez(0), transfer_token_contract
        )

    def execute_mint(token_address, owner, token_id, amount):
        token_contract = sp.contract(
            RecipientTokenAmount.get_type(), token_address, entry_point="mint"
        ).open_some()
        payload = RecipientTokenAmount.make(owner, token_id, amount)
        return sp.transfer_operation(payload, sp.mutez(0), token_contract)

    def exchange_lambda(pair):
        sp.set_type(pair, sp.TPair(sp.TNat, sp.TNat))
        sp.result(
            sp.list(
                [
                    execute_fa2_token_transfer(
                        exchange_token.address, staking_token.address, 0, sp.fst(pair)
                    ),
                    execute_mint(
                        staking_token.address,
                        unified_staking_pool.address,
                        0,
                        sp.snd(pair),
                    ),
                ]
            )
        )

    exchange_key = ExchangeKey.make(
        src_token_id=0,
        src_token_address=exchange_token.address,
        dst_token_id=0,
        dst_token_address=staking_token.address,
    )
    exchange_value = ExchangeValue.make(
        oracle_address=exchange_oracle.address, execution_lambda=exchange_lambda
    )
    scenario.p("cannot set exchange if not admin")
    scenario += unified_staking_pool.set_exchange(
        exchange_key=exchange_key, exchange_value=exchange_value
    ).run(sender=bob.address, now=now, valid=False)
    scenario.p("admin can set exchange")
    scenario += unified_staking_pool.set_exchange(
        exchange_key=exchange_key, exchange_value=exchange_value
    ).run(sender=administrator.address, now=now, valid=True)
    scenario.p("cannot remove exchange if not admin")
    scenario += unified_staking_pool.remove_exchange(exchange_key).run(
        sender=bob.address, now=now, valid=False
    )
    scenario.p("admin can remove exchange")
    scenario += unified_staking_pool.remove_exchange(exchange_key).run(
        sender=administrator.address, now=now, valid=True
    )
    scenario.p("cannot exchange if not existing")
    scenario += unified_staking_pool.swap(
        [sp.record(exchange_key=exchange_key, token_amount=reward_payout)]
    ).run(sender=dan.address, now=now, valid=False)
    scenario.p("anyone can exchange if existing")
    scenario += unified_staking_pool.set_exchange(
        exchange_key=exchange_key, exchange_value=exchange_value
    ).run(sender=administrator.address, now=now, valid=True)
    scenario.p("cannot swap with wrong timestamp")
    scenario += unified_staking_pool.swap(
        [sp.record(exchange_key=exchange_key, token_amount=reward_payout)]
    ).run(sender=dan.address, now=now, valid=False)
    scenario.p("can swap within right time slot")
    now = sp.timestamp(1652850001)
    scenario += unified_staking_pool.swap(
        [sp.record(exchange_key=exchange_key, token_amount=reward_payout)]
    ).run(sender=dan.address, now=now, valid=True)
    scenario.verify_equal(
        exchange_token.data.ledger[unified_staking_pool_key],
        initial_balance - reward_payout,
    )
    scenario.verify_equal(exchange_token.data.ledger[staking_token_key], reward_payout)

    scenario.h2("Testing Views")
    scenario.verify_equal(
        unified_staking_pool.view_balance(sp.record(address=alice.address, token_id=3)),
        1,
    )
    scenario.verify_equal(
        unified_staking_pool.view_balance(sp.record(address=bob.address, token_id=3)), 0
    )
    scenario.verify_equal(
        unified_staking_pool.view_balance(sp.record(address=dan.address, token_id=3)), 0
    )
    scenario.verify_equal(
        unified_staking_pool.view_is_operator(
            sp.record(token_id=3, owner=bob.address, operator=alice.address)
        ),
        True,
    )
    scenario.verify_equal(
        unified_staking_pool.view_is_operator(
            sp.record(token_id=3, owner=bob.address, operator=bob.address)
        ),
        False,
    )
    scenario.verify_equal(unified_staking_pool.view_stake(3).token_amount, alices_stake)
    scenario.verify_equal(unified_staking_pool.view_max_release_period(), 100)
    scenario.verify_equal(
        unified_staking_pool.view_administrator_state(alice.address), -1
    )
    scenario.verify_equal(
        unified_staking_pool.view_administrator_state(administrator.address), 1
    )
    scenario.verify_equal(unified_staking_pool.view_last_stake_id(), 3)
    scenario.verify_equal(
        unified_staking_pool.view_owner_stakes(alice.address), sp.set([3])
    )
    scenario.verify(unified_staking_pool.view_disc_factor() > 0)
    scenario.verify(unified_staking_pool.view_total_stake() > 0)
