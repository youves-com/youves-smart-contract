import time
from pytezos.operation.result import OperationResult


def get_address(pytezos_admin_client, operation_hash):
    while True:
        try:
            opg = pytezos_admin_client.shell.blocks[-10:].find_operation(operation_hash)
            originated_contracts = OperationResult.originated_contracts(opg)

            if len(originated_contracts) >= 1:
                return originated_contracts[0]

            time.sleep(1)
        except:
            pass


def wait_applied(pytezos_admin_client, operation_hash):
    while True:
        try:
            opg = pytezos_admin_client.shell.blocks[-10:].find_operation(operation_hash)

            if OperationResult.is_applied(opg):
                return True

            time.sleep(1)
        except:
            pass
