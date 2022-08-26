import smartpy as sp

import utils.constants as Constants

from utils.internal_mixin import InternalMixin


class PlentyOracle(sp.Contract, InternalMixin):
    """
    This oracles calculates the observed price on the secondary market by checking the plenty reserves.
    """

    def get_init_storage(self):
        """Returns the initial storage of the contract"""
        # TODO: Add support for window based price tracking. 
        storage = {}
        storage["dex_contract"] = self.dex_contract
        storage["token_1_address"] = self.token_1_address
        storage["token_1_id"] = self.token_1_id
        storage["token_2_address"] = self.token_2_address
        storage["token_2_id"] = self.token_2_id
        storage["price"] = 0
        return storage

    def __init__(
        self, dex_contract, token_1_address, token_1_id, token_2_address, token_2_id, token_1_decimals, token_2_decimals
    ):
        self.dex_contract = dex_contract
        self.token_1_address = token_1_address
        self.token_1_id = token_1_id
        self.token_2_address = token_2_address
        self.token_2_id = token_2_id
        self.token_1_decimals = token_1_decimals
        self.token_2_decimals = token_2_decimals
        self.init(**self.get_init_storage())

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_reserves(self, reserves):
        """
        This is the callback where the dex contract sets the reserves used for the price calculations.
        Eventhough it's an open entrypoint it's meaningless because only the data immediately set
        within the "get_price" call is going to be the one used for calculations.
        """
        sp.set_type(reserves, sp.TPair(sp.TNat, sp.TNat))
        self.data.price = (
            sp.fst(reserves) * sp.nat(10**self.token_2_decimals) * Constants.PRICE_PRECISION_FACTOR
        ) // (sp.snd(reserves) * sp.nat(10**self.token_1_decimals))

    @sp.entry_point(check_no_incoming_transfer=True)
    def get_price(self, callback):
        """
        This call will ask the current reserves from the DEX contract and then set them, internally
        the callback is passed such that the calculated price based on the fetched reserves can be
        returned.
        """
        sp.set_type(callback, sp.TContract(sp.TNat))

        get_reserve_balance = sp.contract(
            sp.TPair(
                sp.TPair(
                    sp.TPair(sp.TAddress, sp.TNat), sp.TPair(sp.TAddress, sp.TNat)
                ),
                sp.TContract(sp.TPair(sp.TNat, sp.TNat)),
            ),
            self.data.dex_contract,
            entry_point="getReserveBalance",
        ).open_some()
        set_reserves_callback_contract = sp.contract(
            sp.TPair(sp.TNat, sp.TNat), sp.self_address, entry_point="set_reserves"
        ).open_some()

        sp.transfer(
            (
                (
                    (self.data.token_1_address, self.data.token_1_id),
                    (self.data.token_2_address, self.data.token_2_id),
                ),
                set_reserves_callback_contract,
            ),
            sp.mutez(0),
            get_reserve_balance,
        )
        sp.transfer(callback, sp.mutez(0), sp.self_entry_point("internal_get_price"))

    @sp.entry_point(check_no_incoming_transfer=True)
    def internal_get_price(self, callback):
        """
        This is the internal call that returns the price to the intial callback
        """
        sp.set_type(callback, sp.TContract(sp.TNat))
        self.verify_internal(sp.unit)
        sp.transfer(self.data.price, sp.mutez(0), callback)
