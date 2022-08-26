import smartpy as sp

import utils.constants as Constants
import utils.error_codes as Errors


class FA2ErrorMessage:
    """Static enum used for the FA2 related errors, using the `FA2_` prefix"""

    PREFIX = "FA2_"
    TOKEN_UNDEFINED = "{}TOKEN_UNDEFINED".format(PREFIX)
    """This error is thrown if the token id used in to defined"""
    INSUFFICIENT_BALANCE = "{}INSUFFICIENT_BALANCE".format(PREFIX)
    """This error is thrown if the source address transfers an amount that exceeds its balance"""
    NOT_OWNER = "{}NOT_OWNER".format(PREFIX)
    """This error is thrown if not the owner is performing an action that he/she shouldn't"""
    NOT_OPERATOR = "{}NOT_OPERATOR".format(PREFIX)
    """This error is thrown if neither token owner nor permitted operators are trying to transfer an amount"""


class TokenMetadata:
    """Token metadata object as per FA2 standard"""

    def get_type():
        """Returns a single token metadata type, layouted as per token metadata

        Returns:
            sp.TRecord: single token metadata type, layouted
        """
        return sp.TRecord(
            token_id=sp.TNat, token_info=sp.TMap(sp.TString, sp.TBytes)
        ).layout(("token_id", "token_info"))

    def get_batch_type():
        """Returns a list type containing token metadata types

        Returns:
            sp.TList: smartpy type of a list of tokenmetadata
        """
        return sp.TList(TokenMetadata.get_type())


class Transfer:
    """Transfer object as per FA2 standard"""

    def get_type():
        """Returns a single transfer type, layouted

        Returns:
            sp.TRecord: single transfer type, layouted
        """
        tx_type = sp.TRecord(to_=sp.TAddress, token_id=sp.TNat, amount=sp.TNat).layout(
            ("to_", ("token_id", "amount"))
        )
        transfer_type = sp.TRecord(from_=sp.TAddress, txs=sp.TList(tx_type)).layout(
            ("from_", "txs")
        )
        return transfer_type

    def get_batch_type():
        """Returns a list type containing transfer types

        Returns:
            sp.TList: list type containing transfer types
        """
        return sp.TList(Transfer.get_type())

    def item(from_, txs):
        """Creates a typed transfer item as per FA2 specification

        Args:
            from_ (sp.address): address of the sender
            txs (dict): dictionary containing the keys "to_" (the recipient), "token_id" (id to transfer), and "amount" (amount of token to transfer)

        Returns:
            Transfer: transfer sp.record typed
        """
        return sp.set_type_expr(sp.record(from_=from_, txs=txs), Transfer.get_type())


class UpdateOperator:
    """Update operators object as per FA2 standard"""

    def get_operator_param_type():
        """Parameters included in the update operator request

        Returns:
            sp.TRecord: layouted to match the FA2 standard
        """
        return sp.TRecord(
            owner=sp.TAddress, operator=sp.TAddress, token_id=sp.TNat
        ).layout(("owner", ("operator", "token_id")))

    def get_type():
        """Returns a single update operator type, layouted

        Returns:
            sp.TVariant: single update operator type, layouted
        """
        return sp.TVariant(
            add_operator=UpdateOperator.get_operator_param_type(),
            remove_operator=UpdateOperator.get_operator_param_type(),
        )

    def get_batch_type():
        """Returns a list type containing update operator types

        Returns:
            sp.TList: list type containing update operator types
        """
        return sp.TList(UpdateOperator.get_type())


class BalanceOf:
    """Balance of object as per FA2 standard"""

    def get_response_type():
        """Returns the balance_of reponse type, layouted

        Returns:
            sp.TRecord: balance_of reponse type, layouted as per FA2
        """
        return sp.TList(
            sp.TRecord(request=LedgerKey.get_type(), balance=sp.TNat).layout(
                ("request", "balance")
            )
        )

    def get_type():
        """Returns the balance_of type, layouted

        Returns:
            sp.TRecord: balance_of type, layouted as per FA2
        """
        return sp.TRecord(
            requests=sp.TList(LedgerKey.get_type()),
            callback=sp.TContract(BalanceOf.get_response_type()),
        ).layout(("requests", "callback"))

    def make_one_request(ledger_key, callback):
        """Returns the balance_of request payload for a single ledger_key

        Args:
            ledger_key (LedgerKey): the ledger key you are interested in
            callback (sp.TContract): the callback to be used to return the balance_of response

        Returns:
            sp.record: balance_of request payload for a signle ledger key, typed.
        """
        return sp.set_type_expr(
            sp.record(requests=[ledger_key], callback=callback), BalanceOf.get_type()
        )


