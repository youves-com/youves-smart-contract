import smartpy as sp

from utils.viewer import Viewer
from contracts.oracle.plenty_oracle import PlentyOracle


class DummyPlentyDex(sp.Contract):
    def get_init_storage(self):
        """Returns the initial storage of the contract"""
        storage = {}
        storage["reserves"] = sp.pair(26775791746413662, 16970765105870923)
        return storage

    def __init__(self):
        self.init(**self.get_init_storage())

    @sp.entry_point
    def set_reserves(self, reserves):
        self.data.reserves = reserves

    @sp.entry_point
    def getReserveBalance(self, parameters):
        sp.set_type(
            parameters,
            sp.TPair(
                sp.TPair(
                    sp.TPair(sp.TAddress, sp.TNat), sp.TPair(sp.TAddress, sp.TNat)
                ),
                sp.TContract(sp.TPair(sp.TNat, sp.TNat)),
            ),
        )
        _, callback = sp.match_pair(parameters)
        sp.transfer(self.data.reserves, sp.mutez(0), callback)


@sp.add_test(name="Plenty Oracle Test")
def test():
    scenario = sp.test_scenario()
    scenario.h1("Plenty Oracle")
    scenario.h2("Bootstrapping")
    administrator = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob = sp.test_account("Robert")
    dan = sp.test_account("Dan")
    scenario.h2("Accounts")
    scenario.show([alice, bob, dan])
    dummy_dex = DummyPlentyDex()
    scenario += dummy_dex
    plenty_oracle = PlentyOracle(
        dummy_dex.address, alice.address, 0, alice.address, 0, 12, 12
    )
    scenario += plenty_oracle

    viewer = Viewer()
    scenario += viewer
    return_contract = sp.contract(
        sp.TNat, viewer.address, entry_point="set_nat"
    ).open_some()
    scenario += plenty_oracle.get_price(return_contract).run(sender=administrator)
    scenario.verify_equal(
        viewer.data.nat, 26775791746413662 * 10**6 // 16970765105870923
    )

    scenario.p("Prod Scenario")
    scenario += dummy_dex.set_reserves(
        sp.pair(25550643082999476, 17787437527647666)
    ).run()
    scenario += plenty_oracle.get_price(return_contract).run(sender=administrator)
    scenario.verify_equal(
        viewer.data.nat, 25550643082999476 * 10**6 // 17787437527647666
    )

    scenario.p("Internal can be called only by the contract")
    scenario += plenty_oracle.internal_get_price(return_contract).run(
        sender=administrator, valid=False
    )
    scenario += plenty_oracle.internal_get_price(return_contract).run(
        sender=alice, valid=False
    )
    scenario += plenty_oracle.internal_get_price(return_contract).run(
        sender=plenty_oracle.address
    )
