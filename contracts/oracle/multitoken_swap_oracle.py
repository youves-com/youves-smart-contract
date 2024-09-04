import smartpy as sp

from utils.administrable_mixin import SingleAdministrableMixin
from contracts.tracker.types import TokenVariant
from utils.contract_utils import Ratio


class MultipoolOracle(sp.Contract, SingleAdministrableMixin):
    def __init__(
        self,
        administrators=sp.big_map(l={}, tkey=sp.TAddress, tvalue=sp.TNat),
        price_fetching_lambda=sp.big_map(
            l={}, tkey=TokenVariant.get_type(), tvalue=sp.TLambda(sp.TUnit, Ratio.get_type())),
    ):
        self.init_type(
            sp.TRecord(
                administrators=sp.TBigMap(sp.TAddress, sp.TNat),
                price_fetching_lambda=sp.TBigMap(TokenVariant.get_type(), sp.TLambda(sp.TUnit, Ratio.get_type())),
            )
        )

        self.init(
            administrators=administrators,
            price_fetching_lambda=price_fetching_lambda
        )
    
    @sp.entry_point(check_no_incoming_transfer=True)
    def update_price_fetching_lambda(self, key, fetching_lambda):
        sp.set_type(key, TokenVariant.get_type())
        sp.set_type(fetching_lambda, sp.TLambda(sp.TUnit, Ratio.get_type()))

        self.data.price_fetching_lambda[key] = fetching_lambda

    @sp.entry_point(check_no_incoming_transfer=True)
    def remove_price_fetching_lambda(self, key):
        sp.set_type(key, TokenVariant.get_type())

        del self.data.price_fetching_lambda[key]

    @sp.onchain_view()
    def get_token_price(self, token):
        sp.set_type(token, TokenVariant.get_type())

        sp.verify(self.data.price_fetching_lambda.contains(token), message="UnknownToken")
        sp.result(self.data.price_fetching_lambda[token](sp.unit))