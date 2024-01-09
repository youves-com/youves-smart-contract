import smartpy as sp

import utils.error_codes as Errors
import utils.constants as Constants

from utils.administrable_mixin import SingleAdministrableMixin
from utils.contract_utils import Utils, Ratio
from utils.fa2 import OperatorKey, BalanceOf, FA2ErrorMessage, UpdateOperator, Transfer, TokenMetadata
from utils.internal_mixin import InternalMixin
from contracts.common.types import make_voting_stake

SECONDS_PER_DAY = 24 * 60 * 60
EPOCH_IN_SECONDS = 4 * 7 * SECONDS_PER_DAY
MAX_COOLDOWN_DURATION = 32 * EPOCH_IN_SECONDS # this is 896 days, just like Polkadot's conviction.
MIN_STAKE_AMOUNT = 100_000_000_000 # 0.1 YOUs
DEFAULT_TOKEN_INFO = {"": sp.bytes("0x00")} 

class Stake:
    def get_type():
        return sp.TRecord(
            amount=sp.TNat,
            reward_weight=sp.TNat,
            bailout_weight=sp.TNat,
            accumulated_rewards=sp.TNat,
            accumulated_bailouts=sp.TNat,
            cooldown_duration=sp.TNat,
            cooldown_start_timestamp=sp.TOption(sp.TTimestamp),
            reward_factor=sp.TNat,
            bailout_factor=sp.TNat,
        ).layout(
            (
                "amount",
                (
                    "reward_weight",
                    (
                        "bailout_weight",
                        (
                            "accumulated_rewards",
                            (
                                "accumulated_bailouts",
                                (
                                    "cooldown_duration",
                                    (
                                        "cooldown_start_timestamp",
                                        ("reward_factor", "bailout_factor"),
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
            )
        )

    def make(
        amount,
        reward_weight,
        bailout_weight,
        accumulated_rewards,
        accumulated_bailouts,
        cooldown_duration,
        cooldown_start_timestamp,
        reward_factor,
        bailout_factor,
    ):
        return sp.set_type_expr(
            sp.record(
                amount=amount,
                reward_weight=reward_weight,
                bailout_weight=bailout_weight,
                accumulated_rewards=accumulated_rewards,
                accumulated_bailouts=accumulated_bailouts,
                cooldown_duration=cooldown_duration,
                cooldown_start_timestamp=cooldown_start_timestamp,
                reward_factor=reward_factor,
                bailout_factor=bailout_factor,
            ),
            Stake.get_type(),
        )

    def make_empty():
        return sp.set_type_expr(
            sp.record(
                amount=0,
                reward_weight=0,
                bailout_weight=0,
                accumulated_rewards=0,
                accumulated_bailouts=0,
                cooldown_duration=0,
                cooldown_start_timestamp=sp.none,
                reward_factor=0,
                bailout_factor=0,
            ),
            Stake.get_type(),
        )


class CommitmentPool(sp.Contract, InternalMixin, SingleAdministrableMixin):
    """The commitment pool allows a user to stake their tokens and then get YOU rewards. The
    rewards are coming from fees of the other parts of the platform (farms, mint, etc.).

    Args:
        (sp.Contract): this is a smartpy contract
        (InternalMixin): mixin used whenever we need external data and hence have to trigger an
            internal call (to process after we received said external data)
        (SingleAdministrableMixin): mixin used whenever we have a single administrator.
    """

    def __init__(
        self,
        administrators=sp.big_map(l={}, tkey=sp.TAddress, tvalue=sp.TNat),
        max_cooldown_duration=sp.nat(MAX_COOLDOWN_DURATION),
        epoch_length=sp.nat(EPOCH_IN_SECONDS),
        max_withdraw_delay=sp.nat(2 * 24 * 60 * 60),  # 2 days
        kicker_reward_ratio=Ratio.make(10, 100),  # 10%
        token_address=Constants.DEFAULT_ADDRESS,
        allowed_sources=sp.big_map(l={}, tkey=sp.TAddress, tvalue=sp.TUnit),
        token_id=sp.nat(0),
    ):
        """
        Constructor of the commitment contract.

        Parameters
        ----------
        administrators: sp.TBigMap(sp.TAddress, sp.TNat)
            A big map with the administrators of the contract.
        max_cooldown_duration: sp.TNat
            Maximum duration allowed for a stake cooldown (in seconds). Any duration longer than
            this is considered invalid and rejected by the contract. This parameter needs special
            attention as it cannot be changed later after deployment.
        max_withdraw_delay: sp.TNat
            A buffer period (in seconds) for a user to withdraw their stake before getting kicked
            out by other users. After a user's cooldown period has passed they can still stay in
            the pool and collect rewards/pay bailouts, but after the max_withdraw_delay passed,
            they can be kicked out by other users.
        kicker_reward_ratio: sp.TRecord(numerator=sp.TNat, denominator=sp.TNat)
            The percentage of the accumulated rewards of an user receive by the kicker when they
            kickout from the pool a user that overstays in the pool.
        token_address: sp.TAddress
            The contract address of the staked token.
        token_id: sp.TNat
            The token id of the staked token.
        """
        metadata = sp.big_map(
            l={
                "": sp.bytes("0x74657a6f732d73746f726167653a64617461"),  # "tezos-storage:data"
                "data": sp.utils.bytes_of_string(
                    """
                    { 
                        "name": "Youves Commitment Pool", 
                        "authors": ["Youves <contact@youves.com>"], 
                        "homepage":  "https://app.youves.com"
                    }
                """
                ),
            },
            tkey=sp.TString,
            tvalue=sp.TBytes,
        )
        token_metadata = sp.big_map(l={}, tkey=sp.TNat, tvalue=TokenMetadata.get_type())
        voting_scale_map=sp.map(
            l={
                0  : Ratio.make(0, 10000),     # 0%
                1  : Ratio.make(0, 10000),     # 0%
                2  : Ratio.make(2000, 10000),  # 20%
                3  : Ratio.make(3170, 10000),  # 31.7%
                4  : Ratio.make(4000, 10000),  # 40%
                5  : Ratio.make(4643, 10000),  # 46.43%
                6  : Ratio.make(5170, 10000),  # 51.7%
                7  : Ratio.make(5615, 10000),  # 56.15%
                8  : Ratio.make(6000, 10000),  # 60%
                9  : Ratio.make(6340, 10000),  # 63.4%
                10 : Ratio.make(6644, 10000),  # 66.44%
                11 : Ratio.make(6919, 10000),  # 69.19%
                12 : Ratio.make(7170, 10000),  # 71.7%
                13 : Ratio.make(7401, 10000),  # 74.01%
                14 : Ratio.make(7615, 10000),  # 76.15%
                15 : Ratio.make(7814, 10000),  # 78.14%
                16 : Ratio.make(8000, 10000),  # 80%
                17 : Ratio.make(8175, 10000),  # 81.75%
                18 : Ratio.make(8340, 10000),  # 83.4%
                19 : Ratio.make(8496, 10000),  # 84.96%
                20 : Ratio.make(8644, 10000),  # 86.44%
                21 : Ratio.make(8785, 10000),  # 87.85%
                22 : Ratio.make(8919, 10000),  # 89.19%
                23 : Ratio.make(9047, 10000),  # 90.47%
                24 : Ratio.make(9170, 10000),  # 91.7%
                25 : Ratio.make(9288, 10000),  # 92.88%
                26 : Ratio.make(9401, 10000),  # 94.01%
                27 : Ratio.make(9510, 10000),  # 95.1%
                28 : Ratio.make(9615, 10000),  # 96.15%
                29 : Ratio.make(9716, 10000),  # 97.16%
                30 : Ratio.make(9814, 10000),  # 98.14%
                31 : Ratio.make(9908, 10000),  # 99.08%
                32 : Ratio.make(10000, 10000), # 100%
            }, 
            tkey=sp.TNat, 
            tvalue=Ratio.get_type()
        )
        self.init_type(
            sp.TRecord(
                administrators=sp.TBigMap(sp.TAddress, sp.TNat),
                allowed_sources=sp.TBigMap(sp.TAddress, sp.TUnit),
                ledger=sp.TBigMap(sp.TNat, sp.TAddress),
                operators=sp.TBigMap(OperatorKey.get_type(), sp.TUnit),
                stakes=sp.TBigMap(sp.TNat, Stake.get_type()),
                reward_factor=sp.TNat,
                bailout_factor=sp.TNat,
                total_reward_stake_weight=sp.TNat,
                total_bailout_stake_weight=sp.TNat,
                stake_id_counter=sp.TNat,
                max_cooldown_duration=sp.TNat,
                epoch_length=sp.TNat,
                max_withdraw_delay=sp.TNat,
                kicker_reward_ratio=Ratio.get_type(),
                token_address=sp.TAddress,
                token_id=sp.TNat,
                previous_token_balance=sp.TNat,
                current_token_balance=sp.TNat,
                voting_scale_map=sp.TMap(sp.TNat, Ratio.get_type()),
                metadata = sp.TBigMap(sp.TString, sp.TBytes),
                token_metadata = sp.TBigMap(sp.TNat, TokenMetadata.get_type())
            )
        )

        self.init(
            administrators=administrators,
            allowed_sources=allowed_sources,
            ledger=sp.big_map(l={}, tkey=sp.TNat, tvalue=sp.TAddress),
            operators=sp.big_map(l={}, tkey=OperatorKey.get_type(), tvalue=sp.TUnit),
            stakes=sp.big_map(l={}, tkey=sp.TNat, tvalue=Stake.get_type()),
            reward_factor=sp.nat(Constants.PRECISION_FACTOR),
            bailout_factor=sp.nat(Constants.PRECISION_FACTOR),
            total_reward_stake_weight=sp.nat(0),
            total_bailout_stake_weight=sp.nat(0),
            stake_id_counter=sp.nat(0),
            max_cooldown_duration=max_cooldown_duration,
            epoch_length=epoch_length,
            max_withdraw_delay=max_withdraw_delay,
            kicker_reward_ratio=kicker_reward_ratio,
            token_address=token_address,
            token_id=token_id,
            previous_token_balance=sp.nat(0),
            current_token_balance=sp.nat(0),
            voting_scale_map=voting_scale_map,
            metadata=metadata,
            token_metadata=token_metadata,
        )

    @sp.private_lambda(with_storage="read-write", with_operations=True, wrap_call=True)
    def fetch_token_balance(self, unit):
        """Fetches the token balance of the contract.
        Parameters
        ----------
        unit: sp.TUnit
            Unit parameter

        Raises
        ------
        InvalidEntrypoint
            If the token contract does not have a balance_of entrypoint that respects the FA2
            standard.
        """
        sp.set_type(unit, sp.TUnit)
        Utils.execute_get_own_balance(
            token_address=self.data.token_address,
            token_id=self.data.token_id,
            setter_entrypoint_name="set_token_balance",
        )

    @sp.private_lambda(with_storage="read-write", with_operations=False, wrap_call=True)
    def update_reward_factor(self, unit):
        """
        Updates the reward_factor with the accumulated rewards between calls.

        Parameters
        ----------
        unit: sp.TUnit
            Unit parameter

        Raises
        NegativeReward
            If the current_token_balance is lower than the previous_token_balance.
        """
        sp.set_type(unit, sp.TUnit)
        with sp.if_(self.data.total_reward_stake_weight > sp.nat(0)):
            reward = sp.as_nat(
                self.data.current_token_balance - self.data.previous_token_balance,
                message="NegativeReward",
            )
            self.data.reward_factor += (
                (reward * Constants.PRECISION_FACTOR) // self.data.total_reward_stake_weight
            )
            self.data.previous_token_balance = self.data.current_token_balance

    @sp.private_lambda(with_storage="read-write", with_operations=False, wrap_call=True)
    def update_bailout_factor(self, amount):
        """
        Updates the bailout_factor with the additional bailout amount.

        Parameters
        ----------
        amount: sp.TNat
            The amount paid by the bailout.
        """
        sp.set_type(amount, sp.TNat)
        with sp.if_(self.data.total_bailout_stake_weight > sp.nat(0)):
            self.data.bailout_factor += (
                (amount * Constants.PRECISION_FACTOR) // self.data.total_bailout_stake_weight
            )

    @sp.private_lambda(with_storage="read-only", with_operations=False, wrap_call=True)
    def verify_is_allowed_source(self, unit):
        """Lambda which verifies if a sender is in the set of allowed sources 
        """
        sp.verify(
            self.data.allowed_sources.contains(sp.sender),
            message="NotAllowedSource",
        )

    @sp.entry_point(check_no_incoming_transfer=True)
    def commit(self, param):
        """
        Either:
        * Creates a new stake by commiting the given amount for a specified cooldown period (no
        longer than max_cooldown_duration)
        * Updates an existing one by increasing the amount and/or the cooldown period. Decreases
        of the amount/cooldown period are not allowed.
        The main logic can be found in the associated internal entrypoint.

        Parameters
        ----------
        param: sp.TRecord(
            amount=sp.TNat,
            cooldown_duration=sp.TNat,
            stake_id=sp.TOption(sp.TNat),
        )
            The amount and cooldown duration to be commited for the stake. For an update commit,
            the given amount will be added on top of the existing one and cooldown duration will
            replace the old cooldown duration. If the stake_id is missing, a new stake is created.

        Raises
        ------
        InvalidStakeId
            If the stake id does not exist in the case of an update.
        NotOwner
            If the caller tries to update a stake that they do not own.
        InvalidCooldownDuration
            If the cooldown duration is larger than the max cooldown duration.
            If the cooldown duration is lower than previous cooldown duration in the case of
            an update.
        InvalidState
            If the stake to be updated has entered the cooldown period.
        InsufficientStakedAmount
            If the amount staked is lower than the minimum required (0.1 YOUs)
        """
        sp.set_type(
            param,
            sp.TRecord(
                amount=sp.TNat, 
                cooldown_duration=sp.TNat, 
                stake_id=sp.TOption(sp.TNat))
        )
        sp.verify(
            param.cooldown_duration <= self.data.max_cooldown_duration,
            message="InvalidCooldownDuration",
        )
        with sp.if_(param.stake_id.is_some()):
            stake_id = sp.local("stake_id", param.stake_id.open_some())
            sp.verify(self.data.stakes.contains(stake_id.value), message="InvalidStakeId")
            sp.verify(self.data.ledger[stake_id.value] == sp.sender, message="NotOwner")
            sp.verify(
                self.data.stakes[stake_id.value].cooldown_duration <= param.cooldown_duration,
                message="InvalidCooldownDuration",
            )
            sp.verify(
                self.data.stakes[stake_id.value].cooldown_start_timestamp == sp.none,
                message="InvalidState",
            )
        with sp.else_():
            sp.verify(param.amount >= MIN_STAKE_AMOUNT, message="InsufficientStakedAmount")

        self.fetch_token_balance(sp.unit)
        sp.transfer(
            sp.record(owner=sp.sender, param=param),
            sp.mutez(0),
            sp.self_entry_point("internal_commit"),
        )

    @sp.entry_point(check_no_incoming_transfer=True)
    def recommit(self, stake_id):
        """
        Allows for a stake that is in the cooldown period to be recommited.
        The main logic can be found in the associated internal entrypoint.

        Parameters
        ----------
        stake_id: sp.TNat
            The stake id to be recommited.

        Raises
        ------
        NotOwner
            If the caller is not the owner of the stake.
        InvalidStakeId
            If the selected stake does not exist.
        InvalidState
            If the selected stake is not in cooldown.
        """
        sp.set_type(stake_id, sp.TNat)
        sp.verify(self.data.ledger.contains(stake_id), message="InvalidStakeId")
        sp.verify(self.data.ledger[stake_id] == sp.sender, message="NotOwner")
        sp.verify(
            self.data.stakes[stake_id].cooldown_start_timestamp.is_some(),
            message="InvalidState",
        )

        self.fetch_token_balance(sp.unit)
        sp.transfer(
            sp.record(owner=sp.sender, stake_id=stake_id),
            sp.mutez(0),
            sp.self_entry_point("internal_recommit"),
        )

    @sp.entry_point(check_no_incoming_transfer=True)
    def enter_cooldown(self, stake_id):
        """
        Starts the cooldown period for the given stake id. A stake that is in cooldown has half of
        it's previous weight therefore will receive half of the rewards they are entitled to, but
        will pay bailouts in full amount (as if they were not in cooldown). This decision is made
        to not allow users to avoid paying full bailouts by entering cooldown before a bailout
        is executed and then recommiting.
        The main logic can be found in the associated internal entrypoint.

        Parameters
        ----------
        stake_id: sp.TNat
            The stake id to enter cooldown period.

        Raises
        ------
        NotOwner
            If the caller is not the owner of the stake.
        InvalidState
            If the selected stake is already in cooldown.
        InvalidStakeId
            If the stake does not exist.
        """
        sp.set_type(stake_id, sp.TNat)
        sp.verify(
            self.data.stakes.contains(stake_id),
            message="InvalidStakeId",
        )
        sp.verify(self.data.ledger[stake_id] == sp.sender, message="NotOwner")
        sp.verify(
            self.data.stakes[stake_id].cooldown_start_timestamp == sp.none,
            message="InvalidState",
        )

        self.fetch_token_balance(sp.unit)
        sp.transfer(
            sp.record(owner=sp.sender, stake_id=stake_id),
            sp.mutez(0),
            sp.self_entry_point("internal_enter_cooldown"),
        )

    @sp.entry_point(check_no_incoming_transfer=True)
    def withdraw(self, stake_id):
        """
        Allows a user to withdraw their stake after the cooldown period has passed. The total
        withdrawn amount is calculated by the formula:
        withdrawn_amount = commited amount + received rewards - bailouts to pay.
        The main logic can be found in the associated internal entrypoint.

        NOTE: If bailouts to pay > received rewards then the total withdrawn amount will be lower
        than the commited amount.

        Parameters
        ----------
        stake_id: sp.TNat
            The stake id to be withdrawn.

        Raises
        ------
        NotOwner
            If the caller is not the owner of the stake.
        NotAllowed
            If the selected stake is not ready for withdrawl (stake not in cooldown or the cooldown
            period has not passed).
        InvalidState
            If the stake has not started the cooldown period.
        InvalidStakeId
            If the stake to be withdrawn does not exist.
        """
        sp.set_type(stake_id, sp.TNat)
        sp.verify(
            self.data.stakes.contains(stake_id),
            message="InvalidStakeId",
        )
        stake = sp.local("stake", self.data.stakes[stake_id])
        sp.verify(self.data.ledger[stake_id] == sp.sender, message="NotOwner")
        sp.verify(stake.value.cooldown_start_timestamp.is_some(), message="InvalidState")
        withdrawl_time = sp.local(
            "withdrawl_time",
            stake.value.cooldown_start_timestamp.open_some().add_seconds(
                sp.to_int(stake.value.cooldown_duration)
            ),
        )
        sp.verify(sp.now >= withdrawl_time.value, message="NotAllowed")

        self.fetch_token_balance(sp.unit)
        sp.transfer(
            sp.record(owner=sp.sender, stake_id=stake_id),
            sp.mutez(0),
            sp.self_entry_point("internal_withdraw"),
        )

    @sp.entry_point(check_no_incoming_transfer=True)
    def kickout(self, stake_id):
        """
        Allows anyone to force the withdraw of a stake for which the cooldown period plus a
        maximum withdraw delay (max_withdraw_delay) has passed. The user that forces the withdraw
        is then entitled to a percentage of the accumulated rewards on that stake and will force
        out that stake without necessary being the owner. This mechanism avoids letting users
        staying in the pool to accumulate rewards after their cooldown period has passed.

        Parameters
        ----------
        stake_id: sp.TNat
            The stake id to be kicked out.

        Raises
        ------
        NotAllowed
            If the selected stake is not ready to be kicked out (stake not in cooldown or the
            cooldown period + max_withdraw_delay has not passed).
        InvalidState
            If the stake has not started the cooldown period.
        InvalidStakeId
            If the stake to be withdrawn does not exist.
        """
        sp.set_type(stake_id, sp.TNat)
        sp.verify(
            self.data.stakes.contains(stake_id),
            message="InvalidStakeId",
        )
        stake = sp.local("stake", self.data.stakes[stake_id])
        sp.verify(stake.value.cooldown_start_timestamp.is_some(), message="InvalidState")
        kickout_time = sp.local(
            "kickout_time",
            stake.value.cooldown_start_timestamp.open_some().add_seconds(
                sp.to_int(stake.value.cooldown_duration + self.data.max_withdraw_delay)
            ),
        )
        sp.verify(sp.now > kickout_time.value, message="NotAllowed")

        self.fetch_token_balance(sp.unit)
        sp.transfer(
            sp.record(kicker=sp.sender, owner=self.data.ledger[stake_id], stake_id=stake_id),
            sp.mutez(0),
            sp.self_entry_point("internal_kickout"),
        )

    @sp.entry_point(check_no_incoming_transfer=True)
    def bailout(self, amount, execution_lambda):
        """
        Allows an admin of the contract to pay bad debt accumulated on the platform by using the
        a fair amount of tokens from all stakes in the pool. The amount taken from each stake
        is the percentage: stake_bailout_weight/total_bailout_weight.

        Parameters
        ----------
        amount: sp.TNat
            The amount payed for the bailout for which each stake will be penalized fairly
            (percentage of the stake).
        execution_lambda: sp.TLambda(sp.TNat, sp.TList(sp.TOperation))
            The lambda to be executed for the bailout. In general it will be a transfer of
            amount tokens from the pool to another contract, but having an execution lambda
            allows for more flexibility (e.g. swapping the staking token to another token
            before transfering it).
            NOTE: The execution lambda needs to transfer 'amount' tokens from the pool to another
            address and it is the caller that needs to make sure this happens.

        Raises
        ------
        NotAdmin
            If the caller is not an admin of the contract.
        """
        sp.set_type(amount, sp.TNat)
        sp.set_type(execution_lambda, sp.TLambda(sp.TNat, sp.TList(sp.TOperation)))
        self.verify_is_admin(sp.unit)

        self.fetch_token_balance(sp.unit)
        sp.transfer(
            sp.record(amount=amount, execution_lambda=execution_lambda),
            sp.mutez(0),
            sp.self_entry_point("internal_bailout"),
        )

    @sp.entry_point(check_no_incoming_transfer=True)
    def execute(self, execution_lambda):
        """
        Executes in the name of the contract the lambda stored in the execution lambda.
        This is used for upgreadability/migrations.

        Parameters
        ----------
        execution_lambda: sp.TLambda(sp.TUnit, sp.TList(sp.TOperation))
            The lambda to execute.
        
        Raises
        ------
        NotAdmin
            If the caller of the entrypoint is not an admin of the contract
        """
        sp.set_type(execution_lambda, sp.TLambda(sp.TUnit, sp.TList(sp.TOperation)))
        self.verify_is_admin(sp.unit)
        sp.add_operations(execution_lambda(sp.unit).rev())

    @sp.entry_point(check_no_incoming_transfer=True)
    def update_parameters(self):
        """
        Updates the parameters of the contract, namely the reward factor. As rewards can be
        transfered directly to this contract, we need this entrypoint to make the contract
        aware of these rewards.
        NOTE: All main entrypoints related to staking: commit, recommit, enter_cooldown,
        withdraw do this operation before-hand, but because the contract can be in a state
        where many rewards are transfered to the contract and no staking entrypoints were
        called, having such an entrypoint comes handy.
        """
        self.fetch_token_balance(sp.unit)
        sp.transfer(sp.unit, sp.mutez(0), sp.self_entry_point("internal_update_parameters")) 
    
    @sp.entry_point(check_no_incoming_transfer=True)
    def set_token_balance(self, balance_of_response):
        """
        Sets the current token balance of the contract.
        Parameters
        ----------
        balance_of_response: BalanceOf.get_response_type()
            The response of the balance_of entrypoint call of an FA2 contract.

        Raises
        InvalidBalanceRequest
            If the returned balance is not the balance of the contract.
        """
        sp.set_type(balance_of_response, BalanceOf.get_response_type())
        sp.verify(sp.sender == self.data.token_address, message=Errors.INVALID_SENDER)
        with sp.match_cons(balance_of_response) as balances:
            sp.verify(
                balances.head.request.owner == sp.self_address,
                message=Errors.INVALID_BALANCE_REQUEST,
            )
            self.data.current_token_balance = balances.head.balance

    @sp.entry_point(check_no_incoming_transfer=True)
    def transfer(self, transfers):
        """This entrypoint, as per FA2 standard, takes the provided list of transfers and
        transfers the given amounts between accounts.

        Parameters
        ----------
        transfers: sp.TList(Transfer), where Transfer = sp.TPair(from, sp.TList(to, token_id)).
            A list of transfers where each transfer is composed of a pair of source account and a
            list of receiver accounts with the associated token_id.

        Raises
        ------
        TokenUndefined
            If at least one of the token id in the transfer list is not defined.
        NotOperator
            If the sender is not the owner or an operator for the account.
        NotOwner
            If the source is not the owner of the transfered token.
        """
        sp.set_type(transfers, Transfer.get_batch_type())
        with sp.for_("transfer", transfers) as transfer:
            with sp.for_("tx", transfer.txs) as tx:
                sp.verify(
                    self.data.ledger.contains(tx.token_id),
                    message=FA2ErrorMessage.TOKEN_UNDEFINED,
                )
                sp.verify(
                    self.data.ledger[tx.token_id] == transfer.from_,
                    message=FA2ErrorMessage.NOT_OWNER,
                )
                operator_key = OperatorKey.make(tx.token_id, transfer.from_, sp.sender)
                sp.verify(
                    (sp.sender == transfer.from_) | self.data.operators.contains(operator_key),
                    message=FA2ErrorMessage.NOT_OPERATOR,
                )
                with sp.if_(tx.amount == 1):
                    self.data.ledger[tx.token_id] = tx.to_

    @sp.entry_point(check_no_incoming_transfer=True)
    def update_operators(self, update_operators):
        """This entrypoint, as per FA2 standard, adds/removes accounts that can transfer tokens
        on behalf of the owner.

        Parameters
        ----------
        update-operators : sp.TList(UpdateOperator)
            List of accounts that can/cannot any more transfer tokens on behalf of the owner.

        Raises
        ------
        NotOwner
            If the caller is not owner of the tokens.
        TokenUndefined
            If at least one of the token id in the list is not defined.
        """
        sp.set_type(update_operators, UpdateOperator.get_batch_type())
        with sp.for_("update_operator", update_operators) as update_operator:
            with update_operator.match_cases() as argument:
                with argument.match("add_operator") as add_operator:
                    sp.verify(
                        add_operator.owner == sp.sender,
                        message=FA2ErrorMessage.NOT_OWNER,
                    )
                    sp.verify(
                        self.data.ledger.contains(add_operator.token_id),
                        message=FA2ErrorMessage.TOKEN_UNDEFINED,
                    )
                    operator_key = OperatorKey.make(
                        add_operator.token_id, add_operator.owner, add_operator.operator
                    )
                    self.data.operators[operator_key] = sp.unit
                with argument.match("remove_operator") as remove_operator:
                    sp.verify(
                        remove_operator.owner == sp.sender,
                        message=FA2ErrorMessage.NOT_OWNER,
                    )
                    sp.verify(
                        self.data.ledger.contains(remove_operator.token_id),
                        message=FA2ErrorMessage.TOKEN_UNDEFINED,
                    )
                    operator_key = OperatorKey.make(
                        remove_operator.token_id,
                        remove_operator.owner,
                        remove_operator.operator,
                    )
                    del self.data.operators[operator_key]

    @sp.entry_point(check_no_incoming_transfer=True)
    def balance_of(self, balance_of_requests):
        """This entrypoint, as per FA2 standard, takes balance_of requests and reponds on the
        provided callback contract.

        Parameters
        ----------
        balance_of_requests : sp.TPair(Callback, sp.TList(BalanceOfRequest))
            A pair composed of a list of accounts balance requests and a callback contract where
            the response will be send.

        Raises
        ------
        TokenUndefined
            If at least one of the token id in the balance of request list is not defined.
        """
        sp.set_type(balance_of_requests, BalanceOf.get_type())
        responses = sp.local(
            "responses", sp.set_type_expr(sp.list([]), BalanceOf.get_response_type())
        )
        with sp.for_("request", balance_of_requests.requests) as request:
            sp.verify(
                self.data.ledger.contains(request.token_id),
                message=FA2ErrorMessage.TOKEN_UNDEFINED,
            )
            with sp.if_(self.data.ledger[request.token_id] == request.owner):
                responses.value.push(sp.record(request=request, balance=1))
            with sp.else_():
                responses.value.push(sp.record(request=request, balance=0))

        sp.transfer(responses.value, sp.mutez(0), balance_of_requests.callback)

    @sp.entry_point(check_no_incoming_transfer=True)
    def update_max_withdraw_delay(self, max_withdraw_delay):
        """Updates the maximum withdraw delay before an user other the owner can force
        owner to withdraw.

        Parameters
        ----------
        max_withdraw_delay: sp.TNat
            New maximum allowed withdraw delay before an user can force the owner to withdraw
            the stake.

        Raises
        ------
        NotAdmin
            If the caller is not an admin of the contract.
        """
        sp.set_type(max_withdraw_delay, sp.TNat)
        self.verify_is_admin(sp.unit)
        self.data.max_withdraw_delay = max_withdraw_delay

    @sp.entry_point(check_no_incoming_transfer=True)
    def update_kicker_reward_ratio(self, kicker_reward_ratio):
        """Updates the kicker reward ratio. An user can kick out another user who decided to
        withdraw, but did not. A kicker then is entitled to the set ratio of the other user's
        rewards.

        Parameters
        ----------
        kicker_reward_ratio: Ratio = sp.TPair(sp.TNat, sp.TNat)
            New kicker reward ratio

        Raises
        ------
        NotAdmin
            If the caller is not an admin of the contract.
        """
        sp.set_type(kicker_reward_ratio, Ratio.get_type())
        self.verify_is_admin(sp.unit)
        self.data.kicker_reward_ratio = kicker_reward_ratio

    @sp.entry_point(check_no_incoming_transfer=True)
    def add_allowed_source(self, source):
        """
        Adds an address to the map of allowed sources.

        Parameters
        ----------
        source: sp.TAddress
            The address to be added in the allowed sources map.

        Raises
        ------
        NotAdmin
            If the caller is not an admin of the contract.
        """
        sp.set_type(source, sp.TAddress)
        self.verify_is_admin(sp.unit)
        self.data.allowed_sources[source] = sp.unit

    @sp.entry_point(check_no_incoming_transfer=True)
    def remove_allowed_source(self, source):
        """
        Removes an address from the map of allowed sources.

        Parameters
        ----------
        source: sp.TAddress
            The address to be removed from the allowed sources map.

        Raises
        ------
        NotAdmin
            If the caller is not an admin of the contract.
        """
        """"""
        sp.set_type(source, sp.TAddress)
        self.verify_is_admin(sp.unit)
        del self.data.allowed_sources[source]

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_token_metadata(self, token_metadata):
        """
        Updates the token metadata of a given token.

        Parameters
        ----------
        token_metadata: TokenMetadata.get_type()
            The metadata for a given token.

        Raises
        ------
        InexistentToken
            If the token/stake is not yet existent.
        NotAllowedSource
            If the caller is not an allowed token metadata setter.  
        """
        sp.set_type(token_metadata, TokenMetadata.get_type())
        self.verify_is_allowed_source(sp.unit)
        sp.verify(self.data.ledger.contains(token_metadata.token_id), message="InexistentToken")

        self.data.token_metadata[token_metadata.token_id] = token_metadata

    @sp.entry_point(check_no_incoming_transfer=True)
    def remove_token_metadata(self, token_id):
        """
        Removes the token metadata of the token with the given token_id.

        Parameters
        ----------
        token_id: sp.TNat
            The id of the token for which metadata will be removed.

        Raises
        ------
        NotAllowedSource
            If the caller is not an allowed token metadata setter.  
        TokenStillInUse 
            If the token for which the metadata will be deleted is still in use
            (the corresponding stake was not withdrawn or kicked out)
        """
        sp.set_type(token_id, sp.TNat)

        self.verify_is_allowed_source(sp.unit)
        sp.verify(~self.data.ledger.contains(token_id), message="TokenStillInUse")

        del self.data.token_metadata[token_id]

    @sp.entry_point(check_no_incoming_transfer=True)
    def update_vote_scale_map(self, epoch_length, voting_scale_map):
        """
        Updates the voting scale map and the epoch length. The epoch length must be a
        divisor of max_cooldown_duration and voting_scale_map should contain values from
        0 to max_cooldown_duration/epoch_length with one entry per epoch.

        Parameters
        ----------
        epoch_length: sp.TNat
            New epoch length (divisior of max_cooldown_duration)
        voting_scale_map: sp.TMap(sp.TNat, Ratio(sp.TNat, sp.TNat))
            The new voting scale map in percentages.

        Raises
        ------
        IncorrectEpochLength
            If epoch_length is not a divisor of max_cooldown_duration
        IncompleteVotingMap
            If voting_scale_map does not contains all the values between
            0 and max_cooldown_duration/epoch_length.
        InvalidVotingMap
            If the voting map does contain other values than the ones from 0 to
            max_cooldown_duration/epoch_length.
        NotAdmin
            If the caller is not an admin of the contract.
        """
        sp.set_type(epoch_length, sp.TNat)
        sp.set_type(voting_scale_map, sp.TMap(sp.TNat, Ratio.get_type()))

        self.verify_is_admin(sp.unit)
        sp.verify(self.data.max_cooldown_duration % epoch_length == 0, message="IncorrectEpochLength")
        num_epochs = sp.local("num_epochs", self.data.max_cooldown_duration // epoch_length)
        sp.verify(sp.len(voting_scale_map) == num_epochs.value + 1, message="IncompleteVotingMap")

        with sp.for_("epoch_index", sp.range(0, num_epochs.value + 1, step=1)) as epoch_index:
            sp.verify(voting_scale_map.contains(epoch_index), message="InvalidVotingMap")

        self.data.epoch_length = epoch_length
        self.data.voting_scale_map = voting_scale_map
    
    ###############################################################################################
    #                                    Internal entrypoints                                     #
    ###############################################################################################
    """
    IMPORTANT: These updates that are applied by all internal entrypoints (except bailout):
    1. The reward factor is updated (any rewards that the pool received are taken into account)
    2. The rewards/bailouts for the given stake are updated in the respective accumulated
    rewards/bailouts fields of the stake.
    3. The rewards/bailouts factors are updated to the latest values in the storage.
    """

    @sp.entry_point(check_no_incoming_transfer=True)
    def internal_update_parameters(self):
        """
        Updates the parameters of the contract, namely the reward factor. 
        
        Raises
        ------
        NotInternal
            If the entrypoint was not called by this contract.
        """
        self.verify_internal(sp.unit)
        self.update_reward_factor(sp.unit)

    @sp.entry_point(check_no_incoming_transfer=True)
    def internal_commit(self, owner, param):
        """
        Creates or Updates a stake.

        Parameters
        ----------
        owner: sp.TAddress
            The owner of the stake
        param: sp.TRecord(
            amount=sp.TNat,
            cooldown_duration=sp.TNat,
            stake_id=sp.TOption(sp.TNat)
        )
            The amount and cooldown duration to be commited for the stake. For an update commit,
            the given amount will be added on top of the existing one and cooldown duration will
            replace the old cooldown duration. If the stake_id is missing, a new stake is created.

        Raises
        ------
        NotInternal
            If the entrypoint was not called by this contract.
        """
        sp.set_type(owner, sp.TAddress)
        sp.set_type(
            param,
            sp.TRecord(
                amount=sp.TNat, 
                cooldown_duration=sp.TNat, 
                stake_id=sp.TOption(sp.TNat))
        )
        self.verify_internal(sp.unit)
        self.update_reward_factor(sp.unit)

        Utils.execute_fa2_token_transfer(
            self.data.token_address,
            owner,
            sp.self_address,
            self.data.token_id,
            param.amount,
        )
        self.data.previous_token_balance = self.data.previous_token_balance + param.amount

        with sp.if_(param.stake_id.is_none()):
            stake_id = sp.local("stake_id", self.data.stake_id_counter)
            weight = sp.local("weight", (param.amount * param.cooldown_duration) // self.data.max_cooldown_duration)
            stake = sp.local(
                "stake",
                Stake.make(
                    amount=param.amount,
                    reward_weight=weight.value,
                    bailout_weight=weight.value,
                    accumulated_rewards=0,
                    accumulated_bailouts=0,
                    cooldown_duration=param.cooldown_duration,
                    cooldown_start_timestamp=sp.none,
                    reward_factor=self.data.reward_factor,
                    bailout_factor=self.data.bailout_factor,
                ),
            )
            self.data.stake_id_counter = self.data.stake_id_counter + 1

            self.data.total_reward_stake_weight = (
                self.data.total_reward_stake_weight + stake.value.reward_weight
            )
            self.data.total_bailout_stake_weight = (
                self.data.total_bailout_stake_weight + stake.value.bailout_weight
            )
            self.data.ledger[stake_id.value] = owner
            self.data.stakes[stake_id.value] = stake.value
            self.data.token_metadata[stake_id.value] = sp.record(token_id=stake_id.value, token_info=DEFAULT_TOKEN_INFO)
        with sp.else_():
            stake_id = sp.local("stake_id", param.stake_id.open_some())
            stake = sp.local("stake", self.data.stakes[stake_id.value])
            
            # Update the accumulated rewards/bailouts
            stake.value.accumulated_rewards += (
                (sp.as_nat(self.data.reward_factor - stake.value.reward_factor)
                * stake.value.reward_weight)
                // Constants.PRECISION_FACTOR
            )
            stake.value.accumulated_bailouts += (
                (sp.as_nat(self.data.bailout_factor - stake.value.bailout_factor)
                * stake.value.bailout_weight)
                // Constants.PRECISION_FACTOR
            )
            stake.value.reward_factor = self.data.reward_factor
            stake.value.bailout_factor = self.data.bailout_factor
            # Substact the old weights
            self.data.total_reward_stake_weight = sp.as_nat(
                self.data.total_reward_stake_weight - stake.value.reward_weight
            )
            self.data.total_bailout_stake_weight = sp.as_nat(
                self.data.total_bailout_stake_weight - stake.value.bailout_weight
            )
            # Update the weight and cooldown
            stake.value.amount = stake.value.amount + param.amount
            weight = sp.local(
                "weight", 
                (stake.value.amount * param.cooldown_duration) // self.data.max_cooldown_duration)
            stake.value.reward_weight = weight.value
            stake.value.bailout_weight = weight.value
            stake.value.cooldown_duration = param.cooldown_duration
            # Add the new weights
            self.data.total_reward_stake_weight = (
                self.data.total_reward_stake_weight + stake.value.reward_weight
            )
            self.data.total_bailout_stake_weight = (
                self.data.total_bailout_stake_weight + stake.value.bailout_weight
            )
            self.data.stakes[stake_id.value] = stake.value

    @sp.entry_point(check_no_incoming_transfer=True)
    def internal_recommit(self, owner, stake_id):
        """
        Allows for a stake that is in the cooldown period to be recommited to the pool. The stake
        will have the same cooldown period and the rewards factor will stop being halfed.

        Parameters
        ----------
        owner: sp.TAddress
            The owner of the stake
        stake_id: sp.TNat
            The stake id to be recommited.

        Raises
        ------
        NotInternal
            If the entrypoint was not called by this contract.
        """
        sp.set_type(owner, sp.TAddress)
        sp.set_type(stake_id, sp.TNat)

        self.verify_internal(sp.unit)
        self.update_reward_factor(sp.unit)

        stake = sp.local("stake", self.data.stakes[stake_id])
        stake.value.accumulated_rewards += (
            (sp.as_nat(self.data.reward_factor - stake.value.reward_factor)
            * stake.value.reward_weight)
            // Constants.PRECISION_FACTOR
        )
        stake.value.accumulated_bailouts += (
            (sp.as_nat(self.data.bailout_factor - stake.value.bailout_factor)
            * stake.value.bailout_weight)
            // Constants.PRECISION_FACTOR
        )
        stake.value.reward_factor = self.data.reward_factor
        stake.value.bailout_factor = self.data.bailout_factor

        # Substact the old weights
        self.data.total_reward_stake_weight = sp.as_nat(
            self.data.total_reward_stake_weight - stake.value.reward_weight
        )
        # Update the weight and cooldown (only the reward weight is half, the bailout needs to be
        # paid in full)
        stake.value.reward_weight = (
            (stake.value.amount * stake.value.cooldown_duration) // self.data.max_cooldown_duration
        )
        stake.value.cooldown_start_timestamp = sp.none
        # Add the new weights
        self.data.total_reward_stake_weight = (
            self.data.total_reward_stake_weight + stake.value.reward_weight
        )

        self.data.stakes[stake_id] = stake.value

    @sp.entry_point(check_no_incoming_transfer=True)
    def internal_enter_cooldown(self, owner, stake_id):
        """
        Starts the cooldown period for the given stake id. A stake that is in cooldown has half of
        it's previous weight therefore will receive half of the rewards they are entitled to, but
        will pay bailouts in full amount (as if they were not in cooldown).

        Parameters
        ----------
        owner: sp.TAddress
            The owner of the stake
        stake_id: sp.TNat
            The stake id to enter cooldown period.

        Raises
        ------
        NotInternal
            If the entrypoint was not called by this contract.
        """
        sp.set_type(owner, sp.TAddress)
        sp.set_type(stake_id, sp.TNat)

        self.verify_internal(sp.unit)
        self.update_reward_factor(sp.unit)

        stake = sp.local("stake", self.data.stakes[stake_id])
        stake.value.accumulated_rewards += (
            (sp.as_nat(self.data.reward_factor - stake.value.reward_factor)
            * stake.value.reward_weight)
            // Constants.PRECISION_FACTOR
        )
        stake.value.accumulated_bailouts += (
            (sp.as_nat(self.data.bailout_factor - stake.value.bailout_factor)
            * stake.value.bailout_weight)
            // Constants.PRECISION_FACTOR
        )
        stake.value.reward_factor = self.data.reward_factor
        stake.value.bailout_factor = self.data.bailout_factor
        # Substact the old weights
        self.data.total_reward_stake_weight = sp.as_nat(
            self.data.total_reward_stake_weight - stake.value.reward_weight
        )
        # Update the weight and cooldown (only the reward weight is half, the bailout needs to be
        # paid in full)
        stake.value.reward_weight = stake.value.reward_weight // 2
        stake.value.cooldown_start_timestamp = sp.some(sp.now)
        # Add the new weights
        self.data.total_reward_stake_weight = (
            self.data.total_reward_stake_weight + stake.value.reward_weight
        )

        self.data.stakes[stake_id] = stake.value

    @sp.entry_point(check_no_incoming_transfer=True)
    def internal_withdraw(self, owner, stake_id):
        """
        Allows a user to withdraw their stake after the cooldown period has passed. The total
        withdrawn amount is calculated by the formula:
        withdrawn_amount = amount + received rewards - bailouts to pay.
        This amount is then transfered to the owner and the stake is removed from the storage.

        NOTE: There is a check if the withdrawn amount < 0 to still withdraw the stake. In
        reality this should never happen, but due to rounding issues this is a possibility
        that we want to avoid.

        Parameters
        ----------
        owner: sp.TAddress
            The owner of the stake.
        stake_id: sp.TNat
            The stake id to be withdrawn.

        Raises
        ------
        NotInternal
            If the entrypoint was not called by this contract.
        """
        sp.set_type(owner, sp.TAddress)
        sp.set_type(stake_id, sp.TNat)

        self.verify_internal(sp.unit)
        self.update_reward_factor(sp.unit)

        stake = sp.local("stake", self.data.stakes[stake_id])
        stake.value.accumulated_rewards += (
            (sp.as_nat(self.data.reward_factor - stake.value.reward_factor)
            * stake.value.reward_weight)
            // Constants.PRECISION_FACTOR
        )
        stake.value.accumulated_bailouts += (
            (sp.as_nat(self.data.bailout_factor - stake.value.bailout_factor)
            * stake.value.bailout_weight)
            // Constants.PRECISION_FACTOR
        )

        exit_amount = sp.local("exit_amount", sp.nat(0))
        amount = sp.local("amount", stake.value.amount + stake.value.accumulated_rewards - stake.value.accumulated_bailouts)
        with sp.if_(amount.value > 0):
            exit_amount.value = sp.as_nat(amount.value)

        self.data.total_reward_stake_weight = sp.as_nat(
            self.data.total_reward_stake_weight - stake.value.reward_weight
        )
        self.data.total_bailout_stake_weight = sp.as_nat(
            self.data.total_bailout_stake_weight - stake.value.bailout_weight
        )
        self.data.previous_token_balance = sp.as_nat(
            self.data.previous_token_balance - exit_amount.value
        )

        Utils.execute_fa2_token_transfer(
            self.data.token_address,
            sp.self_address,
            owner,
            self.data.token_id,
            exit_amount.value,
        )
        del self.data.stakes[stake_id]
        del self.data.ledger[stake_id]
        del self.data.token_metadata[stake_id]

    @sp.entry_point(check_no_incoming_transfer=True)
    def internal_kickout(self, kicker, owner, stake_id):
        """
        Allows anyone to force the withdraw of a stake for which the cooldown period plus a delay
        (max_withdraw_delay) has passed. The user that forces the withdraw is entitled to a
        percentage of the accumulated rewards on that stake (only the accumulated rewards). This
        mechanism avoids letting users staying in the pool to accumulate rewards after the cooldown
        period has passed.

        The reward is transfered to the kicker, the remaining amount is transfered to the owner and
        the stake is removed from the storage.

        Parameters
        ----------
        kicker: sp.TAddress
            The kicker who is entitled to a reward.
        owner: sp.TAddress
            The owner of the stake.
        stake_id: sp.TNat
            The stake id to be kicked out.

        Raises
        ------
        NotInternal
            If the entrypoint was not called by this contract.
        """
        sp.set_type(kicker, sp.TAddress)
        sp.set_type(owner, sp.TAddress)
        sp.set_type(stake_id, sp.TNat)

        self.verify_internal(sp.unit)
        self.update_reward_factor(sp.unit)

        stake = sp.local("stake", self.data.stakes[stake_id])
        stake.value.accumulated_rewards += (
            (sp.as_nat(self.data.reward_factor - stake.value.reward_factor)
            * stake.value.reward_weight)
            // Constants.PRECISION_FACTOR
        )
        stake.value.accumulated_bailouts += (
            (sp.as_nat(self.data.bailout_factor - stake.value.bailout_factor)
            * stake.value.bailout_weight)
            // Constants.PRECISION_FACTOR
        )
        kicker_rewards = sp.local(
            "kicker_rewards",
            (stake.value.accumulated_rewards
            * self.data.kicker_reward_ratio.numerator)
            // self.data.kicker_reward_ratio.denominator,
        )
        owner_rewards = sp.local(
            "owner_rewards",
            sp.as_nat(stake.value.accumulated_rewards - kicker_rewards.value),
        )

        exit_amount = sp.local("exit_amount", sp.nat(0))
        amount = sp.local("amount", stake.value.amount + owner_rewards.value - stake.value.accumulated_bailouts)
        with sp.if_(amount.value > 0):
            exit_amount.value = sp.as_nat(amount.value)
        with sp.else_():
            # To adjust for the possibility that the kicker rewards will take out more
            # tokens than the stake have left, we adjust it by adding the negative amount
            # left by the amount + owner_rewards - accumulated_bailouts.
            kicker_rewards.value = sp.as_nat(sp.to_int(kicker_rewards.value) + amount.value) # amount.value is negative.

        self.data.total_reward_stake_weight = sp.as_nat(
            self.data.total_reward_stake_weight - stake.value.reward_weight
        )
        self.data.total_bailout_stake_weight = sp.as_nat(
            self.data.total_bailout_stake_weight - stake.value.bailout_weight
        )
        self.data.previous_token_balance = sp.as_nat(
            self.data.previous_token_balance - (exit_amount.value + kicker_rewards.value)
        )

        Utils.execute_fa2_token_transfer(
            self.data.token_address,
            sp.self_address,
            kicker,
            self.data.token_id,
            kicker_rewards.value,
        )
        Utils.execute_fa2_token_transfer(
            self.data.token_address,
            sp.self_address,
            owner,
            self.data.token_id,
            exit_amount.value,
        )
        del self.data.stakes[stake_id]
        del self.data.ledger[stake_id]
        del self.data.token_metadata[stake_id]

    @sp.entry_point(check_no_incoming_transfer=True)
    def internal_bailout(self, amount, execution_lambda):
        """
        Execute a bailout (pay bad debt accumulated on the platform) by taking the same percentage
        from each stake. The amount is not immediately taken from each individual stake, but the
        bailout_factor is responsible for keeping track of it.
        The amount take from each stake for a single bailout is:
        stake_bailout_weight/total_bailout_weight * amount.

        Parameters
        ----------
        amount: sp.TNat
            The amount payed for the bailout for which each stake will be penalized fairly
        execution_lambda: sp.TLambda(sp.TNat, sp.TList(sp.TOperation))
            The lambda to be executed for the bailout.

        Raises
        ------
        NotInternal
            If the entrypoint was not called by this contract.
        """
        sp.set_type(amount, sp.TNat)
        sp.set_type(execution_lambda, sp.TLambda(sp.TNat, sp.TList(sp.TOperation)))

        self.verify_internal(sp.unit)
        self.update_reward_factor(sp.unit)
        self.update_bailout_factor(amount)

        self.data.previous_token_balance = sp.as_nat(self.data.previous_token_balance - amount)
        sp.add_operations(execution_lambda(amount))

    ###############################################################################################
    #                                    On chain views                                           #
    ###############################################################################################
    @sp.onchain_view()
    def view_stake_info(self, stake_id):
        """
        Returns informations for the given stake_id.

        Parameters
        ----------
        stake_id: sp.TNat
            The id of stake for which information is requested.

        Returns
        -------
        stake_details: Stake.get_type()
            The stake informations stored in the contract's storage.
            NOTE: This view returns the stake information as they are found in the contract's
            storage. It can have not the up to date accumulated rewards/bailouts.
        """
        sp.set_type(stake_id, sp.TNat)
        with sp.if_(~self.data.stakes.contains(stake_id)):
            sp.result(Stake.make_empty())
        with sp.else_():
            sp.result(self.data.stakes[stake_id])

    @sp.onchain_view()
    def get_accumulated_rewards(self, stake_id):
        """
        Returns the current accumulated rewards on stake with the given stake_id.

        Parameters
        ----------
        stake_id: sp.TNat
            The id of stake for which accumulated_rewards is requested.

        Returns
        -------
        accumulated_rewards: sp.TNat
            The current accumulated rewards on the stake.
            NOTE: This view returns the accumulated rewards as they are found in the contract's
            storage. It can not have the up to date accumulated rewards.
        """
        sp.set_type(stake_id, sp.TNat)
        with sp.if_(~self.data.stakes.contains(stake_id)):
            sp.result(sp.nat(0))
        with sp.else_():
            stake = sp.local("stake", self.data.stakes[stake_id])
            sp.result(
                stake.value.accumulated_rewards
                + ((sp.as_nat(self.data.reward_factor - stake.value.reward_factor)
                * stake.value.reward_weight)
                // Constants.PRECISION_FACTOR)
            )

    @sp.onchain_view()
    def get_accumulated_bailouts(self, stake_id):
        """
        Returns the current accumulated bailouts on stake with the given stake_id.

        Parameters
        ----------
        stake_id: sp.TNat
            The id of stake for which accumulated_bailouts is requested.

        Returns
        -------
        accumulated_bailouts: sp.TNat
            The current accumulated bailouts to be paid by the stake.
        """
        sp.set_type(stake_id, sp.TNat)
        with sp.if_(~self.data.stakes.contains(stake_id)):
            sp.result(sp.nat(0))
        with sp.else_():
            stake = sp.local("stake", self.data.stakes[stake_id])
            sp.result(
                stake.value.accumulated_bailouts
                + ((sp.as_nat(self.data.bailout_factor - stake.value.bailout_factor)
                * stake.value.bailout_weight)
                // Constants.PRECISION_FACTOR)
            )

    @sp.onchain_view()
    def get_total_reward_stake_weight(self):
        """
        Returns the total reward stake weight.

        Returns
        -------
        total_reward_stake_weight: sp.TNat
            The total reward stake weight.
        """
        sp.result(self.data.total_reward_stake_weight)

    @sp.onchain_view()
    def get_total_bailout_stake_weight(self):
        """
        Returns the total bailout stake weight.

        Returns
        -------
        total_bailout_stake_weight: sp.TNat
            The total bailout stake weight.
        """
        sp.result(self.data.total_bailout_stake_weight)

    @sp.onchain_view()
    def get_admin_status(self, address):
        """
        Returns the admin status of the given address with the following signification:
        * 0 - proposed admin (address needs to accept the proposal) in order to have admin status.
        * 1 - admin (can execute all admin protected entrypoints)
        * -1 - not an admin (can accept being an admin nor execute admin protected entrypoints)

        Parameters
        ----------
        address: sp.TAddress
            The address for which admin status is checked.

        Returns
        -------
        admin_status: sp.TInt
            The admin status of the address.
        """
        sp.set_type(address, sp.TAddress)
        with sp.if_(self.data.administrators.contains(address)):
            sp.result(sp.to_int(self.data.administrators[address]))
        with sp.else_():
            sp.result(-1)

    @sp.onchain_view()
    def is_operator(self, operator_key):
        """
        Checks if the given operator key is a valid operator key

        Parameters
        ----------
        operator_key: OperatorKey.get_type()
            The operator key to be checked.

        Returns
        -------
        value: sp.TBool
            True if the operator key is valid, false otherwise.
        """
        sp.set_type(operator_key, OperatorKey.get_type())
        sp.result(self.data.operators.contains(operator_key))

    @sp.onchain_view()
    def get_stake_owner(self, stake_id):
        """
        Returns the stake owner of the given stake id.

        Parameters
        ----------
        stake_id: sp.TNat
            The id of the stake for which the owner is requested.

        Returns
        -------
        owner: sp.TAddress
            The address of the owner.
        """
        sp.set_type(stake_id, sp.TNat)

        with sp.if_(self.data.ledger.contains(stake_id)):
            sp.result(sp.some(self.data.ledger[stake_id]))
        with sp.else_():
            sp.result(sp.none)

    @sp.onchain_view()
    def get_voting_details(self, stake_id):
        """
        Returns voting details for the given stake_id.
        The vote weight of a stake is given by the voting scale map.
        The voting scale map represent a map where for each epoch a percentage (from 0% to 100%)
        of the total possible voting power is assigned.

        The maximum cooldown period is split in N number of epochs, therefore:
        (N * self.data.epoch_length == self.data.max_cooldown_duration)
        
        For the given stake we identify for how many of these N epochs will the stake
        be in cooldown (let's assume E epochs) then the voting power of that stake is given by the
        formula: (amount + reward - bailouts) * self.data.voting_scale_map(E)


        NOTE: This view might return not the latest details due to rewards coming in between 2
        operations (commit, withdraw, etc.). We recommed calling the update_parameters entrypoint
        before hand to have the latest values returned by this view. 

        Parameters
        ----------
        stake_id: sp.TNat
            The id of stake for which details are requested

        Returns
        -------
        voting_details: sp.TOptional(sp.TRecord(
            token_amount=sp.TNat,
            vote_weight=sp.TNat,
            owner=sp.TAddress
        )) 
        """
        sp.set_type(stake_id, sp.TNat)
        with sp.if_(~self.data.stakes.contains(stake_id)):
            sp.result(sp.none)
        with sp.else_():
            stake = sp.local("stake", self.data.stakes[stake_id])
            stake.value.accumulated_rewards += (
                (sp.as_nat(self.data.reward_factor - stake.value.reward_factor)
                * stake.value.reward_weight)
                // Constants.PRECISION_FACTOR
            )
            stake.value.accumulated_bailouts += (
                (sp.as_nat(self.data.bailout_factor - stake.value.bailout_factor)
                * stake.value.bailout_weight)
                // Constants.PRECISION_FACTOR
            )
            vote_percentage = sp.local("vote_percentage", self.data.voting_scale_map[stake.value.cooldown_duration // self.data.epoch_length])
            vote_weight = sp.local(
                "vote_weight",
                (sp.as_nat(
                    stake.value.amount
                    + stake.value.accumulated_rewards
                    - stake.value.accumulated_bailouts
                ) * vote_percentage.value.numerator) // vote_percentage.value.denominator
            )
            owner = sp.local("owner", self.data.ledger[stake_id])
            sp.result(sp.some(
                make_voting_stake(stake.value.amount, vote_weight.value, owner.value)
            ))