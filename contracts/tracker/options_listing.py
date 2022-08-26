import smartpy as sp

import utils.error_codes as Errors
import utils.constants as Constants
import utils.fa2 as fa2

from utils.contract_utils import Utils
from contracts.tracker.tracker_engine import Settlement


class Intent:
    """Intent to bid a certain token_amount"""

    def get_type():
        """Returns a single Intent type, layouted

        Returns:
            sp.TRecord: the layouted intent
        """
        return sp.TRecord(token_amount=sp.TNat, start_timestamp=sp.TTimestamp).layout(
            ("token_amount", "start_timestamp")
        )

    def make(token_amount, start_timestamp):
        """Makes an instance of an intent

        Args:
            token_amount (sp.nat): token_amount
            start_timestamp (sp.timestamp): start_timestamp

        Returns:
            Intent: the intent record
        """
        return sp.set_type_expr(
            sp.record(token_amount=token_amount, start_timestamp=start_timestamp),
            Intent.get_type(),
        )


class Execution:
    """Parameter use in fullfill and execute intent"""

    def get_type():
        """Returns a single Execution type, layouted

        Returns:
            sp.TRecord: the layouted intent
        """
        return sp.TRecord(address=sp.TAddress, token_amount=sp.TNat).layout(
            ("address", "token_amount")
        )

    def make(address, token_amount):
        """Makes an instance of an fullfillment

        Args:
            address (sp.address): address
            token_amount (sp.nat): token_amount

        Returns:
            Execution: the fullfillment record
        """
        return sp.set_type_expr(
            sp.record(address=address, token_amount=token_amount), Execution.get_type()
        )


class OptionsListing(sp.Contract):
    """The options listing contract is used for advertising intents to sell tokens for collateral. If no buyer is found within 24 hours
    the option can be executed against a specific vault.

    Args:
        (sp.Contract): this is a smartpy contract
    """

    def get_init_storage(self):
        """Returns the initial storage of the contract used for inheritance of smartpy contracts

        Returns:
            dict: initial storage of the contract
        """
        storage = {}
        storage["intents"] = sp.big_map(tkey=sp.TAddress, tvalue=Intent.get_type())
        storage["token_address"] = self.token_address
        storage["token_id"] = self.token_id
        storage["engine_address"] = self.engine_address
        storage["target_price_oracle"] = self.target_price_oracle

        return storage

    def __init__(self, token_address, token_id, engine_address, target_price_oracle):
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

    @sp.entry_point(check_no_incoming_transfer=True)
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
        sp.verify(
            ~self.data.intents.contains(sp.sender), message=Errors.ALREADY_PRESENT
        )
        sp.verify(
            token_amount >= Constants.MIN_TOKEN_AMOUNT_THRESHOLD,
            message=Errors.AMOUNT_TOO_SMALL,
        )

        Utils.execute_fa2_token_transfer(
            self.data.token_address,
            sp.sender,
            sp.self_address,
            self.data.token_id,
            token_amount,
        )
        self.data.intents[sp.sender] = Intent.make(token_amount, sp.now)

    @sp.entry_point(check_no_incoming_transfer=True)
    def remove_intent(self):
        """entrypoint to remove your own intent
        Pre: storage.intents.contains(sp.sender)
        Post: transfer tokens from self to sender
        Post: del storage.intents[sp.sender]
        """
        intent = self.data.intents[sp.sender]
        Utils.execute_fa2_token_transfer(
            self.data.token_address,
            sp.self_address,
            sp.sender,
            self.data.token_id,
            intent.token_amount,
        )
        del self.data.intents[sp.sender]

    @sp.entry_point
    def fulfill_intent(self, address):
        """This it the actual fullfillment mechanics, it will check if the intent has not expired yet and then if the sp amount sent was enough sell the
        tokens at a premium to the sender.
        Pre: sp.now <= storage.intents[address].start_timestamp + 48hours
        Pre: sp.amount >= 1000
        Post: transfer tokens from self to storage.sender
        Post: send sp.amount to address
        Post: storage.intents[address].token_amount -= sp.amount/(storage.target_price * 0.9375)

        Args:
            address (TAddress): the address of the intent owner
        """
        sp.set_type(address, sp.TAddress)

        intent = sp.local("intent", self.data.intents[address])

        sp.verify(
            sp.now
            <= intent.value.start_timestamp.add_seconds(
                Constants.OPTION_TIME_WINDOW_IN_SECONDS
            ),
            Errors.TOO_LATE,
        )
        sp.verify(
            sp.amount >= Constants.MIN_AMOUNT_THRESHOLD, message=Errors.AMOUNT_TOO_SMALL
        )

        target_price = sp.view(
            "get_price", self.data.target_price_oracle, sp.unit, t=sp.TNat
        ).open_some(Errors.INVALID_VIEW)

        fee_adjusted_target_price = sp.as_nat(target_price
            - (target_price>> Constants.BID_FEE_BITSHIFT)
        )
        token_amount = sp.local(
            "token_amount",
            (sp.utils.mutez_to_nat(sp.amount) * Constants.PRECISION_FACTOR)
            // fee_adjusted_target_price,
        )

        sp.verify(
            intent.value.token_amount >= token_amount.value,
            Errors.INSUFFICIENT_TOKEN_AMOUNT,
        )

        intent.value.token_amount = sp.as_nat(
            intent.value.token_amount - token_amount.value
        )

        Utils.execute_fa2_token_transfer(
            self.data.token_address,
            sp.self_address,
            sp.sender,
            self.data.token_id,
            token_amount.value,
        )

        sp.send(address, sp.amount)

        self.data.intents[address] = intent.value

        with sp.if_(intent.value.token_amount == 0):
            del self.data.intents[address]

    @sp.entry_point(check_no_incoming_transfer=True)
    def execute_intent(self, execution):
        """entrypoint to be used by the used 24h after the intent was published and not fullfilled. It can be executed against a vault.
        The associated tracker engine needs to be an operator for this contract in order to successfully execute a “settle_with_vault” in the tracker engine contract.

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

        intent = sp.local("intent", self.data.intents[sp.sender])
        sp.verify(
            sp.now
            >= intent.value.start_timestamp.add_seconds(
                Constants.ADVERTISE_TIME_WINDOW_IN_SECONDS
            ),
            Errors.TOO_EARLY,
        )
        sp.verify(
            sp.now
            <= intent.value.start_timestamp.add_seconds(
                Constants.OPTION_TIME_WINDOW_IN_SECONDS
            ),
            Errors.TOO_LATE,
        )
        sp.verify(
            intent.value.token_amount >= execution.token_amount,
            Errors.INSUFFICIENT_TOKEN_AMOUNT,
        )
        sp.verify(
            execution.token_amount >= Constants.MIN_TOKEN_AMOUNT_THRESHOLD,
            message=Errors.AMOUNT_TOO_SMALL,
        )

        intent.value.token_amount = sp.as_nat(
            intent.value.token_amount - execution.token_amount
        )

        engine_contract = sp.contract(
            Settlement.get_type(),
            self.data.engine_address,
            entry_point="settle_with_vault",
        ).open_some()
        sp.transfer(
            Settlement.make(execution.address, execution.token_amount, sp.sender),
            sp.mutez(0),
            engine_contract,
        )

        self.data.intents[sp.sender] = intent.value

        with sp.if_(intent.value.token_amount == 0):
            del self.data.intents[sp.sender]
