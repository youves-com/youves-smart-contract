import smartpy as sp


class FA1Transfer:
    """Transfer object as per FA1.2 standard"""

    def get_type():
        """Returns a single transfer type, layouted

        Returns:
            sp.TRecord: single transfer type, layouted
        """
        return sp.TRecord(from_=sp.TAddress, to_=sp.TAddress, value=sp.TNat).layout(
            ("from_ as from", ("to_ as to", "value"))
        )

    def item(from_, to_, value):
        """Creates a typed transfer item as per FA1.2 specification

        Args:
            from_ (sp.address): address of the sender
            to_ (sp.address): address of the receiver
            value (sp.nat): amount to transfer

        Returns:
            Transfer: transfer sp.record typed
        """
        return sp.set_type_expr(
            sp.record(from_=from_, to_=to_, value=value), FA1Transfer.get_type()
        )
