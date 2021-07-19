import smartpy as sp
import tracker.constants as Constants
import tracker.errors as Errors
from tracker.viewer import Viewer
from tracker.utils import Utils, InternalMixin

class Price():
    def get_type():
        return sp.TRecord(exchange_id=sp.TString, symbol=sp.TString, price=sp.TNat, volume=sp.TNat, timestamp=sp.TTimestamp, certificate_sha256=sp.TBytes).layout(("exchange_id",("symbol",("price",("volume", ("timestamp","certificate_sha256"))))))
        
    def make(exchainge_id, symbol, price, volume, timestamp, certificate_sha256):
        return sp.set_type_expr(sp.record(exchange_id=exchainge_id, symbol=symbol, price=price, volume=volume, timestamp=timestamp, certificate_sha256=certificate_sha256), Price.get_type())

class DummyOracle(sp.Contract):
    def get_init_storage(self):
        """Returns the initial storage of the contract"""
        storage = {}
        storage['price'] = sp.nat(1000000)
        return storage

    def __init__(self):
        self.init(**self.get_init_storage())

    @sp.entry_point
    def set_price(self, price):
        self.data.price = price

    @sp.entry_point
    def get_price(self, callback):
        sp.set_type(callback, sp.TContract(sp.TNat))
        sp.transfer(self.data.price, sp.mutez(0), callback)

