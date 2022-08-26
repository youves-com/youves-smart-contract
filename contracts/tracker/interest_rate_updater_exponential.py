import smartpy as sp

import utils.error_codes as Errors
import utils.constants as Constants

from utils.fa2 import LedgerKey, RecipientTokenAmount
from contracts.tracker.interest_rate_updater import InterestRateUpdater


class InterestRateUpdaterExponential(InterestRateUpdater):
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
            // Constants.REFERENCE_INTEREST_UPDATE_INTERVAL
        )
        current_cycle = (
            sp.as_nat(sp.now - sp.timestamp(0))
            // Constants.REFERENCE_INTEREST_UPDATE_INTERVAL
        )

        sp.verify(current_cycle > last_cycle, message=Errors.TOO_EARLY)

        price_difference = sp.local(
            "price_difference", self.data.observed_price - self.data.target_price
        )
        stable_token_difference = sp.min(
            abs(price_difference.value),
            self.data.target_price >> Constants.MAX_STABLE_TOKEN_BITSHIFT,
        )
        normalised_stable_token_difference = (
            stable_token_difference * Constants.FX_MULTIPLIER
        ) / self.data.target_price
        target_step = sp.local(
            "target_step",
            (
                sp.as_nat(
                    (
                        1
                        << (
                            normalised_stable_token_difference
                            >> Constants.SCALING_FACTOR_ONE
                        )
                    )
                    - 1
                )
                * Constants.PRECISION_FACTOR
            )
            >> Constants.SCALING_FACTOR_TWO,
        )

        with sp.if_(price_difference.value > 0):
            self.data.reference_interest_rate = sp.as_nat(
                sp.max(
                    self.data.reference_interest_rate - target_step.value,
                    Constants.SECONDS_INTEREST_MINIMUM,
                )
            )
        with sp.else_():
            self.data.reference_interest_rate = sp.min(
                self.data.reference_interest_rate + target_step.value,
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
