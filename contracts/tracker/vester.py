import smartpy as sp

from utils.contract_utils import Utils


class VestingOperation:
    def get_type():
        return sp.TRecord(
            address=sp.TAddress, token_amount=sp.TNat, deadline=sp.TTimestamp
        ).layout(("address", ("token_amount", "deadline")))

    def get_batch_type():
        return sp.TList(VestingOperation.get_type())

    def make(address, token_amount, deadline):
        return sp.set_type_expr(
            sp.record(address=address, token_amount=token_amount, deadline=deadline),
            VestingOperation.get_type(),
        )


class Ledger:
    def get_key_type():
        return sp.TRecord(
            owner=sp.TAddress,
            locker=sp.TAddress,
        ).layout(("owner", "locker"))

    def get_value_type():
        return sp.TRecord(token_amount=sp.TNat, deadline=sp.TTimestamp).layout(
            ("token_amount", "deadline")
        )

    def make_key(owner, locker):
        return sp.set_type_expr(
            sp.record(owner=owner, locker=locker), Ledger.get_key_type()
        )

    def make_value(token_amount, deadline):
        return sp.set_type_expr(
            sp.record(token_amount=token_amount, deadline=deadline),
            Ledger.get_value_type(),
        )


class DivestingOperation:
    def get_type():
        return sp.TRecord(locker=sp.TAddress, recipient=sp.TAddress).layout(
            ("locker", "recipient")
        )

    def get_batch_type():
        return sp.TList(DivestingOperation.get_type())

    def make(locker, recipient):
        return sp.set_type_expr(
            sp.record(locker=locker, recipient=recipient), DivestingOperation.get_type()
        )


class Vester(sp.Contract):
    def get_init_storage(self):
        """Returns the initial storage of the contract used for inheritance of smartpy contracts

        Returns:
            dict: initial storage of the contract
        """
        storage = {}
        storage["ledger"] = sp.big_map(
            tkey=Ledger.get_key_type(), tvalue=Ledger.get_value_type()
        )
        storage["token_address"] = self.token_address
        storage["token_id"] = self.token_id

        return storage

    def __init__(self, token_address, token_id):
        """ """
        self.token_address = token_address
        self.token_id = token_id
        self.init(**self.get_init_storage())

    @sp.entry_point(check_no_incoming_transfer=True)
    def vest(self, params):
        sp.set_type(params, VestingOperation.get_batch_type())
        with sp.for_("vesting_operation", params) as vesting_operation:
            ledger_key = Ledger.make_key(vesting_operation.address, sp.sender)
            with sp.if_(self.data.ledger.contains(ledger_key)):
                self.data.ledger[ledger_key] = Ledger.make_value(
                    self.data.ledger[ledger_key].token_amount
                    + vesting_operation.token_amount,
                    vesting_operation.deadline,
                )
            with sp.else_():
                self.data.ledger[ledger_key] = Ledger.make_value(
                    vesting_operation.token_amount, vesting_operation.deadline
                )
            Utils.execute_fa2_token_transfer(
                self.data.token_address,
                sp.sender,
                sp.self_address,
                self.data.token_id,
                vesting_operation.token_amount,
            )

    @sp.entry_point(check_no_incoming_transfer=True)
    def divest(self, params):
        sp.set_type(params, DivestingOperation.get_batch_type())
        with sp.for_("divesting_operation", params) as divesting_operation:
            ledger_key = Ledger.make_key(sp.sender, divesting_operation.locker)
            sp.verify(self.data.ledger.contains(ledger_key))
            sp.verify(self.data.ledger[ledger_key].deadline <= sp.now)

            Utils.execute_fa2_token_transfer(
                self.data.token_address,
                sp.self_address,
                divesting_operation.recipient,
                self.data.token_id,
                self.data.ledger[ledger_key].token_amount,
            )
            del self.data.ledger[ledger_key]
