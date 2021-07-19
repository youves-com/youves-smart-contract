import smartpy as sp
import tracker.errors as Errors

class TransferAmount:
    """Type to specify recipient and mutez amount
    """
    def get_type():
        """Returns a single TransferAmount type, layouted

        Returns:
            sp.TRecord: the layouted transfer_amount
        """        
        return sp.TRecord(recipient=sp.TAddress, amount=sp.TMutez).layout(("recipient", "amount"))

    def make(recipient, amount):
        """Makes an instance of an transfer_amount

        Args:
            recipient (sp.address): recipient
            amount (sp.mutez): amount

        Returns:
            Intent: the intent record
        """
        return sp.set_type_expr(sp.record(recipient=recipient, amount=amount), TransferAmount.get_type())

class Vault(sp.Contract):
    """The vault is where the collateral sits. This is segregated/not pooled on purpose. People can choose their own baker. The admin "aka the engine contract" is 
    in total control of the vault. The vault is kept lean on purpose, because it's beeing originated by other contracts (engine).

    Args:
        (sp.Contract): this is a smartpy contract
    """
    def __init__(self, admin_address):
        """takes an address as parameter to set the admin in storage.

        Args:
            admin_address (sp.address): the admin that controls this contract. Cannot be changed.
        """
        self.add_flag("initial-cast")
        self.init(
            admin_address = admin_address
        )

    @sp.entry_point
    def set_delegate(self, delegate):
        """entrypoint that sets the delegate. Only admin can call this
        Pre: sp.sender == storage.admin_address
        Post: sp.set_delegate(delegate)
        Post: call the default entrypoint to update the balance

        Args:
            delegate ([type]): [description]
        """
        sp.verify(sp.sender == self.data.admin_address, message=Errors.NOT_ADMIN)
        sp.set_delegate(delegate)
        sp.send(sp.self_address, sp.mutez(0))

    @sp.entry_point
    def default(self):
        """default entrypoint will automatically "set_vault_balance" on the admin
        Post: admin.set_vault_balance(sp.balance)
        """
        synth_set_balance = sp.contract(sp.TMutez, self.data.admin_address, entry_point="set_vault_balance").open_some()
        sp.transfer(sp.balance, sp.mutez(0), synth_set_balance)
    
    @sp.entry_point
    def withdraw(self, transfer_amount):
        """entrypoint to withdraw the balance from the vault. Only admin can do this:
        Pre: sp.sender == storage.admin_address
        Post: send transfer_amount.amount to transfer_amount.recipient
        Post: call the default entrypoint to update the balance

        Args:
            transfer_amount (TransferAmount): the amount and recipient to transfer to
        """
        sp.verify(sp.sender == self.data.admin_address, message=Errors.NOT_ADMIN)
        sp.set_type(transfer_amount, TransferAmount.get_type())        
        sp.send(transfer_amount.recipient, transfer_amount.amount)
        
if "templates" not in __name__:        
    
    @sp.add_test(name="Vault")
    def test():

        scenario = sp.test_scenario()
        scenario.add_flag("protocol", "florence")
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
        scenario += vault.withdraw(recipient=alice.address, amount=sp.tez(5)).run(sender=administrator)
        scenario += vault.set_delegate(sp.some(alice.public_key_hash)).run(sender=administrator, voting_powers={ alice.public_key_hash : 10 })
        
        scenario += vault.set_delegate(sp.some(bob.public_key_hash)).run(valid=False, sender=bob, voting_powers={ bob.public_key_hash : 10 })
        scenario += vault.withdraw(recipient=alice.address, amount=sp.tez(5)).run(valid=False, sender=bob)
        #scenario += vault.withdraw(recipient=alice.address, amount=sp.tez(17)).run(valid=False, sender=administrator) this error throws but a level deeper such that "valid=False" is not able to identify it and the test crashes.