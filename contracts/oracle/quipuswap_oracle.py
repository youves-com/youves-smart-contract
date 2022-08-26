import smartpy as sp

import utils.constants as Constants

from utils.contract_utils import Utils
from utils.internal_mixin import InternalMixin


class QuipuswapOracle(sp.Contract, InternalMixin):
    """This oracles calculates the observed price on the secondary market by checking the
    quipuswap reserves.
    """

    def get_init_storage(self):
        """Returns the initial storage of the contract"""
        storage = {}
        storage["dex_contract"] = self.dex_contract
        storage["price"] = 0
        return storage

    def __init__(self, dex_contract, token1_decimals, token2_decimals):
        self.dex_contract = dex_contract
        self.token1_decimals = token1_decimals
        self.token2_decimals = token2_decimals

        self.init(**self.get_init_storage())

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_reserves(self, reserves):
        """
        This is the callback where the dex contract sets the reserves used for the price calculations.
        Eventhough it's an open entrypoint it's meaningless because only the data immediately set
        within the "get_price" call is going to be the one used for calculations.
        """
        sp.set_type(reserves, sp.TPair(sp.TNat, sp.TNat))
        self.data.price = (sp.fst(reserves) * sp.nat(10**self.token2_decimals) * Constants.PRICE_PRECISION_FACTOR) // (
            sp.snd(reserves) * sp.nat(10**self.token1_decimals)
        )

    @sp.entry_point(check_no_incoming_transfer=True)
    def get_price(self, callback):
        """
        This call will ask the current reserves from the DEX contract and then set them, internally
        the callback is passed such that the calculated price based on the fetched reserves can be
        returned.
        """
        sp.set_type(callback, sp.TContract(sp.TNat))
        Utils.execute_get(
            self.data.dex_contract,
            "get_reserves",
            "set_reserves",
            value_type=sp.TPair(sp.TNat, sp.TNat),
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
