import smartpy as sp

import utils.constants as Constants
import utils.fa2 as fa2

from contracts.tracker.governance_token import GovernanceToken
from contracts.tracker.stake_manager import StakeManager
from contracts.tracker.liquidity_farm import LiquidityFarm


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


@sp.add_test(name="Liquidity Farm")
def test():
    scenario = sp.test_scenario()
    scenario.h1("Liquidity Farm Unit Test")
    scenario.table_of_contents()

    scenario.h2("Bootstrapping")
    token_id = sp.nat(0)

    administrator = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob = sp.test_account("Robert")
    dan = sp.test_account("Dan")
    source1 = sp.test_account("Source1")
    source2 = sp.test_account("Source2")
    scenario.h2("Accounts")
    scenario.show([administrator, alice, bob, dan])

    scenario.p("Liquidity Token")
    staking_token = DummyFA2(
        {fa2.LedgerKey.make(token_id, administrator.address): sp.unit}
    )
    scenario += staking_token
    scenario += staking_token.set_token_metadata(
        sp.record(token_id=token_id, token_info=sp.map())
    ).run(sender=administrator)

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

    scenario.p("Liquidity Farm")
    liquidity_farm = LiquidityFarm(
        staking_token.address,
        token_id,
        stake_manager.address,
        {
            fa2.LedgerKey.make(
                Constants.GOVERNANCE_TOKEN_ID, administrator.address
            ): sp.unit
        },
    )
    scenario += liquidity_farm
    scenario += stake_manager.set_administrator(
        token_id=token_id, administrator_to_set=liquidity_farm.address
    ).run(sender=administrator)

    scenario.p("Mint")
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

    scenario.h2("Lock Token to Farm")
    scenario += staking_token.update_operators(
        [
            sp.variant(
                "add_operator",
                sp.record(
                    owner=alice.address,
                    operator=liquidity_farm.address,
                    token_id=token_id,
                ),
            )
        ]
    ).run(sender=alice.address)
    scenario += liquidity_farm.deposit(1 * Constants.PRECISION_FACTOR).run(sender=alice)
    scenario.verify_equal(
        governance_token.data.stakes[alice.address], sp.nat(Constants.PRECISION_FACTOR)
    )
    scenario += liquidity_farm.withdraw().run(sender=alice)
    scenario.verify_equal(governance_token.data.stakes.contains(alice.address), False)

    scenario.h2("Only Admin can change incetive")
    scenario += liquidity_farm.set_incentive_factor(
        Constants.PRECISION_FACTOR // 2
    ).run(sender=alice, valid=False)
    scenario += liquidity_farm.set_incentive_factor(
        Constants.PRECISION_FACTOR // 2
    ).run(sender=administrator)

    scenario += liquidity_farm.deposit(Constants.PRECISION_FACTOR // 2).run(
        sender=alice
    )
    scenario.verify_equal(
        governance_token.data.stakes[alice.address],
        sp.nat(Constants.PRECISION_FACTOR // 4),
    )

    scenario.h2("Incentive is always on everything")
    scenario += liquidity_farm.set_incentive_factor(2 * Constants.PRECISION_FACTOR).run(
        sender=administrator
    )
    scenario += liquidity_farm.deposit(Constants.PRECISION_FACTOR // 2).run(
        sender=alice
    )
    scenario.verify_equal(
        governance_token.data.stakes[alice.address],
        sp.nat(2 * Constants.PRECISION_FACTOR),
    )

    scenario.h2("Incentive does not influence withdraw")
    scenario += liquidity_farm.set_incentive_factor(
        100 * Constants.PRECISION_FACTOR
    ).run(sender=administrator)
    scenario += liquidity_farm.withdraw().run(sender=alice)
    scenario.verify_equal(governance_token.data.stakes.contains(alice.address), False)
