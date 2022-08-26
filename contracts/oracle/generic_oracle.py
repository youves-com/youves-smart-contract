import smartpy as sp
import utils.constants as Constants
import utils.error_codes as Errors

from contracts.oracle.job_scheduler import Fulfill

class Response:
    def get_type():
        """The response type used for the price oracle that uses the generic data transmitter.
        """
        return sp.TRecord(
            timestamp=sp.TNat,
            prices=sp.TList(ResponsePriceEntry.get_type())).layout(("timestamp","prices"))
    
    def make(timestamp, prices):
        """Courtesy function typing a record to Response.get_type() for us
        """
        return sp.set_type_expr(sp.record(
                timestamp=timestamp,
                prices=prices), Response.get_type())

class ResponsePriceEntry:
    def get_type():
        return sp.TRecord(symbol=sp.TString, price=sp.TNat).layout(("symbol", "price"))

class ValidPriceEntry:
    def get_type():
        return sp.TRecord(valid_respondants=sp.TSet(sp.TAddress), price=sp.TNat).layout(("valid_respondants", "price"))

    def make(valid_respondants, price):
        return sp.set_type_expr(sp.record(
                valid_respondants=valid_respondants,
                price=price), ValidPriceEntry.get_type())

class StoragePriceEntry:
    def get_type():
        return sp.TRecord(last_epoch=sp.TNat, price=sp.TNat).layout(("last_epoch", "price"))
    
    def make(last_epoch, price):
        return sp.set_type_expr(sp.record(
                last_epoch=last_epoch,
                price=price), StoragePriceEntry.get_type())

