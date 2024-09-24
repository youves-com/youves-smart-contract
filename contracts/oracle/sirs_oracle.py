import smartpy as sp

import utils.constants as Constants
import utils.error_codes as Errors
from utils.administrable_mixin import SingleAdministrableMixin


class SirsOracle(sp.Contract):
    """
    Oracle to return the price of tzBTC in the price of the SIRS (previously known as tzBTC LP)
    token or viceversa.
    The caller can retrieve the price via an on-chain view.
    The price is fetched every 15 mins by a bot that calls an on-chain oracle for the price of
    tzBTC / SIRS. If the price is older than 15 mins, than the oracle will fail.
    """

    def __init__(
        self,
        oracle,
        requires_flip,
        extra_precision_factor,
    ):
        self.init(
            oracle=oracle,
            price=sp.nat(0),
            last_epoch=sp.nat(0),
            validity_window_in_epochs=sp.nat(4),
        )

        self.extra_precision_factor = extra_precision_factor
        self.requires_flip = requires_flip

    @sp.entry_point
    def set_price(self, price):
        sp.set_type(price, sp.TNat)
        current_epoch = sp.local(
            "current_epoch",
            sp.as_nat(sp.now - sp.timestamp(0)) // Constants.ORACLE_EPOCH_INTERVAL,
        )

        sp.verify(
            current_epoch.value > self.data.last_epoch,
            message=Errors.PRICE_ALREADY_SET_IN_EPOCH,
        )
        sp.verify(sp.sender == self.data.oracle, message=Errors.INVALID_SENDER)

        with sp.if_(self.requires_flip):
            self.data.price = (10**12 * self.extra_precision_factor) / price
        with sp.else_():
            self.data.price = price * self.extra_precision_factor
        self.data.last_epoch = (
            sp.as_nat(sp.now - sp.timestamp(0)) // Constants.ORACLE_EPOCH_INTERVAL
        )

    @sp.onchain_view()
    def get_price(self):
        current_epoch = (
            sp.as_nat(sp.now - sp.timestamp(0)) // Constants.ORACLE_EPOCH_INTERVAL
        )
        sp.verify(
            self.data.last_epoch
            > sp.as_nat(current_epoch - self.data.validity_window_in_epochs),
            message=Errors.PRICE_TOO_OLD,
        )
        sp.verify(self.data.price > 0, message=Errors.CANNOT_BE_ZERO)
        sp.result(self.data.price)


class RelativeSirsOracle(sp.Contract):
    """This smart contract is used for the calculation of the right price. It takes the base symbol and puts it into relation with the quote symbol."""

    def __init__(self, sirs_oracle, generic_oracle, symbol):
        self.init(sirs_oracle=sirs_oracle, generic_oracle=generic_oracle, symbol=symbol)

    @sp.entry_point
    def default(self):
        """This is a dummy entrypoint in order to allow us to have the named "get_price" entrypoint (if a contract has only
        1 entrypoint it becomes not-named default otherwise).
        """
        sp.send(sp.sender, sp.amount)

    @sp.onchain_view()
    def get_price(self):
        """this entrypoint can be called by everyone that provides a valid callback. Only if the price is not older than 4 epochs it will be returned.
        IMPORTANT: some engines (i.e. uUSD engine) require for our use case the quote currency to be the collateral we are "flipping" base and quote
        by 1//"stored price" if the python variable self.requires_flip is set to True. This switch is evaluated at compiletime and will not be reflected
        in the resulting michelson.
        """
        base_price = sp.view(
            "get_price", self.data.sirs_oracle, sp.unit, t=sp.TNat
        ).open_some(Errors.INVALID_VIEW)
        quote_price = sp.view(
            "get_price", self.data.generic_oracle, self.data.symbol, t=sp.TNat
        ).open_some(Errors.INVALID_VIEW)

        price = base_price * Constants.PRICE_PRECISION_FACTOR // quote_price
        sp.result(price)


SYMBOL_AND_INVERSE = sp.TRecord(symbol=sp.TString, inversed=sp.TBool).layout(
    ("symbol", "inversed")
)


class GenericRelativeSirsOracle(sp.Contract, SingleAdministrableMixin):
    """This smart contract is used for the calculation of the right price. It takes the base symbol and puts it into relation with the quote symbol."""

    def __init__(
        self,
        symbol_relation_path=sp.list(t=sp.TList(SYMBOL_AND_INVERSE), l=[]),
        administrators=sp.big_map(tkey=sp.TAddress, tvalue=sp.TNat),
        generic_oracle=Constants.DEFAULT_ADDRESS,
        sirs_oracle=Constants.DEFAULT_ADDRESS,
    ):
        """The storage can be initialised with a list of administrators

        Args:
            administrators (dict, optional): the initial list of administrator to allow. Defaults to {}.
        """
        self.storage_dict = {
            "administrators": administrators,
            "generic_oracle": generic_oracle,
            "sirs_oracle": sirs_oracle,
            "symbol_relation_path": symbol_relation_path,
        }

        self.init(**self.storage_dict)

    @sp.entry_point
    def default(self):
        """This is a dummy entrypoint in order to allow us to have the named "get_price" entrypoint (if a contract has only
        1 entrypoint it becomes not-named default otherwise).
        """
        sp.send(sp.sender, sp.amount)

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_symbol_relation_path(self, symbol_relation_path):
        sp.set_type(symbol_relation_path, sp.TList(SYMBOL_AND_INVERSE))
        self.verify_is_admin(sp.unit)
        self.data.symbol_relation_path = symbol_relation_path

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_generic_oracle(self, generic_oracle):
        sp.set_type(generic_oracle, sp.TAddress)
        self.verify_is_admin(sp.unit)
        self.data.generic_oracle = generic_oracle

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_sirs_oracle(self, sirs_oracle):
        sp.set_type(sirs_oracle, sp.TAddress)
        self.verify_is_admin(sp.unit)
        self.data.sirs_oracle = sirs_oracle

    @sp.onchain_view()
    def get_price(self):
        final_price = sp.local("final_price", Constants.PRICE_PRECISION_FACTOR)
        with sp.for_(
            "symbol_relation", self.data.symbol_relation_path
        ) as symbol_relation:
            intermediary_price = sp.view(
                "get_price", self.data.generic_oracle, symbol_relation.symbol, t=sp.TNat
            ).open_some(Errors.INVALID_VIEW)

            with sp.if_(symbol_relation.inversed == sp.bool(False)):
                final_price.value = (
                    final_price.value
                    * intermediary_price
                    / Constants.PRICE_PRECISION_FACTOR
                )
            with sp.else_():
                final_price.value = (
                    final_price.value
                    * Constants.PRICE_PRECISION_FACTOR
                    / intermediary_price
                )
        sirs_price = sp.view(
            "get_price", self.data.sirs_oracle, sp.unit, t=sp.TNat
        ).open_some(Errors.INVALID_VIEW)
        final_price.value = (
            sirs_price * Constants.PRICE_PRECISION_FACTOR / final_price.value
        )
        sp.result(final_price.value)
