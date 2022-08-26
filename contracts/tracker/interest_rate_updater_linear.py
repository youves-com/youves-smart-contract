import smartpy as sp

import utils.error_codes as Errors
import utils.constants as Constants

from contracts.tracker.interest_rate_updater import InterestRateUpdater


class InterestRateUpdaterLinear(InterestRateUpdater):
    """this is the heartpiece of the entire project. The engine that orchestrates all other components. This is also the contract responsible for the interest rate/inflation of the liability/savings rate of the
    synthetic asset. This engine is built to create synthetic asset tokens that by getting data from an oracle the resulting synthetic asset will track that value.

    Args:
        (sp.Contract): this is a smartpy contract
        (AdministrableMixin): mixin used to add the administratble entrypoints
        (InternalMixin): mixin used whenever we need external data and hence have to trigger an internal call (to process after we received said external data)
    """

    @sp.entry_point(check_no_incoming_transfer=True)
    def internal_interest_rate_update(self):
        """updates the reference interest rate if it was not updated yet in this cycle. The minimum and maximum weekly interest rates set the upper and lower boundary of the interest rate.
        Inv: storage.reference_interest_rate >= Constants.SECONDS_INTEREST_MINIMUM
        Inv: storage.reference_interest_rate <= Constants.SECONDS_INTEREST_MAXIMUM
        Pre: sp.now/7days > storage.last_update_timestamp/7days
        Pre: verify_internal()
        Post: update_accrual()
        Post: storage.last_update_timestamp = sp.now
        Post: storage.reference_interest_rate is set according to documentation based on observed/target price difference.
        """
        self.verify_internal(sp.unit)

        last_cycle = (
            sp.as_nat(self.data.last_update_timestamp - sp.timestamp(0))
            // Constants.REFERENCE_INTEREST_UPDATE_LINEAR_INTERVAL
        )
        current_cycle = (
            sp.as_nat(sp.now - sp.timestamp(0))
            // Constants.REFERENCE_INTEREST_UPDATE_LINEAR_INTERVAL
        )

        sp.verify(current_cycle > last_cycle, message=Errors.TOO_EARLY)

        target_step = sp.local(
            "price_difference",
            sp.min(
                sp.max(
                    sp.fst(
                        sp.ediv(
                            (self.data.observed_price - self.data.target_price)
                            * Constants.PRECISION_FACTOR
                            * Constants.LINEAR_RESPONSE_FACTOR,
                            self.data.target_price * Constants.PRECISION_FACTOR,
                        ).open_some()
                    ),
                    Constants.MIN_LINEAR_RESPONSE_STEP,
                ),
                Constants.MAX_LINEAR_RESPONSE_STEP,
            ),
        )

        self.data.reference_interest_rate = sp.min(
            sp.max(
                sp.as_nat(
                    sp.to_int(self.data.reference_interest_rate) + target_step.value
                ),
                Constants.SECONDS_INTEREST_MINIMUM,
            ),
            Constants.SECONDS_INTEREST_MAXIMUM,
        )
        self.data.last_update_timestamp = sp.now

        with sp.for_("engine_addresses", self.data.engine_addresses) as engine_address:
            engine_set_reference_interest_rate = sp.contract(
                sp.TNat, engine_address, entry_point="set_reference_interest_rate"
            ).open_some()
            sp.transfer(
                self.data.reference_interest_rate,
                sp.mutez(0),
                engine_set_reference_interest_rate,
            )
