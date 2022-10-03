import smartpy as sp

import utils.constants as Constants
import utils.fa2 as fa2
from contracts.tracker.distributor import Distributor

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


@sp.add_test(name="Distributor")
def test():
    scenario = sp.test_scenario()
    scenario.h1("Distributor Unit Test")
    scenario.table_of_contents()

    scenario.h2("Bootstrapping")
    token_id = sp.nat(0)

    administrator = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob = sp.test_account("Robert")
    dan = sp.test_account("Dan")

    scenario.h2("Accounts")
    scenario.show([administrator, alice, bob, dan])

    scenario.p("Synthetic Token")
    token_id = 0
    synth_token = DummyFA2(
        {fa2.LedgerKey.make(token_id, administrator.address): sp.unit}
    )
    scenario += synth_token
    scenario += synth_token.set_token_metadata(
        sp.record(token_id=token_id, token_info=sp.map())
    ).run(sender=administrator)

    distributor = Distributor(
        synth_token.address,
        token_id,
        sp.big_map({alice.address: 1000, bob.address: 200, dan.address: 4000}),
    )
    scenario += distributor

    scenario += synth_token.mint(
        fa2.RecipientTokenAmount.make(distributor.address, token_id, 1000)
    ).run(sender=administrator)
    scenario += distributor.settle(sp.set([alice.address, bob.address])).run(
        sender=administrator, valid=False
    )
    scenario += synth_token.mint(
        fa2.RecipientTokenAmount.make(distributor.address, token_id, 200)
    ).run(sender=administrator)
    scenario += distributor.settle(
        sp.set([alice.address, bob.address, dan.address])
    ).run(sender=administrator, valid=False)
    scenario += synth_token.mint(
        fa2.RecipientTokenAmount.make(distributor.address, token_id, 3999)
    ).run(sender=administrator)
    scenario += distributor.settle(
        sp.set([alice.address, bob.address, dan.address])
    ).run(sender=administrator, valid=False)
    scenario += synth_token.mint(
        fa2.RecipientTokenAmount.make(distributor.address, token_id, 1001)
    ).run(sender=administrator)
    scenario += distributor.settle(
        sp.set([alice.address, bob.address, dan.address])
    ).run(sender=administrator)
    scenario += distributor.settle(sp.set([alice.address])).run(
        sender=administrator, valid=False
    )

    scenario.verify_equal(
        synth_token.data.ledger[fa2.LedgerKey.make(token_id, alice.address)], 1000
    )
    scenario.verify_equal(
        synth_token.data.ledger[fa2.LedgerKey.make(token_id, bob.address)], 200
    )
    scenario.verify_equal(
        synth_token.data.ledger[fa2.LedgerKey.make(token_id, dan.address)], 4000
    )
    scenario.verify_equal(
        synth_token.data.ledger[fa2.LedgerKey.make(token_id, distributor.address)], 1000
    )
    scenario.verify_equal(distributor.data.balances.contains(alice.address), False)
    scenario.verify_equal(distributor.data.balances.contains(bob.address), False)
    scenario.verify_equal(distributor.data.balances.contains(dan.address), False)
