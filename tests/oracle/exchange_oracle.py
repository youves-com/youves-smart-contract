import smartpy as sp

from contracts.oracle.exchange_oracle import ExchangeOracle


@sp.add_test(name="Exchange Oracle")
def test():
    scenario = sp.test_scenario()
    scenario.table_of_contents()

    scenario.h2("Bootstrapping")
    administrator = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob = sp.test_account("Robert")
    dan = sp.test_account("Dan")

    scenario.show([administrator, alice, bob, dan])

    exchange_oracle = ExchangeOracle()
    scenario += exchange_oracle
