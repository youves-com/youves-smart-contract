import smartpy as sp

from utils.viewer import Viewer
from contracts.oracle.quipuswap_oracle import QuipuswapOracle


class DummyQuipuswapDex(sp.Contract):
    def get_init_storage(self):
        """Returns the initial storage of the contract"""
        storage = {}
        storage["reserves"] = sp.pair(10**6, 3 * 10**12)
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


@sp.add_test(name="Quipuswap Oracle Test")
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
    quipuswap_oracle = QuipuswapOracle(dummy_dex.address, 6, 12)
    scenario += quipuswap_oracle

    viewer = Viewer()
    scenario += viewer
    return_contract = sp.contract(
        sp.TNat, viewer.address, entry_point="set_nat"
    ).open_some()

    scenario += quipuswap_oracle.get_price(return_contract).run(sender=administrator)
    scenario.verify_equal(viewer.data.nat, 10**6 // 3)

    scenario.p("Prod Scenario")
    scenario += dummy_dex.set_reserves(sp.pair(32187621, 16391132182974)).run()
    scenario += quipuswap_oracle.get_price(return_contract).run(sender=administrator)
    scenario.verify_equal(viewer.data.nat, 1963721)

    scenario.p("Internal can be called only by the contract")
    scenario += quipuswap_oracle.internal_get_price(return_contract).run(
        sender=administrator, valid=False
    )
    scenario += quipuswap_oracle.internal_get_price(return_contract).run(
        sender=alice, valid=False
    )
    scenario += quipuswap_oracle.internal_get_price(return_contract).run(
        sender=quipuswap_oracle.address
    )