class SignedPayloadOracle(sp.Contract):
    """This oracle offers a "set_price" method which acceppts signed payload. If equal or more than "signature_threshold" parties agree on the same price and the payload is not older than "time_window"
    the new price is set in storage. get_price will work as long as the price is not older than "validity_window_in_epochs". Price can only be set once per perio

    Args:
        sp ([type]): [description]
    """
    def __init__(self, trusted_keys, trusted_certificates):
        self.add_flag("initial-cast")
        self.init(
            time_window=sp.int(60*5),#5 min
            validity_window_in_epochs=sp.nat(4),
            last_epoch=sp.nat(0), 
            signature_threshold=sp.nat(2),
            trusted_keys = sp.set_type_expr(trusted_keys, sp.TMap(sp.TKey, sp.TUnit)),
            trusted_certificates = sp.set_type_expr(trusted_certificates, sp.TMap(sp.TBytes, sp.TUnit)),
            price=sp.nat(100000)
        )

    @sp.entry_point
    def set_price(self, signed_payload):
        """This entrypoint can be called by anyone, however the only if the payload is signed correctly the price is update. The higher median price is set in case of even number of payloads, otherwise the median
        price is set. If the price difference is greater than 6.25% then the price is adapted by + or -6.25% depending on the direction of the provided price. 

        Args:
            signed_payload (sp.TMap): this is the payload containing all payaload and signatures
        """
        sp.set_type(signed_payload, sp.TMap(sp.TKey, sp.TMap(sp.TBytes, sp.TSignature)))
        current_epoch = sp.local('current_epoch', sp.as_nat(sp.now-sp.timestamp(0)) // Constants.ORACLE_EPOCH_INTERVAL)
        with sp.if_(self.data.last_epoch < current_epoch.value):
            threshold_counter = sp.local("threshold_counter",sp.map({}, tkey=sp.TBytes, tvalue=sp.TNat))
            price_sorter = sp.local("price_sorter",sp.set())
            
            with sp.for_('signer_item', signed_payload.items()) as signer_item:
                with sp.if_(self.data.trusted_keys.contains(signer_item.key)):
                    with sp.for_('payload_item', signer_item.value.items()) as payload_item:
                        with sp.if_(sp.check_signature(signer_item.key, payload_item.value, payload_item.key)):
                            with sp.if_(threshold_counter.value.contains(payload_item.key)):
                                threshold_counter.value[payload_item.key] += 1
                            with sp.else_():
                                threshold_counter.value[payload_item.key] = 1
            
            with sp.for_('item', threshold_counter.value.items()) as item:
                with sp.if_(item.value >= self.data.signature_threshold):
                    unpacked = sp.unpack(item.key, t=Price.get_type()).open_some()
                    with sp.if_(self.data.trusted_certificates.contains(unpacked.certificate_sha256)):
                        with sp.if_(sp.now < unpacked.timestamp.add_seconds(self.data.time_window)):
                            price_sorter.value.add(unpacked.price)
            
            sorted_prices = sp.local("sorted_prices", price_sorter.value.elements())
            median_price = sp.local("median_price", 0)
            median_runner = sp.local("median_runner", 0)
            
            with sp.for_('price', sorted_prices.value) as price:
                with sp.if_(median_runner.value <= sp.len(sorted_prices.value)/2):
                    median_price.value = price
                    median_runner.value += 1
            
            with sp.if_(median_price.value > 0):
                with sp.if_(self.data.price>>4 > abs(self.data.price-median_price.value)):
                    self.data.price = median_price.value
                with sp.else_():
                    with sp.if_(self.data.price-median_price.value>0):
                        self.data.price = sp.as_nat(self.data.price-(self.data.price>>4))
                    with sp.else_():
                        self.data.price = self.data.price+(self.data.price>>4)
                self.data.last_epoch = current_epoch.value
    
    @sp.entry_point
    def get_price(self, callback):
        """this entrypoint can be called by everyone that provides a valid callback. Only if the price is not older than 4 epochs it will be returned.
        IMPORTANT: as we require for our use case the quote currency to be the collateral we are "flipping" base and quote by 1//"stored price"

        Args:
            callback (sp.TContract(sp.TNat)): callback where to receive the price
        """
        sp.set_type(callback, sp.TContract(sp.TNat))
        current_epoch = sp.as_nat(sp.now-sp.timestamp(0)) / Constants.ORACLE_EPOCH_INTERVAL
        sp.verify(self.data.last_epoch>sp.as_nat(current_epoch-self.data.validity_window_in_epochs), message=Errors.PRICE_TOO_OLD)
        sp.transfer(Constants.PRECISION_FACTOR//self.data.price, sp.mutez(0), callback)

class QuipuswapOracle(sp.Contract, InternalMixin):
    """
    This oracles calculates the observed price on the secondary market by checking the quipuswap reserves
    """

    def get_init_storage(self):
        """Returns the initial storage of the contract"""
        storage = {}
        storage['dex_contract'] = self.dex_contract
        storage['price'] = 0
        return storage
        
    def __init__(self, dex_contract):
        self.dex_contract = dex_contract
        self.init(**self.get_init_storage())
    
    @sp.entry_point
    def set_reserves(self, reserves):
        """
        This is the callback where the dex contract sets the reserves used for the price calculations.
        Eventhough it's an open entrypoint it's meaningless because only the data immediately set 
        within the "get_price" call is going to be the one used for calculations.
        """
        sp.set_type(reserves, sp.TPair(sp.TNat, sp.TNat))
        self.data.price = sp.snd(reserves)//sp.fst(reserves)

    @sp.entry_point
    def get_price(self, callback):
        """
        This call will ask the current reserves from the DEX contract and then set them, internally the callback is passed
        such that the calculated price based on the fetched reserves can be returned.
        """
        sp.set_type(callback, sp.TContract(sp.TNat))
        Utils.execute_get(self.data.dex_contract, "get_reserves", "set_reserves", value_type=sp.TPair(sp.TNat, sp.TNat))
        sp.transfer(callback, sp.mutez(0), sp.self_entry_point("internal_get_price"))
    
    @sp.entry_point
    def internal_get_price(self, callback):
        """
        This is the internal call that returns the price to the intial callback
        """
        sp.set_type(callback, sp.TContract(sp.TNat))
        self.verify_internal(sp.unit)
        sp.transfer(self.data.price, sp.mutez(0), callback)

class FailOracle(sp.Contract):
    @sp.entry_point
    def get_price(self, callback):
        """
        This call will ask the current reserves from the DEX contract and then set them, internally the callback is passed
        such that the calculated price based on the fetched reserves can be returned.
        """
        sp.set_type(callback, sp.TContract(sp.TNat))
        sp.failwith("blocked")
 
if "templates" not in __name__:
    class DummyQuipuswapDex(sp.Contract):
        def get_init_storage(self):
            """Returns the initial storage of the contract"""
            storage = {}
            storage['reserves'] = sp.pair(1411889, 726243520927)
            return storage

        def __init__(self):
            self.init(**self.get_init_storage())

        @sp.entry_point
        def set_reserves(self, reserves):
            self.data.reserves = reserves

        @sp.entry_point
        def get_reserves(self, callback):
            sp.set_type(callback, sp.TContract(sp.TPair(sp.TNat, sp.TNat)))
            sp.transfer(self.data.reserves, sp.mutez(0), callback)

    @sp.add_test(name = "QuipuswapOracleTest")
    def test():
        scenario = sp.test_scenario()
        scenario.h1("Quipuswap  Oracle")
        scenario.h2("Bootstrapping")
        administrator = sp.test_account("Administrator")
        alice = sp.test_account("Alice")
        bob = sp.test_account("Robert")
        dan = sp.test_account("Dan")
        scenario.h2("Accounts")
        scenario.show([alice, bob, dan])
        dummy_dex = DummyQuipuswapDex()
        scenario += dummy_dex
        quipuswap_oracle = QuipuswapOracle(dummy_dex.address)
        scenario += quipuswap_oracle
        
        viewer = Viewer()
        scenario += viewer
        return_contract = sp.contract(
            sp.TNat, viewer.address, entry_point="set_nat").open_some()
        scenario += quipuswap_oracle.get_price(return_contract).run(sender=administrator)
        scenario.verify_equal(viewer.data.nat, 514377) # based of real quipu data, this is the price of 1uUSD expressed in tez

    @sp.add_test(name = "SignedPayloadOracleTest")
    def test():
        scenario = sp.test_scenario()
        scenario.h1("Signed Payload Oracle")
        scenario.h2("Bootstrapping")
        administrator = sp.test_account("Administrator")
        alice = sp.test_account("Alice")
        bob = sp.test_account("Robert")
        dan = sp.test_account("Dan")
        scenario.h2("Accounts")
        scenario.show([alice, bob, dan])

        certificate_1 = sp.bytes("0x01")
        certificate_2 = sp.bytes("0x02")
        certificate_3 = sp.bytes("0x03")
        
        signed_payload_oracle = SignedPayloadOracle({
                alice.public_key:sp.unit,
                bob.public_key:sp.unit,
                dan.public_key:sp.unit
            },{
                certificate_1:sp.unit,
                certificate_2:sp.unit,
                certificate_3:sp.unit
            })
        scenario += signed_payload_oracle
        
        
        scenario.h2("1 payload 3 signatures, change within threshold")
        now = sp.timestamp(Constants.ORACLE_EPOCH_INTERVAL)
        price_payload = sp.pack(Price.make("BNN", "XTZUSD", 100001, 1, now, certificate_1))
        alice_signature = sp.make_signature(alice.secret_key, price_payload)
        bob_signature = sp.make_signature(bob.secret_key, price_payload)
        dan_signature = sp.make_signature(dan.secret_key, price_payload)
        scenario += signed_payload_oracle.set_price({
            alice.public_key:{
                price_payload: alice_signature,
            },
            bob.public_key:{
                price_payload: bob_signature,
            },
            dan.public_key:{
                price_payload: dan_signature,
            },
        }).run(now=now, sender=administrator)
        scenario.verify_equal(signed_payload_oracle.data.price, 100001)
        scenario.verify_equal(signed_payload_oracle.data.last_epoch, 1)
        
        scenario.h2("1 payload 3 signatures, large change")
        now = sp.timestamp(Constants.ORACLE_EPOCH_INTERVAL*2)
        price_payload = sp.pack(Price.make("BNN", "XTZUSD", 200001, 1, now, certificate_1))
        alice_signature = sp.make_signature(alice.secret_key, price_payload)
        bob_signature = sp.make_signature(bob.secret_key, price_payload)
        dan_signature = sp.make_signature(dan.secret_key, price_payload)
        scenario += signed_payload_oracle.set_price({
            alice.public_key:{
                price_payload: alice_signature,
            },
            bob.public_key:{
                price_payload: bob_signature,
            },
            dan.public_key:{
                price_payload: dan_signature,
            },
        }).run(now=now, sender=administrator)
        scenario.verify_equal(signed_payload_oracle.data.price, 100001+(100001>>4))
        scenario.verify_equal(signed_payload_oracle.data.last_epoch, 2)
        
        scenario.h2("3 payloads 3 signatures, median test")
        now = sp.timestamp(Constants.ORACLE_EPOCH_INTERVAL*3)
        price1_payload = sp.pack(Price.make("BNN", "XTZUSD", 100000, 1, now, certificate_1))
        price2_payload = sp.pack(Price.make("CBP", "XTZUSD", 100001, 1, now, certificate_2))
        price3_payload = sp.pack(Price.make("BFX", "XTZUSD", 100002, 1, now, certificate_3))
        
        alice_signature1 = sp.make_signature(alice.secret_key, price1_payload)
        bob_signature1 = sp.make_signature(bob.secret_key, price1_payload)
        dan_signature1 = sp.make_signature(dan.secret_key, price1_payload)
        alice_signature2 = sp.make_signature(alice.secret_key, price2_payload)
        bob_signature2 = sp.make_signature(bob.secret_key, price2_payload)
        dan_signature2 = sp.make_signature(dan.secret_key, price2_payload)
        alice_signature3 = sp.make_signature(alice.secret_key, price3_payload)
        bob_signature3 = sp.make_signature(bob.secret_key, price3_payload)
        dan_signature3 = sp.make_signature(dan.secret_key, price3_payload)
        scenario += signed_payload_oracle.set_price({
            alice.public_key:{
                price1_payload: alice_signature1,
                price2_payload: alice_signature2,
                price3_payload: alice_signature3,
            },
            bob.public_key:{
                price1_payload: bob_signature1,
                price2_payload: bob_signature2,
                price3_payload: bob_signature3,
            },
            dan.public_key:{
                price1_payload: dan_signature1,
                price2_payload: dan_signature2,
                price3_payload: dan_signature3,
            },
        }).run(now=now, sender=administrator)
        scenario.verify_equal(signed_payload_oracle.data.price, 100001)
        scenario.verify_equal(signed_payload_oracle.data.last_epoch, 3)
        
        scenario.h2("2 payloads 3 signatures, higher median test")
        now = sp.timestamp(Constants.ORACLE_EPOCH_INTERVAL*4)
        price1_payload = sp.pack(Price.make("CBP", "XTZUSD", 100002, 1, now, certificate_2))
        price2_payload = sp.pack(Price.make("BFX", "XTZUSD", 100003, 1, now, certificate_3))
        
        alice_signature1 = sp.make_signature(alice.secret_key, price1_payload)
        bob_signature1 = sp.make_signature(bob.secret_key, price1_payload)
        dan_signature1 = sp.make_signature(dan.secret_key, price1_payload)
        alice_signature2 = sp.make_signature(alice.secret_key, price2_payload)
        bob_signature2 = sp.make_signature(bob.secret_key, price2_payload)
        dan_signature2 = sp.make_signature(dan.secret_key, price2_payload)
        scenario += signed_payload_oracle.set_price({
            alice.public_key:{
                price1_payload: alice_signature1,
                price2_payload: alice_signature2,
            },
            bob.public_key:{
                price1_payload: bob_signature1,
                price2_payload: bob_signature2,
            },
            dan.public_key:{
                price1_payload: dan_signature1,
                price2_payload: dan_signature2,
            },
        }).run(now=now, sender=administrator)
        scenario.verify_equal(signed_payload_oracle.data.price, 100003)
        scenario.verify_equal(signed_payload_oracle.data.last_epoch, 4)
        
        scenario.h2("non matching payloads are discarded")
        now = sp.timestamp(Constants.ORACLE_EPOCH_INTERVAL*5)
        
        price1_payload = sp.pack(Price.make("BNN", "XTZUSD", 100013, 1, now, certificate_1))
        price2_payload = sp.pack(Price.make("CBP", "XTZUSD", 100014, 1, now, certificate_2))
        price3_payload = sp.pack(Price.make("BFX", "XTZUSD", 100015, 1, now, certificate_3))
        price4_payload = sp.pack(Price.make("CBP", "XTZUSD", 100001, 1, now, certificate_2))
        price5_payload = sp.pack(Price.make("BFX", "XTZUSD", 100002, 1, now, certificate_3))
        
        alice_signature1 = sp.make_signature(alice.secret_key, price1_payload)
        bob_signature1 = sp.make_signature(bob.secret_key, price1_payload)
        dan_signature1 = sp.make_signature(dan.secret_key, price1_payload)
        alice_signature2 = sp.make_signature(alice.secret_key, price2_payload)
        bob_signature2 = sp.make_signature(bob.secret_key, price4_payload)
        dan_signature2 = sp.make_signature(dan.secret_key, price5_payload)
        alice_signature3 = sp.make_signature(alice.secret_key, price3_payload)
        bob_signature3 = sp.make_signature(bob.secret_key, price4_payload)
        dan_signature3 = sp.make_signature(dan.secret_key, price5_payload)
        scenario += signed_payload_oracle.set_price({
            alice.public_key:{
                price1_payload: alice_signature1,
                price2_payload: alice_signature2,
                price3_payload: alice_signature3,
            },
            bob.public_key:{
                price1_payload: bob_signature1,
                price2_payload: bob_signature2,
                price3_payload: bob_signature3,
            },
            dan.public_key:{
                price1_payload: dan_signature1,
                price2_payload: dan_signature2,
                price3_payload: dan_signature3,
            },
        }).run(now=now, sender=administrator)
        scenario.verify_equal(signed_payload_oracle.data.price, 100013)
        scenario.verify_equal(signed_payload_oracle.data.last_epoch, 5)
        
        scenario.h2("needs threshold for setting")
        now = sp.timestamp(Constants.ORACLE_EPOCH_INTERVAL*6)
        
        price1_payload = sp.pack(Price.make("BNN", "XTZUSD", 100018, 1, now, certificate_1))
        price2_payload = sp.pack(Price.make("CBP", "XTZUSD", 100019, 1, now, certificate_2))
        price3_payload = sp.pack(Price.make("BFX", "XTZUSD", 100020, 1, now, certificate_3))
        price4_payload = sp.pack(Price.make("CBP", "XTZUSD", 100001, 1, now, certificate_2))
        price5_payload = sp.pack(Price.make("BFX", "XTZUSD", 100002, 1, now, certificate_3))
        
        alice_signature1 = sp.make_signature(alice.secret_key, price1_payload)
        bob_signature1 = sp.make_signature(bob.secret_key, price2_payload)
        dan_signature1 = sp.make_signature(dan.secret_key, price3_payload)
        alice_signature2 = sp.make_signature(alice.secret_key, price2_payload)
        bob_signature2 = sp.make_signature(bob.secret_key, price4_payload)
        dan_signature2 = sp.make_signature(dan.secret_key, price5_payload)
        alice_signature3 = sp.make_signature(alice.secret_key, price3_payload)
        bob_signature3 = sp.make_signature(bob.secret_key, price4_payload)
        dan_signature3 = sp.make_signature(dan.secret_key, price5_payload)
        scenario += signed_payload_oracle.set_price({
            alice.public_key:{
                price1_payload: alice_signature1,
                price2_payload: alice_signature2,
                price3_payload: alice_signature3,
            },
            bob.public_key:{
                price1_payload: bob_signature1,
                price2_payload: bob_signature2,
                price3_payload: bob_signature3,
            },
            dan.public_key:{
                price1_payload: dan_signature1,
                price2_payload: dan_signature2,
                price3_payload: dan_signature3,
            },
        }).run(now=now, sender=administrator)
        scenario.verify_equal(signed_payload_oracle.data.price, 100013)
        scenario.verify_equal(signed_payload_oracle.data.last_epoch, 5)
        
        scenario.h2("cannot sign self multiple times")
        now = sp.timestamp(Constants.ORACLE_EPOCH_INTERVAL*7)
        
        price1_payload = sp.pack(Price.make("BNN", "XTZUSD", 100000, 1, now, certificate_1))
        price2_payload = sp.pack(Price.make("CBP", "XTZUSD", 100001, 1, now, certificate_2))
        price3_payload = sp.pack(Price.make("BFX", "XTZUSD", 100002, 1, now, certificate_3))
        
        alice_signature1 = sp.make_signature(alice.secret_key, price1_payload)
        bob_signature1 = sp.make_signature(alice.secret_key, price1_payload)
        dan_signature1 = sp.make_signature(alice.secret_key, price1_payload)
        alice_signature2 = sp.make_signature(alice.secret_key, price2_payload)
        bob_signature2 = sp.make_signature(alice.secret_key, price2_payload)
        dan_signature2 = sp.make_signature(alice.secret_key, price2_payload)
        alice_signature3 = sp.make_signature(alice.secret_key, price3_payload)
        bob_signature3 = sp.make_signature(alice.secret_key, price3_payload)
        dan_signature3 = sp.make_signature(alice.secret_key, price3_payload)
        scenario += signed_payload_oracle.set_price({
            alice.public_key:{
                price1_payload: alice_signature1,
                price2_payload: alice_signature2,
                price3_payload: alice_signature3,
            },
            bob.public_key:{
                price1_payload: bob_signature1,
                price2_payload: bob_signature2,
                price3_payload: bob_signature3,
            },
            dan.public_key:{
                price1_payload: dan_signature1,
                price2_payload: dan_signature2,
                price3_payload: dan_signature3,
            },
        }).run(now=now, sender=administrator)
        scenario.verify_equal(signed_payload_oracle.data.price, 100013)
        scenario.verify_equal(signed_payload_oracle.data.last_epoch, 5)
        
        scenario.h2("1 payload 3 signatures, but too late")
        now = sp.timestamp(Constants.ORACLE_EPOCH_INTERVAL*8)
        price_payload = sp.pack(Price.make("BNN", "XTZUSD", 100001, 1, now, certificate_1))
        alice_signature = sp.make_signature(alice.secret_key, price_payload)
        bob_signature = sp.make_signature(bob.secret_key, price_payload)
        dan_signature = sp.make_signature(dan.secret_key, price_payload)
        scenario += signed_payload_oracle.set_price({
            alice.public_key:{
                price_payload: alice_signature,
            },
            bob.public_key:{
                price_payload: bob_signature,
            },
            dan.public_key:{
                price_payload: dan_signature,
            },
        }).run(now=now.add_seconds(5*60+1), sender=administrator)
        scenario.verify_equal(signed_payload_oracle.data.price, 100013)
        scenario.verify_equal(signed_payload_oracle.data.last_epoch, 5)
        
        scenario.h2("get an old price")
        now = sp.timestamp(Constants.ORACLE_EPOCH_INTERVAL*9)
        viewer = Viewer()
        scenario += viewer
        return_contract = sp.contract(
            sp.TNat, viewer.address, entry_point="set_nat").open_some()
        scenario += signed_payload_oracle.get_price(return_contract).run(now=now, sender=administrator, valid=False)
        
        scenario.h2("get up to date price")
        now = sp.timestamp(Constants.ORACLE_EPOCH_INTERVAL*9)
        price_payload = sp.pack(Price.make("BNN", "XTZUSD", 100001, 1, now, certificate_1))
        alice_signature = sp.make_signature(alice.secret_key, price_payload)
        bob_signature = sp.make_signature(bob.secret_key, price_payload)
        dan_signature = sp.make_signature(dan.secret_key, price_payload)
        scenario += signed_payload_oracle.set_price({
            alice.public_key:{
                price_payload: alice_signature,
            },
            bob.public_key:{
                price_payload: bob_signature,
            },
            dan.public_key:{
                price_payload: dan_signature,
            },
        }).run(now=now.add_seconds(4*60), sender=administrator)
        scenario.verify_equal(signed_payload_oracle.data.price, 100001)
        scenario.verify_equal(signed_payload_oracle.data.last_epoch, 9)
        
        scenario += signed_payload_oracle.get_price(return_contract).run(now=now, sender=administrator)
        scenario.verify_equal(viewer.data.nat, Constants.PRECISION_FACTOR//100001)

        scenario.h2("only allow if certificate matches")
        now = sp.timestamp(Constants.ORACLE_EPOCH_INTERVAL*10)
        price_payload = sp.pack(Price.make("BNN", "XTZUSD", 100099, 1, now, sp.bytes("0x05")))
        alice_signature = sp.make_signature(alice.secret_key, price_payload)
        bob_signature = sp.make_signature(bob.secret_key, price_payload)
        dan_signature = sp.make_signature(dan.secret_key, price_payload)
        scenario += signed_payload_oracle.set_price({
            alice.public_key:{
                price_payload: alice_signature,
            },
            bob.public_key:{
                price_payload: bob_signature,
            },
            dan.public_key:{
                price_payload: dan_signature,
            },
        }).run(now=now.add_seconds(4*60), sender=administrator)
        scenario.verify_equal(signed_payload_oracle.data.price, 100001)
        scenario.verify_equal(signed_payload_oracle.data.last_epoch, 9)
        
        scenario.h2("make sure the base/quote flip works")
        scenario += signed_payload_oracle.get_price(return_contract).run(now=now, sender=administrator)
        scenario.verify_equal(viewer.data.nat, Constants.PRECISION_FACTOR//100001)



