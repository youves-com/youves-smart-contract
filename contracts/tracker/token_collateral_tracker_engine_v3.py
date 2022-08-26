import smartpy as sp

import utils.error_codes as Errors
import utils.constants as Constants
from utils.contract_utils import Ratio, Utils
from utils.fa2 import AdministrableMixin, LedgerKey

from contracts.tracker.base_tracker_engine_v3 import BaseTrackerEngine, Settlement, Liquidation

from contracts.tracker.governance_token import Stake

class TokenTrackerEngine(BaseTrackerEngine):
    """this is the heartpiece of the entire project. The engine that orchestrates all other components. This is also the contract responsible for the interest rate/inflation of the liability/savings rate of the
    synthetic asset. This engine is built to create synthetic asset tokens that by getting data from an oracle the resulting synthetic asset will track that value.

    Args:
        (sp.Contract): this is a smartpy contract
        (AdministrableMixin): mixin used to add the administratble entrypoints
    """

    def get_init_storage(self):
        """Returns the initial storage of the contract used for inheritance of smartpy contracts

        Returns:
            dict: initial storage of the contract
        """
        storage = super().get_init_storage()

        storage["vault_contexts"] = sp.big_map(
            tkey=sp.TAddress,
            tvalue=sp.TRecord(
                minted=sp.TNat, balance=sp.TNat, introducer=sp.TOption(sp.TAddress)
            ),
        )

        return storage

    def __init__(
        self,
        token_contract,
        token_id,
        collateral_token_contract,
        collateral_token_id=0,
        collateral_token_type=Constants.TOKEN_TYPE_FA2,
        price_extra_precision_factor=1,
        token_decimals=12,
        collateral_token_decimals=12,
        administrators={},
    ):
        """init to set the token and administrators, in order to be fully operational set_contracts need to be called first.
        Args:
            token_contract (sp.address): token address
            token_id (sp.nat): token id
            administrators (dict, optional): the administrators allowed to set the contracts. Defaults to {}.
        """
        self.token_contract = token_contract
        self.token_id = token_id
        self.collateral_token_contract = collateral_token_contract
        self.collateral_token_id = collateral_token_id
        self.administrators = administrators
        self.collateral_token_type = collateral_token_type
        self.price_extra_precision_factor = price_extra_precision_factor
        self.collateral_token_decimals = collateral_token_decimals
        self.token_decimals = token_decimals

        self.init_type(
            sp.TRecord(
                accrual_update_timestamp = sp.TTimestamp,
                administrators = sp.TBigMap(LedgerKey.get_type(), sp.TUnit),
                collateral_token_contract = sp.TAddress,
                collateral_token_id = sp.TNat,
                compound_interest_rate = sp.TNat,
                governance_token_contract = sp.TAddress,
                options_contract = sp.TAddress,
                reference_interest_rate = sp.TNat,
                spread_rate = sp.TNat,
                reward_pool_contract = sp.TAddress,
                savings_pool_contract = sp.TAddress,
                target_price_oracle = sp.TAddress,
                interest_rate_setter_contract = sp.TAddress,
                token_contract = sp.TAddress,
                token_id = sp.TNat,
                total_supply = sp.TNat,
                vault_contexts = sp.TBigMap(
                    sp.TAddress,
                    sp.TRecord(
                        minted=sp.TNat,
                        balance=sp.TNat,
                        introducer=sp.TOption(sp.TAddress)
                    ).right_comb()
                ),
                collateral_ratio = Ratio.get_type(),
                settlement_ratio = Ratio.get_type(),
                minting_fee_ratio = Ratio.get_type(),
                introducer_ratio = Ratio.get_type(),
                settlement_reward_fee_ratio = Ratio.get_type(),
                settlement_payout_ratio = Ratio.get_type(),
                liquidation_payout_ratio = Ratio.get_type(),
            ).right_comb()
        )

        self.init(**self.get_init_storage())

    @sp.entry_point(check_no_incoming_transfer=True)
    def create_vault(self, introducer):
        """
        creates a new vault for the sender
        """
        sp.set_type(introducer, sp.TOption(sp.TAddress))
        with sp.if_(~self.data.vault_contexts.contains(sp.sender)):
            self.data.vault_contexts[sp.sender] = sp.record(
                minted=sp.nat(0), balance=0, introducer=introducer
            )

    @sp.entry_point(check_no_incoming_transfer=True)
    def deposit(self, token_amount):
        """external entrypoint to deposit a certain amount of tokens (requires you to have called update_operators to allow this contract first).
        The actual logic is in internal_deposit.

        Post: storage.sender = sp.sender
        Post: fetch_reward_balance()
        Post: calls self.internal_deposit

        Args:
            token_amount (sp.nat): the amount of tokens
        """

        sp.set_type(token_amount, sp.TNat)
        if self.collateral_token_type == Constants.TOKEN_TYPE_FA2:
            Utils.execute_fa2_token_transfer(
                self.data.collateral_token_contract,
                sp.sender,
                sp.self_address,
                self.data.collateral_token_id,
                token_amount,
            )
        elif self.collateral_token_type == Constants.TOKEN_TYPE_FA1:
            Utils.execute_fa1_token_transfer(
                self.data.collateral_token_contract,
                sp.sender,
                sp.self_address,
                token_amount,
            )
        self.data.vault_contexts[sp.sender].balance += token_amount

    @sp.entry_point(check_no_incoming_transfer=True)
    def execute(self, _lambda):
        """Executes in the name of the contract the given lambda and updates the storage,
        of the current contract. Used mainly for migration purposes."""
        sp.set_type(
            _lambda,
            sp.TLambda(
                sp.TBigMap(
                    sp.TAddress,
                    sp.TRecord(minted=sp.TNat, balance=sp.TNat, introducer=sp.TOption(sp.TAddress)).right_comb()
                ),
                sp.TPair(
                    sp.TBigMap(
                        sp.TAddress,
                        sp.TRecord(minted=sp.TNat, balance=sp.TNat, introducer=sp.TOption(sp.TAddress)).right_comb()
                    ),
                    sp.TList(sp.TOperation),
                )))
        self.verify_is_admin(Constants.DEFAULT_TOKEN_ID)

        result = sp.compute(_lambda(self.data.vault_contexts))
        self.data.vault_contexts = sp.fst(result)
        
        sp.add_operations(sp.snd(result).rev())
