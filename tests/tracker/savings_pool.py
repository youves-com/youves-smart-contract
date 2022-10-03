import smartpy as sp

import utils.constants as Constants
import utils.fa2 as fa2

from utils.contract_utils import Utils

import contracts.tracker.vester as vester
from contracts.tracker.savings_pool import SavingsPool


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

    @sp.entry_point
    def burn(self, recipient_token_amount):
        sp.set_type(recipient_token_amount, fa2.RecipientTokenAmount.get_type())
        self.data.ledger[
            fa2.LedgerKey.make(
                recipient_token_amount.token_id, recipient_token_amount.owner
            )
        ] = sp.as_nat(
            self.data.ledger[
                fa2.LedgerKey.make(
                    recipient_token_amount.token_id, recipient_token_amount.owner
                )
            ]
            - recipient_token_amount.token_amount
        )


@sp.add_test(name="Savings Pool")
def test():
    scenario = sp.test_scenario()
    scenario.add_flag("protocol", "ithaca")
    scenario.h1("Savings Pool Unit Test")
    scenario.table_of_contents()

    scenario.h2("Bootstrapping")
    token_id = sp.nat(0)

    administrator = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob = sp.test_account("Robert")
    dan = sp.test_account("Dan")

    scenario.show([administrator, alice, bob, dan])

    staking_token = DummyFA2(
        {fa2.LedgerKey.make(token_id, administrator.address): sp.unit}
    )
    scenario += staking_token

    tracker_engine = DummyEngine(staking_token.address)
    scenario += tracker_engine

    scenario += staking_token.set_token_metadata(
        token_id=token_id, token_info=sp.map()
    ).run(sender=administrator)

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

    savings_pool = SavingsPool(
        tracker_engine.address,
        staking_token.address,
        token_id,
        {fa2.LedgerKey.make(sp.nat(0), administrator.address): sp.unit},
    )
    scenario += savings_pool
    scenario += tracker_engine.set_pool_contract(savings_pool.address)

    scenario.h2("Start staking")
    scenario += staking_token.update_operators(
        [
            sp.variant(
                "add_operator",
                sp.record(
                    owner=alice.address,
                    operator=savings_pool.address,
                    token_id=token_id,
                ),
            )
        ]
    ).run(sender=alice.address)
    scenario += savings_pool.deposit(1 * Constants.PRECISION_FACTOR).run(sender=alice)

    scenario.h2("Claim after a week")
    now = sp.timestamp(Constants.SECONDS_PER_WEEK)

    scenario += savings_pool.withdraw().run(
        sender=alice, now=now, valid=False
    )  # Vesting contract not set.

    # Set vesting contract before any withdraw operation can happen
    vesting_contract = vester.Vester(staking_token.address, token_id)
    scenario += vesting_contract

    params = sp.record(
        contract=vesting_contract.address,
        duration_in_seconds=Constants.DEFAULT_VESTING_DURATION_IN_SECONDS,
    )
    scenario += savings_pool.set_vesting_contract(params).run(sender=administrator)
    scenario.verify_equal(savings_pool.data.vesting_contract, vesting_contract.address)
    scenario.verify_equal(
        savings_pool.data.vesting_duration_in_seconds,
        Constants.DEFAULT_VESTING_DURATION_IN_SECONDS,
    )
    scenario.verify(
        staking_token.data.operators.contains(
            fa2.OperatorKey.make(
                savings_pool.data.token_id,
                savings_pool.address,
                vesting_contract.address,
            )
        )
    )

    scenario += savings_pool.withdraw().run(sender=alice, now=now)
    scenario.verify_equal(
        staking_token.data.ledger[fa2.LedgerKey.make(0, vesting_contract.address)],
        Constants.SECONDS_PER_WEEK + 1 * Constants.PRECISION_FACTOR,
    )

    alices_weight = Constants.SECONDS_PER_WEEK + 1 * Constants.PRECISION_FACTOR
    total_weight = alices_weight

    scenario.p("Multiclaim yields nothing")
    scenario += savings_pool.withdraw().run(sender=alice, now=now, valid=False)
    scenario.verify_equal(
        staking_token.data.ledger[fa2.LedgerKey.make(0, vesting_contract.address)],
        total_weight,
    )

    scenario.p("Put back what was withdrawed")
    scenario += vesting_contract.divest(
        [vester.DivestingOperation.make(savings_pool.address, alice.address)]
    ).run(
        sender=alice.address,
        now=now.add_seconds(Constants.DEFAULT_VESTING_DURATION_IN_SECONDS),
    )
    scenario.verify_equal(
        staking_token.data.ledger[fa2.LedgerKey.make(0, alice.address)], alices_weight
    )
    scenario += savings_pool.deposit(
        Constants.SECONDS_PER_WEEK + 1 * Constants.PRECISION_FACTOR
    ).run(sender=alice, now=now)

    scenario.h2("Bob joins after a week")
    now = sp.timestamp(Constants.SECONDS_PER_WEEK * 2)
    scenario += staking_token.update_operators(
        [
            sp.variant(
                "add_operator",
                sp.record(
                    owner=bob.address, operator=savings_pool.address, token_id=token_id
                ),
            )
        ]
    ).run(sender=bob.address)
    scenario += savings_pool.deposit(1 * Constants.PRECISION_FACTOR).run(
        sender=bob, now=now
    )

    alices_weight += Constants.SECONDS_PER_WEEK
    bobs_weight = 1 * Constants.PRECISION_FACTOR
    total_weight = alices_weight + bobs_weight

    scenario.p("Both claim after 3 weeks")
    now = sp.timestamp(Constants.SECONDS_PER_WEEK * 3)

    scenario += savings_pool.withdraw().run(sender=alice, now=now)
    scenario += savings_pool.withdraw().run(sender=bob, now=now)

    alices_weight += Constants.SECONDS_PER_WEEK * alices_weight // total_weight
    bobs_weight += Constants.SECONDS_PER_WEEK * bobs_weight // total_weight
    total_weight = alices_weight + bobs_weight

    scenario.verify_equal(
        staking_token.data.ledger[fa2.LedgerKey.make(0, vesting_contract.address)],
        total_weight,
    )

    scenario.p("Put back what was withdrawed")
    scenario += vesting_contract.divest(
        [vester.DivestingOperation.make(savings_pool.address, alice.address)]
    ).run(
        sender=alice.address,
        now=now.add_seconds(Constants.DEFAULT_VESTING_DURATION_IN_SECONDS),
    )
    scenario += vesting_contract.divest(
        [vester.DivestingOperation.make(savings_pool.address, bob.address)]
    ).run(
        sender=bob.address,
        now=now.add_seconds(Constants.DEFAULT_VESTING_DURATION_IN_SECONDS),
    )
    scenario.verify_equal(
        staking_token.data.ledger[fa2.LedgerKey.make(0, alice.address)], alices_weight
    )
    scenario.verify_equal(
        staking_token.data.ledger[fa2.LedgerKey.make(0, bob.address)], bobs_weight
    )

    scenario += savings_pool.deposit(alices_weight).run(sender=alice, now=now)
    scenario += savings_pool.deposit(bobs_weight).run(sender=bob, now=now)

    scenario.h2("Fixed rewards randomly flies in")
    scenario += staking_token.mint(
        owner=savings_pool.address,
        token_id=token_id,
        token_amount=1 * Constants.PRECISION_FACTOR,
    ).run(now=now)

    alices_weight += Constants.PRECISION_FACTOR * alices_weight // total_weight
    bobs_weight += Constants.PRECISION_FACTOR * bobs_weight // total_weight
    total_weight = alices_weight + bobs_weight

    scenario.p("Dan joins late (not ellegible for fixed reward")
    now = sp.timestamp(Constants.SECONDS_PER_WEEK * 4)
    scenario += staking_token.update_operators(
        [
            sp.variant(
                "add_operator",
                sp.record(
                    owner=dan.address, operator=savings_pool.address, token_id=token_id
                ),
            )
        ]
    ).run(sender=dan.address)
    scenario += savings_pool.deposit(1 * Constants.PRECISION_FACTOR).run(
        sender=dan, now=now
    )

    alices_weight += Constants.SECONDS_PER_WEEK * alices_weight // total_weight
    bobs_weight += Constants.SECONDS_PER_WEEK * bobs_weight // total_weight
    dans_weight = 1 * Constants.PRECISION_FACTOR
    total_weight = alices_weight + bobs_weight + dans_weight

    scenario.p("All claim after 5 weeks")
    now = sp.timestamp(Constants.SECONDS_PER_WEEK * 5)

    alices_weight += Constants.SECONDS_PER_WEEK * alices_weight // total_weight
    bobs_weight += Constants.SECONDS_PER_WEEK * bobs_weight // total_weight
    dans_weight += Constants.SECONDS_PER_WEEK * dans_weight // total_weight
    total_weight = alices_weight + bobs_weight + dans_weight

    scenario += savings_pool.withdraw().run(sender=alice, now=now)
    scenario += savings_pool.withdraw().run(sender=bob, now=now)
    scenario += savings_pool.withdraw().run(sender=dan, now=now)

    scenario.verify_equal(
        staking_token.data.ledger[fa2.LedgerKey.make(0, vesting_contract.address)],
        total_weight,
    )

    scenario.p("Put back what was withdrawed")
    scenario += vesting_contract.divest(
        [vester.DivestingOperation.make(savings_pool.address, alice.address)]
    ).run(
        sender=alice.address,
        now=now.add_seconds(Constants.DEFAULT_VESTING_DURATION_IN_SECONDS),
    )
    scenario += vesting_contract.divest(
        [vester.DivestingOperation.make(savings_pool.address, bob.address)]
    ).run(
        sender=bob.address,
        now=now.add_seconds(Constants.DEFAULT_VESTING_DURATION_IN_SECONDS),
    )
    scenario += vesting_contract.divest(
        [vester.DivestingOperation.make(savings_pool.address, dan.address)]
    ).run(
        sender=dan.address,
        now=now.add_seconds(Constants.DEFAULT_VESTING_DURATION_IN_SECONDS),
    )

    scenario.verify_equal(
        staking_token.data.ledger[fa2.LedgerKey.make(0, alice.address)],
        alices_weight + 1,
    )
    scenario.verify_equal(
        staking_token.data.ledger[fa2.LedgerKey.make(0, bob.address)], bobs_weight
    )
    scenario.verify_equal(
        staking_token.data.ledger[fa2.LedgerKey.make(0, dan.address)], dans_weight - 1
    )

    scenario += savings_pool.deposit(alices_weight + 1).run(sender=alice, now=now)
    scenario += savings_pool.deposit(bobs_weight).run(sender=bob, now=now)
    scenario += savings_pool.deposit(dans_weight - 1).run(sender=dan, now=now)

    scenario.h2("Dan leaves after 6 weeks and rejoins after 7")
    now = sp.timestamp(Constants.SECONDS_PER_WEEK * 6)

    alices_weight += Constants.SECONDS_PER_WEEK * alices_weight // total_weight
    bobs_weight += Constants.SECONDS_PER_WEEK * bobs_weight // total_weight
    dans_weight += Constants.SECONDS_PER_WEEK * dans_weight // total_weight
    total_weight = alices_weight + bobs_weight

    scenario += savings_pool.withdraw().run(sender=dan, now=now)
    scenario.verify_equal(
        staking_token.data.ledger[fa2.LedgerKey.make(0, vesting_contract.address)],
        dans_weight - 2,
    )
    scenario += vesting_contract.divest(
        [vester.DivestingOperation.make(savings_pool.address, dan.address)]
    ).run(
        sender=dan.address,
        now=now.add_seconds(Constants.DEFAULT_VESTING_DURATION_IN_SECONDS),
    )
    scenario.verify_equal(
        staking_token.data.ledger[fa2.LedgerKey.make(0, dan.address)], dans_weight - 2
    )

    scenario.p("Rejoins")
    now = sp.timestamp(Constants.SECONDS_PER_WEEK * 7)

    scenario += savings_pool.deposit(dans_weight - 2).run(sender=dan, now=now)

    alices_weight += Constants.SECONDS_PER_WEEK * alices_weight // total_weight
    bobs_weight += Constants.SECONDS_PER_WEEK * bobs_weight // total_weight
    dans_weight = dans_weight - 2
    total_weight = alices_weight + bobs_weight + dans_weight

    scenario += savings_pool.withdraw().run(sender=alice, now=now)
    scenario += savings_pool.withdraw().run(sender=bob, now=now)
    scenario += savings_pool.withdraw().run(sender=dan, now=now)

    scenario.verify_equal(
        staking_token.data.ledger[fa2.LedgerKey.make(0, vesting_contract.address)],
        total_weight,
    )

    scenario += vesting_contract.divest(
        [vester.DivestingOperation.make(savings_pool.address, alice.address)]
    ).run(
        sender=alice.address,
        now=now.add_seconds(Constants.DEFAULT_VESTING_DURATION_IN_SECONDS),
    )
    scenario += vesting_contract.divest(
        [vester.DivestingOperation.make(savings_pool.address, bob.address)]
    ).run(
        sender=bob.address,
        now=now.add_seconds(Constants.DEFAULT_VESTING_DURATION_IN_SECONDS),
    )
    scenario += vesting_contract.divest(
        [vester.DivestingOperation.make(savings_pool.address, dan.address)]
    ).run(
        sender=dan.address,
        now=now.add_seconds(Constants.DEFAULT_VESTING_DURATION_IN_SECONDS),
    )

    scenario.verify_equal(
        staking_token.data.ledger[fa2.LedgerKey.make(0, alice.address)],
        alices_weight + 1,
    )
    scenario.verify_equal(
        staking_token.data.ledger[fa2.LedgerKey.make(0, bob.address)], bobs_weight
    )
    scenario.verify_equal(
        staking_token.data.ledger[fa2.LedgerKey.make(0, dan.address)], dans_weight - 1
    )

    scenario.p("Put back what was withdrawed")
    scenario += savings_pool.deposit(alices_weight + 1).run(sender=alice, now=now)
    scenario += savings_pool.deposit(bobs_weight).run(sender=bob, now=now)
    scenario += savings_pool.deposit(dans_weight - 1).run(sender=dan, now=now)

    scenario += staking_token.burn(
        owner=savings_pool.address,
        token_id=token_id,
        token_amount=1 * Constants.PRECISION_FACTOR,
    ).run(sender=savings_pool.address, now=now)
    scenario += savings_pool.default().run(
        sender=staking_token.address, amount=sp.tez(10), now=now
    )

    alices_weight -= 1 * Constants.PRECISION_FACTOR * alices_weight // total_weight
    bobs_weight -= 1 * Constants.PRECISION_FACTOR * bobs_weight // total_weight
    dans_weight -= 1 * Constants.PRECISION_FACTOR * dans_weight // total_weight
    total_weight = alices_weight + bobs_weight + dans_weight

    # now = sp.timestamp(Constants.SECONDS_PER_WEEK*7)

    # alices_weight += Constants.SECONDS_PER_WEEK*alices_weight//total_weight
    # bobs_weight += Constants.SECONDS_PER_WEEK*bobs_weight//total_weight
    # dans_weight += Constants.SECONDS_PER_WEEK*dans_weight//total_weight
    # total_weight = alices_weight + bobs_weight + dans_weight

    scenario += savings_pool.withdraw().run(sender=alice, now=now)
    scenario.show(sp.tez(10) - sp.split_tokens(sp.tez(10), alices_weight, total_weight))
    scenario.show(savings_pool.balance)
    estimated_contract_balance = sp.tez(10) - sp.split_tokens(
        sp.tez(10), alices_weight, total_weight
    )
    scenario.verify_equal(savings_pool.balance, estimated_contract_balance)
    scenario += savings_pool.withdraw().run(sender=bob, now=now)
    estimated_contract_balance -= sp.split_tokens(sp.tez(10), bobs_weight, total_weight)
    scenario.verify_equal(savings_pool.balance, estimated_contract_balance)
    scenario += savings_pool.withdraw().run(sender=dan, now=now)
    estimated_contract_balance -= sp.split_tokens(sp.tez(10), dans_weight, total_weight)
    scenario.verify_equal(
        savings_pool.balance, estimated_contract_balance + sp.mutez(1)
    )  # flooring error of 2 mutez...

    scenario.verify_equal(
        staking_token.data.ledger[fa2.LedgerKey.make(0, vesting_contract.address)],
        alices_weight + bobs_weight + dans_weight + 5,
    )
    scenario += vesting_contract.divest(
        [vester.DivestingOperation.make(savings_pool.address, alice.address)]
    ).run(
        sender=alice.address,
        now=now.add_seconds(Constants.DEFAULT_VESTING_DURATION_IN_SECONDS),
    )
    scenario += vesting_contract.divest(
        [vester.DivestingOperation.make(savings_pool.address, bob.address)]
    ).run(
        sender=bob.address,
        now=now.add_seconds(Constants.DEFAULT_VESTING_DURATION_IN_SECONDS),
    )
    scenario += vesting_contract.divest(
        [vester.DivestingOperation.make(savings_pool.address, dan.address)]
    ).run(
        sender=dan.address,
        now=now.add_seconds(Constants.DEFAULT_VESTING_DURATION_IN_SECONDS),
    )

    scenario.verify_equal(
        staking_token.data.ledger[fa2.LedgerKey.make(0, alice.address)],
        alices_weight + 4,
    )
    scenario.verify_equal(
        staking_token.data.ledger[fa2.LedgerKey.make(0, bob.address)], bobs_weight + 1
    )
    scenario.verify_equal(
        staking_token.data.ledger[fa2.LedgerKey.make(0, dan.address)], dans_weight
    )
    scenario.verify_equal(
        savings_pool.balance, sp.mutez(2)
    )  # flooring error of 2 mutez...
