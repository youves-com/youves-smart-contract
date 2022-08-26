import smartpy as sp

from contracts.oracle.job_scheduler import Fulfill

import utils.constants as Constants
import utils.error_codes as Errors


class Response:
    def get_type():
        """The response type used for the price oracle that uses the generic data
        transmitter.
        """
        return sp.TRecord(
            timestamp=sp.TNat, prices=sp.TList(ResponsePriceEntry.get_type())
        ).layout(("timestamp", "prices"))

    def make(timestamp, prices):
        """Courtesy function typing a record to Response.get_type()."""
        return sp.set_type_expr(
            sp.record(timestamp=timestamp, prices=prices), Response.get_type()
        )


class ResponsePriceEntry:
    def get_type():
        """A single price entry response type used for the price oracle that uses the
        generic data transmitter.
        """
        return sp.TRecord(symbol=sp.TString, price=sp.TNat).layout(("symbol", "price"))


class ValidPriceEntry:
    def get_type():
        """A valid single price entry type stored in the smart contract in order to do
        price aggregation.
        """
        return sp.TRecord(valid_respondants=sp.TSet(sp.TAddress), price=sp.TNat).layout(
            ("valid_respondants", "price")
        )

    def make(valid_respondants, price):
        """Courtesy function typing a record to ValidPriceEntry.get_type()."""
        return sp.set_type_expr(
            sp.record(valid_respondants=valid_respondants, price=price),
            ValidPriceEntry.get_type(),
        )


class StoragePriceEntry:
    """A single storage price entry type stored in the prices big map of the smart contract."""

    def get_type():
        return sp.TRecord(last_epoch=sp.TNat, price=sp.TNat).layout(
            ("last_epoch", "price")
        )

    def make(last_epoch, price):
        """Courtesy function typing a record to StoragePriceEntry.get_type()."""
        return sp.set_type_expr(
            sp.record(last_epoch=last_epoch, price=price), StoragePriceEntry.get_type()
        )


