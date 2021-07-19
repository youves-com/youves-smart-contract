import smartpy as sp

import tracker.errors as Errors
import tracker.constants as Constants
from tracker.utils import Utils, InternalMixin
import tracker.fa2 as fa2
from tracker.tracker_engine import Settlement

class Intent:
    """Intent to bid a certain token_amount
    """
    def get_type():
        """Returns a single Intent type, layouted

        Returns:
            sp.TRecord: the layouted intent
        """
        return sp.TRecord(token_amount=sp.TNat, start_timestamp=sp.TTimestamp).layout(("token_amount", "start_timestamp"))

    def make(token_amount, start_timestamp):
        """Makes an instance of an intent

        Args:
            token_amount (sp.nat): token_amount
            start_timestamp (sp.timestamp): start_timestamp

        Returns:
            Intent: the intent record
        """
        return sp.set_type_expr(sp.record(token_amount=token_amount, start_timestamp=start_timestamp), Intent.get_type())

class Execution:
    """Parameter use in fullfill and execute intent
    """
    def get_type():
        """Returns a single Execution type, layouted

        Returns:
            sp.TRecord: the layouted intent
        """
        return sp.TRecord(address=sp.TAddress, token_amount=sp.TNat).layout(("address", "token_amount"))

    def make(address, token_amount):
        """Makes an instance of an fullfillment

        Args:
            address (sp.address): address
            token_amount (sp.nat): token_amount

        Returns:
            Execution: the fullfillment record
        """
        return sp.set_type_expr(sp.record(address=address, token_amount=token_amount), Execution.get_type())

