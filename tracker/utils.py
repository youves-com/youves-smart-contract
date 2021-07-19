import smartpy as sp
import tracker.errors as Errors
import tracker.fa2 as fa2

class InternalMixin():
    """Internal mixin adds a subentrypoint to check whetever this is an internal call.
    """
    @sp.sub_entry_point
    def verify_internal(self, unit):
        """verifies if it's an internal call

        Pre: sp.sender == sp.self_address

        Args:
            unit (sp.unit): nothing
        """
        sp.verify(sp.sender == sp.self_address,
                  message=Errors.NOT_INTERNAL)

class Utils:
    """Utils class to facilitate certain operation. This is just syntactic sugar.

    """
    def execute_token_transfer(token_address, from_, to_, token_id, amount):
        """executes a single fa2 token transfer

        Args:
            token_address (sp.address): token address
            from_ (sp.address): sender
            to_ (sp.address): recipient
            token_id (sp.nat): token id
            amount (sp.nat): token amount to transfer
        """
        transfer_token_contract = sp.contract(fa2.Transfer.get_batch_type(
            ), token_address, entry_point="transfer").open_some()
        transfer_payload = [fa2.Transfer.item(from_, [sp.record(
                to_=to_, token_id=token_id, amount=amount)])]
        sp.transfer(transfer_payload, sp.mutez(0), transfer_token_contract)

    def execute_get(contract_address, getter_entrypoint, setter_entrypoint, value_type=sp.TNat):
        """generic method to get a certain value from an external contract

        Args:
            contract_address (sp.adress): contract where we pass our callback
            getter_entrypoint (sp.string): entrypoint
            setter_entrypoint (sp.string): our callback
            value_type ([type], optional): callback value type. Defaults to sp.TNat.
        """
        getter_contract = sp.contract(sp.TContract(
            value_type), contract_address, entry_point=getter_entrypoint).open_some()
        callback_contract = sp.contract(
            value_type, sp.self_address, entry_point=setter_entrypoint).open_some()
        sp.transfer(callback_contract, sp.mutez(0), getter_contract)

    def execute_get_own_balance(token_address, token_id, setter_entrypoint):
        """executes a single fa2 balance request of the own balance.

        Args:
            token_address ([type]): token address to request balance from
            token_id (sp.nat): token id
            setter_entrypoint (sp.string): our callback
        """
        getter_contract = sp.contract(fa2.BalanceOf.get_type(), token_address, entry_point="balance_of").open_some()
        callback_contract = sp.contract(
            fa2.BalanceOf.get_response_type(), sp.self_address, entry_point=setter_entrypoint).open_some()
        sp.transfer(fa2.BalanceOf.make_one_request(fa2.LedgerKey.make(token_id, sp.self_address), callback_contract), sp.mutez(0), getter_contract)

    def execute_token_mint(token_address, to_, token_id, amount):
        """executes a token mint on the given address for the given amount.

        Args:
            token_address (sp.address): token address
            to_ (sp.address): address that where the amount will be minted
            token_id (sp.nat): token id
            amount (sp.nat): token amount to mint
        """
        Utils.execute_token_amount_operation(token_address, to_, token_id, amount)

    def execute_token_burn(token_address, to_, token_id, amount):
        """executes a token burn on the given address for the given amount.

        Args:
            token_address (sp.address): token address
            to_ (sp.address): address that where the amount will be burned
            token_id (sp.nat): token id
            amount (sp.nat): token amount to burn
        """
        Utils.execute_token_amount_operation(token_address, to_, token_id, amount, operation="burn")

    def execute_token_amount_operation(token_address, to_, token_id, amount, operation="mint"):
        """executes a RecipientTokenAmount operation on the given token address. In our context this can either be burn or mint.

        Args:
            token_address (sp.address): token address
            to_ (sp.address): address parameter
            token_id (sp.nat): token id
            amount (sp.nat): token amount to use
            operation (str, optional): entrypoint name in our case mint or burn. Defaults to "mint".
        """
        mint_token_contract = sp.contract(fa2.RecipientTokenAmount.get_type(
            ), token_address, entry_point=operation).open_some()
        mint_payload = fa2.RecipientTokenAmount.make(
                to_,  token_id, amount)

        sp.transfer(mint_payload, sp.mutez(0), mint_token_contract)

    def execute_update(contract_address):
        """calls the entrypoint "update" with unit params on contract address.

        Args:
            contract_address (sp.TContract): the contract to execute the call on
        """
        update_contract = sp.contract(sp.TUnit, contract_address, entry_point="update").open_some()
        sp.transfer(sp.unit, sp.mutez(0), update_contract)
