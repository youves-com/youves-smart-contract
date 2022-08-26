import smartpy as sp

import utils.constants as Constants

from utils.contract_utils import Utils
from utils.internal_mixin import InternalMixin
from utils.administrable_mixin import SingleAdministrableMixin


class InterestRateUpdater(sp.Contract, InternalMixin, SingleAdministrableMixin):
    """this is the heartpiece of the entire project. The engine that orchestrates all other components. This is also the contract responsible for the interest rate/inflation of the liability/savings rate of the
    synthetic asset. This engine is built to create synthetic asset tokens that by getting data from an oracle the resulting synthetic asset will track that value.

    Args:
        (sp.Contract): this is a smartpy contract
        (AdministrableMixin): mixin used to add the administratble entrypoints
        (InternalMixin): mixin used whenever we need external data and hence have to trigger an internal call (to process after we received said external data)
    """

    def get_init_storage(self):
        """Returns the initial storage of the contract used for inheritance of smartpy contracts

        Returns:
            dict: initial storage of the contract
        """
        storage = {}

        storage["reference_interest_rate"] = Constants.SECONDS_INTEREST_MINIMUM

        storage["last_update_timestamp"] = sp.timestamp(0)

        storage["target_price_oracle_address"] = self.target_price_oracle_address
        storage["observed_price_oracle_address"] = self.observed_price_oracle_address
        storage["engine_addresses"] = self.engine_addresses

        storage["target_price"] = sp.nat(0)
        storage["observed_price"] = sp.nat(0)
        storage["administrators"] = sp.set_type_expr(
            self.administrators, sp.TBigMap(sp.TAddress, sp.TNat)
        )

        return storage

    def __init__(
        self,
        engine_addresses,
        target_price_oracle_address,
        observed_price_oracle_address,
        administrators=sp.big_map({}),
    ):
        """init to set the token and administrators, in order to be fully operational set_contracts need to be called first.
        Args:
            token_contract (sp.address): token address
            token_id (sp.nat): token id
            administrators (dict, optional): the administrators allowed to set the contracts. Defaults to {}.
        """
        self.engine_addresses = engine_addresses
        self.target_price_oracle_address = target_price_oracle_address
        self.observed_price_oracle_address = observed_price_oracle_address
        self.administrators = administrators
        
        self.init(**self.get_init_storage())

    @sp.private_lambda(with_storage="read-write", with_operations=True, wrap_call=True)
    def fetch_target_price(self, unit):
        """sub entrypoint which triggers a price fetch for the price to be set using the callback on the "set_target_price" entrypoint

        Args:
            unit (sp.unit): nothing
        """
        Utils.execute_get(
            self.data.target_price_oracle_address, "get_price", "set_target_price"
        )

    @sp.private_lambda(with_storage="read-write", with_operations=True, wrap_call=True)
    def fetch_observed_price(self, unit):
        """sub entrypoint which triggers a price fetch for the price to be set using the callback on the "set_observed_price" entrypoint

        Args:
            unit (sp.unit): nothing
        """
        Utils.execute_get(
            self.data.observed_price_oracle_address, "get_price", "set_observed_price"
        )

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_target_price(self, target_price):
        """entrypoint used by the oracle to set the price
        Pre: sp.sender == storage.target_price_oracle
        Post: storage.target_price = target_price
        Args:
            target_price (sp.nat): price provided by the oracle
        """
        sp.set_type(target_price, sp.TNat)
        self.data.target_price = target_price

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_observed_price(self, observed_price):
        """entrypoint used by the oracle to set the price
        Pre: sp.sender == storage.observed_price_oracle
        Post: storage.observed_price = observed_price
        Args:
            observed_price (sp.nat): price provided by the oracle
        """
        sp.set_type(observed_price, sp.TNat)
        self.data.observed_price = observed_price

    @sp.entry_point(check_no_incoming_transfer=True)
    def interest_rate_update(self):
        """this entrypoint allows anyone to request for a referecne_interest update. Can only be once every week. The actual logic can be found in "internal_interest_rate_update".
        Post: fetch_target_price()
        Post: fetch_observed_price
        Post: calls self.internal_interest_rate_update
        """
        self.fetch_target_price(sp.unit)
        self.fetch_observed_price(sp.unit)
        sp.transfer(
            sp.unit, sp.mutez(0), sp.self_entry_point("internal_interest_rate_update")
        )

    @sp.entry_point(check_no_incoming_transfer=True)
    def add_engine(self, engine_address):
        """this entrypoint adds a new engine to the list of engines to be updated by the contract.
        Only an admin can call this entrypoint.
        Args:
            engine_address (sp.TAddress): The engine address to be added.
        """
        sp.set_type(engine_address, sp.TAddress)

        self.verify_is_admin(sp.unit)
        self.data.engine_addresses.push(engine_address)

    @sp.entry_point(check_no_incoming_transfer=True)
    def update_target_price_oracle(self, new_target_price_oracle):
        """this entrypoint update the target price oracle. It is the duty of the caller to
        make sure that the given oracle has the necessary entrypoints. Only an admin can 
        call this entrypoint.

        Args:
            new_target_price_oracle (sp.TAddress): The new target price oracle
        """
        sp.set_type(new_target_price_oracle, sp.TAddress)

        self.verify_is_admin(sp.unit)
        self.data.target_price_oracle_address = new_target_price_oracle
    
    @sp.entry_point(check_no_incoming_transfer=True)
    def update_observed_price_oracle(self, new_observed_price_oracle):
        """this entrypoint update the observed price oracle. It is the duty of the caller to
        make sure that the given oracle has the necessary entrypoints. Only an admin can 
        call this entrypoint.

        Args:
            new_observed_price_oracle (sp.TAddress): The new observed price oracle
        """
        sp.set_type(new_observed_price_oracle, sp.TAddress)

        self.verify_is_admin(sp.unit)
        self.data.observed_price_oracle_address = new_observed_price_oracle

    @sp.entry_point(check_no_incoming_transfer=True)
    def internal_interest_rate_update(self):
        print("TODO implement")
        pass