class PriceOracle(sp.Contract):
    """The generic price oracle accepts prices from the set sources and set script.
    The change in price logic is controlled by the validation and aggregation lambdas.
    This version of the oracle uses the onchain views to return prices.
    Only the administrator is allowed to change the script and sources.
    """

    def __init__(self, administrator):
        self.init(
            prices=sp.big_map(tkey=sp.TString, tvalue=StoragePriceEntry.get_type()),
            aggregation_lambda=sp.lambda_michelson(
                "{ CDR; UNPAIR; PUSH nat 0; DUP 3; COMPARE; GT; IF {} { PUSH int 501; FAILWITH }; DUP; PUSH nat 0; COMPARE; EQ; IF { PUSH bool True } { SWAP; DUP; DUG 2; SWAP; DUP; DUG 2; SUB; ABS; PUSH nat 4; DUP 3; LSR; COMPARE; GT }; IF { DROP } { PUSH int 0; DIG 2; DUP 3; SUB; COMPARE; GT; IF { DUP; PUSH nat 4; SWAP; LSR; SWAP; SUB; ISNAT; IF_NONE { PUSH int 668; FAILWITH } {} } { DUP; PUSH nat 4; SWAP; LSR; ADD } } }",
                sp.TPair(sp.TString, sp.TPair(sp.TNat, sp.TNat)),
                sp.TNat,
            ),
            validation_lambda=sp.lambda_michelson(
                "{ CDR; UNPAIR; SWAP; DUP; DUG 2; SWAP; SUB; ABS; PUSH nat 10; DIG 2; LSR; COMPARE; GE }",
                sp.TPair(sp.TString, sp.TPair(sp.TNat, sp.TNat)),
                sp.TBool,
            ),
            response_threshold=sp.nat(3),
            validity_window_in_epochs=sp.nat(4),
            valid_script=sp.bytes(
                "0x697066733a2f2f516d624c705353554e3473596a773368594577624c743762534a58734635476150507074476a776f59787363414a"
            ),
            valid_prices=sp.map(tkey=sp.TString, tvalue=ValidPriceEntry.get_type()),
            valid_epoch=sp.nat(0),
            contract_outside_cache_no=sp.nat(0),
            valid_sources=sp.set(
                [
                    sp.address("tz3PmupcJFTWizddEahCtjtzDEhJf5TuuajK"),
                    sp.address("tz3Q1QZ6SEQrTMCQ7cmWRwjD5oNr7z9SnCej"),
                    sp.address("tz3QjWnggCRS3y69uJCYY5k9YzS2WZEjuEzA"),
                    sp.address("tz3WiiCLAxz1ZFDTQc1S3D6VMzc6zFPguXqG"),
                    sp.address("tz3X63qJMCMfSMrkCb8KvDp23H4ZLPPx91Qn"),
                    sp.address("tz3ZAMjByo3Z3BwzgB5C115dJCmPCwGCjaP9"),
                    sp.address("tz3ZS8y81un52EXqTTx2VWPnRo5QVD5DHFM7"),
                    sp.address("tz3a2Ykw7gLK2m8BtfyaBW6NJgkfuN24bPUA"),
                    sp.address("tz3a7rwcnRBRdQ2Zk8FEDfSnpSnUp6yfZB7F"),
                    sp.address("tz3bRpk37rjwiScKBmd6ABncweZLTL3qBoVv"),
                    sp.address("tz3gGCrSvKfJpUd3w6ckSvBFbRJ5RjWU9zEw"),
                    sp.address("tz3h9cHjBwt8M6f1UpAK3KjNbfDVKy3ha79u"),
                    sp.address("tz3ic98e3UpVhujJLj8HfqqzJZt7jWoubZwA"),
                ]
            ),
            administrator=administrator,
            proposed_administrator=administrator,
        )

    @sp.entry_point(check_no_incoming_transfer=True)
    def touch(self):
        """Entrypoint used to cache the smart contract if it is not cached. The entrypoint
        updates the counter which stores how many times the contract was outside the cache.
        In reality this entrypoint can be called by anyone, therefore the counter serves
        as an approximation and not the real value.
        """
        self.data.contract_outside_cache_no += 1

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_valid_script(self, script):
        """Entrypoint used by the admin to set the valid script.
        Only admin is allowed to call this entrypoint.
        """
        sp.verify(sp.sender == self.data.administrator, message=Errors.NOT_ADMIN)
        self.data.valid_script = script

    @sp.entry_point(check_no_incoming_transfer=True)
    def propose_administrator(self, proposed_administrator):
        """Entrypoint used by the admin to set the new admin. Only admin is allowed to call this entrypoint.
        """
        sp.verify(sp.sender==self.data.administrator, message=Errors.NOT_ADMIN)
        self.data.proposed_administrator = proposed_administrator

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_administrator(self):
        """Entrypoint used by the proposed admin to set itself as admin.
        """
        sp.verify(sp.sender==self.data.proposed_administrator, message=Errors.NOT_ADMIN)
        self.data.administrator = self.data.proposed_administrator

    @sp.entry_point(check_no_incoming_transfer=True)
    def update_threshold(self, threshold):
        """Entrypoint used by the admin to set the threshold for the number of valid responses.
        """
        sp.verify(sp.sender==self.data.administrator, message=Errors.NOT_ADMIN)
        self.data.response_threshold = threshold
    
    @sp.entry_point(check_no_incoming_transfer=True)
    def add_valid_source(self, source):
        """Entrypoint used by the admin to add a new source.
        Only admin is allowed to call this entrypoint.
        """
        sp.verify(sp.sender == self.data.administrator, message=Errors.NOT_ADMIN)
        self.data.valid_sources.add(source)

    @sp.entry_point(check_no_incoming_transfer=True)
    def remove_valid_source(self, source):
        """Entrypoint used by the admin to remove an existing source.
        Only admin is allowed to call this entrypoint.
        """
        sp.verify(sp.sender == self.data.administrator, message=Errors.NOT_ADMIN)
        self.data.valid_sources.remove(source)

    @sp.entry_point(check_no_incoming_transfer=True)
    def update_aggregation_lambda(self, _lambda):
        """Entrypoint used by the admin to update the aggregation lambda.
        Only admin is allowed to call this entrypoint.
        """
        sp.verify(sp.sender == self.data.administrator, message=Errors.NOT_ADMIN)

        sp.set_type(
            _lambda,
            sp.TLambda(sp.TPair(sp.TString, sp.TPair(sp.TNat, sp.TNat)), sp.TNat),
        )
        self.data.aggregation_lambda = _lambda

    @sp.entry_point(check_no_incoming_transfer=True)
    def update_validation_lambda(self, _lambda):
        """Entrypoint used by the admin to update the validation lambda.
        Only admin is allowed to call this entrypoint.
        """
        sp.verify(sp.sender == self.data.administrator, message=Errors.NOT_ADMIN)

        sp.set_type(
            _lambda,
            sp.TLambda(sp.TPair(sp.TString, sp.TPair(sp.TNat, sp.TNat)), sp.TBool),
        )
        self.data.validation_lambda = _lambda

    @sp.entry_point(check_no_incoming_transfer=True)
    def fulfill(self, fulfill):
        """The fulfill entrypoint is called by the data transmitter directly. It's your
        responsibility to make it as efficient as possible (it has a gas and storage limit
        of 11000). While the sp.sender of this entrypoint will always be the JobScheduler
        above, the sp.source will always be the data transmitter. It's your responsibility
        to check that you are receivng the data from the right source. This implementation
        does also aggregate multiple respondants, hence the slightly more complex
        implementation.

        This entrypoint checks if the source and script is valid, then if the answer fits
        in the current epoch, comes from a new source and matches with some minor precision
        margin the value set by a previous source the response is counted as +1. If the
        response counter reaches the threshold the price in storage is set and ready to be
        used by the get_price view.
        """
        sp.set_type(fulfill, Fulfill.get_type())

        sp.verify(
            self.data.valid_script == fulfill.script, message=Errors.INVALID_SCRIPT
        )
        sp.verify(
            self.data.valid_sources.contains(sp.source), message=Errors.INVALID_SOURCE
        )

        response = sp.local(
            "response", sp.unpack(fulfill.payload, Response.get_type()).open_some()
        )
        current_epoch = sp.local(
            "current_epoch", response.value.timestamp // Constants.ORACLE_EPOCH_INTERVAL
        )
        sp.verify(
            current_epoch.value
            == sp.as_nat(sp.now - sp.timestamp(0)) // Constants.ORACLE_EPOCH_INTERVAL,
            message=Errors.NOT_IN_EPOCH,
        )

        with sp.if_((current_epoch.value > self.data.valid_epoch)):
            self.data.valid_prices = sp.map({})
            self.data.valid_epoch = current_epoch.value

        validation_lambda = sp.local("validation_lambda", self.data.validation_lambda)
        aggregation_lambda = sp.local("aggregation_lambda", self.data.aggregation_lambda)
        with sp.for_("price", response.value.prices) as price:
            with sp.if_(~self.data.valid_prices.contains(price.symbol)):
                self.data.valid_prices[price.symbol] = ValidPriceEntry.make(
                    sp.set(), price.price
                )
            valid_price = sp.local(
                "valid_price", self.data.valid_prices[price.symbol].price
            )
            validation_lambda_param = sp.pair(
                price.symbol, sp.pair(price.price, valid_price.value)
            )
            with sp.if_(validation_lambda.value(validation_lambda_param)):
                self.data.valid_prices[price.symbol].valid_respondants.add(sp.source)
                with sp.if_(
                    sp.len(self.data.valid_prices[price.symbol].valid_respondants)
                    >= self.data.response_threshold
                ):
                    with sp.if_(~self.data.prices.contains(price.symbol)):
                        self.data.prices[price.symbol] = StoragePriceEntry.make(
                            current_epoch.value, valid_price.value
                        )
                    with sp.else_():
                        last_price = sp.local("last_price", self.data.prices[price.symbol])
                        with sp.if_(last_price.value.last_epoch < current_epoch.value):
                            aggregation_lambda_param = sp.pair(
                                price.symbol,
                                sp.pair(
                                    last_price.value.price, valid_price.value
                                ),
                            )
                            self.data.prices[price.symbol] = StoragePriceEntry.make(
                                current_epoch.value,
                                aggregation_lambda.value(aggregation_lambda_param),
                            )
    
    @sp.onchain_view()
    def get_price(self, symbol):
        """Onchain view used to read the price out of storage. The onchain view takes the
        symbol as parameter and reads the respective entry from storage to then return it.
        The price is only returned if it is not older than the validity window set in
        storage expressed it interval integer.
        """
        current_epoch = (
            sp.as_nat(sp.now - sp.timestamp(0)) // Constants.ORACLE_EPOCH_INTERVAL
        )
        sp.verify(
            self.data.prices[symbol].last_epoch
            > sp.as_nat(current_epoch - self.data.validity_window_in_epochs),
            message=Errors.PRICE_TOO_OLD,
        )
        sp.verify(self.data.prices[symbol].price > 0, message=Errors.CANNOT_BE_ZERO)
        sp.result(self.data.prices[symbol].price)