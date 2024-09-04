import smartpy as sp

from utils.administrable_mixin import SingleAdministrableMixin
from utils.contract_utils import Utils, Ratio
from utils.internal_mixin import InternalMixin
from contracts.tracker.types import TokenVariant
from utils.fa2 import (
    OperatorKey,
    BalanceOf,
    FA2ErrorMessage,
    UpdateOperator,
    Transfer,
    TokenMetadata,
)

NULL_ADDRESS = sp.address("tz1Ke2h7sDdakHJQh8WX4Z372du1KChsksyU")

class InvariantParams:
    def get_type():
        return sp.TRecord(
            x=sp.TNat,
            y=sp.TNat,
            z=sp.TNat
        ).layout(("x", ("y", "z")))

    def get_swap_type():
        return sp.TRecord(
            x=sp.TNat,
            y=sp.TNat,
            z=sp.TNat,
            dx = sp.TNat
        ).layout(("x", ("y", ("z", "dx"))))

class TokenData:
    def get_type():
        return sp.TRecord(
            funds = sp.TNat,
            multiplier = sp.TNat,
        ).layout(("funds", "multiplier"))
    
    def make(funds, multiplier):
        return sp.set_type_expr(
            sp.record(funds=funds, multiplier=multiplier),
            TokenData.get_type()
        )

class Liquidity:
    def get_add_liquidity_type():
        return sp.TRecord(
            owner = sp.TAddress,
            min_lqt_minted = sp.TNat,
            src_token = TokenVariant.get_type(),
            src_token_amount=sp.TNat,
            other_tokens_max_deposited = sp.TMap(TokenVariant.get_type(), sp.TNat),
            deadline=sp.TTimestamp
        ).layout(("owner", ("min_lqt_minted", ("src_token", ("src_token_amount", ("other_tokens_max_deposited", "deadline"))))))

    def get_remove_liquidity_type():
        return sp.TRecord(
            receiver = sp.TAddress,
            lqt_burned = sp.TNat,
            min_tokens_withdrawn = sp.TMap(TokenVariant.get_type(), sp.TNat),
            deadline = sp.TTimestamp,
        ).layout(("receiver", ("lqt_burned", ("min_tokens_withdrawn", "deadline"))))
    
    def get_mint_or_burn_type():
        return sp.TRecord(
            quantity = sp.TInt,
            target = sp.TAddress
        ).layout(("quantity", "target"))

class Swap:
    def get_type():
        return sp.TRecord(
            src_token=TokenVariant.get_type(),
            dst_token=TokenVariant.get_type(),
            amount_sold = sp.TNat,
            min_amount_bought = sp.TNat,
            receiver = sp.TAddress,
            deadline = sp.TTimestamp,
        ).layout(("src_token", ("dst_token", ("amount_sold", ("min_amount_bought", ("receiver", "deadline"))))))
    
    def get_tokens_bought_type():
        return sp.TRecord(
            src_token=TokenVariant.get_type(),
            dst_token=TokenVariant.get_type(),
            amount_sold = sp.TNat,
        ).layout(("src_token", ("dst_token", "amount_sold")))

    def make_tokens_bought(src_token, dst_token, amount_sold):
        return sp.set_type_expr(
            sp.record(src_token=src_token, dst_token=dst_token, amount_sold=amount_sold),
            Swap.get_tokens_bought_type()
        )

class TransferType:
    def get_type():
        return sp.TRecord(
            token=TokenVariant.get_type(),
            sender=sp.TAddress,
            receiver=sp.TAddress,
            amount=sp.TNat,
        ).layout(("token", ("sender", ("receiver", "amount"))))

    def make(token, sender, receiver, amount):
        return sp.set_type_expr(
            sp.record(token=token, sender=sender, receiver=receiver, amount=amount),
            TransferType.get_type(),
        )

