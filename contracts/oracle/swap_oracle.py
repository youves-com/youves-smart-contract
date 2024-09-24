import smartpy as sp

import utils.constants as Constants
import utils.error_codes as Errors
from utils.administrable_mixin import SingleAdministrableMixin
from contracts.oracle.on_demand_oracle import PriceData

class AggregationItem:
    def get_type():
        return sp.TRecord(
            oracle=sp.TAddress,
            symbol=sp.TOption(sp.TString),
            validity_in_seconds=sp.TOption(sp.TInt),
            reverse=sp.TBool
        ).layout(("oracle", ("symbol", ("validity_in_seconds", "reverse"))))

class FlatCurveTargetOracle(sp.Contract, SingleAdministrableMixin):
    def __init__(
        self,
        administrators=sp.big_map(l={}, tkey=sp.TAddress, tvalue=sp.TNat),
        aggregation_path=sp.list(l=[], t=AggregationItem.get_type()),
        price_precision_factor=sp.nat(10**12),
        metadata = sp.big_map(
            l={
                "": sp.bytes(
                    "0x74657a6f732d73746f726167653a64617461"
                ),  # "tezos-storage:data"
                "data": sp.utils.bytes_of_string(
                    '{ "name": "Youves Flat Curve Target Oracle", "authors": ["Youves <contact@youves.com>"], "homepage":  "https://app.youves.com" }'
                ),
            },
            tkey=sp.TString,
            tvalue=sp.TBytes,
        )
    ):
        self.init_type(
            sp.TRecord(
                administrators=sp.TBigMap(sp.TAddress, sp.TNat),
                aggregation_path=sp.TList(AggregationItem.get_type()),
                price_precision_factor=sp.TNat,
                metadata=sp.TBigMap(sp.TString, sp.TBytes),
            )
        )
        self.init(
            administrators=administrators,
            aggregation_path=aggregation_path,
            price_precision_factor=price_precision_factor,
            metadata=metadata,
        )

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_aggregation_path(self, path):
        sp.set_type(path, sp.TList(AggregationItem.get_type()))
        self.verify_is_admin(sp.unit)

        self.data.aggregation_path = path
    
    @sp.onchain_view()
    def get_cash_price_in_token(self):
        inverse_price = sp.local(
            "inverse_price",
            sp.view(
                "get_token_price_in_cash",
                sp.self_address,
                sp.unit,
                t=sp.TNat
            ).open_some())
        
        sp.result(self.data.price_precision_factor * self.data.price_precision_factor // inverse_price.value)
    
    @sp.onchain_view()
    def get_token_price_in_cash(self):
        extra_precision_factor = sp.local("extra_precision_factor", sp.nat(1))
        with sp.if_(self.data.price_precision_factor > Constants.PRICE_PRECISION_FACTOR):
            extra_precision_factor.value = self.data.price_precision_factor // Constants.PRICE_PRECISION_FACTOR
        
        price = sp.local("price", self.data.price_precision_factor)
        with sp.for_("item", self.data.aggregation_path) as item:
            local_price = sp.local("local_price", self.data.price_precision_factor)
            with sp.if_(item.symbol.is_some()):
                with sp.if_(item.validity_in_seconds.is_some()):
                    price_with_timestamp = sp.local(
                        "price_with_timestamp",
                        sp.view("get_price_with_timestamp", item.oracle, item.symbol.open_some(), t=PriceData.get_type()).open_some(message="Invalid view: get_price_with_timestamp")
                    )
                    last_valid_timestamp = sp.local(
                        "last_valid_timestamp",
                        price_with_timestamp.value.last_update_timestamp.add_seconds(item.validity_in_seconds.open_some())
                    )
                    sp.verify(sp.now <= last_valid_timestamp.value, message="PriceTooOld")
                    local_price.value = price_with_timestamp.value.price
                with sp.else_():
                    local_price.value = sp.view("get_price", item.oracle, item.symbol.open_some(), t=sp.TNat).open_some(message="Invalid view: get_price")
            with sp.else_():
                local_price.value = sp.view("get_price", item.oracle, sp.unit, t=sp.TNat).open_some(message="Invalid view: get_price")
            
            with sp.if_(item.reverse == sp.bool(True)):
                local_price.value = Constants.PRICE_PRECISION_FACTOR * Constants.PRICE_PRECISION_FACTOR // local_price.value

            local_price.value = local_price.value * extra_precision_factor.value
            price.value = price.value * local_price.value // self.data.price_precision_factor
        sp.result(price.value)
    