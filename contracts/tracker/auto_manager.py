import smartpy as sp

import utils.error_codes as Errors

from utils.administrable_mixin import SingleAdministrableMixin, AdministratorState


class AutoManager(sp.Contract, SingleAdministrableMixin):
    """Contract that allows"""

    def __init__(self, administrators={}):
        """The storage can be initialised with a list of administrators

        Args:
            administrators (dict, optional): the initial list of administrator to allow. Defaults to {}.
        """
        self.storage_dict = {
            "administrators": administrators,
            "allowed_lambdas": sp.big_map(tkey=sp.TBytes, tvalue=sp.TSet(sp.TAddress)),
        }
        self.init(**self.storage_dict)

    @sp.entry_point(check_no_incoming_transfer=True)
    def default(self):
        pass

    @sp.entry_point(check_no_incoming_transfer=True)
    def add_execution_payload(self, execution_payload, manager):
        sp.set_type(execution_payload, sp.TLambda(sp.TUnit, sp.TList(sp.TOperation)))
        self.verify_is_admin(sp.unit)
        lambda_key = sp.local("lambda_key", sp.pack(execution_payload))
        with sp.if_(~self.data.allowed_lambdas.contains(lambda_key.value)):
            self.data.allowed_lambdas[lambda_key.value] = sp.set([])
        self.data.allowed_lambdas[lambda_key.value].add(manager)

    @sp.entry_point(check_no_incoming_transfer=True)
    def remove_execution_payload(self, execution_payload, manager):
        sp.set_type(execution_payload, sp.TLambda(sp.TUnit, sp.TList(sp.TOperation)))
        self.verify_is_admin(sp.unit)
        lambda_key = sp.local("lambda_key", sp.pack(execution_payload))
        with sp.if_(self.data.allowed_lambdas.contains(lambda_key.value)):
            self.data.allowed_lambdas[lambda_key.value].remove(manager)

    @sp.entry_point(check_no_incoming_transfer=True)
    def execute(self, execution_payload):
        """Only an admin for token_id 0 can call this entrypoint. It executes in the name of the contract the lambda stored in the execution payload.
        This is used for upgreadability/migrations.
        Pre: verify_is_admin(0)
        Post: push execution_payload on execution stack

        Args:
            execution_payload (sp.TLambda(sp.TUnit, sp.TList(sp.TOperation))): the lambda to execute
        """
        sp.set_type(execution_payload, sp.TLambda(sp.TUnit, sp.TList(sp.TOperation)))
        lambda_key = sp.local("lambda_key", sp.pack(execution_payload))
        with sp.if_(
            (
                ~self.data.administrators.contains(sp.sender)
                & self.data.allowed_lambdas.contains(lambda_key.value)
            )
        ):
            sp.verify(
                self.data.allowed_lambdas[lambda_key.value].contains(sp.sender),
                message=Errors.NOT_ADMIN,
            )
        with sp.else_():
            self.verify_is_admin(sp.unit)
        sp.add_operations(execution_payload(sp.unit).rev())
