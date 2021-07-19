import smartpy as sp

class Viewer(sp.Contract):
    def __init__(self):
        self.init(
            address=sp.address("tz1RKmJwoAiaqFdjQYSbFy1j7u7UhEFsqXq7"),
            nat = sp.nat(0)
        )

    @sp.entry_point
    def set_address(self, address):
        sp.set_type_expr(address, sp.TAddress)
        self.data.address = address

    @sp.entry_point
    def set_nat(self, nat):
        sp.set_type_expr(nat, sp.TNat)
        self.data.nat = nat