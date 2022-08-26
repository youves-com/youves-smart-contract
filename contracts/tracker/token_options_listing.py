import smartpy as sp

import utils.error_codes as Errors
import utils.constants as Constants

from contracts.tracker.options_listing import OptionsListing, Intent
from utils.contract_utils import Utils


class TokenFulfill:
    """Parameter use in fullfill for the token options listing"""

    def get_type():
        """Returns a single TokenFulfill type, layouted

        Returns:
            sp.TRecord: the layouted intent
        """
        return sp.TRecord(address=sp.TAddress, collateral_token_amount=sp.TNat).layout(
            ("address", "collateral_token_amount")
        )

    def make(address, collateral_token_amount):
        """Makes an instance of an fullfillment

        Args:
            address (sp.address): address
            collateral_token_amount (sp.nat): collateral_token_amount

        Returns:
            TokenFulfill: the fullfillment record
        """
        return sp.set_type_expr(
            sp.record(address=address, collateral_token_amount=collateral_token_amount),
            TokenFulfill.get_type(),
        )


class TokenOptionsListing(OptionsListing):
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
        storage["intents"] = sp.big_map(tkey=sp.TAddress, tvalue=Intent.get_type())
        storage["token_address"] = self.token_address
        storage["token_id"] = self.token_id
        storage["collateral_token_address"] = self.collateral_token_address
        storage["collateral_token_id"] = self.collateral_token_id
        storage["engine_address"] = self.engine_address
        storage["target_price_oracle"] = self.target_price_oracle

        return storage

    def __init__(
        self,
        token_address,
        token_id,
        collateral_token_address,
        collateral_token_id,
        engine_address,
        target_price_oracle,
        collateral_token_type=Constants.TOKEN_TYPE_FA2,
        token_decimals=12,
        collateral_token_decimals=12,
        price_extra_precision_factor=1,
    ):
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
        self.collateral_token_address = collateral_token_address
        self.collateral_token_id = collateral_token_id
        self.engine_address = engine_address
        self.collateral_token_type = collateral_token_type
        self.token_decimals = token_decimals
        self.collateral_token_decimals = collateral_token_decimals
        self.price_extra_precision_factor = price_extra_precision_factor
        self.init(**self.get_init_storage())

    @sp.entry_point(check_no_incoming_transfer=True)
    def fulfill_intent(self, token_fulfill):
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
        sp.set_type(token_fulfill, TokenFulfill.get_type())
        intent = sp.local("intent", self.data.intents[token_fulfill.address])

        sp.verify(
            sp.now
            <= intent.value.start_timestamp.add_seconds(
                Constants.OPTION_TIME_WINDOW_IN_SECONDS
            ),
            Errors.TOO_LATE,
        )
        sp.verify(
            token_fulfill.collateral_token_amount
            >= Constants.MIN_COLLATERAL_AMOUNT_THRESHOLD,
            message=Errors.AMOUNT_TOO_SMALL,
        )

        target_price = sp.view(
            "get_price", self.data.target_price_oracle, sp.unit, t=sp.TNat
        ).open_some(Errors.INVALID_VIEW)

        fee_adjusted_target_price = sp.local(
            "fee_adjusted_target_price",
            sp.as_nat(
                target_price
                - (target_price >> Constants.BID_FEE_BITSHIFT)
            ),
        )
        token_payout_amount = sp.local(
            "token_payout_amount",
            (
                (
                    token_fulfill.collateral_token_amount
                    * Constants.PRICE_PRECISION_FACTOR
                    * self.price_extra_precision_factor
                )
                * 10**self.token_decimals
            )
            // (fee_adjusted_target_price.value * 10**self.collateral_token_decimals),
        )

        sp.verify(
            intent.value.token_amount >= token_payout_amount.value,
            Errors.INSUFFICIENT_TOKEN_AMOUNT,
        )

        intent.value.token_amount = sp.as_nat(
            intent.value.token_amount - token_payout_amount.value
        )

        Utils.execute_fa2_token_transfer(
            self.data.token_address,
            sp.self_address,
            sp.sender,
            self.data.token_id,
            token_payout_amount.value,
        )

        if self.collateral_token_type == Constants.TOKEN_TYPE_FA2:
            Utils.execute_fa2_token_transfer(
                self.data.collateral_token_address,
                sp.sender,
                token_fulfill.address,
                self.data.collateral_token_id,
                token_fulfill.collateral_token_amount,
            )
        elif self.collateral_token_type == Constants.TOKEN_TYPE_FA1:
            Utils.execute_fa1_token_transfer(
                self.data.collateral_token_address,
                sp.sender,
                token_fulfill.address,
                token_fulfill.collateral_token_amount,
            )

        self.data.intents[token_fulfill.address] = intent.value

        with sp.if_(intent.value.token_amount == 0):
            del self.data.intents[token_fulfill.address]
