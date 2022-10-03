import smartpy as sp

from utils.administrable_mixin import AdministratorState

from contracts.tracker.auto_manager import AutoManager


def execute_tez_transfer(recipient, amount):
    return sp.transfer_operation(
        sp.unit, amount, sp.contract(sp.TUnit, recipient).open_some()
    )


@sp.add_test(name="Auto Manager")
def test():
    scenario = sp.test_scenario()
    scenario.h1("Auto Manager Unit Test")
    scenario.table_of_contents()

    scenario.h2("Bootstrapping")

    administrator = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob = sp.test_account("Robert")
    dan = sp.test_account("Dan")

    auto_manager = AutoManager({administrator.address: AdministratorState.SET})
    scenario += auto_manager
    scenario += auto_manager.default().run(amount=sp.mutez(1000))

    scenario.h2("Testing Admin Functionality")
    scenario.h3("Not Allowed Admin management Functionality")
    scenario += auto_manager.propose_administrator(alice.address).run(
        sender=alice, valid=False
    )
    scenario += auto_manager.set_administrator().run(sender=alice, valid=False)
    scenario += auto_manager.remove_administrator(alice.address).run(
        sender=alice, valid=False
    )
    scenario += auto_manager.set_administrator().run(sender=administrator, valid=False)

    scenario.h3("Allowed Admin management Functionality")
    scenario += auto_manager.propose_administrator(alice.address).run(
        sender=administrator, valid=True
    )
    scenario += auto_manager.set_administrator().run(sender=administrator, valid=False)
    scenario += auto_manager.remove_administrator(alice.address).run(
        sender=administrator, valid=True
    )
    scenario += auto_manager.propose_administrator(alice.address).run(
        sender=administrator, valid=True
    )
    scenario += auto_manager.set_administrator().run(sender=alice, valid=True)
    scenario += auto_manager.remove_administrator(alice.address).run(
        sender=administrator, valid=True
    )

    scenario.h2("Testing Direct Execution")

    def tez_transfer(unit):
        sp.set_type(unit, sp.TUnit)
        sp.result(
            sp.list(
                [
                    execute_tez_transfer(
                        sp.address("tz1WxrQuZ4CK1MBUa2GqUWK1yJ4J6EtG1Gwi"), sp.mutez(10)
                    )
                ]
            )
        )

    scenario.show(sp.build_lambda(tez_transfer))
    scenario += auto_manager.execute(tez_transfer).run(sender=alice, valid=False)
    scenario += auto_manager.execute(tez_transfer).run(sender=administrator, valid=True)

    scenario.h2("Testing Manager Execution")
    scenario += auto_manager.add_execution_payload(
        execution_payload=tez_transfer, manager=alice.address
    ).run(sender=alice, valid=False)
    scenario += auto_manager.add_execution_payload(
        execution_payload=tez_transfer, manager=alice.address
    ).run(sender=administrator, valid=True)
    scenario += auto_manager.execute(tez_transfer).run(sender=alice, valid=True)

    scenario += auto_manager.remove_execution_payload(
        execution_payload=tez_transfer, manager=alice.address
    ).run(sender=alice, valid=False)
    scenario += auto_manager.remove_execution_payload(
        execution_payload=tez_transfer, manager=alice.address
    ).run(sender=administrator, valid=True)
    scenario += auto_manager.execute(tez_transfer).run(sender=alice, valid=False)

    scenario.h2("Different User")
    scenario += auto_manager.add_execution_payload(
        execution_payload=tez_transfer, manager=alice.address
    ).run(sender=administrator, valid=True)
    scenario += auto_manager.execute(tez_transfer).run(sender=bob, valid=False)
    scenario += auto_manager.add_execution_payload(
        execution_payload=tez_transfer, manager=bob.address
    ).run(sender=alice, valid=False)
    scenario += auto_manager.add_execution_payload(
        execution_payload=tez_transfer, manager=bob.address
    ).run(sender=administrator, valid=True)
    scenario += auto_manager.execute(tez_transfer).run(sender=alice, valid=True)
    scenario += auto_manager.execute(tez_transfer).run(sender=bob, valid=True)

    scenario.h2("Now a slightly different lambda")

    def tez_transfer_fake(unit):
        sp.set_type(unit, sp.TUnit)
        sp.result(
            sp.list(
                [
                    execute_tez_transfer(
                        sp.address("tz1WxrQuZ4CK1MBUa2GqUWK1yJ4J6EtG1Gwi"), sp.mutez(1)
                    )
                ]
            )
        )

    scenario.show(tez_transfer_fake)
    scenario += auto_manager.execute(tez_transfer_fake).run(sender=alice, valid=False)
