import smartpy as sp

import utils.constants as Constants
import utils.fa2 as fa2

from utils.contract_utils import Utils

from contracts.tracker.tracker_engine import Settlement
from contracts.tracker.options_listing import OptionsListing
from contracts.oracle.dummy_oracle import DummyOracle


class DummyEngine(sp.Contract):
    def __init__(self, token_address):
        self.init(token_address=token_address)

    @sp.entry_point
    def default(self):
        sp.send(sp.sender, sp.amount)

    @sp.entry_point
    def settle_with_vault(self, settlement):
        sp.set_type(settlement, Settlement.get_type())
        Utils.execute_token_burn(
            self.data.token_address, sp.sender, sp.nat(0), settlement.token_amount
        )
        sp.send(settlement.recipient, sp.mutez(0))
        sp.send(settlement.vault_owner, sp.mutez(0))


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


@sp.add_test(name="Options Listing")
def test():
    scenario = sp.test_scenario()
    scenario.add_flag("protocol", "ithaca")
    scenario.h1("Options Listing Unit Test")
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

    token = DummyFA2()
    scenario += token
    token_id = sp.nat(0)

    engine = DummyEngine(token.address)
    scenario += engine

    options_listing = OptionsListing(
        token.address, token_id, engine.address, target_oracle.address
    )
    scenario += options_listing

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
    scenario += token.update_operators(
        [
            sp.variant(
                "add_operator",
                sp.record(
                    owner=alice.address,
                    operator=options_listing.address,
                    token_id=token_id,
                ),
            )
        ]
    ).run(sender=alice.address)
    scenario += token.update_operators(
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
    ).run(sender=bob.address)
    scenario += token.update_operators(
        [
            sp.variant(
                "add_operator",
                sp.record(
                    owner=dan.address,
                    operator=options_listing.address,
                    token_id=token_id,
                ),
            )
        ]
    ).run(sender=dan.address)

    scenario.h2("Create intent to sell")
    scenario.p("Cannot advertise more than what alice has")
    scenario += options_listing.advertise_intent(12 * Constants.PRECISION_FACTOR).run(
        sender=alice, valid=False
    )
    scenario.p("But can part of what alice has")
    scenario += options_listing.advertise_intent(5 * Constants.PRECISION_FACTOR).run(
        sender=alice
    )
    scenario.verify_equal(options_listing.data.intents.contains(alice.address), True)
    scenario.verify_equal(
        options_listing.data.intents[alice.address].token_amount,
        5 * Constants.PRECISION_FACTOR,
    )
    scenario.verify_equal(
        token.data.ledger[fa2.LedgerKey.make(token_id, options_listing.address)],
        5 * Constants.PRECISION_FACTOR,
    )
    scenario.verify_equal(
        token.data.ledger[fa2.LedgerKey.make(token_id, alice.address)],
        5 * Constants.PRECISION_FACTOR,
    )

    scenario.h2("Remove intent to sell")
    scenario.p("Cannot remove intent if does not have")
    scenario += options_listing.remove_intent().run(sender=bob, valid=False)
    scenario.p("Can remove what I previously created")
    scenario += options_listing.remove_intent().run(sender=alice)
    scenario.verify_equal(options_listing.data.intents.contains(alice.address), False)
    scenario.verify_equal(
        token.data.ledger[fa2.LedgerKey.make(token_id, alice.address)],
        10 * Constants.PRECISION_FACTOR,
    )

    scenario.p("Putting back intent")
    scenario += options_listing.advertise_intent(5 * Constants.PRECISION_FACTOR).run(
        sender=alice
    )

    scenario.h2("Fullfill Intent")

    fee_amount = (
        5 * Constants.PRECISION_FACTOR * 1000000
    ) >> Constants.BID_FEE_BITSHIFT
    matching_amount = (
        sp.as_nat(5 * Constants.PRECISION_FACTOR * 1000000 - fee_amount)
        / Constants.PRECISION_FACTOR
    )
    scenario.p("Cannot fullfill too late")
    scenario += options_listing.fulfill_intent(alice.address).run(
        sender=bob,
        amount=sp.utils.nat_to_mutez(matching_amount),
        now=sp.timestamp(2 * 24 * 60 * 60 + 1),
        valid=False,
    )
    scenario.p("Can if amount is right")
    scenario += options_listing.fulfill_intent(alice.address).run(
        sender=bob,
        amount=sp.utils.nat_to_mutez(matching_amount),
        now=sp.timestamp(0),
        valid=True,
    )

    scenario.verify_equal(options_listing.data.intents.contains(alice.address), False)
    scenario.verify_equal(
        token.data.ledger[fa2.LedgerKey.make(token_id, alice.address)],
        5 * Constants.PRECISION_FACTOR,
    )
    scenario.verify_equal(
        token.data.ledger[fa2.LedgerKey.make(token_id, bob.address)],
        15 * Constants.PRECISION_FACTOR,
    )

    scenario.p("Putting back intent")
    scenario += options_listing.advertise_intent(5 * Constants.PRECISION_FACTOR).run(
        sender=alice
    )

    scenario.p("Partial intent fullfillment")
    fee_amount = (
        2 * Constants.PRECISION_FACTOR * 1000000
    ) >> Constants.BID_FEE_BITSHIFT
    matching_amount = (
        sp.as_nat(2 * Constants.PRECISION_FACTOR * 1000000 - fee_amount)
        / Constants.PRECISION_FACTOR
    )
    scenario += options_listing.fulfill_intent(alice.address).run(
        sender=bob, amount=sp.utils.nat_to_mutez(matching_amount), valid=True
    )

    scenario.verify_equal(options_listing.data.intents.contains(alice.address), True)
    scenario.verify_equal(
        token.data.ledger[fa2.LedgerKey.make(token_id, bob.address)],
        17 * Constants.PRECISION_FACTOR,
    )
    scenario.verify_equal(
        token.data.ledger[fa2.LedgerKey.make(token_id, options_listing.address)],
        3 * Constants.PRECISION_FACTOR,
    )
    scenario.verify_equal(
        options_listing.data.intents[alice.address].token_amount,
        3 * Constants.PRECISION_FACTOR,
    )
    scenario += options_listing.remove_intent().run(sender=alice)
    scenario.p("Putting back intent")

    scenario += token.mint(
        owner=alice.address,
        token_id=token_id,
        token_amount=10 * Constants.PRECISION_FACTOR,
    )
    scenario += options_listing.advertise_intent(5 * Constants.PRECISION_FACTOR).run(
        sender=alice
    )

    scenario.h2("Execute Intent")
    scenario.p("Cannot execute too early")
    scenario += options_listing.execute_intent(
        address=bob.address, token_amount=2 * Constants.PRECISION_FACTOR
    ).run(sender=alice, valid=False, now=sp.timestamp(0))
    scenario.p("Cannot execute too big amount")
    scenario += options_listing.execute_intent(
        address=bob.address, token_amount=6 * Constants.PRECISION_FACTOR
    ).run(sender=alice, valid=False, now=sp.timestamp(24 * 60 * 60))
    scenario.p("Can execute intent")
    scenario += options_listing.execute_intent(
        address=bob.address, token_amount=5 * Constants.PRECISION_FACTOR
    ).run(sender=alice, now=sp.timestamp(24 * 60 * 60))
    scenario.show(token.data.ledger[fa2.LedgerKey.make(token_id, bob.address)])
    scenario.verify_equal(
        token.data.ledger[fa2.LedgerKey.make(token_id, bob.address)],
        17 * Constants.PRECISION_FACTOR,
    )
    scenario.verify_equal(
        token.data.ledger[fa2.LedgerKey.make(token_id, alice.address)],
        8 * Constants.PRECISION_FACTOR,
    )
    scenario.verify_equal(
        token.data.ledger[fa2.LedgerKey.make(token_id, options_listing.address)], 0
    )