class LedgerKey:
    """Ledger key used when looking up balances"""

    def get_type():
        """Returns a single ledger key type, layouted

        Returns:
            sp.TRecord: layouted type of a ledger lookup key
        """
        return sp.TRecord(owner=sp.TAddress, token_id=sp.TNat).layout(
            ("owner", "token_id")
        )

    def make(token_id, owner):
        """Creates a typed ledger key

        Args:
            token_id (sp.nat): the token id
            owner (sp.address): address of the owner

        Returns:
            sp.record: typed ledger key
        """
        return sp.set_type_expr(
            sp.record(owner=owner, token_id=token_id), LedgerKey.get_type()
        )


class OperatorKey:
    """Operator key used when looking up operation permissions"""

    def get_type():
        """Returns a single operator key type, layouted

        Returns:
            sp.TRecord: single operator key type, layouted
        """
        return sp.TRecord(
            token_id=sp.TNat, owner=sp.TAddress, operator=sp.TAddress
        ).layout(("owner", ("operator", "token_id")))

    def make(token_id, owner, operator):
        """Creates a typed operator key

        Args:
            token_id (sp.nat): token id
            owner (sp.address): owner address
            operator (sp.address): operator

        Returns:
            sp.record: typed operator key
        """
        return sp.set_type_expr(
            sp.record(token_id=token_id, owner=owner, operator=operator),
            OperatorKey.get_type(),
        )


class RecipientTokenAmount:
    """Helper type used whenever amount, recipient and token id needs to be defined"""

    def get_type():
        """Get the token amount type

        Returns:
            sp.TRecord: [description]
        """
        return sp.TRecord(
            owner=sp.TAddress, token_id=sp.TNat, token_amount=sp.TNat
        ).layout(("owner", ("token_id", "token_amount")))

    def get_batch_type():
        """Get a list of the token amount type

        Returns:
            sp.TList: the token amount list type
        """
        return sp.TList(RecipientTokenAmount.get_type())

    def make(owner, token_id, token_amount):
        """Creates a typed token amount

        Args:
            owner (sp.address): owner
            token_id (sp.nat): token id
            token_amount (sp.nat): amount

        Returns:
            sp.record: typed token amount
        """
        return sp.set_type_expr(
            sp.record(owner=owner, token_id=token_id, token_amount=token_amount),
            RecipientTokenAmount.get_type(),
        )


