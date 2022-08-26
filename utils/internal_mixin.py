import smartpy as sp
import utils.error_codes as Errors


class InternalMixin:
    """Internal mixin adds a subentrypoint to check whetever this is an internal call."""

    @sp.private_lambda(with_storage=None, with_operations=False, wrap_call=True)
    def verify_internal(self, unit):
        """verifies if it's an internal call

        Pre: sp.sender == sp.self_address

        Args:
            unit (sp.unit): nothing
        """
        sp.set_type(unit, sp.TUnit)
        sp.verify(sp.sender == sp.self_address, message=Errors.NOT_INTERNAL)
