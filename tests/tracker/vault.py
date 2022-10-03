import smartpy as sp

from contracts.tracker.vault import Vault


@sp.add_test(name="Vault")
def test():

    scenario = sp.test_scenario()
    scenario.add_flag("protocol", "ithaca")
    scenario.h1("Vault")
    scenario.table_of_contents()

    administrator = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob = sp.test_account("Robert")
    dan = sp.test_account("Dan")
    scenario.h2("Accounts")
    scenario.show([administrator, alice, bob, dan])

    vault = Vault(administrator.address)
    scenario += vault
    scenario += vault.default().run(amount=sp.tez(10), sender=administrator)
    scenario += vault.default().run(amount=sp.tez(11), sender=administrator)
    scenario += vault.withdraw(recipient=alice.address, amount=sp.tez(5)).run(
        sender=administrator
    )
    scenario += vault.set_delegate(sp.some(alice.public_key_hash)).run(
        sender=administrator, voting_powers={alice.public_key_hash: 10}
    )

    scenario += vault.set_delegate(sp.some(bob.public_key_hash)).run(
        valid=False, sender=bob, voting_powers={bob.public_key_hash: 10}
    )
    scenario += vault.withdraw(recipient=alice.address, amount=sp.tez(5)).run(
        valid=False, sender=bob
    )
    # scenario += vault.withdraw(recipient=alice.address, amount=sp.tez(17)).run(valid=False, sender=administrator) this error throws but a level deeper such that "valid=False" is not able to identify it and the test crashes.
