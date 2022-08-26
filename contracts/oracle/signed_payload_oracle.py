import smartpy as sp

import utils.constants as Constants
import utils.error_codes as Errors


class Price:
    def get_type():
        return sp.TRecord(
            exchange_id=sp.TString,
            symbol=sp.TString,
            price=sp.TNat,
            volume=sp.TNat,
            timestamp=sp.TTimestamp,
            certificate_sha256=sp.TBytes,
        ).layout(
            (
                "exchange_id",
                ("symbol", ("price", ("volume", ("timestamp", "certificate_sha256")))),
            )
        )

    def make(exchainge_id, symbol, price, volume, timestamp, certificate_sha256):
        return sp.set_type_expr(
            sp.record(
                exchange_id=exchainge_id,
                symbol=symbol,
                price=price,
                volume=volume,
                timestamp=timestamp,
                certificate_sha256=certificate_sha256,
            ),
            Price.get_type(),
        )


class SignedPayloadOracle(sp.Contract):
    """This oracle offers a "set_price" method which acceppts signed payload. If equal or more than
    "signature_threshold" parties agree on the same price and the payload is not older than
    "time_window" the new price is set in storage. get_price will work as long as the price is not
    older than "validity_window_in_epochs". Price can only be set once per period.

    Args:
        sp ([type]): [description]
    """

    def __init__(self, trusted_keys, trusted_certificates):
        self.add_flag("initial-cast")
        self.init(
            time_window=sp.int(60 * 5),  # 5 min
            validity_window_in_epochs=sp.nat(4),
            last_epoch=sp.nat(0),
            signature_threshold=sp.nat(2),
            trusted_keys=sp.set_type_expr(trusted_keys, sp.TMap(sp.TKey, sp.TUnit)),
            trusted_certificates=sp.set_type_expr(
                trusted_certificates, sp.TMap(sp.TBytes, sp.TUnit)
            ),
            price=sp.nat(100000),
        )

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_price(self, signed_payload):
        """This entrypoint can be called by anyone, however the only if the payload is signed
        correctly the price is update. The higher median price is set in case of even number of
        payloads, otherwise the median price is set. If the price difference is greater than 6.25%
        then the price is adapted by + or -6.25% depending on the direction of the provided price.

        Args:
            signed_payload (sp.TMap): this is the payload containing all payaload and signatures
        """
        sp.set_type(signed_payload, sp.TMap(sp.TKey, sp.TMap(sp.TBytes, sp.TSignature)))
        current_epoch = sp.local(
            "current_epoch",
            sp.as_nat(sp.now - sp.timestamp(0)) // Constants.ORACLE_EPOCH_INTERVAL,
        )
        with sp.if_(self.data.last_epoch < current_epoch.value):
            threshold_counter = sp.local(
                "threshold_counter", sp.map({}, tkey=sp.TBytes, tvalue=sp.TNat)
            )
            price_sorter = sp.local("price_sorter", sp.set())

            with sp.for_("signer_item", signed_payload.items()) as signer_item:
                with sp.if_(self.data.trusted_keys.contains(signer_item.key)):
                    with sp.for_(
                        "payload_item", signer_item.value.items()
                    ) as payload_item:
                        with sp.if_(
                            sp.check_signature(
                                signer_item.key, payload_item.value, payload_item.key
                            )
                        ):
                            with sp.if_(
                                threshold_counter.value.contains(payload_item.key)
                            ):
                                threshold_counter.value[payload_item.key] += 1
                            with sp.else_():
                                threshold_counter.value[payload_item.key] = 1

            with sp.for_("item", threshold_counter.value.items()) as item:
                with sp.if_(item.value >= self.data.signature_threshold):
                    unpacked = sp.unpack(item.key, t=Price.get_type()).open_some()
                    with sp.if_(
                        self.data.trusted_certificates.contains(
                            unpacked.certificate_sha256
                        )
                    ):
                        with sp.if_(
                            sp.now
                            < unpacked.timestamp.add_seconds(self.data.time_window)
                        ):
                            price_sorter.value.add(unpacked.price)

            sorted_prices = sp.local("sorted_prices", price_sorter.value.elements())
            median_price = sp.local("median_price", 0)
            median_runner = sp.local("median_runner", 0)

            with sp.for_("price", sorted_prices.value) as price:
                with sp.if_(median_runner.value <= sp.len(sorted_prices.value) // 2):
                    median_price.value = price
                    median_runner.value += 1

            with sp.if_(median_price.value > 0):
                with sp.if_(
                    self.data.price >> 4 > abs(self.data.price - median_price.value)
                ):
                    self.data.price = median_price.value
                with sp.else_():
                    with sp.if_(self.data.price - median_price.value > 0):
                        self.data.price = sp.as_nat(
                            self.data.price - (self.data.price >> 4)
                        )
                    with sp.else_():
                        self.data.price = self.data.price + (self.data.price >> 4)
                self.data.last_epoch = current_epoch.value

    @sp.entry_point(check_no_incoming_transfer=True)
    def get_price(self, callback):
        """this entrypoint can be called by everyone that provides a valid callback. Only if the
        price is not older than 4 epochs it will be returned.
        IMPORTANT: as we require for our use case the quote currency to be the collateral we are
        "flipping" base and quote by 1//"stored price"

        Args:
            callback (sp.TContract(sp.TNat)): callback where to receive the price
        """
        sp.set_type(callback, sp.TContract(sp.TNat))
        current_epoch = (
            sp.as_nat(sp.now - sp.timestamp(0)) // Constants.ORACLE_EPOCH_INTERVAL
        )
        sp.verify(
            self.data.last_epoch
            > sp.as_nat(current_epoch - self.data.validity_window_in_epochs),
            message=Errors.PRICE_TOO_OLD,
        )
        sp.transfer(
            Constants.PRECISION_FACTOR // self.data.price, sp.mutez(0), callback
        )
