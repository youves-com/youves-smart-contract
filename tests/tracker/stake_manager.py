import smartpy as sp

import utils.constants as Constants
import utils.fa2 as fa2

from contracts.tracker.governance_token import Stake
from contracts.tracker.governance_token import GovernanceToken
from contracts.tracker.stake_manager import StakeManager


@sp.add_test(name="Stake Manager")
def test():
    scenario = sp.test_scenario()
    scenario.h1("Governance Stake Manager")
    scenario.table_of_contents()

    scenario.h2("Bootstrapping")
    administrator = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob = sp.test_account("Robert")
    dan = sp.test_account("Dan")
    source1 = sp.test_account("Source1")
    source2 = sp.test_account("Source2")

    fixed_stake1 = sp.test_account("Fixed Stake Receiver 1")
    fixed_stake2 = sp.test_account("Fixed Stake Receiver 2")

    scenario.h2("Accounts")
    scenario.show([administrator, alice, bob, dan])

    scenario.p("Governance Token")
    governance_token = GovernanceToken(
        administrator.address,
        {
            fa2.LedgerKey.make(
                Constants.GOVERNANCE_TOKEN_ID, administrator.address
            ): sp.unit
        },
    )
    scenario += governance_token

    scenario.p("Stake Manager")
    stake_manager = StakeManager(
        governance_token.address,
        sp.big_map(
            {
                fa2.LedgerKey.make(
                    Constants.GOVERNANCE_TOKEN_ID, administrator.address
                ): sp.unit,
                fa2.LedgerKey.make(
                    Constants.GOVERNANCE_TOKEN_ID, source1.address
                ): sp.unit,
                fa2.LedgerKey.make(
                    Constants.GOVERNANCE_TOKEN_ID, source2.address
                ): sp.unit,
            }
        ),
    )
    scenario += stake_manager
    scenario += governance_token.set_administrator(
        token_id=Constants.GOVERNANCE_TOKEN_ID,
        administrator_to_set=stake_manager.address,
    ).run(sender=administrator)

    scenario.h2("First Source sets Stake")
    scenario += stake_manager.update_stake(Stake.make(alice.address, sp.nat(10))).run(
        sender=source1
    )
    scenario += stake_manager.update_stake(Stake.make(bob.address, sp.nat(10))).run(
        sender=source1
    )
    scenario.verify_equal(governance_token.data.stakes[alice.address], sp.nat(10))
    scenario.verify_equal(governance_token.data.stakes[bob.address], sp.nat(10))
    scenario.verify_equal(governance_token.data.total_stake, sp.nat(20))

    scenario.h2("Second Source sets Stake (Cannot rewrite 1 source stake)")
    scenario += stake_manager.update_stake(Stake.make(alice.address, sp.nat(3))).run(
        sender=source2
    )
    scenario += stake_manager.update_stake(Stake.make(bob.address, sp.nat(3))).run(
        sender=source2
    )
    scenario.verify_equal(governance_token.data.stakes[alice.address], sp.nat(13))
    scenario.verify_equal(governance_token.data.stakes[bob.address], sp.nat(13))
    scenario.verify_equal(governance_token.data.total_stake, sp.nat(26))

    scenario.h2("First Updates")
    scenario += stake_manager.update_stake(Stake.make(alice.address, sp.nat(5))).run(
        sender=source1
    )
    scenario += stake_manager.update_stake(Stake.make(bob.address, sp.nat(5))).run(
        sender=source1
    )
    scenario.verify_equal(governance_token.data.stakes[alice.address], sp.nat(8))
    scenario.verify_equal(governance_token.data.stakes[bob.address], sp.nat(8))
    scenario.verify_equal(governance_token.data.total_stake, sp.nat(16))

    scenario.h2("Second Exits")
    scenario += stake_manager.update_stake(Stake.make(alice.address, sp.nat(0))).run(
        sender=source2
    )
    scenario += stake_manager.update_stake(Stake.make(bob.address, sp.nat(0))).run(
        sender=source2
    )
    scenario.verify_equal(governance_token.data.stakes[alice.address], sp.nat(5))
    scenario.verify_equal(governance_token.data.stakes[bob.address], sp.nat(5))
    scenario.verify_equal(governance_token.data.total_stake, sp.nat(10))

    scenario.h2("First Exits")
    scenario += stake_manager.update_stake(Stake.make(alice.address, sp.nat(0))).run(
        sender=source1
    )
    scenario += stake_manager.update_stake(Stake.make(bob.address, sp.nat(0))).run(
        sender=source1
    )
    scenario.verify_equal(governance_token.data.stakes.contains(alice.address), False)
    scenario.verify_equal(governance_token.data.stakes.contains(bob.address), False)
    scenario.verify_equal(governance_token.data.total_stake, sp.nat(0))

    scenario.h1("Staking Factors")
    scenario.p("Source 1 counts double")
    scenario += stake_manager.set_stake_factor(
        address=source1.address, factor=2 * Constants.PRECISION_FACTOR
    ).run(sender=source1)
    scenario += stake_manager.update_stake(Stake.make(alice.address, sp.nat(10))).run(
        sender=source1
    )
    scenario += stake_manager.update_stake(Stake.make(bob.address, sp.nat(10))).run(
        sender=source2
    )
    scenario.verify_equal(governance_token.data.stakes[alice.address], sp.nat(20))
    scenario.verify_equal(governance_token.data.stakes[bob.address], sp.nat(10))
    scenario.verify_equal(governance_token.data.total_stake, sp.nat(30))

    scenario.p("Source 1 counts half")
    scenario += stake_manager.set_stake_factor(
        address=source1.address, factor=int(0.5 * Constants.PRECISION_FACTOR)
    ).run(sender=source1)
    scenario += stake_manager.update_stake(Stake.make(alice.address, sp.nat(10))).run(
        sender=source1
    )
    scenario += stake_manager.update_stake(Stake.make(bob.address, sp.nat(10))).run(
        sender=source2
    )
    scenario.verify_equal(governance_token.data.stakes[alice.address], sp.nat(5))
    scenario.verify_equal(governance_token.data.stakes[bob.address], sp.nat(10))
    scenario.verify_equal(governance_token.data.total_stake, sp.nat(15))

    scenario.p("Source 1 counts single")
    scenario += stake_manager.set_stake_factor(
        address=source1.address, factor=1 * Constants.PRECISION_FACTOR
    ).run(sender=source1)
    scenario += stake_manager.update_stake(Stake.make(alice.address, sp.nat(10))).run(
        sender=source1
    )
    scenario += stake_manager.update_stake(Stake.make(bob.address, sp.nat(10))).run(
        sender=source2
    )
    scenario.verify_equal(governance_token.data.stakes[alice.address], sp.nat(10))
    scenario.verify_equal(governance_token.data.stakes[bob.address], sp.nat(10))
    scenario.verify_equal(governance_token.data.total_stake, sp.nat(20))

    scenario.p("Exit")
    scenario += stake_manager.update_stake(Stake.make(alice.address, sp.nat(0))).run(
        sender=source1
    )
    scenario += stake_manager.update_stake(Stake.make(bob.address, sp.nat(0))).run(
        sender=source2
    )
    scenario.verify_equal(governance_token.data.stakes.contains(alice.address), False)
    scenario.verify_equal(governance_token.data.stakes.contains(bob.address), False)
    scenario.verify_equal(governance_token.data.total_stake, sp.nat(0))

    scenario.h1("Fixed Stakes")
    scenario += stake_manager.set_fixed_stake(
        address=fixed_stake1.address, ratio=int(0.2 * Constants.PRECISION_FACTOR)
    ).run(sender=source1)
    scenario += stake_manager.set_fixed_stake(
        address=fixed_stake2.address, ratio=int(0.2 * Constants.PRECISION_FACTOR)
    ).run(sender=source1)

    scenario.p("Start")
    scenario += stake_manager.update_stake(Stake.make(alice.address, sp.nat(10))).run(
        sender=source1
    )
    scenario += stake_manager.update_stake(Stake.make(bob.address, sp.nat(10))).run(
        sender=source2
    )
    scenario += stake_manager.update_fixed_stakes(
        [fixed_stake1.address, fixed_stake2.address]
    ).run()
    scenario.verify_equal(governance_token.data.stakes[alice.address], sp.nat(10))
    scenario.verify_equal(governance_token.data.stakes[bob.address], sp.nat(10))
    scenario.verify_equal(governance_token.data.stakes[fixed_stake1.address], sp.nat(4))
    scenario.verify_equal(governance_token.data.stakes[fixed_stake2.address], sp.nat(4))
    scenario.verify_equal(governance_token.data.total_stake, sp.nat(28))

    scenario.p("Go more")
    scenario += stake_manager.update_stake(Stake.make(alice.address, sp.nat(20))).run(
        sender=source1
    )
    scenario += stake_manager.update_stake(Stake.make(bob.address, sp.nat(20))).run(
        sender=source2
    )
    scenario += stake_manager.update_fixed_stakes(
        [fixed_stake1.address, fixed_stake2.address]
    ).run()
    scenario.verify_equal(governance_token.data.stakes[alice.address], sp.nat(20))
    scenario.verify_equal(governance_token.data.stakes[bob.address], sp.nat(20))
    scenario.verify_equal(governance_token.data.stakes[fixed_stake1.address], sp.nat(8))
    scenario.verify_equal(governance_token.data.stakes[fixed_stake2.address], sp.nat(8))
    scenario.verify_equal(governance_token.data.total_stake, sp.nat(56))

    scenario.p("Go less")
    scenario += stake_manager.update_stake(Stake.make(alice.address, sp.nat(5))).run(
        sender=source1
    )
    scenario += stake_manager.update_stake(Stake.make(bob.address, sp.nat(5))).run(
        sender=source2
    )
    scenario += stake_manager.update_fixed_stakes(
        [fixed_stake1.address, fixed_stake2.address]
    ).run()
    scenario.verify_equal(governance_token.data.stakes[alice.address], sp.nat(5))
    scenario.verify_equal(governance_token.data.stakes[bob.address], sp.nat(5))
    scenario.verify_equal(governance_token.data.stakes[fixed_stake1.address], sp.nat(2))
    scenario.verify_equal(governance_token.data.stakes[fixed_stake2.address], sp.nat(2))
    scenario.verify_equal(governance_token.data.total_stake, sp.nat(14))

    scenario.p("Change Stake 2 to 0")
    scenario += stake_manager.set_fixed_stake(
        address=fixed_stake2.address, ratio=int(0 * Constants.PRECISION_FACTOR)
    ).run(sender=source1)
    scenario += stake_manager.update_stake(Stake.make(alice.address, sp.nat(5))).run(
        sender=source1
    )
    scenario += stake_manager.update_stake(Stake.make(bob.address, sp.nat(5))).run(
        sender=source2
    )
    scenario += stake_manager.update_fixed_stakes(
        [fixed_stake1.address, fixed_stake2.address]
    ).run()
    scenario.verify_equal(governance_token.data.stakes[alice.address], sp.nat(5))
    scenario.verify_equal(governance_token.data.stakes[bob.address], sp.nat(5))
    scenario.verify_equal(governance_token.data.stakes[fixed_stake1.address], sp.nat(2))
    # scenario.verify_equal(governance_token.data.stakes[fixed_stake2.address], sp.nat(0))
    scenario.verify_equal(governance_token.data.total_stake, sp.nat(12))

    scenario.p("Change Stake 2 to double")
    scenario += stake_manager.set_fixed_stake(
        address=fixed_stake2.address, ratio=int(0.4 * Constants.PRECISION_FACTOR)
    ).run(sender=source1)
    scenario += stake_manager.update_stake(Stake.make(alice.address, sp.nat(5))).run(
        sender=source1
    )
    scenario += stake_manager.update_stake(Stake.make(bob.address, sp.nat(5))).run(
        sender=source2
    )
    scenario += stake_manager.update_fixed_stakes(
        [fixed_stake1.address, fixed_stake2.address]
    ).run()
    scenario.verify_equal(governance_token.data.stakes[alice.address], sp.nat(5))
    scenario.verify_equal(governance_token.data.stakes[bob.address], sp.nat(5))
    scenario.verify_equal(governance_token.data.stakes[fixed_stake1.address], sp.nat(2))
    scenario.verify_equal(governance_token.data.stakes[fixed_stake2.address], sp.nat(4))
    scenario.verify_equal(governance_token.data.total_stake, sp.nat(16))

    scenario.p("Exit")
    scenario += stake_manager.update_stake(Stake.make(alice.address, sp.nat(0))).run(
        sender=source1
    )
    scenario += stake_manager.update_stake(Stake.make(bob.address, sp.nat(0))).run(
        sender=source2
    )
    scenario += stake_manager.update_fixed_stakes(
        [fixed_stake1.address, fixed_stake2.address]
    ).run()
    # scenario.verify_equal(governance_token.data.stakes[alice.address], sp.nat(0))
    # scenario.verify_equal(governance_token.data.stakes[bob.address], sp.nat(0))
    # scenario.verify_equal(governance_token.data.stakes[fixed_stake1.address], sp.nat(0))
    # scenario.verify_equal(governance_token.data.stakes[fixed_stake2.address], sp.nat(0))
    scenario.verify_equal(governance_token.data.total_stake, sp.nat(0))

    scenario.h2("Import Stake")
    scenario += stake_manager.update_stake(Stake.make(bob.address, sp.nat(1))).run(
        sender=source1
    )
    scenario += stake_manager.import_stakes(
        [
            sp.record(updater=source1.address, owner=bob.address, amount=10),
            sp.record(updater=source1.address, owner=dan.address, amount=13),
        ]
    ).run(sender=administrator)
    scenario.verify_equal(
        stake_manager.data.total_stake, sp.nat(14)
    )  # bob was already in the global stakes once so he cannot be imported.
    scenario.verify_equal(
        stake_manager.data.global_stakes[dan.address], sp.nat(13)
    )  # bob was already in the global stakes once so he cannot be imported.
    scenario.verify_equal(
        stake_manager.data.global_stakes[bob.address], sp.nat(1)
    )  # bob was already in the global stakes once so he cannot be imported.
