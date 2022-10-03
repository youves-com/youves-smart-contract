import smartpy as sp

import utils.constants as Constants
import utils.fa2 as fa2

from contracts.tracker.governance_token import GovernanceToken


@sp.add_test(name="Governance Token")
def test():
    scenario = sp.test_scenario()
    scenario.add_flag("protocol", "ithaca")
    scenario.h1("Governance Token Unit Test")
    scenario.table_of_contents()

    administrator = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob = sp.test_account("Robert")
    dan = sp.test_account("Dan")
    scenario.h2("Accounts")
    scenario.show([administrator, alice, bob, dan])

    scenario.h2("Bootstrapping")

    governance_token = GovernanceToken(
        administrator.address, {fa2.LedgerKey.make(0, administrator.address): sp.unit}
    )
    scenario += governance_token

    scenario.h2("Single phase issuance happy path")

    scenario.h3("Bob enters at time 0 ")
    now = sp.timestamp(0)
    scenario += governance_token.update_stake(
        address=bob.address, amount=Constants.PRECISION_FACTOR
    ).run(sender=administrator, now=now)

    scenario.h3("Bob receives full issuance for one week")
    now = sp.timestamp(Constants.SECONDS_PER_WEEK * 1)
    scenario += governance_token.claim().run(sender=bob, now=now)
    scenario.verify_equal(
        governance_token.data.ledger[fa2.LedgerKey.make(0, bob.address)],
        Constants.SECONDS_PER_WEEK * Constants.GOVERNANCE_TOKEN_ISSUANCE_RATE,
    )  # bob recei
    scenario.verify_equal(
        governance_token.data.ledger[fa2.LedgerKey.make(0, administrator.address)],
        governance_token.data.ledger[fa2.LedgerKey.make(0, bob.address)]
        >> Constants.TREASURY_REWARD_BITSHIFT,
    )  # treasury receives fair share

    scenario.h3("Alice enters after 2 weeks")
    now = sp.timestamp(Constants.SECONDS_PER_WEEK * 2)
    scenario += governance_token.update_stake(
        address=alice.address, amount=Constants.PRECISION_FACTOR
    ).run(sender=administrator, now=now)

    scenario.h3("Alice and bob claim after 3 weeks")
    now = sp.timestamp(Constants.SECONDS_PER_WEEK * 3)
    scenario += governance_token.claim().run(sender=bob, now=now)
    scenario += governance_token.claim().run(sender=alice, now=now)
    scenario.verify_equal(
        governance_token.data.ledger[fa2.LedgerKey.make(0, bob.address)],
        Constants.SECONDS_PER_WEEK * Constants.GOVERNANCE_TOKEN_ISSUANCE_RATE * 2
        + Constants.SECONDS_PER_WEEK * Constants.GOVERNANCE_TOKEN_ISSUANCE_RATE // 2,
    )  # 2 full phases plus one half phase
    scenario.verify_equal(
        governance_token.data.ledger[fa2.LedgerKey.make(0, alice.address)],
        Constants.SECONDS_PER_WEEK * Constants.GOVERNANCE_TOKEN_ISSUANCE_RATE // 2,
    )
    scenario.verify_equal(
        governance_token.data.ledger[fa2.LedgerKey.make(0, administrator.address)],
        (
            governance_token.data.ledger[fa2.LedgerKey.make(0, bob.address)]
            + governance_token.data.ledger[fa2.LedgerKey.make(0, alice.address)]
        )
        >> Constants.TREASURY_REWARD_BITSHIFT,
    )  # treasury receives fair share

    scenario.h3("Alice leaves after 4 weeks")
    now = sp.timestamp(Constants.SECONDS_PER_WEEK * 4)
    scenario += governance_token.update_stake(address=alice.address, amount=0).run(
        sender=administrator, now=now
    )

    scenario.h3("Claim after 5 weeks")
    now = sp.timestamp(Constants.SECONDS_PER_WEEK * 5)
    scenario += governance_token.claim().run(sender=bob, now=now)
    scenario += governance_token.claim().run(sender=alice, now=now)
    scenario.verify_equal(
        governance_token.data.ledger[fa2.LedgerKey.make(0, bob.address)],
        Constants.SECONDS_PER_WEEK * Constants.GOVERNANCE_TOKEN_ISSUANCE_RATE * 3
        + Constants.SECONDS_PER_WEEK * Constants.GOVERNANCE_TOKEN_ISSUANCE_RATE,
    )  # 3 full phases plus two half phase
    scenario.verify_equal(
        governance_token.data.ledger[fa2.LedgerKey.make(0, alice.address)],
        Constants.SECONDS_PER_WEEK * Constants.GOVERNANCE_TOKEN_ISSUANCE_RATE,
    )
    scenario.verify_equal(
        governance_token.data.ledger[fa2.LedgerKey.make(0, administrator.address)],
        (
            governance_token.data.ledger[fa2.LedgerKey.make(0, bob.address)]
            + governance_token.data.ledger[fa2.LedgerKey.make(0, alice.address)]
        )
        >> Constants.TREASURY_REWARD_BITSHIFT,
    )  # treasury receives fair share

    scenario.h2("Multi phase issuance happy path")
    now = sp.timestamp(Constants.SECONDS_PER_WEEK * 52)
    scenario += governance_token.claim().run(sender=bob, now=now)
    scenario.verify_equal(
        governance_token.data.ledger[fa2.LedgerKey.make(0, bob.address)],
        Constants.SECONDS_PER_WEEK * Constants.GOVERNANCE_TOKEN_ISSUANCE_RATE * 50
        + Constants.SECONDS_PER_WEEK * Constants.GOVERNANCE_TOKEN_ISSUANCE_RATE,
    )  # 3+47 full phases plus two half phases
    scenario.verify_equal(
        governance_token.data.ledger[fa2.LedgerKey.make(0, administrator.address)],
        (
            governance_token.data.ledger[fa2.LedgerKey.make(0, bob.address)]
            + governance_token.data.ledger[fa2.LedgerKey.make(0, alice.address)]
        )
        >> Constants.TREASURY_REWARD_BITSHIFT,
    )  # treasury receives fair share

    scenario.h3("Moving to the second phase")
    now = sp.timestamp(
        Constants.SECONDS_PER_WEEK * 53
    )  # 52*7 == 364 days in old phase and 7 days in new phase

    scenario += governance_token.claim().run(sender=bob, now=now)
    scenario.verify_equal(
        governance_token.data.ledger[fa2.LedgerKey.make(0, bob.address)],
        Constants.SECONDS_PER_WEEK * Constants.GOVERNANCE_TOKEN_ISSUANCE_RATE * 51
        + Constants.SECONDS_PER_WEEK * (Constants.GOVERNANCE_TOKEN_ISSUANCE_RATE >> 1),
    )
    scenario.verify_equal(
        governance_token.data.ledger[fa2.LedgerKey.make(0, administrator.address)],
        (
            governance_token.data.ledger[fa2.LedgerKey.make(0, bob.address)]
            + governance_token.data.ledger[fa2.LedgerKey.make(0, alice.address)]
        )
        >> Constants.TREASURY_REWARD_BITSHIFT,
    )  # treasury receives fair share

    scenario.h3("Again only second phase")
    now = sp.timestamp(Constants.SECONDS_PER_WEEK * 54)

    scenario += governance_token.claim().run(sender=bob, now=now)
    scenario.verify_equal(
        governance_token.data.ledger[fa2.LedgerKey.make(0, bob.address)],
        Constants.SECONDS_PER_WEEK * Constants.GOVERNANCE_TOKEN_ISSUANCE_RATE * 51
        + Constants.SECONDS_PER_WEEK
        * 2
        * (Constants.GOVERNANCE_TOKEN_ISSUANCE_RATE >> 1),
    )
    scenario.verify_equal(
        governance_token.data.ledger[fa2.LedgerKey.make(0, administrator.address)],
        (
            governance_token.data.ledger[fa2.LedgerKey.make(0, bob.address)]
            + governance_token.data.ledger[fa2.LedgerKey.make(0, alice.address)]
        )
        >> Constants.TREASURY_REWARD_BITSHIFT,
    )  # treasury receives fair share

    now = sp.timestamp(Constants.SECONDS_PER_WEEK * 60)
    scenario += governance_token.claim().run(sender=bob, now=now)
    scenario.verify_equal(
        governance_token.data.ledger[fa2.LedgerKey.make(0, bob.address)],
        Constants.SECONDS_PER_WEEK * Constants.GOVERNANCE_TOKEN_ISSUANCE_RATE * 51
        + Constants.SECONDS_PER_WEEK
        * 8
        * (Constants.GOVERNANCE_TOKEN_ISSUANCE_RATE >> 1),
    )
    scenario.verify_equal(
        governance_token.data.ledger[fa2.LedgerKey.make(0, administrator.address)],
        (
            governance_token.data.ledger[fa2.LedgerKey.make(0, bob.address)]
            + governance_token.data.ledger[fa2.LedgerKey.make(0, alice.address)]
        )
        >> Constants.TREASURY_REWARD_BITSHIFT,
    )  # treasury receives fair share

    scenario.h3("Going to third phase with alice joining")
    now = sp.timestamp(Constants.SECONDS_PER_WEEK * 61)
    scenario += governance_token.update_stake(
        address=alice.address, amount=Constants.PRECISION_FACTOR
    ).run(sender=administrator, now=now)

    now = sp.timestamp(
        Constants.SECONDS_PER_WEEK * 105
    )  # 105 is 2*364 and 7 days of the new phase
    scenario += governance_token.claim().run(sender=bob, now=now)
    scenario += governance_token.claim().run(sender=alice, now=now)
    scenario.verify_equal(
        governance_token.data.ledger[fa2.LedgerKey.make(0, bob.address)],
        Constants.SECONDS_PER_WEEK * Constants.GOVERNANCE_TOKEN_ISSUANCE_RATE * 51
        + Constants.SECONDS_PER_WEEK
        * 9
        * (Constants.GOVERNANCE_TOKEN_ISSUANCE_RATE >> 1)
        + 43
        * Constants.SECONDS_PER_WEEK
        * (Constants.GOVERNANCE_TOKEN_ISSUANCE_RATE >> 1)
        // 2
        + Constants.SECONDS_PER_WEEK
        * (Constants.GOVERNANCE_TOKEN_ISSUANCE_RATE >> 2)
        // 2,
    )  # one week more without alice (=> 62), then 43 weeks 50/50 split (104-61) at phase 2 rate, and 5 split days at phase 3
    scenario.verify_equal(
        governance_token.data.ledger[fa2.LedgerKey.make(0, alice.address)],
        Constants.SECONDS_PER_WEEK * Constants.GOVERNANCE_TOKEN_ISSUANCE_RATE
        + 43
        * Constants.SECONDS_PER_WEEK
        * (Constants.GOVERNANCE_TOKEN_ISSUANCE_RATE >> 1)
        // 2
        + Constants.SECONDS_PER_WEEK
        * (Constants.GOVERNANCE_TOKEN_ISSUANCE_RATE >> 2)
        // 2,
    )  # one week more without alice (=> 62), then 43 weeks 50/50 split (104-61) at phase 2 rate, and 5 split days at phase 3
    scenario.verify_equal(
        governance_token.data.ledger[fa2.LedgerKey.make(0, administrator.address)],
        (
            governance_token.data.ledger[fa2.LedgerKey.make(0, bob.address)]
            + governance_token.data.ledger[fa2.LedgerKey.make(0, alice.address)]
        )
        >> Constants.TREASURY_REWARD_BITSHIFT,
    )  # treasury receives fair share

    scenario.h3("Treasury Change")
    scenario.p("only an admin can change the treasury")
    scenario += governance_token.set_treasury(fa2.LedgerKey.make(0, dan.address)).run(
        sender=dan, now=now, valid=False
    )
    scenario += governance_token.set_treasury(fa2.LedgerKey.make(0, dan.address)).run(
        sender=administrator, now=now, valid=True
    )
    scenario.verify_equal(
        governance_token.data.ledger[fa2.LedgerKey.make(0, dan.address)], 0
    )
    now = sp.timestamp(Constants.SECONDS_PER_WEEK * 106)
    scenario += governance_token.claim().run(sender=bob, now=now)
    scenario.verify_equal(
        governance_token.data.ledger[fa2.LedgerKey.make(0, dan.address)],
        (Constants.SECONDS_PER_WEEK * (Constants.GOVERNANCE_TOKEN_ISSUANCE_RATE >> 2))
        >> Constants.TREASURY_REWARD_BITSHIFT,
    )  # treasury receives fair share
