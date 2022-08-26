import smartpy as sp


class DummyOracle(sp.Contract):
    def get_init_storage(self):
        """Returns the initial storage of the contract"""
        storage = {}
        storage["price"] = sp.nat(1000000)
        return storage

    def __init__(self):
        self.init(**self.get_init_storage())

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_price(self, price):
        sp.set_type(price, sp.TNat)
        self.data.price = price

    @sp.entry_point(check_no_incoming_transfer=True)
    def get_price(self, callback):
        sp.set_type(callback, sp.TContract(sp.TNat))
        sp.transfer(self.data.price, sp.mutez(0), callback)

    @sp.onchain_view(name="get_price")
    def view_get_price(self):
        sp.result(self.data.price)
