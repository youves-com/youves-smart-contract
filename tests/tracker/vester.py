import smartpy as sp

from utils.fa2 import LedgerKey, RecipientTokenAmount, AdministrableFA2
import utils.constants as Constants

from contracts.tracker.vester import (
    Vester,
    VestingOperation,
    DivestingOperation,
    Ledger,
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


@sp.add_test(name="Vester Contract")
def test():
    scenario = sp.test_scenario()
    scenario.add_flag("protocol", "ithaca")
    scenario.h1("Vester Contract Unit Test")
    scenario.table_of_contents()
    token_id = sp.nat(0)

    scenario.h2("Bootstrapping")
    administrator = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob = sp.test_account("Robert")
    dan = sp.test_account("Dan")
    savings_pool = sp.test_account("SavingsPool")
    scenario.show([administrator, alice, bob, dan, savings_pool])

    token = DummyFA2({LedgerKey.make(token_id, administrator.address): sp.unit})
    scenario += token
    scenario += token.set_token_metadata(token_id=token_id, token_info=sp.map()).run(
        sender=administrator
    )

    scenario += token.mint(
        owner=alice.address,
        token_id=token_id,
        token_amount=10 * Constants.PRECISION_FACTOR,
    )
    scenario += token.mint(
        owner=bob.address,
        token_id=token_id,
        token_amount=10 * Constants.PRECISION_FACTOR,
    )
    scenario += token.mint(
        owner=dan.address,
        token_id=token_id,
        token_amount=10 * Constants.PRECISION_FACTOR,
    )
    scenario += token.mint(
        owner=savings_pool.address,
        token_id=token_id,
        token_amount=100 * Constants.PRECISION_FACTOR,
    )

    scenario += token.update_operators(
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

    vester = Vester(token.address, token_id)
    scenario += vester

    scenario.h2("Test vest entry point")
    scenario.h3("Cannot vest if vester contract is not operator for the locker")
    now = sp.timestamp(0)
    vesting_for_alice = VestingOperation.make(
        alice.address, 10 * Constants.PRECISION_FACTOR, now.add_seconds(10)
    )
    vesting_for_bob = VestingOperation.make(
        bob.address, 20 * Constants.PRECISION_FACTOR, now.add_seconds(10)
    )

    scenario += vester.vest([vesting_for_alice]).run(
        sender=savings_pool, now=now, valid=False
    )

    # Add vester as an operator for the locker
    scenario += token.update_operators(
        [
            sp.variant(
                "add_operator",
                sp.record(
                    owner=savings_pool.address,
                    operator=vester.address,
                    token_id=token_id,
                ),
            )
        ]
    ).run(sender=savings_pool.address)

    scenario.h3("Vesting for alice")
    scenario += vester.vest([vesting_for_alice]).run(sender=savings_pool, now=now)
    alice_ledger_key = Ledger.make_key(alice.address, savings_pool.address)
    scenario.verify(vester.data.ledger.contains(alice_ledger_key))
    scenario.verify(
        vester.data.ledger[alice_ledger_key]
        == Ledger.make_value(10 * Constants.PRECISION_FACTOR, now.add_seconds(10))
    )

    scenario.h3("Vesting for bob")
    scenario += vester.vest([vesting_for_bob]).run(sender=savings_pool, now=now)
    bob_ledger_key = Ledger.make_key(bob.address, savings_pool.address)
    scenario.verify(vester.data.ledger.contains(bob_ledger_key))
    scenario.verify(
        vester.data.ledger[bob_ledger_key]
        == Ledger.make_value(20 * Constants.PRECISION_FACTOR, now.add_seconds(10))
    )

    scenario.verify(
        token.data.ledger.contains(LedgerKey.make(token_id, vester.address))
    )
    scenario.verify(
        token.data.ledger[LedgerKey.make(token_id, vester.address)]
        == 30 * Constants.PRECISION_FACTOR
    )
    scenario.verify(
        token.data.ledger[LedgerKey.make(token_id, savings_pool.address)]
        == 70 * Constants.PRECISION_FACTOR
    )

    scenario.h2("Divesting")
    scenario.h3("Cannot divest if not owner")
    divesting = DivestingOperation.make(savings_pool.address, bob.address)
    # Dan tries to divest for bob.
    scenario += vester.divest([divesting]).run(
        sender=dan, now=now.add_seconds(100), valid=False
    )

    scenario.h3("Cannot divest if not enough time has passed")
    alice_divesting = DivestingOperation.make(savings_pool.address, alice.address)
    scenario += vester.divest([alice_divesting]).run(
        sender=savings_pool, now=now.add_seconds(9), valid=False
    )

    scenario.h3("Divesting")
    scenario += vester.divest([alice_divesting]).run(
        sender=alice, now=now.add_seconds(10)
    )
    scenario.verify(~vester.data.ledger.contains(alice_ledger_key))
    scenario.verify(
        token.data.ledger[LedgerKey.make(token_id, savings_pool.address)]
        == 70 * Constants.PRECISION_FACTOR
    )
    scenario.verify(
        token.data.ledger[LedgerKey.make(token_id, alice.address)]
        == 20 * Constants.PRECISION_FACTOR
    )
    scenario.verify(
        token.data.ledger[LedgerKey.make(token_id, vester.address)]
        == 20 * Constants.PRECISION_FACTOR
    )

    bob_divesting = DivestingOperation.make(
        savings_pool.address, dan.address
    )  # bob divests with dan as a recipient
    scenario += vester.divest([bob_divesting]).run(sender=bob, now=now.add_seconds(10))
    scenario.verify(~vester.data.ledger.contains(bob_ledger_key))
    scenario.verify(
        token.data.ledger[LedgerKey.make(token_id, savings_pool.address)]
        == 70 * Constants.PRECISION_FACTOR
    )
    scenario.verify(
        token.data.ledger[LedgerKey.make(token_id, bob.address)]
        == 10 * Constants.PRECISION_FACTOR
    )
    scenario.verify(
        token.data.ledger[LedgerKey.make(token_id, dan.address)]
        == 30 * Constants.PRECISION_FACTOR
    )
    scenario.verify(
        ~token.data.ledger.contains(LedgerKey.make(token_id, vester.address))
    )