class BaseFA2(sp.Contract):
    """Base FA2 contract, which implements the required entry points"""

    def get_init_storage(self):
        """Returns the initial storage of the contract used for inheritance of smartpy contracts

        Returns:
            dict: initial storage of the contract
        """
        return dict(
            ledger=sp.big_map(tkey=LedgerKey.get_type(), tvalue=sp.TNat),
            token_metadata=sp.big_map(tkey=sp.TNat, tvalue=TokenMetadata.get_type()),
            total_supply=sp.big_map(tkey=sp.TNat, tvalue=sp.TNat),
            operators=sp.big_map(tkey=OperatorKey.get_type(), tvalue=sp.TUnit),
        )

    def __init__(self):
        """Has no constructor parameters, initialises the storage"""
        self.init(**self.get_init_storage())

    @sp.entry_point(check_no_incoming_transfer=True)
    def transfer(self, transfers):
        """entrypoint to perform one or multiple transfers. Compatible with FA2 standard
        Pre: storage.ledger[LedgerKey(transfer._from, transfer.txs.token_id)] >= transfer.txs.token_amount
        Pre: sp.sender == transfer._from || storage.operators.contains(OperatorKey(transfer._from, sp.sender, transfer.txs.token_id))
        Post: storage.ledger[LedgerKey(transfer._from, transfer.txs.token_id)] -= transfer.txs.token_amount
        Post: storage.ledger[LedgerKey(transfer.txs.to_, transfer.txs.token_id)] += transfer.txs.token_amount

        Args:
            transfers (sp.list(Transfer)): batch transfer type
        """
        sp.set_type(transfers, Transfer.get_batch_type())
        with sp.for_("transfer", transfers) as transfer:
            with sp.for_("tx", transfer.txs) as tx:
                from_user_ledger_key = sp.local(
                    "from_user_ledger_key", LedgerKey.make(tx.token_id, transfer.from_)
                )
                to_user_ledger_key = sp.local(
                    "to_user_ledger_key", LedgerKey.make(tx.token_id, tx.to_)
                )
                operator_key = OperatorKey.make(tx.token_id, transfer.from_, sp.sender)

                sp.verify(
                    self.data.ledger.get(from_user_ledger_key.value, sp.nat(0))
                    >= tx.amount,
                    message=FA2ErrorMessage.INSUFFICIENT_BALANCE,
                )
                sp.verify(
                    (sp.sender == transfer.from_)
                    | self.data.operators.contains(operator_key),
                    message=FA2ErrorMessage.NOT_OPERATOR,
                )
                with sp.if_(tx.amount > 0):
                    self.data.ledger[from_user_ledger_key.value] = sp.as_nat(
                        self.data.ledger[from_user_ledger_key.value] - tx.amount
                    )
                    self.data.ledger[to_user_ledger_key.value] = (
                        self.data.ledger.get(to_user_ledger_key.value, 0) + tx.amount
                    )

                    with sp.if_(
                        self.data.ledger[from_user_ledger_key.value] == sp.nat(0)
                    ):
                        del self.data.ledger[from_user_ledger_key.value]

    @sp.entry_point(check_no_incoming_transfer=True)
    def update_operators(self, update_operators):
        """As per FA2 standard, allows a token owner to set an operator who will be allowed to perform transfers on her/his behalf

        Pre: update_operator.add_operator.owner == sp.sender
        Pre: update_operator.remove_operator.owner == sp.sender
        Post: set storage.operators[OperatorKey(update_operator.add_operator.owner, update_operator.add_operator.operator, update_operator.add_operator.token_id)]
        Post: set storage.operators[OperatorKey(update_operator.remove_operator.owner, update_operator.remove_operator.operator, update_operator.remove_operator.token_id)]

        Args:
            update_operators (sp.list(UpdateOperator)): batch update operator type
        """
        sp.set_type(update_operators, UpdateOperator.get_batch_type())
        with sp.for_("update_operator", update_operators) as update_operator:
            with update_operator.match_cases() as argument:
                with argument.match("add_operator") as update:
                    sp.verify(
                        update.owner == sp.sender, message=FA2ErrorMessage.NOT_OWNER
                    )
                    operator_key = OperatorKey.make(
                        update.token_id, update.owner, update.operator
                    )
                    self.data.operators[operator_key] = sp.unit
                with argument.match("remove_operator") as update:
                    sp.verify(
                        update.owner == sp.sender, message=FA2ErrorMessage.NOT_OWNER
                    )
                    operator_key = OperatorKey.make(
                        update.token_id, update.owner, update.operator
                    )
                    del self.data.operators[operator_key]

    @sp.entry_point(check_no_incoming_transfer=True)
    def balance_of(self, balance_of_request):
        """This entrypoint as per FA2 standard, takes balance_of requests and reponds on the provided callback contract.

        Args:
            balance_of_request (BalanceOf): the request
        """
        sp.set_type(balance_of_request, BalanceOf.get_type())

        responses = sp.local(
            "responses", sp.set_type_expr(sp.list([]), BalanceOf.get_response_type())
        )
        with sp.for_("request", balance_of_request.requests) as request:
            sp.verify(
                self.data.token_metadata.contains(request.token_id),
                message=FA2ErrorMessage.TOKEN_UNDEFINED,
            )
            responses.value.push(
                sp.record(request=request, balance=self.data.ledger.get(request, 0))
            )

        sp.transfer(responses.value, sp.mutez(0), balance_of_request.callback)


class AdministrableMixin:
    """Mixin used to compose andministrable functionality of a contract. Still requires the inerhiting contract to define the apropiate storage."""

    @sp.private_lambda(with_storage="read-write", with_operations=True, wrap_call=True)
    def verify_is_admin(self, token_id):
        """Sub entrypoint which verifies if a sender is in the set of admins
        Pre: storage.administrators.contains(LedgerKey(sp.sender, token_id))

        Args:
            token_id (sp.nat): token id to check for admin
        """
        administrator_ledger_key = LedgerKey.make(token_id, sp.sender)
        sp.verify(
            self.data.administrators.contains(administrator_ledger_key),
            message=Errors.NOT_ADMIN,
        )

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_administrator(self, token_id, administrator_to_set):
        """Only an existing admin can call this entrypoint. If the sender is correct the new admin is set
        Pre: verify_is_admin(token_id)
        Post: storage.administrators[LedgerKey(administrator_to_set, token_id)] = sp.unit

        Args:
            token_id (sp.nat): token id
            administrator_to_set (sp.address): the administrator that should be set
        """
        sp.set_type(token_id, sp.TNat)
        sp.set_type(administrator_to_set, sp.TAddress)
        self.verify_is_admin(token_id)

        administrator_ledger_key = LedgerKey.make(token_id, administrator_to_set)
        self.data.administrators[administrator_ledger_key] = sp.unit

    @sp.entry_point(check_no_incoming_transfer=True)
    def remove_administrator(self, token_id, administrator_to_remove):
        """Only an existing admin can call this entrypoint. This removes a administrator entry entirely from the map (even the executing admin if requested)
        Pre: verify_is_admin(token_id)
        Post: del storage.administrators[LedgerKey(administrator_to_set, token_id)]

        Args:
            token_id (sp.nat): token id
            administrator_to_remove (sp.address): the administrator that should be removed
        """
        sp.set_type(token_id, sp.TNat)
        sp.set_type(administrator_to_remove, sp.TAddress)
        self.verify_is_admin(token_id)

        administrator_to_remove_key = LedgerKey.make(token_id, administrator_to_remove)
        del self.data.administrators[administrator_to_remove_key]

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
        self.verify_is_admin(Constants.DEFAULT_TOKEN_ID)
        sp.add_operations(execution_payload(sp.unit).rev())


