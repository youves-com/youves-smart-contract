import smartpy as sp
import utils.error_codes as Errors
import utils.constants as Constants
from utils.fa2 import LedgerKey


class AdministratorState:
    PROPOSED = 0
    SET = 1


class SingleAdministrableMixin:
    """Mixin used to compose andministrable functionality of a contract. Still requires the inerhiting contract to define the apropiate storage."""

    @sp.private_lambda(with_storage="read-only", with_operations=False, wrap_call=True)
    def verify_is_admin(self, unit):
        """Sub entrypoint which verifies if a sender is in the set of admins
        Pre: storage.administrators[sp.sender] == AdministratorState.SET
        """
        sp.verify(
            self.data.administrators[sp.sender] == AdministratorState.SET,
            message=Errors.NOT_ADMIN,
        )

    @sp.entry_point(check_no_incoming_transfer=True)
    def propose_administrator(self, administrator_to_propose):
        """Only an existing admin can call this entrypoint. If the sender is correct the new admin is set
        Pre: verify_is_admin(token_id)
        Post: storage.administrators[LedgerKey(administrator_to_set, token_id)] = sp.unit

        Args:
            administrator_to_set (sp.address): the administrator that should be set
        """
        sp.set_type(administrator_to_propose, sp.TAddress)
        self.verify_is_admin(sp.unit)
        self.data.administrators[administrator_to_propose] = AdministratorState.PROPOSED

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_administrator(self):
        """Only an existing admin can call this entrypoint. If the sender is correct the new admin is set
        Pre: verify(sp.sender == AdministratorState.PROPOSED)
        Post: storage.administrators[sp.sender] = AdministratorState.SET

        """
        sp.verify(
            self.data.administrators[sp.sender] == AdministratorState.PROPOSED,
            message=Errors.NOT_PROPOSED_ADMIN,
        )
        self.data.administrators[sp.sender] = AdministratorState.SET

    @sp.entry_point(check_no_incoming_transfer=True)
    def remove_administrator(self, administrator_to_remove):
        """Only an existing admin can call this entrypoint. This removes a administrator entry entirely from the map (even the executing admin if requested)
        Pre: verify_is_admin(token_id)
        Post: del storage.administrators[administrator_to_remove]

        Args:
            administrator_to_remove (sp.address): the administrator that should be removed
        """
        sp.set_type(administrator_to_remove, sp.TAddress)
        self.verify_is_admin(sp.unit)
        del self.data.administrators[administrator_to_remove]

    @staticmethod
    def get_storage_fields():
        return {"administrators": sp.big_map(tkey=sp.TAddress, tvalue=sp.TNat)}
