import smartpy as sp

from utils.viewer import Viewer
import utils.constants as Constants
from contracts.oracle.liquidity_pool_oracle import LPPriceOracle


class DummyValueToken(sp.Contract):
    def __init__(self, balance):
        self.init(balance=balance)

    @sp.entry_point
    def setBalance(self, balance):
        self.data.balance = balance

    @sp.entry_point
    def getBalance(self, parameters):
        sp.set_type(parameters, sp.TPair(sp.TAddress, sp.TContract(sp.TNat)))
        sp.transfer(self.data.balance, sp.mutez(0), sp.snd(parameters))


class DummyLPToken(sp.Contract):
    def __init__(self, total_supply):
        self.init(total_supply=total_supply)

    @sp.entry_point
    def setTotalSupply(self, total_supply):
        self.data.total_supply = total_supply

    @sp.entry_point
    def getTotalSupply(self, parameters):
        sp.set_type(parameters, sp.TPair(sp.TUnit, sp.TContract(sp.TNat)))
        sp.transfer(self.data.total_supply, sp.mutez(0), sp.snd(parameters))


class DummyOracle(sp.Contract):
    def __init__(self, price):
        self.init(price=price)

    @sp.entry_point
    def default(self):
        pass

    @sp.onchain_view()
    def get_price(self, symbol):
        sp.set_type(symbol, sp.TString)
        sp.result(self.data.price)