class AdministrableFA2(BaseFA2, AdministrableMixin):
    """FA2 Contract with administrators per token"""

    def get_init_storage(self):
        """Returns the initial storage of the contract used for inheritance of smartpy contracts

        Returns:
            dict: initial storage of the contract
        """
        storage = super().get_init_storage()
        storage["administrators"] = sp.big_map(
            l=self.administrators, tkey=LedgerKey.get_type(), tvalue=sp.TUnit
        )
        return storage

    def __init__(self, administrators={}):
        """The storage can be initialised with a list of administrators

        Args:
            administrators (dict, optional): the initial list of administrator to allow. Defaults to {}.
        """
        self.administrators = administrators
        self.add_flag("initial-cast")
        super().__init__()

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_token_metadata(self, token_metadata):
        """Only an admin for token id 0 can call this entrypoint. It will set the token_metadata of the token if it was not already previously set and also set the sender as the admin.
        Pre: verify_is_admin(0)
        Post: storage.token_metadata[token_metadata.id] = token_metadata
        Post: storage.administrator[LedgerKey(sp.sender, token_metadata.id)] = sp.unit
        Post: storage.total_supply[token_metadata.id] = 0

        Args:
            token_metadata (TokenMetadata): the token metadata to set
        """
        sp.set_type(token_metadata, TokenMetadata.get_type())

        self.verify_is_admin(Constants.DEFAULT_TOKEN_ID)
        with sp.if_(~self.data.token_metadata.contains(token_metadata.token_id)):
            self.data.token_metadata[token_metadata.token_id] = token_metadata
            self.data.administrators[
                LedgerKey.make(token_metadata.token_id, sp.sender)
            ] = sp.unit
            self.data.total_supply[token_metadata.token_id] = 0

    @sp.entry_point(check_no_incoming_transfer=True)
    def mint(self, recipient_token_amount):
        """Allows to mint new tokens to the specified reciepient address, only a token administrator can do this
        Pre: verify_is_admin(recipient_token_amount.token_id)
        Post: storage.ledger[LedgerKey(recipient_token_amount.owner, recipient_token_amount.token_id)] += recipient_token_amount.token_amount
        Post: storage.total_supply[recipient_token_amount.token_id] += recipient_token_amount.token_amount

        Args:
            recipient_token_amount (RecipientTokenAmount): a record that has owner, token_amount and token_id
        """
        sp.set_type(recipient_token_amount, RecipientTokenAmount.get_type())
        self.verify_is_admin(recipient_token_amount.token_id)
        owner_ledger_key = LedgerKey.make(
            recipient_token_amount.token_id, recipient_token_amount.owner
        )
        self.data.ledger[owner_ledger_key] = (
            self.data.ledger.get(owner_ledger_key, 0)
            + recipient_token_amount.token_amount
        )
        self.data.total_supply[
            recipient_token_amount.token_id
        ] += recipient_token_amount.token_amount

    @sp.entry_point(check_no_incoming_transfer=True)
    def burn(self, recipient_token_amount):
        """Allows to mint new tokens to the specified reciepient address, only a token administrator can do this
        Pre: verify_is_admin(recipient_token_amount.token_id)
        Pre: storage.ledger[LedgerKey(recipient_token_amount.owner, recipient_token_amount.token_id)] >= recipient_token_amount.token_amount
        Post: storage.ledger[LedgerKey(recipient_token_amount.owner, recipient_token_amount.token_id)] -= recipient_token_amount.token_amount
        Post: storage.total_supply[recipient_token_amount.token_id] -= recipient_token_amount.token_amount

        Args:
            recipient_token_amount (RecipientTokenAmount): a record that has owner, token_amount and token_id
        """
        sp.set_type(recipient_token_amount, RecipientTokenAmount.get_type())
        self.verify_is_admin(recipient_token_amount.token_id)
        owner_ledger_key = LedgerKey.make(
            recipient_token_amount.token_id, recipient_token_amount.owner
        )
        self.data.ledger[owner_ledger_key] = sp.as_nat(
            self.data.ledger.get(owner_ledger_key, 0)
            - recipient_token_amount.token_amount
        )
        self.data.total_supply[recipient_token_amount.token_id] = sp.as_nat(
            self.data.total_supply[recipient_token_amount.token_id]
            - recipient_token_amount.token_amount
        )
        with sp.if_(self.data.ledger.get(owner_ledger_key, sp.nat(0)) == sp.nat(0)):
            del self.data.ledger[owner_ledger_key]
