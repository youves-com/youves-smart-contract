import smartpy as sp

import utils.error_codes as Errors
import utils.constants as Constants

from utils.administrable_mixin import SingleAdministrableMixin


class ExchangeOracle(sp.Contract, SingleAdministrableMixin):
    """The ExchangeOracle allows to determine the min_out for a unified staking trade.

    Args:
        (sp.Contract): this is a smartpy contract
        (SingleAdministrableMixin): mixin used whenever we have a single administrator.

    """

    def __init__(
        self,
        symbol_relation_path=sp.list(t=sp.TString, l=[]),
        slippage_numerator=sp.nat(1),
        slippage_denominator=sp.nat(1),
        administrators=sp.big_map(tkey=sp.TAddress, tvalue=sp.TNat),
        src_token_decimals=12,
        dst_token_decimals=12,
    ):
        """The storage can be initialised with a list of administrators

        Args:
            administrators (dict, optional): the initial list of administrator to allow. Defaults to {}.
        """
        self.storage_dict = {
            "administrators": administrators,
            "price_oracle": Constants.DEFAULT_ADDRESS,
            "symbol_relation_path": symbol_relation_path,
            "slippage_numerator": slippage_numerator,
            "slippage_denominator": slippage_denominator,
        }
        self.src_token_decimals = src_token_decimals
        self.dst_token_decimals = dst_token_decimals

        self.init(**self.storage_dict)

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_symbol_relation_path(self, symbol_relation_path):
        sp.set_type(symbol_relation_path, sp.TList(sp.TString))
        self.verify_is_admin(sp.unit)
        self.data.symbol_relation_path = symbol_relation_path

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_price_oracle(self, price_oracle):
        sp.set_type(price_oracle, sp.TAddress)
        self.verify_is_admin(sp.unit)
        self.data.price_oracle = price_oracle

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_slippage(self, slippage):
        sp.set_type(
            slippage,
            sp.TRecord(slippage_numerator=sp.TNat, slippage_denominator=sp.TNat).layout(
                ("slippage_numerator", "slippage_denominator")
            ),
        )
        self.verify_is_admin(sp.unit)
        self.data.slippage_numerator = slippage.slippage_numerator
        self.data.slippage_denominator = slippage.slippage_denominator

    @sp.onchain_view()
    def get_min_out(self, token_amount):
        sp.set_type(token_amount, sp.TNat)
        price = sp.local("price", 0)
        with sp.for_("symbol", self.data.symbol_relation_path) as symbol:
            with sp.if_(price.value == 0):
                price.value = sp.view(
                    "get_price", self.data.price_oracle, symbol, t=sp.TNat
                ).open_some(Errors.INVALID_VIEW)
            with sp.else_():
                price.value = (
                    price.value
                    * Constants.PRICE_PRECISION_FACTOR
                    // sp.view(
                        "get_price", self.data.price_oracle, symbol, t=sp.TNat
                    ).open_some(Errors.INVALID_VIEW)
                )

        sp.result(
            (token_amount * (10**self.dst_token_decimals) * price.value * self.data.slippage_numerator)
            // ((10**self.src_token_decimals) * Constants.PRICE_PRECISION_FACTOR * self.data.slippage_denominator)
        )
