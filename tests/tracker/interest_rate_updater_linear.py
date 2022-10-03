import smartpy as sp

import utils.error_codes as Errors
import utils.constants as Constants

from contracts.oracle.dummy_oracle import DummyOracle
from contracts.tracker.interest_rate_updater_linear import InterestRateUpdaterLinear

STARTING_BALANCE = 1000 * 10**12


@sp.add_test(name="Interest Rate Response Linear")
def test():
    scenario = sp.test_scenario()
    scenario.h1("Interest Rate Response Test")
    scenario.table_of_contents()

    scenario.h2("Bootstrapping")
    administrator = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob = sp.test_account("Robert")
    dan = sp.test_account("Dan")
    scenario.h2("Accounts")
    scenario.show([administrator, alice, bob, dan])

    target_oracle = DummyOracle()
    scenario += target_oracle
    observed_oracle = DummyOracle()
    scenario += observed_oracle
    interest_rate_updater = InterestRateUpdaterLinear(
        [Constants.DEFAULT_ADDRESS], target_oracle.address, observed_oracle.address
    )
    scenario += interest_rate_updater

    scenario.h3("Update Interest Rate on track")
    scenario.p("Will fail if called prematurely")

    scenario += interest_rate_updater.interest_rate_update().run(
        sender=alice, valid=False
    )
    now = sp.timestamp(Constants.REFERENCE_INTEREST_UPDATE_LINEAR_INTERVAL)

    scenario.p("Will not change if observed and target are same")
    scenario += interest_rate_updater.interest_rate_update().run(sender=alice, now=now)
    scenario.verify_equal(
        interest_rate_updater.data.reference_interest_rate,
        Constants.SECONDS_INTEREST_MINIMUM,
    )

    scenario.p("Cannot call in same epoch...")
    scenario += interest_rate_updater.interest_rate_update().run(
        sender=alice, now=now, valid=False
    )

    scenario.h3("Price of synth too low")
    observed_price = 500000
    now = sp.timestamp(2 * Constants.REFERENCE_INTEREST_UPDATE_LINEAR_INTERVAL)
    scenario += observed_oracle.set_price(observed_price)

    scenario.p("The price of the synth half of what it should be")
    scenario += interest_rate_updater.interest_rate_update().run(sender=alice, now=now)
    new_reference_interest_rate = (
        Constants.SECONDS_INTEREST_MINIMUM + Constants.MAX_LINEAR_RESPONSE_STEP
    )  # 1833 is the max response step
    scenario.verify_equal(
        interest_rate_updater.data.reference_interest_rate, new_reference_interest_rate
    )

    responses = {
        890000: 126,
        900000: 126,
        990000: 12,
        1000000: 0,
        1009000: -12,
        1100000: -126,
        1110000: -126,
    }

    for observed_price, value in responses.items():
        scenario.p(
            "The price of the synth is {} %% off target".format(
                (1000000 - observed_price) / 10000
            )
        )
        now = now.add_seconds(Constants.REFERENCE_INTEREST_UPDATE_LINEAR_INTERVAL)
        scenario += observed_oracle.set_price(observed_price)
        scenario += interest_rate_updater.interest_rate_update().run(
            sender=alice, now=now
        )
        new_reference_interest_rate += value
        scenario.verify_equal(
            interest_rate_updater.data.reference_interest_rate,
            new_reference_interest_rate,
        )

    scenario.p("test minimum interest rate boundary")
    now = now.add_seconds(Constants.REFERENCE_INTEREST_UPDATE_LINEAR_INTERVAL)
    scenario += observed_oracle.set_price(10**20)  # super high price
    scenario += interest_rate_updater.interest_rate_update().run(sender=alice, now=now)
    new_reference_interest_rate += Constants.MIN_LINEAR_RESPONSE_STEP  # max response
    scenario.verify_equal(
        interest_rate_updater.data.reference_interest_rate, new_reference_interest_rate
    )
    scenario.verify_equal(
        Constants.SECONDS_INTEREST_MINIMUM, new_reference_interest_rate
    )

    now = now.add_seconds(Constants.REFERENCE_INTEREST_UPDATE_LINEAR_INTERVAL)
    scenario += observed_oracle.set_price(10**20)  # super high price
    scenario += interest_rate_updater.interest_rate_update().run(sender=alice, now=now)
    scenario.verify_equal(
        interest_rate_updater.data.reference_interest_rate,
        Constants.SECONDS_INTEREST_MINIMUM,
    )

    scenario.p("test maximum interest rate boundary")
    while True:
        now = now.add_seconds(Constants.REFERENCE_INTEREST_UPDATE_LINEAR_INTERVAL)
        scenario += observed_oracle.set_price(0)  # super low price
        scenario += interest_rate_updater.interest_rate_update().run(
            sender=alice, now=now
        )
        new_reference_interest_rate += Constants.MAX_LINEAR_RESPONSE_STEP
        scenario.verify_equal(
            interest_rate_updater.data.reference_interest_rate,
            min(new_reference_interest_rate, Constants.SECONDS_INTEREST_MAXIMUM),
        )
        if new_reference_interest_rate >= Constants.SECONDS_INTEREST_MAXIMUM:
            break
    now = now.add_seconds(Constants.REFERENCE_INTEREST_UPDATE_LINEAR_INTERVAL)
    scenario += observed_oracle.set_price(0)  # super low price
    scenario += interest_rate_updater.interest_rate_update().run(sender=alice, now=now)
    scenario.verify_equal(
        interest_rate_updater.data.reference_interest_rate,
        Constants.SECONDS_INTEREST_MAXIMUM,
    )
    new_reference_interest_rate = Constants.SECONDS_INTEREST_MAXIMUM

    scenario.p("test minimum interest rate boundary")
    while True:
        now = now.add_seconds(Constants.REFERENCE_INTEREST_UPDATE_LINEAR_INTERVAL)
        scenario += observed_oracle.set_price(10**16)  # super high price
        scenario += interest_rate_updater.interest_rate_update().run(
            sender=alice, now=now
        )
        new_reference_interest_rate += Constants.MIN_LINEAR_RESPONSE_STEP
        scenario.verify_equal(
            interest_rate_updater.data.reference_interest_rate,
            max(new_reference_interest_rate, Constants.SECONDS_INTEREST_MINIMUM),
        )
        if new_reference_interest_rate <= 1350:
            break

    scenario.p("testing a prod response")
    scenario.show(interest_rate_updater.data.reference_interest_rate)
    scenario += observed_oracle.set_price(313170)
    scenario += target_oracle.set_price(353819)
    now = now.add_seconds(Constants.REFERENCE_INTEREST_UPDATE_LINEAR_INTERVAL)
    scenario += interest_rate_updater.interest_rate_update().run(sender=alice, now=now)
    scenario.show(interest_rate_updater.data.reference_interest_rate)