@sp.add_test(name="LP Price Oracle")
def test():
    scenario = sp.test_scenario()
    scenario.h1("LP Price Oracle")

    scenario.h2("Bootstrapping")
    administrator = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob = sp.test_account("Robert")
    dan = sp.test_account("Dan")

    scenario.h2("Accounts")
    scenario.show([administrator, alice, bob, dan])

    tzbtc_balance = sp.nat(20775622511)
    value_token = DummyValueToken(tzbtc_balance)
    scenario += value_token

    total_supply_lptoken = sp.nat(177550279)
    lp_token = DummyLPToken(total_supply_lptoken)
    scenario += lp_token

    bitcoin_price = sp.nat(47403660000)
    value_token_oracle = DummyOracle(bitcoin_price)
    scenario += value_token_oracle

    lp_price_oracle = LPPriceOracle(
        lp_token.address,
        administrator.address,
        value_token.address,
        8,
        value_token_oracle.address,
        "BTC",
        requires_flip=False,
    )
    scenario += lp_price_oracle

    viewer = Viewer()
    scenario += viewer
    return_contract = sp.contract(
        sp.TNat, viewer.address, entry_point="set_nat"
    ).open_some()

    now = sp.timestamp(Constants.ORACLE_EPOCH_INTERVAL * 0)

    scenario.h2("Call get_price unflipped")
    scenario += lp_price_oracle.get_price(return_contract).run(now=now)
    scenario.verify_equal(viewer.data.nat, 10**12 // 9014163)

    scenario.h2("Call get_price flipped")
    flipped_lp_price_oracle = LPPriceOracle(
        lp_token.address,
        administrator.address,
        value_token.address,
        8,
        value_token_oracle.address,
        "BTC",
        requires_flip=True,
    )
    scenario += flipped_lp_price_oracle
    scenario += flipped_lp_price_oracle.get_price(return_contract).run(now=now)
    scenario.verify_equal(viewer.data.nat, 9014163)

    scenario.h2("Call get_price min boundary")
    scenario.p("Simulate 50 impact down instant")
    scenario += value_token.setBalance(sp.nat(20775622511) // 2)
    scenario += flipped_lp_price_oracle.get_price(return_contract).run(now=now)

    scenario.p("Simulate 50 impact down 1second")
    now = sp.timestamp(1)
    scenario += flipped_lp_price_oracle.get_price(return_contract).run(now=now)

    scenario.p("Simulate 50 impact down 30second")
    now = sp.timestamp(30)
    scenario += flipped_lp_price_oracle.get_price(return_contract).run(now=now)

    scenario.p("Simulate 50 impact down 15min")
    now = sp.timestamp(Constants.ORACLE_EPOCH_INTERVAL)
    scenario += flipped_lp_price_oracle.get_price(return_contract).run(now=now)

    scenario.p("Simulate 50 impact down 30min")
    now = sp.timestamp(2 * Constants.ORACLE_EPOCH_INTERVAL)
    scenario += flipped_lp_price_oracle.get_price(return_contract).run(now=now)

    scenario.p("Simulate 50 impact down 60min")
    now = sp.timestamp(4 * Constants.ORACLE_EPOCH_INTERVAL)
    scenario += flipped_lp_price_oracle.get_price(return_contract).run(now=now)

    scenario.h2("Call get_price max boundary")
    scenario.p("Simulate 50 impact up instant")
    scenario += value_token.setBalance(sp.nat(20775622511) * 2)
    scenario += flipped_lp_price_oracle.get_price(return_contract).run(now=now)

    scenario.p("Simulate 50 impact up 1second")
    now = sp.timestamp(4 * Constants.ORACLE_EPOCH_INTERVAL + 1)
    scenario += flipped_lp_price_oracle.get_price(return_contract).run(now=now)

    scenario.p("Simulate 50 impact up 30second")
    now = sp.timestamp(4 * Constants.ORACLE_EPOCH_INTERVAL + 30)
    scenario += flipped_lp_price_oracle.get_price(return_contract).run(now=now)

    scenario.p("Simulate 50 impact up 15min")
    now = sp.timestamp(
        4 * Constants.ORACLE_EPOCH_INTERVAL + Constants.ORACLE_EPOCH_INTERVAL
    )
    scenario += flipped_lp_price_oracle.get_price(return_contract).run(now=now)

    scenario.p("Simulate 50 impact up 30min")
    now = sp.timestamp(
        4 * Constants.ORACLE_EPOCH_INTERVAL + 2 * Constants.ORACLE_EPOCH_INTERVAL
    )
    scenario += flipped_lp_price_oracle.get_price(return_contract).run(now=now)

    scenario.p("Simulate 50 impact up 60min")
    now = sp.timestamp(
        4 * Constants.ORACLE_EPOCH_INTERVAL + 4 * Constants.ORACLE_EPOCH_INTERVAL
    )
    scenario += flipped_lp_price_oracle.get_price(return_contract).run(now=now)

    scenario.h2("Call get_price below boundary")
    scenario.p("Simulate 3.125 impact down instant")
    scenario += value_token.setBalance(sp.nat(20716121970) + (20716121970 >> 5))
    scenario += flipped_lp_price_oracle.get_price(return_contract).run(now=now)

    scenario.p("Simulate 3.125 impact down 1second")
    now = sp.timestamp(
        4 * Constants.ORACLE_EPOCH_INTERVAL + 4 * Constants.ORACLE_EPOCH_INTERVAL + 1
    )
    scenario += flipped_lp_price_oracle.get_price(return_contract).run(now=now)

    scenario.p("Simulate 3.125 impact down 30second")
    now = sp.timestamp(
        4 * Constants.ORACLE_EPOCH_INTERVAL + 4 * Constants.ORACLE_EPOCH_INTERVAL + 30
    )
    scenario += flipped_lp_price_oracle.get_price(return_contract).run(now=now)

    scenario.p("Simulate 3.125 impact down 15min")
    now = sp.timestamp(
        4 * Constants.ORACLE_EPOCH_INTERVAL
        + 4 * Constants.ORACLE_EPOCH_INTERVAL
        + Constants.ORACLE_EPOCH_INTERVAL
    )
    scenario += flipped_lp_price_oracle.get_price(return_contract).run(now=now)

    scenario.p("Simulate 3.125 impact down 30min")
    now = sp.timestamp(
        4 * Constants.ORACLE_EPOCH_INTERVAL
        + 4 * Constants.ORACLE_EPOCH_INTERVAL
        + 2 * Constants.ORACLE_EPOCH_INTERVAL
    )
    scenario += flipped_lp_price_oracle.get_price(return_contract).run(now=now)

    scenario.p("Simulate 3.125 impact down 60min")
    now = sp.timestamp(
        4 * Constants.ORACLE_EPOCH_INTERVAL
        + 4 * Constants.ORACLE_EPOCH_INTERVAL
        + 4 * Constants.ORACLE_EPOCH_INTERVAL
    )
    scenario += flipped_lp_price_oracle.get_price(return_contract).run(now=now)

    scenario.h2("Call get_price above boundary")
    scenario.p("Simulate 3.125 impact up instant")
    scenario += value_token.setBalance(sp.nat(21363500781 - (21363500781 >> 5)))
    scenario += flipped_lp_price_oracle.get_price(return_contract).run(now=now)

    scenario.p("Simulate 3.125 impact up 1second")
    now = sp.timestamp(
        4 * Constants.ORACLE_EPOCH_INTERVAL
        + 4 * Constants.ORACLE_EPOCH_INTERVAL
        + 4 * Constants.ORACLE_EPOCH_INTERVAL
        + 1
    )
    scenario += flipped_lp_price_oracle.get_price(return_contract).run(now=now)

    scenario.p("Simulate 3.125 impact up 30second")
    now = sp.timestamp(
        4 * Constants.ORACLE_EPOCH_INTERVAL
        + 4 * Constants.ORACLE_EPOCH_INTERVAL
        + 4 * Constants.ORACLE_EPOCH_INTERVAL
        + 30
    )
    scenario += flipped_lp_price_oracle.get_price(return_contract).run(now=now)

    scenario.p("Simulate 3.125 impact up 15min")
    now = sp.timestamp(
        4 * Constants.ORACLE_EPOCH_INTERVAL
        + 4 * Constants.ORACLE_EPOCH_INTERVAL
        + 4 * Constants.ORACLE_EPOCH_INTERVAL
        + Constants.ORACLE_EPOCH_INTERVAL
    )
    scenario += flipped_lp_price_oracle.get_price(return_contract).run(now=now)

    scenario.p("Simulate 3.125 impact up 30min")
    now = sp.timestamp(
        4 * Constants.ORACLE_EPOCH_INTERVAL
        + 4 * Constants.ORACLE_EPOCH_INTERVAL
        + 4 * Constants.ORACLE_EPOCH_INTERVAL
        + 2 * Constants.ORACLE_EPOCH_INTERVAL
    )
    scenario += flipped_lp_price_oracle.get_price(return_contract).run(now=now)

    scenario.p("Simulate 3.125 impact up 60min")
    now = sp.timestamp(
        4 * Constants.ORACLE_EPOCH_INTERVAL
        + 4 * Constants.ORACLE_EPOCH_INTERVAL
        + 4 * Constants.ORACLE_EPOCH_INTERVAL
        + 4 * Constants.ORACLE_EPOCH_INTERVAL
    )
    scenario += flipped_lp_price_oracle.get_price(return_contract).run(now=now)