class OptionsListing(sp.Contract, InternalMixin):
    """The options listing contract is used for advertising intents to sell tokens for collateral. If no buyer is found within 24 hours
    the option can be executed against a specific vault.

    Args:
        (sp.Contract): this is a smartpy contract
        (InternalMixin): mixin used whenever we need external data and hence have to trigger an internal call (to process after we received said external data)
    """

    def get_init_storage(self):
        """Returns the initial storage of the contract used for inheritance of smartpy contracts

        Returns:
            dict: initial storage of the contract
        """
        storage = {}
        storage['intents'] = sp.big_map(tkey=sp.TAddress, tvalue=Intent.get_type())
        storage['token_address'] = self.token_address
        storage['token_id'] = self.token_id
        storage['engine_address'] = self.engine_address
        storage['target_price_oracle'] = self.target_price_oracle
        storage['target_price'] = sp.nat(0)

        storage['sender'] = Constants.DEFAULT_ADDRESS
        return storage

    def __init__(self, token_address, token_id, engine_address,  target_price_oracle):
        """The options listing is dependend on a specific token and specific engine + oracle.

        Args:
            token_address (sp.address): the synthetic asset token contact
            token_id (sp.nat): token id of the synthetic asset
            engine_address (sp.address): the tracker engine used to execute this option on
            target_price_oracle (sp.address): needed for when the option is fullfilled such that the price is correct
        """
        self.target_price_oracle = target_price_oracle
        self.token_address = token_address
        self.token_id = token_id
        self.engine_address = engine_address
        self.init(**self.get_init_storage())

    @sp.sub_entry_point
    def fetch_target_price(self, unit):
        """sub entrypoint which triggers a price fetch for the price to be set using the callback on the "set_target_price" entrypoint

        Args:
            unit (sp.unit): nothing
        """
        sp.set_type(unit, sp.TUnit)
        Utils.execute_get(self.data.target_price_oracle, "get_price", "set_target_price")

    @sp.entry_point
    def set_target_price(self, target_price):
        """entrypoint used by the oracle to set the price
        Pre: sp.sender == storage.target_price_oracle
        Post: storage.target_price = target_price
        Args:
            target_price (sp.nat): price provided by the oracle
        """
        sp.set_type(target_price, sp.TNat)
        sp.verify(sp.sender == self.data.target_price_oracle)
        self.data.target_price = target_price

    @sp.entry_point
    def advertise_intent(self, token_amount):
        """entrypoint used by a token holder to create the intention to sell a certain amount of tokens at a premium. The tokens will be
        transfered to the options contract. A holder can have only a single intent, if a new one needs to be created the user needs to use
        "remove_intent" first.
        Pre: not storage.intents.contains(sp.sender)
        Post: transfer tokens from sender to self
        Post: storage.intents[sp.sender] = Intent(token_amount, sp.now)

        Args:
            token_amount (sp.nat): token amount to store in intent
        """
        sp.verify(~self.data.intents.contains(sp.sender),
                message=Errors.INTENT_ALREADY_EXISTS)
        sp.verify(token_amount >= Constants.MIN_TOKEN_AMOUNT_THRESHOLD,
                message=Errors.AMOUNT_TOO_SMALL)

        Utils.execute_token_transfer(self.data.token_address, sp.sender, sp.self_address, self.data.token_id, token_amount)
        self.data.intents[sp.sender] = Intent.make(token_amount, sp.now)

    @sp.entry_point
    def remove_intent(self):
        """entrypoint to remove your own intent
        Pre: storage.intents.contains(sp.sender)
        Post: transfer tokens from self to sender
        Post: del storage.intents[sp.sender]
        """
        intent = self.data.intents[sp.sender]
        Utils.execute_token_transfer(self.data.token_address, sp.self_address, sp.sender, self.data.token_id, intent.token_amount)
        del self.data.intents[sp.sender]

    @sp.entry_point
    def fulfill_intent(self, address):
        """Fullfills an existing intent. Since this relies on external data we first fetch the data and then call "internal_fullfill_intent"
        Post: storage.sender = sp.sender
        Post: fetch_target_price()
        Post: call internal_fullfill_intent

        Args:
            address (TAddress): the address of the intent owner
        """
        sp.set_type(address, sp.TAddress)
        self.data.sender = sp.sender
        self.fetch_target_price(sp.unit)
        sp.transfer(address, sp.amount, sp.self_entry_point("internal_fulfill_intent"))

    @sp.entry_point
    def internal_fulfill_intent(self, address):
        """This it the actual fullfillment mechanics, it will check if the intent has not expired yet and then if the sp amount sent was enough sell the
        tokens at a premium to the sender.
        Pre: verify_internal()
        Pre: sp.now <= storage.intents[address].start_timestamp + 48hours
        Pre: sp.amount >= 1000
        Post: transfer tokens from self to storage.sender
        Post: send sp.amount to address
        Post: storage.intents[address].token_amount -= sp.amount/(storage.target_price * 0.9375)

        Args:
            address (TAddress): the address of the intent owner
        """
        sp.set_type(address, sp.TAddress)
        self.verify_internal(sp.unit)

        intent = sp.local("intent", self.data.intents[address])


        sp.verify(sp.now <= intent.value.start_timestamp.add_seconds(
            Constants.OPTION_TIME_WINDOW_IN_SECONDS), Errors.TOO_LATE)
        sp.verify(sp.amount >= Constants.MIN_AMOUNT_THRESHOLD, message=Errors.AMOUNT_TOO_SMALL)
        
        fee_adjusted_target_price = sp.as_nat(self.data.target_price - (self.data.target_price>>Constants.BID_FEE_BITSHIFT))
        token_amount = sp.local("token_amount", (sp.utils.mutez_to_nat(sp.amount) * Constants.PRECISION_FACTOR) // fee_adjusted_target_price)
        
        sp.verify(intent.value.token_amount >= token_amount.value,
                  Errors.INSUFFICIENT_TOKEN_AMOUNT)
        
        intent.value.token_amount = sp.as_nat(intent.value.token_amount - token_amount.value)
        
        Utils.execute_token_transfer(self.data.token_address, sp.self_address, self.data.sender,  self.data.token_id, token_amount.value)

        sp.send(address, sp.amount)

        self.data.intents[address] = intent.value

        with sp.if_(intent.value.token_amount == 0):
            del self.data.intents[address]

    @sp.entry_point
    def execute_intent(self, execution):
        """entrypoint to be used by the used 24h after the intent was published and not fullfilled. It can be executed against a vault.
        Pre: Pre: sp.now >= storage.intents[execution.address].start_timestamp + 24hours. Can be executed against multiple vaults.
        Pre: sp.now <= storage.intents[execution.address].start_timestamp + 48hours
        Pre: execution.token_amount >= storage.intents[execution.address].token_amount
        Post: transfer tokens to the vault owner
        Post: calls the "settle_with_vault" function on the engine contract
        Post: storage.intents[execution.address].token_amount -= execution.token_amount
        Args:
            execution (Fullfillmnent): what you want to execute
        """
        sp.set_type(execution, Execution.get_type())

        intent = sp.local("intent",self.data.intents[sp.sender])
        sp.verify(sp.now >= intent.value.start_timestamp.add_seconds(
            Constants.ADVERTISE_TIME_WINDOW_IN_SECONDS), Errors.TOO_EARLY)
        sp.verify(sp.now <= intent.value.start_timestamp.add_seconds(
            Constants.OPTION_TIME_WINDOW_IN_SECONDS), Errors.TOO_LATE)
        sp.verify(intent.value.token_amount >= execution.token_amount,
                  Errors.INSUFFICIENT_TOKEN_AMOUNT)
        intent.value.token_amount = sp.as_nat(intent.value.token_amount - execution.token_amount)

        engine_contract = sp.contract(Settlement.get_type(),
                            self.data.engine_address, entry_point="settle_with_vault").open_some()
        sp.transfer(Settlement.make(execution.address, execution.token_amount, sp.sender), sp.mutez(0), engine_contract)

        self.data.intents[sp.sender] = intent.value

        with sp.if_(intent.value.token_amount == 0):
            del self.data.intents[sp.sender]


if __name__=="__main__":
    from tracker.oracle import DummyOracle

    class DummyEngine(sp.Contract):
        def __init__(self, token_address):
            self.init(token_address = token_address)

        @sp.entry_point
        def default(self):
            sp.send(sp.sender, sp.amount)

        @sp.entry_point
        def settle_with_vault(self, settlement):
            sp.set_type(settlement, Settlement.get_type())
            Utils.execute_token_burn(self.data.token_address, sp.sender, sp.nat(0), settlement.token_amount)
            sp.send(settlement.recipient, sp.mutez(0))
            sp.send(settlement.vault_owner, sp.mutez(0))


    class DummyFA2(fa2.AdministrableFA2):

        @sp.entry_point
        def mint(self, recipient_token_amount):
            sp.set_type(recipient_token_amount, fa2.RecipientTokenAmount.get_type())
            with sp.if_(self.data.ledger.contains(fa2.LedgerKey.make(recipient_token_amount.token_id, recipient_token_amount.owner))):
                self.data.ledger[fa2.LedgerKey.make(recipient_token_amount.token_id, recipient_token_amount.owner)]+=recipient_token_amount.token_amount
            with sp.else_():
                self.data.ledger[fa2.LedgerKey.make(recipient_token_amount.token_id, recipient_token_amount.owner)]=recipient_token_amount.token_amount

        @sp.entry_point
        def burn(self, recipient_token_amount):
            sp.set_type(recipient_token_amount, fa2.RecipientTokenAmount.get_type())
            self.data.ledger[fa2.LedgerKey.make(recipient_token_amount.token_id, recipient_token_amount.owner)]=sp.as_nat(self.data.ledger[fa2.LedgerKey.make(recipient_token_amount.token_id, recipient_token_amount.owner)]-recipient_token_amount.token_amount)


    @sp.add_test(name="Options Listing")
    def test():
        scenario = sp.test_scenario()
        scenario.add_flag("protocol", "florence")
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
        token_id=sp.nat(0)

        engine = DummyEngine(token.address)
        scenario += engine

        options_listing = OptionsListing(token.address, token_id, engine.address, target_oracle.address)
        scenario += options_listing

        scenario += token.mint(owner=alice.address, token_id=token_id, token_amount=10*Constants.PRECISION_FACTOR)
        scenario += token.mint(owner=bob.address, token_id=token_id, token_amount=10*Constants.PRECISION_FACTOR)
        scenario += token.mint(owner=dan.address, token_id=token_id, token_amount=10*Constants.PRECISION_FACTOR)
        scenario += token.update_operators([sp.variant('add_operator', sp.record(
            owner=alice.address, operator=options_listing.address, token_id=token_id))]).run(sender=alice.address)
        scenario += token.update_operators([sp.variant('add_operator', sp.record(
            owner=bob.address, operator=options_listing.address, token_id=token_id))]).run(sender=bob.address)
        scenario += token.update_operators([sp.variant('add_operator', sp.record(
            owner=dan.address, operator=options_listing.address, token_id=token_id))]).run(sender=dan.address)

        scenario.h2("Create intent to sell")
        scenario.p("Cannot advertise more than what alice has")
        scenario += options_listing.advertise_intent(12*Constants.PRECISION_FACTOR).run(sender=alice, valid=False)
        scenario.p("But can part of what alice has")
        scenario += options_listing.advertise_intent(5*Constants.PRECISION_FACTOR).run(sender=alice)
        scenario.verify_equal(options_listing.data.intents.contains(alice.address), True)
        scenario.verify_equal(options_listing.data.intents[alice.address].token_amount, 5*Constants.PRECISION_FACTOR)
        scenario.verify_equal(token.data.ledger[fa2.LedgerKey.make(token_id, options_listing.address)], 5*Constants.PRECISION_FACTOR)
        scenario.verify_equal(token.data.ledger[fa2.LedgerKey.make(token_id, alice.address)], 5*Constants.PRECISION_FACTOR)

        scenario.h2("Remove intent to sell")
        scenario.p("Cannot remove intent if does not have")
        scenario += options_listing.remove_intent().run(sender=bob, valid=False)
        scenario.p("Can remove what I previously created")
        scenario += options_listing.remove_intent().run(sender=alice)
        scenario.verify_equal(options_listing.data.intents.contains(alice.address), False)
        scenario.verify_equal(token.data.ledger[fa2.LedgerKey.make(token_id, alice.address)], 10*Constants.PRECISION_FACTOR)

        scenario.p("Putting back intent")
        scenario += options_listing.advertise_intent(5*Constants.PRECISION_FACTOR).run(sender=alice)

        scenario.h2("Fullfill Intent")

        fee_amount = (5*Constants.PRECISION_FACTOR*1000000)>>Constants.BID_FEE_BITSHIFT
        matching_amount = sp.as_nat(5*Constants.PRECISION_FACTOR*1000000-fee_amount)/Constants.PRECISION_FACTOR
        scenario.p("Cannot fullfill too late")
        scenario += options_listing.fulfill_intent(alice.address).run(sender=bob, amount=sp.utils.nat_to_mutez(matching_amount), now=sp.timestamp(2*24*60*60+1), valid=False)
        scenario.p("Can if amount is right")
        scenario += options_listing.fulfill_intent(alice.address).run(sender=bob, amount=sp.utils.nat_to_mutez(matching_amount), now=sp.timestamp(0), valid=True)

        scenario.verify_equal(options_listing.data.intents.contains(alice.address), False)
        scenario.verify_equal(token.data.ledger[fa2.LedgerKey.make(token_id, alice.address)], 5*Constants.PRECISION_FACTOR)
        scenario.verify_equal(token.data.ledger[fa2.LedgerKey.make(token_id, bob.address)], 15*Constants.PRECISION_FACTOR)

        scenario.p("Putting back intent")
        scenario += options_listing.advertise_intent(5*Constants.PRECISION_FACTOR).run(sender=alice)

        scenario.p("Partial intent fullfillment")
        fee_amount = (2*Constants.PRECISION_FACTOR*1000000)>>Constants.BID_FEE_BITSHIFT
        matching_amount = sp.as_nat(2*Constants.PRECISION_FACTOR*1000000-fee_amount)/Constants.PRECISION_FACTOR
        scenario += options_listing.fulfill_intent(alice.address).run(sender=bob, amount=sp.utils.nat_to_mutez(matching_amount), valid=True)

        scenario.verify_equal(options_listing.data.intents.contains(alice.address), True)
        scenario.verify_equal(token.data.ledger[fa2.LedgerKey.make(token_id, bob.address)], 17*Constants.PRECISION_FACTOR)
        scenario.verify_equal(token.data.ledger[fa2.LedgerKey.make(token_id, options_listing.address)], 3*Constants.PRECISION_FACTOR)
        scenario.verify_equal(options_listing.data.intents[alice.address].token_amount, 3*Constants.PRECISION_FACTOR)
        scenario += options_listing.remove_intent().run(sender=alice)
        scenario.p("Putting back intent")

        scenario += token.mint(owner=alice.address, token_id=token_id, token_amount=10*Constants.PRECISION_FACTOR)
        scenario += options_listing.advertise_intent(5*Constants.PRECISION_FACTOR).run(sender=alice)

        scenario.h2("Execute Intent")
        scenario.p("Cannot execute too early")
        scenario += options_listing.execute_intent(address=bob.address, token_amount=2*Constants.PRECISION_FACTOR).run(sender=alice, valid=False, now=sp.timestamp(0))
        scenario.p("Cannot execute too big amount")
        scenario += options_listing.execute_intent(address=bob.address, token_amount=6*Constants.PRECISION_FACTOR).run(sender=alice, valid=False, now=sp.timestamp(24*60*60))
        scenario.p("Can execute intent")
        scenario += options_listing.execute_intent(address=bob.address, token_amount=5*Constants.PRECISION_FACTOR).run(sender=alice, now=sp.timestamp(24*60*60))
        scenario.show(token.data.ledger[fa2.LedgerKey.make(token_id, bob.address)])
        scenario.verify_equal(token.data.ledger[fa2.LedgerKey.make(token_id, bob.address)], 17*Constants.PRECISION_FACTOR)
        scenario.verify_equal(token.data.ledger[fa2.LedgerKey.make(token_id, alice.address)], 8*Constants.PRECISION_FACTOR)
        scenario.verify_equal(token.data.ledger[fa2.LedgerKey.make(token_id, options_listing.address)], 0)


