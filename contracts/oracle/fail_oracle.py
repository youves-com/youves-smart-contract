import smartpy as sp


class FailOracle(sp.Contract):
    @sp.entry_point(check_no_incoming_transfer=True)
    def default(self):
        """
        Needs more than 1 entrypoint
        """
        sp.failwith("blocked")

    @sp.entry_point(check_no_incoming_transfer=True)
    def get_price(self, callback):
        """
        This call will ask the current reserves from the DEX contract and then set them, internally
        the callback is passed such that the calculated price based on the fetched reserves can be
        returned.
        """
        sp.set_type(callback, sp.TContract(sp.TNat))
        sp.failwith("blocked")
