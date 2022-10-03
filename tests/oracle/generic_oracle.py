import smartpy as sp

import utils.constants as Constants
from utils.viewer import Viewer

from contracts.oracle.job_scheduler import Fulfill, JobScheduler, Job
from contracts.oracle.generic_oracle import (
    PriceOracle,
    RelativeProxyOracle,
    LegacyProxyOracle,
    Response,
)


@sp.add_test(name="Generic Price Oracle old")
def test():
    scenario = sp.test_scenario()
    scenario.h1("Job Scheduler")

    scenario.h2("Bootstrapping")
    administrator = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob = sp.test_account("Robert")
    dan = sp.test_account("Dan")

    scenario.h2("Accounts")
    scenario.show([administrator, alice, bob, dan])

    scheduler = JobScheduler(administrator.address)
    scenario += scheduler

    price_oracle = PriceOracle(administrator.address)
    scenario += price_oracle

    script = sp.bytes(
        "0x697066733a2f2f516d50367043416a5337525948383768573366454a754631524b6f75486a7a55674c5035694e61323853636b5533"
    )
    valid_executor1 = sp.address("tz3S9uYxmGahffYfcYURijrCGm1VBqiH4mPe")
    valid_executor2 = sp.address("tz3YzXZtqPHuFyX7zxGpkxjAtoA1gnYQkEnL")
    valid_executor3 = sp.address("tz3Qg4gvJDj8f4hy3ewvb3wyxEXYXRYbZ6Mz")
    valid_executor4 = sp.address("tz3cXew4V1uXDtxuQde5iFSKpxoiF5udC3L1")

    interval = 900
    fee = 1700
    gas_limit = 11000
    storage_limit = 12000
    start = sp.timestamp(0)
    end = sp.timestamp(1800000)

    job = Job.make_publish(
        valid_executor1,
        script,
        start,
        end,
        interval,
        fee,
        gas_limit,
        storage_limit,
        price_oracle.address,
    )
    scenario += scheduler.publish(job).run(sender=administrator.address)
    job = Job.make_publish(
        valid_executor2,
        script,
        start,
        end,
        interval,
        fee,
        gas_limit,
        storage_limit,
        price_oracle.address,
    )
    scenario += scheduler.publish(job).run(sender=administrator.address)
    job = Job.make_publish(
        valid_executor3,
        script,
        start,
        end,
        interval,
        fee,
        gas_limit,
        storage_limit,
        price_oracle.address,
    )
    scenario += scheduler.publish(job).run(sender=administrator.address)
    job = Job.make_publish(
        valid_executor4,
        script,
        start,
        end,
        interval,
        fee,
        gas_limit,
        storage_limit,
        price_oracle.address,
    )
    scenario += scheduler.publish(job).run(sender=administrator.address)
    job = Job.make_publish(
        alice.address,
        script,
        start,
        end,
        interval,
        fee,
        gas_limit,
        storage_limit,
        price_oracle.address,
    )
    scenario += scheduler.publish(job).run(sender=administrator.address)

    now = Constants.ORACLE_EPOCH_INTERVAL + Constants.ORACLE_EPOCH_INTERVAL
    price = sp.nat(6000000)

    scenario.h2("Response publishing")
    scenario.p("Only valid executors can publish a new price")
    scenario += scheduler.fulfill(
        Fulfill.make(
            script,
            sp.pack(
                Response.make(
                    now - 1,
                    [
                        sp.record(symbol="DEFI", price=price),
                        sp.record(symbol="XTZ", price=price),
                        sp.record(symbol="BTC", price=price),
                    ],
                )
            ),
        )
    ).run(
        sender=alice.address, source=alice.address, valid=False, now=sp.timestamp(now)
    )
    scenario.verify_equal(price_oracle.data.valid_prices.contains("DEFI"), False)

    scenario.p("Only valid executors can publish a new price")
    scenario += scheduler.fulfill(
        Fulfill.make(
            script,
            sp.pack(
                Response.make(
                    now - 1,
                    [
                        sp.record(symbol="DEFI", price=price),
                        sp.record(symbol="XTZ", price=price),
                        sp.record(symbol="BTC", price=price),
                    ],
                )
            ),
        )
    ).run(sender=valid_executor1, source=valid_executor1, now=sp.timestamp(now))
    scenario.verify_equal(price_oracle.data.valid_prices["DEFI"].price, price)

    scenario.h2("Response Threshold")
    scenario.p("Same Executor only counts once")
    scenario += scheduler.fulfill(
        Fulfill.make(
            script,
            sp.pack(
                Response.make(
                    now - 1,
                    [
                        sp.record(symbol="DEFI", price=price),
                        sp.record(symbol="XTZ", price=price),
                        sp.record(symbol="BTC", price=price),
                    ],
                )
            ),
        )
    ).run(sender=valid_executor1, source=valid_executor1, now=sp.timestamp(now))
    scenario += scheduler.fulfill(
        Fulfill.make(
            script,
            sp.pack(
                Response.make(
                    now - 1,
                    [
                        sp.record(symbol="DEFI", price=price),
                        sp.record(symbol="XTZ", price=price),
                        sp.record(symbol="BTC", price=price),
                    ],
                )
            ),
        )
    ).run(sender=valid_executor1, source=valid_executor1, now=sp.timestamp(now))
    scenario += scheduler.fulfill(
        Fulfill.make(
            script,
            sp.pack(
                Response.make(
                    now - 1,
                    [
                        sp.record(symbol="DEFI", price=price),
                        sp.record(symbol="XTZ", price=price),
                        sp.record(symbol="BTC", price=price),
                    ],
                )
            ),
        )
    ).run(sender=valid_executor1, source=valid_executor1, now=sp.timestamp(now))
    scenario.verify_equal(price_oracle.data.prices.contains("DEFI"), False)

    scenario.p(
        "Different Executor non-matching (too big difference) price does not count"
    )
    price = sp.nat(6007000)
    scenario += scheduler.fulfill(
        Fulfill.make(
            script,
            sp.pack(
                Response.make(
                    now - 1,
                    [
                        sp.record(symbol="DEFI", price=price),
                        sp.record(symbol="XTZ", price=price),
                        sp.record(symbol="BTC", price=price),
                    ],
                )
            ),
        )
    ).run(sender=valid_executor2, source=valid_executor2, now=sp.timestamp(now))
    scenario += scheduler.fulfill(
        Fulfill.make(
            script,
            sp.pack(
                Response.make(
                    now - 1,
                    [
                        sp.record(symbol="DEFI", price=price),
                        sp.record(symbol="XTZ", price=price),
                        sp.record(symbol="BTC", price=price),
                    ],
                )
            ),
        )
    ).run(sender=valid_executor3, source=valid_executor3, now=sp.timestamp(now))
    scenario += scheduler.fulfill(
        Fulfill.make(
            script,
            sp.pack(
                Response.make(
                    now - 1,
                    [
                        sp.record(symbol="DEFI", price=price),
                        sp.record(symbol="XTZ", price=price),
                        sp.record(symbol="BTC", price=price),
                    ],
                )
            ),
        )
    ).run(sender=valid_executor4, source=valid_executor4, now=sp.timestamp(now))
    scenario.verify_equal(price_oracle.data.prices.contains("DEFI"), False)

    scenario.p("Different Executor with all matching works")
    price = sp.nat(6000000)
    scenario += scheduler.fulfill(
        Fulfill.make(
            script,
            sp.pack(
                Response.make(
                    now - 1,
                    [
                        sp.record(symbol="DEFI", price=price),
                        sp.record(symbol="XTZ", price=price),
                        sp.record(symbol="BTC", price=price),
                    ],
                )
            ),
        )
    ).run(sender=valid_executor2, source=valid_executor2, now=sp.timestamp(now))
    scenario += scheduler.fulfill(
        Fulfill.make(
            script,
            sp.pack(
                Response.make(
                    now - 1,
                    [
                        sp.record(symbol="DEFI", price=price),
                        sp.record(symbol="XTZ", price=price),
                        sp.record(symbol="BTC", price=price),
                    ],
                )
            ),
        )
    ).run(sender=valid_executor3, source=valid_executor3, now=sp.timestamp(now))
    scenario.verify_equal(price_oracle.data.prices["DEFI"].price, price)

    scenario.p("Big price drop only impacts 6.25%")
    price = sp.nat(1)
    now += Constants.ORACLE_EPOCH_INTERVAL
    scenario += scheduler.fulfill(
        Fulfill.make(
            script,
            sp.pack(
                Response.make(
                    now - 1,
                    [
                        sp.record(symbol="DEFI", price=price),
                        sp.record(symbol="XTZ", price=price),
                        sp.record(symbol="BTC", price=price),
                    ],
                )
            ),
        )
    ).run(sender=valid_executor2, source=valid_executor2, now=sp.timestamp(now))
    scenario += scheduler.fulfill(
        Fulfill.make(
            script,
            sp.pack(
                Response.make(
                    now - 1,
                    [
                        sp.record(symbol="DEFI", price=price),
                        sp.record(symbol="XTZ", price=price),
                        sp.record(symbol="BTC", price=price),
                    ],
                )
            ),
        )
    ).run(sender=valid_executor3, source=valid_executor3, now=sp.timestamp(now))
    scenario += scheduler.fulfill(
        Fulfill.make(
            script,
            sp.pack(
                Response.make(
                    now - 1,
                    [
                        sp.record(symbol="DEFI", price=price),
                        sp.record(symbol="XTZ", price=price),
                        sp.record(symbol="BTC", price=price),
                    ],
                )
            ),
        )
    ).run(sender=valid_executor4, source=valid_executor4, now=sp.timestamp(now))
    scenario.verify_equal(price_oracle.data.prices["DEFI"].price, 5625000)

    scenario.p("Big price increase only impacts 6.25%")
    price = sp.nat(90000000)
    now += Constants.ORACLE_EPOCH_INTERVAL
    scenario += scheduler.fulfill(
        Fulfill.make(
            script,
            sp.pack(
                Response.make(
                    now - 1,
                    [
                        sp.record(symbol="DEFI", price=price),
                        sp.record(symbol="XTZ", price=price),
                        sp.record(symbol="BTC", price=price),
                    ],
                )
            ),
        )
    ).run(sender=valid_executor2, source=valid_executor2, now=sp.timestamp(now))
    scenario += scheduler.fulfill(
        Fulfill.make(
            script,
            sp.pack(
                Response.make(
                    now - 1,
                    [
                        sp.record(symbol="DEFI", price=price),
                        sp.record(symbol="XTZ", price=price),
                        sp.record(symbol="BTC", price=price),
                    ],
                )
            ),
        )
    ).run(sender=valid_executor3, source=valid_executor3, now=sp.timestamp(now))
    scenario += scheduler.fulfill(
        Fulfill.make(
            script,
            sp.pack(
                Response.make(
                    now - 1,
                    [
                        sp.record(symbol="DEFI", price=price),
                        sp.record(symbol="XTZ", price=price),
                        sp.record(symbol="BTC", price=price),
                    ],
                )
            ),
        )
    ).run(sender=valid_executor4, source=valid_executor4, now=sp.timestamp(now))
    scenario.verify_equal(price_oracle.data.prices["DEFI"].price, 5976562)

    scenario.p("Inaccurate but similar answers are accepted")
    price = sp.nat(90000000)
    now += Constants.ORACLE_EPOCH_INTERVAL
    scenario += scheduler.fulfill(
        Fulfill.make(
            script,
            sp.pack(
                Response.make(
                    now - 1,
                    [
                        sp.record(symbol="DEFI", price=price),
                        sp.record(symbol="XTZ", price=price),
                        sp.record(symbol="BTC", price=price),
                    ],
                )
            ),
        )
    ).run(sender=valid_executor2, source=valid_executor2, now=sp.timestamp(now))
    scenario += scheduler.fulfill(
        Fulfill.make(
            script,
            sp.pack(
                Response.make(
                    now - 1,
                    [
                        sp.record(symbol="DEFI", price=price + 1),
                        sp.record(symbol="XTZ", price=price + 1),
                        sp.record(symbol="BTC", price=price + 1),
                    ],
                )
            ),
        )
    ).run(sender=valid_executor3, source=valid_executor3, now=sp.timestamp(now))
    scenario += scheduler.fulfill(
        Fulfill.make(
            script,
            sp.pack(
                Response.make(
                    now - 1,
                    [
                        sp.record(symbol="DEFI", price=price + 3),
                        sp.record(symbol="XTZ", price=price + 3),
                        sp.record(symbol="BTC", price=price + 3),
                    ],
                )
            ),
        )
    ).run(sender=valid_executor4, source=valid_executor4, now=sp.timestamp(now))
    scenario.verify_equal(price_oracle.data.prices["DEFI"].price, 6350097)

    viewer = Viewer()
    scenario += viewer
    return_contract = sp.contract(
        sp.TNat, viewer.address, entry_point="set_nat"
    ).open_some()

    scenario.h2("using the proxy")
    proxy = LegacyProxyOracle(price_oracle.address, "BTC")
    scenario += proxy
    scenario += proxy.get_price(return_contract).run(now=sp.timestamp(now), valid=True)
    scenario.verify_equal(viewer.data.nat, 6350097)

    scenario.h2("get an old price through the proxy")
    now = sp.timestamp(Constants.ORACLE_EPOCH_INTERVAL * 10)
    scenario += proxy.get_price(return_contract).run(now=now, valid=False)

    scenario.h2("only admin can set new script")
    scenario += price_oracle.set_valid_script(sp.bytes("0x01")).run(
        sender=alice, valid=False
    )
    scenario += price_oracle.set_valid_script(sp.bytes("0x02")).run(
        sender=administrator
    )
    scenario.verify_equal(price_oracle.data.valid_script, sp.bytes("0x02"))

    scenario.h2("only admin can set a new source")
    scenario += price_oracle.add_valid_source(alice.address).run(
        sender=alice, valid=False
    )
    scenario.verify_equal(
        price_oracle.data.valid_sources.contains(alice.address), False
    )
    scenario.verify_equal(price_oracle.data.valid_sources.contains(bob.address), False)
    scenario += price_oracle.add_valid_source(bob.address).run(sender=administrator)
    scenario.verify_equal(
        price_oracle.data.valid_sources.contains(alice.address), False
    )
    scenario.verify_equal(price_oracle.data.valid_sources.contains(bob.address), True)

    scenario.h2("only admin can remove source")
    scenario += price_oracle.remove_valid_source(bob.address).run(
        sender=alice, valid=False
    )
    scenario.verify_equal(
        price_oracle.data.valid_sources.contains(alice.address), False
    )
    scenario.verify_equal(price_oracle.data.valid_sources.contains(bob.address), True)
    scenario += price_oracle.remove_valid_source(bob.address).run(sender=administrator)
    scenario.verify_equal(
        price_oracle.data.valid_sources.contains(alice.address), False
    )
    scenario.verify_equal(price_oracle.data.valid_sources.contains(bob.address), False)

    scenario.h2("only admin can set admin")
    scenario += price_oracle.set_administrator(alice.address).run(
        sender=alice, valid=False
    )
    scenario += price_oracle.set_administrator(bob.address).run(sender=administrator)
    scenario.verify_equal(price_oracle.data.administrator, bob.address)
    scenario += price_oracle.set_administrator(administrator.address).run(
        sender=administrator, valid=False
    )
    scenario += price_oracle.set_administrator(administrator.address).run(sender=bob)
    scenario.verify_equal(price_oracle.data.administrator, administrator.address)

    relative_proxy_oracle = RelativeProxyOracle(price_oracle.address, "XTZ", "BTC")
    now = Constants.ORACLE_EPOCH_INTERVAL * 6
    scenario += relative_proxy_oracle
    scenario += relative_proxy_oracle.get_price(return_contract).run(
        now=sp.timestamp(now), valid=True
    )
    scenario.verify_equal(viewer.data.nat, 1000000)

    scenario.h2("realistic price")
    now = Constants.ORACLE_EPOCH_INTERVAL * 20
    scenario += price_oracle.set_valid_script(script).run(sender=administrator)
    scenario += scheduler.fulfill(
        Fulfill.make(
            script,
            sp.pack(
                Response.make(
                    now - 1,
                    [
                        sp.record(symbol="DEFI", price=3500000),
                        sp.record(symbol="XTZ", price=3500000),
                        sp.record(symbol="BTC", price=38415000000),
                    ],
                )
            ),
        )
    ).run(sender=valid_executor2, source=valid_executor2, now=sp.timestamp(now))
    scenario += scheduler.fulfill(
        Fulfill.make(
            script,
            sp.pack(
                Response.make(
                    now - 1,
                    [
                        sp.record(symbol="DEFI", price=3500000),
                        sp.record(symbol="XTZ", price=3500000),
                        sp.record(symbol="BTC", price=38415000000),
                    ],
                )
            ),
        )
    ).run(sender=valid_executor3, source=valid_executor3, now=sp.timestamp(now))
    scenario += scheduler.fulfill(
        Fulfill.make(
            script,
            sp.pack(
                Response.make(
                    now - 1,
                    [
                        sp.record(symbol="DEFI", price=3500000),
                        sp.record(symbol="XTZ", price=3500000),
                        sp.record(symbol="BTC", price=38415000000),
                    ],
                )
            ),
        )
    ).run(sender=valid_executor4, source=valid_executor4, now=sp.timestamp(now))
    scenario += relative_proxy_oracle.get_price(return_contract).run(
        now=sp.timestamp(now), valid=True
    )
    scenario.verify_equal(viewer.data.nat, 882352)
    # scenario.verify(relation_proxy_oracle.get_price()==10)