class MultitokenCurveSwap(sp.Contract, SingleAdministrableMixin, InternalMixin):
    def __init__(
        self,
        administrators=sp.big_map(l={}, tkey=sp.TAddress, tvalue=sp.TNat),
        tokens=sp.map(l={}, tkey=TokenVariant.get_type(), tvalue=TokenData.get_type()),
        lqt_address=NULL_ADDRESS,
        lqt_total=sp.nat(0),
        target_oracle=NULL_ADDRESS,
        swap_fee=Ratio.make(1, 1000), # 0.1%
        rewards_receiver=NULL_ADDRESS,
        rewards_ratio=Ratio.make(50, 100), # 50%
        baking_rewards_receiver=NULL_ADDRESS,
        amplitude=sp.nat(100),
        enabled=sp.bool(False)
    ):
        self.init_type(
            sp.TRecord(
                administrators=sp.TBigMap(sp.TAddress, sp.TNat),
                tokens=sp.TMap(TokenVariant.get_type(), TokenData.get_type()),
                lqt_address=sp.TAddress,
                lqt_total=sp.TNat,
                target_oracle=sp.TAddress,
                swap_fee=Ratio.get_type(),
                rewards_receiver=sp.TAddress,
                rewards_ratio=Ratio.get_type(),
                baking_rewards_receiver=sp.TAddress,
                amplitude=sp.TNat,
                enabled=sp.TBool
            )
        )

        self.init(
            administrators=administrators,
            tokens=tokens,
            lqt_address=lqt_address,
            lqt_total=lqt_total,
            target_oracle=target_oracle,
            swap_fee=swap_fee,
            rewards_receiver=rewards_receiver,
            rewards_ratio=rewards_ratio,
            baking_rewards_receiver=baking_rewards_receiver,
            amplitude=amplitude,
            enabled=enabled,
        )

    @sp.private_lambda(with_storage="read-write", with_operations=True, wrap_call=True)
    def execute_token_transfer(self, param):
        """
        Lambda used for transferring tokens. For FA1 and FA2 tokens the transfer is standard.
        For transfers of tez:
        - in case of receiving tez, a check is done for the amount set and the actual amount of tez
          received.
        - in case of sending tez, a normal tez transfer operation is created.

        Params:
            - param (TransferType) - the details to execute a transfer: sender, receiver, amount
              and token_contract.
        Returns:
            An operation to execute the token transfer.
        """
        sp.set_type(param, TransferType.get_type())
        with param.token.match_cases() as variant:
            with variant.match("fa2") as fa2:
                Utils.execute_fa2_token_transfer(
                    fa2.contract,
                    param.sender,
                    param.receiver,
                    fa2.token_id,
                    param.amount,
                )
            with variant.match("fa1") as fa1:
                Utils.execute_fa1_token_transfer(
                    fa1, param.sender, param.receiver, param.amount
                )
            with variant.match("tez") as tez:
                with sp.if_(param.sender == sp.self_address):
                    with sp.if_(param.amount > 0):
                        sp.send(param.receiver, sp.utils.nat_to_mutez(param.amount))

    @sp.private_lambda(with_storage="read-write", with_operations=True, wrap_call=True)
    def mint_or_burn_liquidity(self, param):
        sp.set_type(param, Liquidity.get_mint_or_burn_type())
        mint_or_burn_ep = sp.contract(
            Liquidity.get_mint_or_burn_type(),
            self.data.lqt_address,
            entry_point = "mintOrBurn"
        ).open_some(message="InvalidEntrypoint: mintOrBurn")
        sp.transfer(param, sp.mutez(0), mint_or_burn_ep)

    @sp.entry_point
    def default(self, unit):
        sp.set_type(unit, sp.TUnit)
        with sp.if_(self.data.baking_rewards_receiver != sp.self_address):
            sp.send(self.data.baking_rewards_receiver, sp.amount)

    @sp.entry_point
    def add_liquidity(self, param):
        sp.set_type(param, Liquidity.get_add_liquidity_type())

        tokens_deposited = sp.local("tokens_deposited", param.other_tokens_max_deposited)
        tokens_deposited.value[param.src_token] = param.src_token_amount

        sp.verify(self.data.enabled == sp.bool(True), message="PoolDisabled")
        sp.verify(param.deadline >= sp.now, message="DeadlinePassed")
        sp.verify(sp.len(tokens_deposited.value) == sp.len(self.data.tokens), message="InvalidNumberOfTokens")
        
        # Check that the tez amount corresponds with the sent amount.
        tez = sp.variant("tez", sp.unit)
        with sp.if_(tokens_deposited.value.contains(tez)):
            sp.verify(tokens_deposited.value[tez] == sp.utils.mutez_to_nat(sp.amount), message="InvalidTezAmountSent")
        with sp.else_():
            sp.verify(sp.amount == sp.mutez(0), message="InvalidTezAmountSent")

        # update the balance of tez
        balance = sp.local("balance", sp.utils.mutez_to_nat(sp.balance))
        amount = sp.local("amount", sp.utils.mutez_to_nat(sp.amount))
        funds = sp.local("funds", sp.as_nat(balance.value - amount.value))
        with sp.if_(self.data.tokens.contains(tez)):
            self.data.tokens[tez] = TokenData.make(funds=funds.value, multiplier=self.data.tokens[tez].multiplier)
            sp.verify(param.src_token == tez, message="TezMustBeTheSourceToken")

        sp.transfer(
            sp.unit,
            sp.mutez(0),
            sp.self_entry_point("request_own_balances")
        )
        sp.transfer(
            sp.record(param=param, sender=sp.sender),
            sp.mutez(0),
            sp.self_entry_point("add_liquidity_internal"))

    @sp.entry_point(check_no_incoming_transfer=True)
    def add_liquidity_internal(self, param, sender):
        sp.set_type(param, Liquidity.get_add_liquidity_type())
        sp.set_type(sender, sp.TAddress)

        self.verify_internal(sp.unit)
        sp.verify(self.data.tokens.contains(param.src_token), message="UnknownToken")
        src_funds = sp.local("src_funds", self.data.tokens[param.src_token].funds)

        tokens_deposited = sp.local("tokens_deposited", param.other_tokens_max_deposited)
        tokens_deposited.value[param.src_token] = param.src_token_amount

        with sp.for_("item", tokens_deposited.value.items()) as item:
            sp.verify(self.data.tokens.contains(item.key), message="UnknownToken")

            deposited_amount = sp.local(
                "deposited_amount",
                (param.src_token_amount * self.data.tokens[item.key].funds) // src_funds.value)
            sp.verify(deposited_amount.value <= item.value, message="CannotDepositMoreThanSetValue")

            self.data.tokens[item.key] = TokenData.make(
                self.data.tokens[item.key].funds + deposited_amount.value,
                self.data.tokens[item.key].multiplier
            )
            transfer = TransferType.make(
                token=item.key,
                sender=sender,
                receiver=sp.self_address,
                amount = deposited_amount.value
            )
            self.execute_token_transfer(transfer)

        lqt_minted = sp.local(
            "lqt_minted",
            param.src_token_amount * self.data.lqt_total // src_funds.value
        )
        sp.verify(lqt_minted.value >= param.min_lqt_minted, message="CannotMintEnoughLiquidity")
        self.data.lqt_total = self.data.lqt_total + lqt_minted.value
        self.mint_or_burn_liquidity(
            sp.record(
                quantity=sp.to_int(lqt_minted.value),
                target = param.owner 
            ))

    @sp.entry_point(check_no_incoming_transfer=True)
    def remove_liquidity(self, param):
        sp.set_type(param, Liquidity.get_remove_liquidity_type())

        sp.verify(self.data.enabled == sp.bool(True), message="PoolDisabled")
        sp.verify(param.deadline >= sp.now, message="DeadlinePassed")
        sp.verify(sp.len(param.min_tokens_withdrawn) == sp.len(self.data.tokens), message="InvalidNumberOfTokens")

        # update the balance of tez
        funds = sp.local("balance", sp.utils.mutez_to_nat(sp.balance))
        tez = sp.variant("tez", sp.unit)
        with sp.if_(self.data.tokens.contains(tez)):
            self.data.tokens[tez] = TokenData.make(funds=funds.value, multiplier=self.data.tokens[tez].multiplier)

        sp.transfer(
            sp.unit,
            sp.mutez(0),
            sp.self_entry_point("request_own_balances")
        )
        sp.transfer(
            sp.record(param=param, sender=sp.sender),
            sp.mutez(0),
            sp.self_entry_point("remove_liquidity_internal"))

    @sp.entry_point(check_no_incoming_transfer=True)
    def remove_liquidity_internal(self, param, sender):
        sp.set_type(param, Liquidity.get_remove_liquidity_type())
        sp.set_type(sender, sp.TAddress)

        self.verify_internal(sp.unit)

        with sp.for_("item", param.min_tokens_withdrawn.items()) as item:
            sp.verify(self.data.tokens.contains(item.key), message="UnknownToken")

            withdrawn_amount = sp.local(
                "withdrawn_amount",
                (param.lqt_burned * self.data.tokens[item.key].funds) // self.data.lqt_total)
            sp.verify(withdrawn_amount.value >= item.value, message="CannotWithdrawLessThanSetValue")

            # Update token data an make the transfer
            self.data.tokens[item.key] = TokenData.make(
                sp.as_nat(self.data.tokens[item.key].funds - withdrawn_amount.value, message="TooManyTokensWithdrawn"),
                self.data.tokens[item.key].multiplier
            )
            transfer = TransferType.make(
                token=item.key,
                sender=sp.self_address,
                receiver=param.receiver,
                amount = withdrawn_amount.value
            )
            self.execute_token_transfer(transfer)
        # Update the liquidity and make the burn
        self.data.lqt_total = sp.as_nat(self.data.lqt_total - param.lqt_burned, message="TooMuchLqtBurned")
        self.mint_or_burn_liquidity(
            sp.record(
                quantity=(0-param.lqt_burned),
                target = sender
            ))

    @sp.entry_point
    def token_swap(self, param):
        sp.set_type(param, Swap.get_type())

        sp.verify(self.data.enabled == sp.bool(True), message="PoolDisabled")
        sp.verify(param.deadline >= sp.now, message="DeadlinePassed")
        sp.verify(self.data.tokens.contains(param.src_token), message="UnknownSrcToken")
        sp.verify(self.data.tokens.contains(param.dst_token), message="UnknownDstToken")

        tez = sp.variant("tez", sp.unit)
        with sp.if_(param.src_token == tez):
            sp.verify(param.amount_sold == sp.utils.mutez_to_nat(sp.amount), message="InvalidTezAmountSent")
        with sp.else_():
            sp.verify(sp.mutez(0) == sp.amount, message="InvalidTezAmountSent")

        # update the balance of tez
        balance = sp.local("balance", sp.utils.mutez_to_nat(sp.balance))
        amount = sp.local("amount", sp.utils.mutez_to_nat(sp.amount))
        funds = sp.local("funds", sp.as_nat(balance.value - amount.value))
        with sp.if_(self.data.tokens.contains(tez)):
            self.data.tokens[tez] = TokenData.make(funds=funds.value, multiplier=self.data.tokens[tez].multiplier)

        sp.transfer(
            sp.unit,
            sp.mutez(0),
            sp.self_entry_point("request_own_balances")
        )
        sp.transfer(
            sp.record(param=param, sender=sp.sender),
            sp.mutez(0),
            sp.self_entry_point("token_swap_internal"))

    @sp.entry_point
    def token_swap_internal(self, param, sender):
        sp.set_type(param, Swap.get_type())
        sp.set_type(sender, sp.TAddress)

        self.verify_internal(sp.unit)

        total_tokens_bought = sp.local(
            "total_tokens_bought",
            sp.view(
                "total_expected_out_amount",
                sp.self_address,
                Swap.make_tokens_bought(src_token=param.src_token, dst_token=param.dst_token, amount_sold=param.amount_sold),
                t=sp.TNat
            ).open_some(message="Invalid view: total_expected_out_amount"))
        total_fee = sp.local("total_fee", self.data.swap_fee.numerator * total_tokens_bought.value // self.data.swap_fee.denominator)
        tokens_bought = sp.local("tokens_bought", sp.as_nat(total_tokens_bought.value - total_fee.value))
        sp.verify(tokens_bought.value >= param.min_amount_bought, message="MinAmountBoughtGreaterThanTokensBought")

        rewards_receiver_fee = sp.local(
            "rewards_receiver_fee",
            self.data.rewards_ratio.numerator * total_fee.value // self.data.rewards_ratio.denominator)
        total_paid = sp.local("total_paid", tokens_bought.value + rewards_receiver_fee.value)
        
        self.data.tokens[param.src_token].funds += param.amount_sold
        self.data.tokens[param.dst_token].funds = sp.as_nat(self.data.tokens[param.dst_token].funds - total_paid.value, message="DstTokenWouldBeNegative")
        
        in_transfer = TransferType.make(
            token=param.src_token,
            sender=sender,
            receiver=sp.self_address,
            amount = param.amount_sold 
        )
        self.execute_token_transfer(in_transfer)

        out_transfer = TransferType.make(
            token=param.dst_token,
            sender=sp.self_address,
            receiver=param.receiver,
            amount = tokens_bought.value
        )
        self.execute_token_transfer(out_transfer)
        
        out_receiver_transfer = TransferType.make(
            token=param.dst_token,
            sender=sp.self_address,
            receiver=self.data.rewards_receiver,
            amount = rewards_receiver_fee.value
        )
        self.execute_token_transfer(out_receiver_transfer)

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_lqt_address(self, lqt_address):
        sp.set_type(lqt_address, sp.TAddress)
        self.verify_is_admin(sp.unit)
        sp.verify(self.data.lqt_address == NULL_ADDRESS, message="LiquidityAddressAlreadySet")

        self.data.lqt_address = lqt_address

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_rewards_ratio(self, ratio):
        sp.set_type(ratio, Ratio.get_type())
        self.verify_is_admin(sp.unit)
        
        sp.verify(ratio.numerator <= ratio.denominator, message="RatioShouldBeLessThanOne")
        sp.verify(ratio.denominator != sp.nat(0), message="DenominatorCannotBeZero")
        
        self.data.rewards_ratio = ratio

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_rewards_receiver(self, rewards_receiver):
        sp.set_type(rewards_receiver, sp.TAddress)
        self.verify_is_admin(sp.unit)
        
        self.data.rewards_receiver = rewards_receiver 

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_baking_rewards_receiver(self, baking_rewards_receiver):
        sp.set_type(baking_rewards_receiver, sp.TAddress)
        self.verify_is_admin(sp.unit)
        
        self.data.baking_rewards_receiver = baking_rewards_receiver 

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_amplitude(self, amplitude):
        sp.set_type(amplitude, sp.TNat)
        self.verify_is_admin(sp.unit)
        
        self.data.amplitude = amplitude 

    @sp.entry_point(check_no_incoming_transfer=True)
    def enable(self, enable):
        sp.set_type(enable, sp.TBool)
        self.verify_is_admin(sp.unit)
        
        self.data.enabled = enable 

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_swap_fee(self, fee):
        sp.set_type(fee, Ratio.get_type())
        self.verify_is_admin(sp.unit)
        
        sp.verify(fee.denominator != sp.nat(0), message="InvalidZeroDenominator")
        sp.verify(fee.numerator <= fee.denominator, message="InvalidSwapFee")
        
        self.data.swap_fee = fee 

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_target_oracle(self, target_oracle):
        sp.set_type(target_oracle, sp.TAddress)
        self.verify_is_admin(sp.unit)

        self.data.target_oracle = target_oracle

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_baker(self, baker):
        sp.set_type(baker, sp.TOption(sp.TKeyHash))
        self.verify_is_admin(sp.unit)

        sp.set_delegate(baker)

    ########################## Internal EPS #######################################
    @sp.entry_point(check_no_incoming_transfer=True)
    def set_fa2_balance(self, balance_of_response):
        sp.set_type(balance_of_response, BalanceOf.get_response_type())
        with sp.match_cons(balance_of_response) as balances:
            sp.verify(
                balances.head.request.owner == sp.self_address,
                message="InvalidBalanceOfResponse"
            )
            token = sp.variant("fa2", sp.record(contract=sp.sender, token_id=balances.head.request.token_id))
            sp.verify(self.data.tokens.contains(token), message="UnknownFA2Token")
            self.data.tokens[token] = TokenData.make(balances.head.balance, self.data.tokens[token].multiplier)

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_fa1_balance(self, balance):
        sp.set_type(balance, sp.TNat)
        token = sp.variant("fa1", sp.sender)
        sp.verify(self.data.tokens.contains(token), message="UnknownFA1Token")

        self.data.tokens[token] = TokenData.make(balance, self.data.tokens[token].multiplier)

    @sp.entry_point(check_no_incoming_transfer=True)
    def request_own_balances(self, unit):
        sp.set_type(unit, sp.TUnit);
        sp.verify((sp.sender == sp.self_address) | (sp.sender == sp.source), message="SenderNotAllowed")
        
        with sp.for_("token", self.data.tokens.keys()) as token:
            with token.match_cases() as arg:
                    with arg.match("fa2") as fa2:
                        Utils.execute_get_own_fa2_balance(
                            token_address=fa2.contract,
                            token_id=fa2.token_id,
                            setter_entrypoint_name="set_fa2_balance"
                        )
                    with arg.match("fa1") as fa1:
                        Utils.execute_get_own_fa1_balance(
                            token_address=fa1,
                            setter_entrypoint_name="set_fa1_balance"
                        )
                    with arg.match("tez") as tez:
                        sp.verify(self.data.tokens.contains(sp.variant("tez", sp.unit)), message="InvalidTezToken")

    ##################################################################################### 
    @sp.onchain_view()
    def get_invariant(self, unit):
        sp.set_type(unit, sp.TUnit)
        rounds = sp.local("rounds", sp.nat(0))
        token_sum = sp.local("token_sum", sp.nat(0))
        token_prod = sp.local("token_prod", sp.nat(1))
        n = sp.local("n", sp.len(self.data.tokens))
        nn = sp.local("nn", sp.nat(1))

        with sp.for_("item", self.data.tokens.items()) as item:
            price = sp.local("price", sp.view(
                "get_token_price",
                self.data.target_oracle,
                item.key,
                t=Ratio.get_type()
            ).open_some(message="InvalidView: get_token_price"))
            normalized_funds = sp.local(
                "normalized_funds",
                (item.value.funds * item.value.multiplier * price.value.numerator) // price.value.denominator
            )
            token_sum.value = token_sum.value + normalized_funds.value
            token_prod.value = token_prod.value * normalized_funds.value 
            nn.value = nn.value * n.value
        Ann = sp.local("Ann", self.data.amplitude * nn.value)

        D = sp.local("D", token_sum.value+2)
        newD = sp.local("newD", token_sum.value)

        with sp.while_(abs(newD.value - D.value) > 1):
            D.value = newD.value
            
            tmp = sp.local("tmp", D.value * D.value * D.value * D.value // (nn.value * token_prod.value))
            tmp2 = sp.local("tmp2", sp.as_nat(Ann.value * token_sum.value - tmp.value))
            newD.value = tmp2.value // sp.as_nat(Ann.value - 1)
            rounds.value += 1
            with sp.if_(rounds.value == sp.nat(200)):
                D.value = newD.value

        sp.verify(rounds.value < 200, message="InvariantDoesNotConverge")
        sp.result(newD.value)

    @sp.onchain_view()
    def total_expected_out_amount(self, param):
        sp.set_type(param, Swap.get_tokens_bought_type())

        ####################### Start calculating tokens bought ######
        invariant = sp.local(
            "invariant",
            sp.view(
                "get_invariant",
                sp.self_address,
                sp.unit,
                t=sp.TNat
            ).open_some(message="Invalid view: get_invariant"))
        token_sum = sp.local("token_sum", sp.nat(0))
        token_prod = sp.local("token_prod", sp.nat(1))
        n = sp.local("n", sp.len(self.data.tokens))
        nn = sp.local("nn", sp.nat(1))

        tokens = sp.local("tokens", self.data.tokens)
        tokens.value[param.src_token].funds += param.amount_sold
        old_y = sp.local("old_y", sp.nat(0))

        with sp.for_("item", tokens.value.items()) as item:
            nn.value *= n.value
            with sp.if_(item.key != param.dst_token):
                price = sp.local("price", sp.view(
                    "get_token_price",
                    self.data.target_oracle,
                    item.key,
                    t=Ratio.get_type()
                ).open_some(message="InvalidView: get_token_price"))

                normalized_funds = sp.local(
                    "normalized_funds",
                    (item.value.funds * item.value.multiplier * price.value.numerator) // price.value.denominator
                )
                token_sum.value = token_sum.value + normalized_funds.value
                token_prod.value = token_prod.value * normalized_funds.value 
            with sp.else_():
                price = sp.local("price", sp.view(
                    "get_token_price",
                    self.data.target_oracle,
                    item.key,
                    t=Ratio.get_type()
                ).open_some(message="InvalidView: get_token_price"))
                old_y.value = (item.value.funds * item.value.multiplier * price.value.numerator) // price.value.denominator

        Ann = sp.local("Ann", self.data.amplitude * nn.value)

        b = sp.local("b", token_sum.value + invariant.value // Ann.value)
        c = sp.local("c", invariant.value * invariant.value * invariant.value * invariant.value // (token_prod.value * Ann.value * nn.value))

        y = sp.local("y", invariant.value) 
        yprev = sp.local("yprev", invariant.value+2)
        rounds = sp.local("rounds", sp.nat(0))

        with sp.while_(abs(yprev.value - y.value) > 1):
            yprev.value = y.value
            y.value = (y.value * y.value + c.value) // sp.as_nat(2 * y.value + b.value - invariant.value)
            rounds.value += 1
            with sp.if_(rounds.value == sp.nat(200)):
                yprev.value = y.value

        sp.verify(rounds.value < 200, message="dyDoesNotConverge")

        dy = sp.local("dy", sp.as_nat(old_y.value - y.value - 1))
        price = sp.local("price", sp.view(
            "get_token_price",
            self.data.target_oracle,
            param.dst_token,
            t=Ratio.get_type()
        ).open_some(message="InvalidView: get_token_price"))
        tokens_bought = sp.local("tokens_bought", dy.value * price.value.denominator // (tokens.value[param.dst_token].multiplier * price.value.numerator))
        sp.result(tokens_bought.value)

    @sp.onchain_view()
    def get_token_funds(self, token):
        sp.set_type(token, TokenVariant.get_type())
        sp.verify(self.data.tokens.contains(token), message="UnknownToken")
        sp.result(self.data.tokens[token].funds)

    @sp.onchain_view()
    def get_token_funds_in_usd(self, token):
        sp.set_type(token, TokenVariant.get_type())
        sp.verify(self.data.tokens.contains(token), message="UnknownToken")

        price = sp.local("price", sp.view(
            "get_token_price",
            self.data.target_oracle,
            token,
            t=Ratio.get_type()
        ).open_some(message="InvalidView: get_token_price"))

        sp.result(Ratio.make(self.data.tokens[token].funds * price.value.numerator, price.value.denominator))
    
    @sp.onchain_view()
    def get_liquidity_funds(self, unit):
        sp.set_type(unit, sp.TUnit)
        sp.result(self.data.lqt_total)

    @sp.onchain_view()
    def get_liquidity_usd_price(self, unit):
        sp.set_type(unit, sp.TUnit)

        lqt_value_in_usd = sp.local("lqt_value_in_usd", sp.nat(0))
        with sp.for_("item", self.data.tokens.items()) as item:
            price = sp.local("price", sp.view(
                "get_token_price",
                self.data.target_oracle,
                item.key,
                t=Ratio.get_type()
            ).open_some(message="InvalidView: get_token_price"))
            normalized_funds = sp.local(
                "normalized_funds",
                (item.value.funds * item.value.multiplier * price.value.numerator) // (price.value.denominator * sp.nat(100))
            )
            lqt_value_in_usd.value += normalized_funds.value
        
        sp.result(Ratio.make(lqt_value_in_usd.value, self.data.lqt_total))

    @sp.onchain_view()
    def get_invariant_debug(self, param):
        sp.set_type(param, sp.TMap(TokenVariant.get_type(), sp.TNat))

        rounds = sp.local("rounds", sp.nat(0))

        token_sum = sp.local("token_sum", sp.nat(0))
        token_prod = sp.local("token_prod", sp.nat(1))
        n = sp.local("n", sp.len(param))
        nn = sp.local("nn", sp.nat(1))

        with sp.for_("funds", param.values()) as funds:
            token_sum.value = token_sum.value + funds
            token_prod.value = token_prod.value * funds
            nn.value = nn.value * n.value

        Ann = sp.local("Ann", self.data.amplitude * nn.value)

        D = sp.local("D", token_sum.value+2)
        newD = sp.local("newD", token_sum.value)

        with sp.while_(abs(newD.value - D.value) > 1):
            D.value = newD.value
            
            tmp = sp.local("tmp", D.value * D.value * D.value * D.value // (nn.value * token_prod.value))
            tmp2 = sp.local("tmp2", sp.as_nat(Ann.value * token_sum.value - tmp.value))
            newD.value = tmp2.value // sp.as_nat(Ann.value - 1)
            rounds.value += 1
            with sp.if_(rounds.value == sp.nat(200)):
                D.value = newD.value

        sp.verify(rounds.value < 200, message="InvariantDoesNotConverge")
        sp.result(newD.value)

    @sp.onchain_view()
    def tokens_bought_debug(self, param):
        sp.set_type(param,
            sp.TRecord(
                funds=sp.TMap(TokenVariant.get_type(), sp.TNat),
                src_token=TokenVariant.get_type(),
                dst_token=TokenVariant.get_type(),
                sold_amount=sp.TNat,
            ))

        ####################### Start calculating tokens bought ######
        invariant = sp.local(
            "invariant",
            sp.view(
                "get_invariant_view_complex",
                sp.self_address,
                param.funds,
                t=sp.TNat
            ).open_some(message="Invalid view"))
        token_sum = sp.local("token_sum", sp.nat(0))
        token_prod = sp.local("token_prod", sp.nat(1))
        n = sp.local("n", sp.len(param.funds))
        nn = sp.local("nn", sp.nat(1))

        param.funds[param.src_token] = param.funds[param.src_token] + param.sold_amount
        with sp.for_("item", param.funds.items()) as item:
            nn.value *= n.value
            with sp.if_(item.key != param.dst_token):
                token_sum.value += item.value
                token_prod.value *= item.value
        Ann = sp.local("Ann", self.data.amplitude * nn.value)

        b = sp.local("b", token_sum.value + invariant.value // Ann.value)
        c = sp.local("c", invariant.value * invariant.value * invariant.value * invariant.value // (token_prod.value * Ann.value * nn.value))

        y = sp.local("y", invariant.value) 
        yprev = sp.local("yprev", invariant.value+2)
        rounds = sp.local("rounds", sp.nat(0))

        with sp.while_(abs(yprev.value - y.value) > 1):
            yprev.value = y.value
            y.value = (y.value * y.value + c.value) // sp.as_nat(2 * y.value + b.value - invariant.value)
            rounds.value += 1
            with sp.if_(rounds.value == sp.nat(200)):
                yprev.value = y.value

        sp.verify(rounds.value < 200, message="dyDoesNotConverge")

        dy = sp.local("dy", sp.as_nat(param.funds[param.dst_token] - y.value - 1))
        sp.result(dy.value)