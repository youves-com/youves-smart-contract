import smartpy as sp

import utils.constants as Constants
import utils.error_codes as Errors


class LPPriceOracle(sp.Contract):
    """
        Oracle to return the price of tzBTC in the price of the SIRS (previously known as tzBTC LP)
        token or viceversa.
    """

    def __init__(
        self,
        lp_token_address,
        lp_address,
        value_token_address,
        value_token_decimals,
        requires_flip=True,
    ):
        self.init(
            lpt_total_supply=sp.nat(0),
            value_token_balance_of=sp.nat(0),
            value_token_per_lpt_ratio=sp.nat(0),
            last_update=sp.timestamp(0),
            lp_token_address=lp_token_address,
            lp_address=lp_address,
            value_token_address=value_token_address,
        )

        self.value_token_decimals = value_token_decimals
        self.requires_flip = requires_flip

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_lpt_total_supply(self, lpt_total_supply):
        """Entrypoint used by the LP token to provide its total supply"""
        self.data.lpt_total_supply = lpt_total_supply

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_value_token_balance_of(self, value_token_balance_of):
        """Entrypoint used by the value token to provide the balance"""
        self.data.value_token_balance_of = value_token_balance_of

    @sp.entry_point(check_no_incoming_transfer=True)
    def get_price(self, callback):
        """Entrypoint used to update the ratio"""
        sp.set_type(callback, sp.TContract(sp.TNat))

        get_total_supply_contract = sp.contract(
            sp.TPair(sp.TUnit, sp.TContract(sp.TNat)),
            self.data.lp_token_address,
            entry_point="getTotalSupply",
        ).open_some()
        total_supply_callback_contract = sp.contract(
            sp.TNat, sp.self_address, entry_point="set_lpt_total_supply"
        ).open_some()
        sp.transfer(
            sp.pair(sp.unit, total_supply_callback_contract),
            sp.mutez(0),
            get_total_supply_contract,
        )

        get_value_token_balance_contract = sp.contract(
            sp.TPair(sp.TAddress, sp.TContract(sp.TNat)),
            self.data.value_token_address,
            entry_point="getBalance",
        ).open_some()
        value_token_balance_callback_contract = sp.contract(
            sp.TNat, sp.self_address, entry_point="set_value_token_balance_of"
        ).open_some()
        sp.transfer(
            sp.pair(self.data.lp_address, value_token_balance_callback_contract),
            sp.mutez(0),
            get_value_token_balance_contract,
        )

        sp.transfer(callback, sp.mutez(0), sp.self_entry_point("internal_get_price"))

    @sp.entry_point(check_no_incoming_transfer=True)
    def internal_get_price(self, callback):
        sp.set_type(callback, sp.TContract(sp.TNat))
        sp.verify(sp.sender == sp.self_address, message=Errors.NOT_INTERNAL)
        new_value_token_per_lpt_ratio = sp.local(
            "new_value_token_per_lpt_ratio",
            self.data.value_token_balance_of
            * Constants.PRICE_PRECISION_FACTOR
            // self.data.lpt_total_supply,
        )

        # we accept a max change of the ratio of 3.125 per 15min because we have *2 multiplication
        with sp.if_((self.data.value_token_per_lpt_ratio != 0)):
            max_value_token_per_lpt_ratio_diff = sp.local(
                "max_value_token_per_lpt_ratio_diff",
                (self.data.value_token_per_lpt_ratio >> 5)
                * sp.min(
                    sp.as_nat(sp.now - self.data.last_update),
                    Constants.ORACLE_EPOCH_INTERVAL,
                )
                // Constants.ORACLE_EPOCH_INTERVAL,
            )
            new_value_token_per_lpt_ratio_max = (
                self.data.value_token_per_lpt_ratio
                + max_value_token_per_lpt_ratio_diff.value
            )
            new_value_token_per_lpt_ratio_min = sp.as_nat(
                self.data.value_token_per_lpt_ratio
                - max_value_token_per_lpt_ratio_diff.value
            )
            self.data.value_token_per_lpt_ratio = sp.min(
                sp.max(
                    new_value_token_per_lpt_ratio.value,
                    new_value_token_per_lpt_ratio_min,
                ),
                new_value_token_per_lpt_ratio_max,
            )
        with sp.else_():
            self.data.value_token_per_lpt_ratio = new_value_token_per_lpt_ratio.value

        self.data.last_update = sp.now

        if self.requires_flip:
            sp.transfer(
                (
                    Constants.PRICE_PRECISION_FACTOR**2
                    * 10**self.value_token_decimals
                )
                // (self.data.value_token_per_lpt_ratio * 2),
                sp.mutez(0),
                callback,
            )
        else:
            sp.transfer(
                (self.data.value_token_per_lpt_ratio * 2)
                // (10**self.value_token_decimals),
                sp.mutez(0),
                callback,
            )

class RelativeLPPriceOracle(sp.Contract):
    """
        Oracle to return the price of a given token in the price of SIRS (previously know as tzBTC LP)
        token or viceversa.
    """

    def __init__(
        self,
        tzbtc_sirs_oracle_address,
        generic_oracle_address,
        generic_oracle_symbol,
        requires_flip=True,
    ):
        self.init(
            tzbtc_sirs_oracle_address=tzbtc_sirs_oracle_address,
            generic_oracle_address=generic_oracle_address,
            generic_oracle_symbol=generic_oracle_symbol,
            tzbtc_sirs_price=sp.nat(0),
        )
        self.requires_flip = requires_flip
    
    @sp.entry_point(check_no_incoming_transfer=True)
    def get_price(self, callback):
        """Entrypoint used to return the price to the callback contract"""
        sp.set_type(callback, sp.TContract(sp.TNat))

        tzbtc_sirs_oracle_contract = sp.contract(
            sp.TContract(sp.TNat), self.data.tzbtc_sirs_oracle_address, "get_price").open_some()
        
        sp.transfer(sp.self_entry_point("set_tzbtc_sirs_price"), sp.mutez(0), tzbtc_sirs_oracle_contract)
        sp.transfer(callback, sp.mutez(0), sp.self_entry_point("internal_get_price"))
    
    @sp.entry_point(check_no_incoming_transfer=True)
    def set_tzbtc_sirs_price(self, price):
        sp.set_type(price, sp.TNat)

        sp.verify(sp.sender == self.data.tzbtc_sirs_oracle_address, message=Errors.INVALID_SENDER)
        self.data.tzbtc_sirs_price = price
        
    
    @sp.entry_point(check_no_incoming_transfer=True)
    def internal_get_price(self, callback):
        sp.set_type(callback, sp.TContract(sp.TNat))
        sp.verify(sp.sender == sp.self_address, message=Errors.NOT_INTERNAL)

        symbol_price = sp.view(
            "get_price",
            self.data.generic_oracle_address,
            self.data.generic_oracle_symbol,
            t=sp.TNat,
        ).open_some(Errors.INVALID_VIEW)

        price = sp.local("price", self.data.tzbtc_sirs_price * Constants.PRICE_PRECISION_FACTOR // symbol_price)
        if self.requires_flip:
            sp.transfer(
                Constants.PRICE_PRECISION_FACTOR**2 // price.value,
                sp.mutez(0),
                callback
            )
        else:
            sp.transfer(price.value, sp.mutez(0), callback)
