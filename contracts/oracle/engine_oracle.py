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
            price_precision_factor=sp.TNat,
            reverse=sp.TBool,
        ).layout(
            (
                "oracle",
                (
                    "symbol",
                    ("validity_in_seconds", ("price_precision_factor", "reverse")),
                ),
            )
        )


class EngineOracle(sp.Contract, SingleAdministrableMixin):
    def __init__(
        self,
        administrators=sp.big_map(l={}, tkey=sp.TAddress, tvalue=sp.TNat),
        aggregation_path=sp.list(l=[], t=AggregationItem.get_type()),
        price_precision_factor=sp.nat(10**12),
        metadata=sp.big_map(
            l={
                "": sp.bytes(
                    "0x74657a6f732d73746f726167653a64617461"
                ),  # "tezos-storage:data"
                "data": sp.utils.bytes_of_string(
                    '{ "name": "Youves Engine Oracle", "authors": ["Youves <contact@youves.com>"], "homepage":  "https://app.youves.com" }'
                ),
            },
            tkey=sp.TString,
            tvalue=sp.TBytes,
        ),
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

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_price_precision_factor(self, price_precision_factor):
        sp.set_type(price_precision_factor, sp.TNat)
        self.verify_is_admin(sp.unit)

        self.data.price_precision_factor = price_precision_factor

    @sp.onchain_view()
    def get_price(self):
        price = sp.local("price", self.data.price_precision_factor)

        with sp.for_("item", self.data.aggregation_path) as item:
            local_price = sp.local("local_price", self.data.price_precision_factor)
            with sp.if_(item.symbol.is_some()):
                with sp.if_(item.validity_in_seconds.is_some()):
                    # if the validity in seconds is set, we check the price is not too old.
                    price_with_timestamp = sp.local(
                        "price_with_timestamp",
                        sp.view(
                            "get_price_with_timestamp",
                            item.oracle,
                            item.symbol.open_some(),
                            t=PriceData.get_type(),
                        ).open_some(message="Invalid view: get_price_with_timestamp"),
                    )
                    last_valid_timestamp = sp.local(
                        "last_valid_timestamp",
                        price_with_timestamp.value.last_update_timestamp.add_seconds(
                            item.validity_in_seconds.open_some()
                        ),
                    )
                    sp.verify(
                        sp.now <= last_valid_timestamp.value, message="PriceTooOld"
                    )
                    local_price.value = (
                        price_with_timestamp.value.price
                        * self.data.price_precision_factor
                        // item.price_precision_factor
                    )
                with sp.else_():
                    # if not, we accept the price as it is
                    local_price.value = sp.view(
                        "get_price", item.oracle, item.symbol.open_some(), t=sp.TNat
                    ).open_some(message="Invalid view: get_price")
                    local_price.value = (
                        local_price.value
                        * self.data.price_precision_factor
                        // item.price_precision_factor
                    )
            with sp.else_():
                local_price.value = sp.view(
                    "get_price", item.oracle, sp.unit, t=sp.TNat
                ).open_some(message="Invalid view: get_price")
                local_price.value = (
                    local_price.value
                    * self.data.price_precision_factor
                    // item.price_precision_factor
                )

            with sp.if_(item.reverse == sp.bool(True)):
                price.value = price.value * self.data.price_precision_factor // local_price.value
            with sp.else_():
                price.value = price.value * local_price.value // self.data.price_precision_factor
        sp.result(price.value)


class AsyncEngineOracle(sp.Contract, SingleAdministrableMixin):
    def __init__(
        self,
        administrators=sp.big_map(l={}, tkey=sp.TAddress, tvalue=sp.TNat),
        aggregation_path=sp.list(l=[], t=AggregationItem.get_type()),
        price_precision_factor=sp.nat(10**12),
        metadata=sp.big_map(
            l={
                "": sp.bytes(
                    "0x74657a6f732d73746f726167653a64617461"
                ),  # "tezos-storage:data"
                "data": sp.utils.bytes_of_string(
                    '{ "name": "Youves Engine Oracle", "authors": ["Youves <contact@youves.com>"], "homepage":  "https://app.youves.com" }'
                ),
            },
            tkey=sp.TString,
            tvalue=sp.TBytes,
        ),
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
    
    @sp.entry_point(check_no_incoming_transfer=True)
    def set_price_precision_factor(self, price_precision_factor):
        sp.set_type(price_precision_factor, sp.TNat)
        self.verify_is_admin(sp.unit)

        self.data.price_precision_factor = price_precision_factor

    @sp.entry_point(check_no_incoming_transfer=True)
    def get_price(self, callback):
        sp.set_type(callback, sp.TContract(sp.TNat))
        price = sp.local(
            "price",
            sp.view("get_price_view", sp.self_address, sp.unit, t=sp.TNat).open_some(),
        )
        sp.transfer(price.value, sp.mutez(0), callback)

    @sp.onchain_view()
    def get_price_view(self):
        price = sp.local("price", self.data.price_precision_factor)

        with sp.for_("item", self.data.aggregation_path) as item:
            local_price = sp.local("local_price", self.data.price_precision_factor)
            with sp.if_(item.symbol.is_some()):
                with sp.if_(item.validity_in_seconds.is_some()):
                    price_with_timestamp = sp.local(
                        "price_with_timestamp",
                        sp.view(
                            "get_price_with_timestamp",
                            item.oracle,
                            item.symbol.open_some(),
                            t=PriceData.get_type(),
                        ).open_some(message="Invalid view: get_price_with_timestamp"),
                    )
                    last_valid_timestamp = sp.local(
                        "last_valid_timestamp",
                        price_with_timestamp.value.last_update_timestamp.add_seconds(
                            item.validity_in_seconds.open_some()
                        ),
                    )
                    sp.verify(
                        sp.now <= last_valid_timestamp.value, message="PriceTooOld"
                    )
                    local_price.value = (
                        price_with_timestamp.value.price
                        * self.data.price_precision_factor
                        // item.price_precision_factor
                    )
                with sp.else_():
                    local_price.value = sp.view(
                        "get_price", item.oracle, item.symbol.open_some(), t=sp.TNat
                    ).open_some(message="Invalid view: get_price")
                    local_price.value = (
                        local_price.value
                        * self.data.price_precision_factor
                        // item.price_precision_factor
                    )

            with sp.else_():
                local_price.value = sp.view(
                    "get_price", item.oracle, sp.unit, t=sp.TNat
                ).open_some(message="Invalid view: get_price")
                local_price.value = (
                    local_price.value
                    * self.data.price_precision_factor
                    // item.price_precision_factor
                )

            with sp.if_(item.reverse == sp.bool(True)):
                price.value = price.value * self.data.price_precision_factor * self.data.price_precision_factor // local_price.value
            with sp.else_():
                price.value = price.value * local_price.value // self.data.price_precision_factor
        sp.result(price.value)