class PriceOracle(sp.Contract):
    """The generic price oracle accepts prices from the set sources and set script. The price is allowed to change only 6.25% max from the previous
    set price. This version of the oracle uses the onchain views. Only the administrator is allowed to change the script and sources.
    """
    def __init__(self, administrator):
        self.init(
            prices=sp.big_map(tkey=sp.TString, tvalue=StoragePriceEntry.get_type()),
            last_epoch=sp.nat(0),
            response_threshold=sp.nat(3),
            validity_window_in_epochs=sp.nat(4),
            valid_script=sp.bytes("0x697066733a2f2f516d50367043416a5337525948383768573366454a754631524b6f75486a7a55674c5035694e61323853636b5533"),
            valid_prices = sp.map(tkey=sp.TString, tvalue=ValidPriceEntry.get_type()),
            valid_epoch=sp.nat(0),
            valid_sources = sp.set([
                sp.address("tz3S9uYxmGahffYfcYURijrCGm1VBqiH4mPe"),
                sp.address("tz3YzXZtqPHuFyX7zxGpkxjAtoA1gnYQkEnL"),
                sp.address("tz3Qg4gvJDj8f4hy3ewvb3wyxEXYXRYbZ6Mz"),
                sp.address("tz3cXew4V1uXDtxuQde5iFSKpxoiF5udC3L1"),
                sp.address("tz3UJN1ZMF7dAS9kJA3FQ5HTmZEpdpCgctjy")
            ]), 
            administrator=administrator 
        )
    
    @sp.entry_point(check_no_incoming_transfer=True)
    def set_valid_script(self, script):
        """Entrypoint used by the admin to set the valid script. Only admin is allowed to call this entrypoint.
        """
        sp.verify(sp.sender==self.data.administrator, message=Errors.NOT_ADMIN)
        self.data.valid_script = script

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_administrator(self, administrator):
        """Entrypoint used by the admin to set the new admin. Only admin is allowed to call this entrypoint.
        """
        sp.verify(sp.sender==self.data.administrator, message=Errors.NOT_ADMIN)
        self.data.administrator = administrator
    
    @sp.entry_point(check_no_incoming_transfer=True)
    def add_valid_source(self, source):
        """Entrypoint used by the admin to add a new source. Only admin is allowed to call this entrypoint.
        """
        sp.verify(sp.sender==self.data.administrator, message=Errors.NOT_ADMIN)
        self.data.valid_sources.add(source)

    @sp.entry_point(check_no_incoming_transfer=True)
    def remove_valid_source(self, source):
        """Entrypoint used by the admin to remove an existing source. Only admin is allowed to call this entrypoint.
        """
        sp.verify(sp.sender==self.data.administrator, message=Errors.NOT_ADMIN)
        self.data.valid_sources.remove(source)

    @sp.private_lambda()
    def smooth(self, pair):
        """Lambda that takes as paramenter a pair (old_value: TNat, new_value: TNat) and returns 
        if the change is bigger than 6.25% old_value*1.0625 if the change is smaller than 6.25% old_value*0.9375. If the
        value is in between between new_value is returned.
        """
        old_value, new_value = sp.match_pair(pair)
        sp.verify(new_value > 0, message=Errors.INVALID_ZERO_VALUE)
        with sp.if_((old_value==0) | (old_value>>4 > abs(old_value-new_value))):
            sp.result(new_value)
        with sp.else_():
            with sp.if_(old_value-new_value>0):
                sp.result(sp.as_nat(old_value-(old_value>>4)))
            with sp.else_():
                sp.result(old_value+(old_value>>4))

    @sp.entry_point(check_no_incoming_transfer=True)
    def fulfill(self, fulfill):
        """The fulfill entrypoint is called by the data transmitter directly. It's your responsibility to make it
        as efficient as possible (it has a gas and storage limit of 11000). While the sp.sender of this entrypoint
        will always be the JobScheduler above, the sp.source will always be the data transmitter. It's your
        responsibility to check that you are receivng the data from the right source. This implementation does
        also aggregate multiple respondants, hence the slightly more complex implementation. 

        This entrypoint checks if the source and script is valid, then if the answer fits in the current epoch
        , comes from a new source and matches with some minor precision margin the value set by a previous source
        the response is counted as +1. If the response counter reaches the threshold the price in storage is set 
        and ready to be used by the get_price entrypoint.
        """
        sp.set_type(fulfill, Fulfill.get_type())

        sp.verify(self.data.valid_script == fulfill.script, message=Errors.INVALID_SCRIPT)
        sp.verify(self.data.valid_sources.contains(sp.source), message=Errors.INVALID_SOURCE)
        
        response = sp.local("response", sp.unpack(fulfill.payload, Response.get_type()).open_some())

        current_epoch = sp.local("current_epoch", response.value.timestamp // Constants.ORACLE_EPOCH_INTERVAL)
        sp.verify(current_epoch.value+1 == sp.as_nat(sp.now-sp.timestamp(0)) // Constants.ORACLE_EPOCH_INTERVAL, message=Errors.NOT_IN_EPOCH)

        with sp.if_((current_epoch.value != self.data.valid_epoch)):
            self.data.valid_prices = sp.map({})
            self.data.valid_epoch = current_epoch.value

        with sp.for_('price', response.value.prices) as price:
            with sp.if_(~self.data.valid_prices.contains(price.symbol)):
                self.data.valid_prices[price.symbol] = ValidPriceEntry.make(sp.set(), price.price)
            valid_price =  sp.local("valid_price", self.data.valid_prices[price.symbol].price)
            with sp.if_(valid_price.value>>Constants.PRICE_PRECISION_SHIFT >= abs(price.price - valid_price.value)):
                self.data.valid_prices[price.symbol].valid_respondants.add(sp.source)
                with sp.if_(sp.len(self.data.valid_prices[price.symbol].valid_respondants) >= self.data.response_threshold):
                    with sp.if_(~self.data.prices.contains(price.symbol)):
                        self.data.prices[price.symbol] = StoragePriceEntry.make(current_epoch.value, valid_price.value)
                    with sp.else_():
                        self.data.prices[price.symbol] = StoragePriceEntry.make(current_epoch.value,  self.smooth(sp.pair(self.data.prices[price.symbol].price, valid_price.value)))

    @sp.onchain_view()
    def get_price(self, symbol):
        """Onchain view used to read the price out of storage. The onchain view takes the symbol as parameter and reads the respective
        entry from storage to then return it. The price is only returned if it is not older than the validity window set in storage 
        expressed it interval integer. This
        """
        current_epoch = sp.as_nat(sp.now-sp.timestamp(0)) // Constants.ORACLE_EPOCH_INTERVAL
        sp.verify(self.data.prices[symbol].last_epoch>sp.as_nat(current_epoch-self.data.validity_window_in_epochs), message=Errors.PRICE_TOO_OLD)
        sp.verify(self.data.prices[symbol].price>0, message=Errors.CANNOT_BE_ZERO)
        sp.result(self.data.prices[symbol].price)

class ProxyOracle(sp.Contract):
    """This smart contract is used for retrocompatibility. It allows contracts that used the pre-onchain-view callback "get_price(cb)" 
    entrypoint to read data from the new generic oracle that uses the onchain view standard. It's instantiated with the oracle's address
    and symbol to request. 
    """
    def __init__(self, oracle, symbol, requires_flip=False, extra_precision_factor=sp.nat(1)):
        self.requires_flip = requires_flip
        self.extra_precision_factor = extra_precision_factor
        self.init(
            oracle=oracle,
            symbol=symbol
        )
        
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
        price = sp.view("get_price", self.data.oracle, self.data.symbol, t=sp.TNat).open_some(Errors.INVALID_VIEW)     
        if self.requires_flip:  
            sp.result((10**12 * self.extra_precision_factor) // price)
        else:
            sp.result(price * self.extra_precision_factor)

class LegacyProxyOracle(sp.Contract):
    """This smart contract is used for retrocompatibility. It allows contracts that used the pre-onchain-view callback "get_price(cb)" 
    entrypoint to read data from the new generic oracle that uses the onchain view standard. It's instantiated with the oracle's address
    and symbol to request. 
    """
    def __init__(self, oracle, symbol, requires_flip=False, extra_precision_factor=sp.nat(1)):
        self.requires_flip = requires_flip
        self.extra_precision_factor = extra_precision_factor
        self.init(
            oracle=oracle,
            symbol=symbol
        )
        
    @sp.entry_point
    def default(self):
        """This is a dummy entrypoint in order to allow us to have the named "get_price" entrypoint (if a contract has only 
        1 entrypoint it becomes not-named default otherwise).
        """
        sp.send(sp.sender, sp.amount)

    @sp.entry_point(check_no_incoming_transfer=True)
    def get_price(self, callback):
        """this entrypoint can be called by everyone that provides a valid callback. Only if the price is not older than 4 epochs it will be returned.
        IMPORTANT: some engines (i.e. uUSD engine) require for our use case the quote currency to be the collateral we are "flipping" base and quote 
        by 1//"stored price" if the python variable self.requires_flip is set to True. This switch is evaluated at compiletime and will not be reflected
        in the resulting michelson.
 
        Args:
            callback (sp.TContract(sp.TNat)): callback where to receive the price
        """
        sp.set_type(callback, sp.TContract(sp.TNat))
        price = sp.view("get_price", self.data.oracle, self.data.symbol, t=sp.TNat).open_some(Errors.INVALID_VIEW)     
        if self.requires_flip:  
            sp.transfer((10**12 * self.extra_precision_factor)//price, sp.mutez(0), callback)
        else:
            sp.transfer(price * self.extra_precision_factor, sp.mutez(0), callback)

class RelativeProxyOracle(sp.Contract):
    """This smart contract is used for the calculation of the right price. It takes the base symbol and puts it into relation with the quote symbol.
    """
    def __init__(self, oracle, base_symbol, quote_symbol):
        self.init(
            oracle=oracle,
            base_symbol=base_symbol,
            quote_symbol=quote_symbol
        )

    @sp.entry_point
    def default(self):
        """This is a dummy entrypoint in order to allow us to have the named "get_price" entrypoint (if a contract has only 
        1 entrypoint it becomes not-named default otherwise).
        """
        sp.send(sp.sender, sp.amount)

    @sp.entry_point(check_no_incoming_transfer=True)
    def get_price(self, callback):
        """this entrypoint can be called by everyone that provides a valid callback. Only if the price is not older than 4 epochs it will be returned.
        IMPORTANT: some engines (i.e. uUSD engine) require for our use case the quote currency to be the collateral we are "flipping" base and quote 
        by 1//"stored price" if the python variable self.requires_flip is set to True. This switch is evaluated at compiletime and will not be reflected
        in the resulting michelson.
 
        Args:
            callback (sp.TContract(sp.TNat)): callback where to receive the price
        """
        sp.set_type(callback, sp.TContract(sp.TNat))

        price = sp.view("view_price", sp.self_address, sp.unit, t=sp.TNat).open_some(Errors.INVALID_VIEW)
        sp.transfer(price, sp.mutez(0), callback)

    @sp.onchain_view()
    def view_price(self):
        """this entrypoint can be called by everyone that provides a valid callback. Only if the price is not older than 4 epochs it will be returned.
        IMPORTANT: some engines (i.e. uUSD engine) require for our use case the quote currency to be the collateral we are "flipping" base and quote 
        by 1//"stored price" if the python variable self.requires_flip is set to True. This switch is evaluated at compiletime and will not be reflected
        in the resulting michelson.
        """
        base_price = sp.view("get_price", self.data.oracle, self.data.base_symbol, t=sp.TNat).open_some(Errors.INVALID_VIEW)     
        quote_price = sp.view("get_price", self.data.oracle, self.data.quote_symbol, t=sp.TNat).open_some(Errors.INVALID_VIEW)     

        price = base_price * Constants.PRICE_PRECISION_FACTOR // quote_price
        sp.result(price)