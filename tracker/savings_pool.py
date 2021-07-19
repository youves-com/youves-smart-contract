import smartpy as sp

import tracker.errors as Errors
import tracker.constants as Constants
from tracker.utils import Utils, InternalMixin
import tracker.fa2 as fa2

class SavingsPool(sp.Contract, InternalMixin):
    """The savings pool allows a user to lock their tokens and then get a reward on the same token type like was locked. This means that there are compounding
    effects and we cannot "simply" use the method used in "StakingPool". Minters are able to get tokens out of this contract at a premium when they call the
    bailout function. The tez paid for the bailout are distributed fairly among the savings pool participant. Since the latter is a different token as the stake
    we need to work with distribution factors similar to "StakingPool" for the tez distribution.

    Args:
        (sp.Contract): this is a smartpy contract
        (InternalMixin): mixin used whenever we need external data and hence have to trigger an internal call (to process after we received said external data)
    """
    def get_init_storage(self):
        """Returns the initial storage of the contract used for inheritance of smartpy contracts

        Returns:
            dict: initial storage of the contract
        """
        storage = {}

        storage['total_stake'] = sp.nat(0) # total sta
        storage['disc_factor'] = sp.nat(Constants.PRECISION_FACTOR)
        storage['dist_factor'] = sp.nat(0)

        storage['dist_factors'] = sp.big_map(tkey=sp.TAddress, tvalue=sp.TNat)
        storage['stakes'] = sp.big_map(tkey=sp.TAddress, tvalue=sp.TNat)

        storage['token_address'] = self.token_address
        storage['token_id'] = self.token_id

        storage['engine_address'] = self.engine_address

        storage['sender'] = Constants.DEFAULT_ADDRESS

        storage['last_balance'] = sp.nat(0)
        storage['current_balance'] = sp.nat(0)

        return storage

    def __init__(self, engine_address, token_address, token_id):
        """specifies the engine that is allowed to execute the bailout an the token used for staking.

        Args:
            engine_address (sp.address): engine address
            token_address (sp.address): token address
            token_id (sp.nat): token id
        """
        self.engine_address = engine_address
        self.token_address = token_address
        self.token_id = token_id
        self.init(**self.get_init_storage())

    @sp.sub_entry_point
    def fetch_reward_balance(self, unit):
        """sub entrypoint which triggers a own token balance fetch to be set using the callback on the "set_balance" entrypoint.
        Furthermore this sub entrypoint calls the update function on the engine such that if a new accrual happened we get it.
        The order is reversed because in sub entrypoints the operation stack returned is processed as a stack (execute_update is processed before).

        Post: get token balance
        Post: call update on engine
        Args:
            unit (sp.unit): nothing
        """
        Utils.execute_update(self.data.engine_address)
        Utils.execute_get_own_balance(self.data.token_address, self.data.token_id, "set_balance")

    @sp.sub_entry_point
    def sub_update_factor(self, unit):
        """sub entrypoint which updates the discount factor based on the received reward.

        Pre: storage.total_stake > 0
        Post: storage.last_balance = storage.current_balance
        Post: storage.disc_fator += ((storage.current_balance - storage.last_balance)*10**12)/storage.total_stake

        Args:
            unit (sp.unit): nothing
        """
        with sp.if_(self.data.total_stake > 0):
            reward = sp.as_nat(self.data.current_balance - self.data.last_balance)
            self.data.disc_factor += reward*Constants.PRECISION_FACTOR/self.data.total_stake
            self.data.last_balance = self.data.current_balance

    @sp.entry_point
    def set_balance(self, balance_of_response):
        """called by the token contract to set the apropriate balance.

        Args:
            balance_of_response (sp.nat): fa2 balance_of response used to set the current_balance
        """
        sp.set_type(balance_of_response, fa2.BalanceOf.get_response_type())
        #sp.verify(sp.sender==self.data.staking_token_address) no need, we know we are the last to update?
        with sp.match_cons(balance_of_response) as matched_balance_of_response:
            self.data.current_balance = matched_balance_of_response.head.balance

    @sp.entry_point
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
        self.data.sender = sp.sender
        self.fetch_reward_balance(sp.unit)
        sp.transfer(token_amount, sp.mutez(0), sp.self_entry_point(
            "internal_deposit"))

    @sp.entry_point
    def internal_deposit(self, token_amount):
        """internal entrypoint to deposit a certain token amount to the contract and calculate the stake and distribution factor.
        The stakes are discounted to the t=0 point in time, such that we store for every participant the t=0 stake. Also if the
        participant is ellegible for a tez distribution this call will send the ellegible amount to the sender.

        Pre: verify_internal()
        Post: sub_update_factor()
        Post: transfer token_amount tokens fron sp.sender to sp.self_address
        Post: storage.stakes[storage.sender] += token_amount*10**12/storage.disc_factor
        Post: send (storage.stakes[storage.sender]*storage.dist_factor - storage.dist_factors[storage.sender])/10**12) to storage.sender
        Post: storage.dist_factors[storage.sender] = self.data.dist_factor
        Post: storage.last_balance += token_amount
        Post: storage.total_stake += token_amount*10**12/storage.disc_factor
        Args:
            token_amount (sp.nat): the amount of tokens
        """
        sp.set_type(token_amount, sp.TNat)
        self.verify_internal(sp.unit)
        self.sub_update_factor(sp.unit)

        Utils.execute_token_transfer(self.data.token_address, self.data.sender, sp.self_address, self.data.token_id, token_amount)

        discounted_amount = sp.local("discounted_amount", token_amount*Constants.PRECISION_FACTOR/self.data.disc_factor)

        with sp.if_(self.data.stakes.contains(self.data.sender)):
            self.data.stakes[self.data.sender] += discounted_amount.value
        with sp.else_():
            self.data.stakes[self.data.sender] = discounted_amount.value
        with sp.if_(self.data.dist_factors.contains(self.data.sender) & (self.data.dist_factors[self.data.sender] < self.data.dist_factor)):
            ellegible_amount = self.data.stakes[self.data.sender] * sp.as_nat(self.data.dist_factor - self.data.dist_factors[self.data.sender])/Constants.PRECISION_FACTOR
            sp.send(self.data.sender, sp.utils.nat_to_mutez(ellegible_amount))

        self.data.dist_factors[self.data.sender] = self.data.dist_factor
        self.data.total_stake += discounted_amount.value
        self.data.last_balance += token_amount

    @sp.entry_point
    def withdraw(self):
        """withdraws the total stake and reward, if there was a tez payout that as well. The actual logic is in internal_withdraw.

        Post: storage.sender = sp.sender
        Post: fetch_reward_balance()
        Post: calls self.internal_withdraw
        """
        self.data.sender = sp.sender
        self.fetch_reward_balance(sp.unit)
        sp.transfer(sp.unit, sp.mutez(0), sp.self_entry_point(
            "internal_withdraw"))

    @sp.entry_point
    def internal_withdraw(self):
        """internal entrypoint to withdraw the own stake and any distributed tez reward the user is ellegible to receive.
        Pre: verify_internal()
        Pre: storage.stake.contains(storage.sender)
        Post: sub_update_factor()
        Post: transfer token_amount tokens fron sp.self_address to sp.sender
        Post: send (storage.stakes[storage.sender]*storage.dist_factor - storage.dist_factors[storage.sender])/10**12) to storage.sender
        Post: storage.last_balance -= storage.stakes[storage.sender]*storage.disc_factor/10**12
        Post: storage.total_stake -= storage.stakes[storage.sender]
        Post: del storage.stakes[storage.sender]
        Post: del storage.dist_factors[storage.sender]
        """
        self.verify_internal(sp.unit)
        self.sub_update_factor(sp.unit)

        current_amount = sp.local("current_amount", self.data.stakes[self.data.sender]*self.data.disc_factor/Constants.PRECISION_FACTOR)
        Utils.execute_token_transfer(self.data.token_address, sp.self_address, self.data.sender, self.data.token_id, current_amount.value)

        with sp.if_(self.data.dist_factors[self.data.sender] < self.data.dist_factor):
            ellegible_amount = self.data.stakes[self.data.sender] * sp.as_nat(self.data.dist_factor - self.data.dist_factors[self.data.sender])/Constants.PRECISION_FACTOR
            sp.send(self.data.sender, sp.utils.nat_to_mutez(ellegible_amount))

        self.data.last_balance = sp.as_nat(self.data.last_balance-current_amount.value)
        self.data.total_stake = sp.as_nat(self.data.total_stake-self.data.stakes[self.data.sender])

        del self.data.stakes[self.data.sender]
        del self.data.dist_factors[self.data.sender]

    @sp.entry_point
    def default(self):
        """entrypoint used to accept tez payments. Will distribute these evenly among the pool using the dist_factor methodology.
        Pre: storage.total_stake > 0
        Post: storage.dist_factor += sp.amount*10**12/storage.total_stake
        """
        self.data.dist_factor += sp.utils.mutez_to_nat(sp.amount)*Constants.PRECISION_FACTOR//self.data.total_stake

    @sp.entry_point
    def bailout(self, token_amount):
        """this entrypoint is used by the engine to bailout a specifc token_amount. As we require up-to-date values before doing so we actually have the logic in the "internal_bailout"
        Post: storage.sender = sp.sender
        Post: fetch_reward_balance()
        Post: call "internal_bailout"
        Args:
            token_amount (sp.nat): token amount to bail out
        """
        sp.set_type(token_amount, sp.TNat)
        self.data.sender = sp.sender
        self.fetch_reward_balance(sp.unit)
        sp.transfer(token_amount, sp.mutez(0), sp.self_entry_point("internal_bailout"))

    @sp.entry_point
    def internal_bailout(self, token_amount):
        """internal entrypoint to bailout the specific token amount. The amount is deduced from every pool participant relative to their stake.

        Pre: verify_internal()
        Pre: storage.total_stake > 0
        Pre: storage.sender == storage.engine_address
        Pre: storage.last_balance >= token_amount
        Post: disc_factor = (storage.last_balance - token_amount)*10**12/storage.total_stake
        Post: storage.last_balance = (storage.last_balance - token_amount)

        Args:
            token_amount (sp.nat): token amount to bail out
        """
        sp.set_type(token_amount, sp.TNat)
        self.verify_internal(sp.unit)

        sp.verify(self.data.sender == self.data.engine_address, Errors.NOT_ADMIN)
        sp.verify(self.data.last_balance >= token_amount, Errors.INSUFFICIENT_TOKEN_AMOUNT)

        self.data.disc_factor = sp.as_nat(self.data.last_balance-token_amount)*Constants.PRECISION_FACTOR/self.data.total_stake
        self.data.last_balance = sp.as_nat(self.data.last_balance-token_amount)

if __name__=="__main__":
    class DummyEngine(sp.Contract):
        def __init__(self, token_address):
            self.init(accrual_update_timestamp=sp.timestamp(0), pool_contract=Constants.DEFAULT_ADDRESS, token_address = token_address)

        @sp.entry_point
        def set_pool_contract(self, pool_contract): # need to have more than one entrypoint...
            self.data.pool_contract = pool_contract

        @sp.entry_point
        def update(self):
            Utils.execute_token_mint(self.data.token_address, self.data.pool_contract, sp.nat(0), sp.as_nat(sp.now-self.data.accrual_update_timestamp))
            self.data.accrual_update_timestamp = sp.now

    class DummyFA2(fa2.AdministrableFA2):

        @sp.entry_point
        def mint(self, recipient_token_amount):
            sp.set_type(recipient_token_amount, fa2.RecipientTokenAmount.get_type())
            with sp.if_(self.data.ledger.contains(fa2.LedgerKey.make(recipient_token_amount.token_id, recipient_token_amount.owner))):
                self.data.ledger[fa2.LedgerKey.make(recipient_token_amount.token_id, recipient_token_amount.owner)]+=recipient_token_amount.token_amount
            with sp.else_():
                self.data.ledger[fa2.LedgerKey.make(recipient_token_amount.token_id, recipient_token_amount.owner)]=recipient_token_amount.token_amount

        @sp.entry_point
        def burn(self, recipient_token_amount):
            sp.set_type(recipient_token_amount, fa2.RecipientTokenAmount.get_type())
            self.data.ledger[fa2.LedgerKey.make(recipient_token_amount.token_id, recipient_token_amount.owner)]=sp.as_nat(self.data.ledger[fa2.LedgerKey.make(recipient_token_amount.token_id, recipient_token_amount.owner)]-recipient_token_amount.token_amount)


    @sp.add_test(name="Savings Pool")
    def test():
        scenario = sp.test_scenario()
        scenario.add_flag("protocol", "florence")
        scenario.h1("Savings Pool Unit Test")
        scenario.table_of_contents()

        scenario.h2("Bootstrapping")
        token_id = sp.nat(0)

        administrator = sp.test_account("Administrator")
        alice = sp.test_account("Alice")
        bob = sp.test_account("Robert")
        dan = sp.test_account("Dan")

        scenario.show([administrator, alice, bob, dan])

        staking_token = DummyFA2({fa2.LedgerKey.make(0, administrator.address):sp.unit})
        tracker_engine = DummyEngine(staking_token.address)

        scenario += staking_token
        scenario += tracker_engine


        scenario += staking_token.set_token_metadata(token_id=token_id, token_info=sp.map()).run(sender=administrator)

        scenario += staking_token.mint(owner=alice.address, token_id=token_id, token_amount=1*Constants.PRECISION_FACTOR)
        scenario += staking_token.mint(owner=bob.address, token_id=token_id, token_amount=1*Constants.PRECISION_FACTOR)
        scenario += staking_token.mint(owner=dan.address, token_id=token_id, token_amount=1*Constants.PRECISION_FACTOR)

        savings_pool = SavingsPool(tracker_engine.address, staking_token.address, token_id)
        scenario += tracker_engine.set_pool_contract(savings_pool.address)
        scenario += savings_pool

        scenario.h2("Start staking")
        scenario += staking_token.update_operators([sp.variant('add_operator', sp.record(
            owner=alice.address, operator=savings_pool.address, token_id=token_id))]).run(sender=alice.address)
        scenario += savings_pool.deposit(1*Constants.PRECISION_FACTOR).run(sender=alice)

        scenario.h2("Claim after a week")
        now = sp.timestamp(Constants.SECONDS_PER_WEEK)

        scenario += savings_pool.withdraw().run(sender=alice, now=now)
        scenario.verify_equal(staking_token.data.ledger[fa2.LedgerKey.make(0, alice.address)], Constants.SECONDS_PER_WEEK + 1*Constants.PRECISION_FACTOR)

        alices_weight = Constants.SECONDS_PER_WEEK + 1*Constants.PRECISION_FACTOR
        total_weight = alices_weight

        scenario.p("Multiclaim yields nothing")
        scenario += savings_pool.withdraw().run(sender=alice, now=now, valid=False)
        scenario.verify_equal(staking_token.data.ledger[fa2.LedgerKey.make(0, alice.address)], Constants.SECONDS_PER_WEEK + 1*Constants.PRECISION_FACTOR)

        scenario.p("Put back what was withdrawed")
        scenario += savings_pool.deposit(Constants.SECONDS_PER_WEEK + 1*Constants.PRECISION_FACTOR).run(sender=alice, now=now)

        scenario.h2("Bob joins after a week")
        now = sp.timestamp(Constants.SECONDS_PER_WEEK*2)

        scenario += staking_token.update_operators([sp.variant('add_operator', sp.record(
            owner=bob.address, operator=savings_pool.address, token_id=token_id))]).run(sender=bob.address)
        scenario += savings_pool.deposit(1*Constants.PRECISION_FACTOR).run(sender=bob, now=now)

        alices_weight += Constants.SECONDS_PER_WEEK
        bobs_weight = 1*Constants.PRECISION_FACTOR
        total_weight = alices_weight + bobs_weight

        scenario.p("Both claim after 3 weeks")
        now = sp.timestamp(Constants.SECONDS_PER_WEEK*3)

        scenario += savings_pool.withdraw().run(sender=alice, now=now)
        scenario += savings_pool.withdraw().run(sender=bob, now=now)

        alices_weight += Constants.SECONDS_PER_WEEK*alices_weight//total_weight
        bobs_weight += Constants.SECONDS_PER_WEEK*bobs_weight//total_weight
        total_weight = alices_weight + bobs_weight

        scenario.verify_equal(staking_token.data.ledger[fa2.LedgerKey.make(0, alice.address)], alices_weight)
        scenario.verify_equal(staking_token.data.ledger[fa2.LedgerKey.make(0, bob.address)], bobs_weight)

        scenario.p("Put back what was withdrawed")
        scenario += savings_pool.deposit(alices_weight).run(sender=alice, now=now)
        scenario += savings_pool.deposit(bobs_weight).run(sender=bob, now=now)

        scenario.h2("Fixed rewards randomly flies in")
        scenario += staking_token.mint(owner=savings_pool.address, token_id=token_id, token_amount=1*Constants.PRECISION_FACTOR).run(now=now)

        alices_weight += Constants.PRECISION_FACTOR*alices_weight//total_weight
        bobs_weight += Constants.PRECISION_FACTOR*bobs_weight//total_weight
        total_weight = alices_weight + bobs_weight

        scenario.p("Dan joins late (not ellegible for fixed reward")
        now = sp.timestamp(Constants.SECONDS_PER_WEEK*4)
        scenario += staking_token.update_operators([sp.variant('add_operator', sp.record(
            owner=dan.address, operator=savings_pool.address, token_id=token_id))]).run(sender=dan.address)
        scenario += savings_pool.deposit(1*Constants.PRECISION_FACTOR).run(sender=dan, now=now)

        alices_weight += Constants.SECONDS_PER_WEEK*alices_weight//total_weight
        bobs_weight += Constants.SECONDS_PER_WEEK*bobs_weight//total_weight
        dans_weight = 1*Constants.PRECISION_FACTOR
        total_weight = alices_weight + bobs_weight + dans_weight

        scenario.p("All claim after 5 weeks")
        now = sp.timestamp(Constants.SECONDS_PER_WEEK*5)

        alices_weight += Constants.SECONDS_PER_WEEK*alices_weight//total_weight
        bobs_weight += Constants.SECONDS_PER_WEEK*bobs_weight//total_weight
        dans_weight += Constants.SECONDS_PER_WEEK*dans_weight//total_weight
        total_weight = alices_weight + bobs_weight + dans_weight

        scenario += savings_pool.withdraw().run(sender=alice, now=now)
        scenario += savings_pool.withdraw().run(sender=bob, now=now)
        scenario += savings_pool.withdraw().run(sender=dan, now=now)
        scenario.verify_equal(staking_token.data.ledger[fa2.LedgerKey.make(0, alice.address)], alices_weight+1)
        scenario.verify_equal(staking_token.data.ledger[fa2.LedgerKey.make(0, bob.address)], bobs_weight)
        scenario.verify_equal(staking_token.data.ledger[fa2.LedgerKey.make(0, dan.address)], dans_weight-1)

        scenario.p("Put back what was withdrawed")
        scenario += savings_pool.deposit(alices_weight+1).run(sender=alice, now=now)
        scenario += savings_pool.deposit(bobs_weight).run(sender=bob, now=now)
        scenario += savings_pool.deposit(dans_weight-1).run(sender=dan, now=now)


        scenario.h2("Dan leaves after 6 weeks and rejoins after 7")
        now = sp.timestamp(Constants.SECONDS_PER_WEEK*6)

        alices_weight += Constants.SECONDS_PER_WEEK*alices_weight//total_weight
        bobs_weight += Constants.SECONDS_PER_WEEK*bobs_weight//total_weight
        dans_weight += Constants.SECONDS_PER_WEEK*dans_weight//total_weight
        total_weight = alices_weight + bobs_weight

        scenario += savings_pool.withdraw().run(sender=dan, now=now)

        scenario.p("Rejoins")
        now = sp.timestamp(Constants.SECONDS_PER_WEEK*7)

        scenario += savings_pool.deposit(dans_weight-2).run(sender=dan, now=now)

        alices_weight += Constants.SECONDS_PER_WEEK*alices_weight//total_weight
        bobs_weight += Constants.SECONDS_PER_WEEK*bobs_weight//total_weight
        dans_weight = dans_weight-2
        total_weight = alices_weight + bobs_weight + dans_weight

        scenario += savings_pool.withdraw().run(sender=alice, now=now)
        scenario += savings_pool.withdraw().run(sender=bob, now=now)
        scenario += savings_pool.withdraw().run(sender=dan, now=now)

        scenario.verify_equal(staking_token.data.ledger[fa2.LedgerKey.make(0, alice.address)], alices_weight+1)
        scenario.verify_equal(staking_token.data.ledger[fa2.LedgerKey.make(0, bob.address)], bobs_weight)
        scenario.verify_equal(staking_token.data.ledger[fa2.LedgerKey.make(0, dan.address)], dans_weight-1)

        scenario.p("Put back what was withdrawed")
        scenario += savings_pool.deposit(alices_weight+1).run(sender=alice, now=now)
        scenario += savings_pool.deposit(bobs_weight).run(sender=bob, now=now)
        scenario += savings_pool.deposit(dans_weight-1).run(sender=dan, now=now)

        scenario.p("Bailout Executed")
        scenario += savings_pool.bailout(1*Constants.PRECISION_FACTOR).run(sender=tracker_engine.address, now=now)
        scenario += staking_token.burn(owner=savings_pool.address, token_id=token_id, token_amount=1*Constants.PRECISION_FACTOR).run(sender=savings_pool.address, now=now)
        scenario += savings_pool.default().run(sender=staking_token.address, amount=sp.tez(10), now=now)

        alices_weight -= 1*Constants.PRECISION_FACTOR*alices_weight//total_weight
        bobs_weight -= 1*Constants.PRECISION_FACTOR*bobs_weight//total_weight
        dans_weight -= 1*Constants.PRECISION_FACTOR*dans_weight//total_weight
        total_weight = alices_weight + bobs_weight + dans_weight

        #now = sp.timestamp(Constants.SECONDS_PER_WEEK*7)

        #alices_weight += Constants.SECONDS_PER_WEEK*alices_weight//total_weight
        #bobs_weight += Constants.SECONDS_PER_WEEK*bobs_weight//total_weight
        #dans_weight += Constants.SECONDS_PER_WEEK*dans_weight//total_weight
        #total_weight = alices_weight + bobs_weight + dans_weight

        scenario += savings_pool.withdraw().run(sender=alice, now=now)
        scenario.show(sp.tez(10)-sp.split_tokens(sp.tez(10), alices_weight, total_weight))
        scenario.show(savings_pool.balance)
        estimated_contract_balance = sp.tez(10)-sp.split_tokens(sp.tez(10), alices_weight, total_weight)
        scenario.verify_equal(savings_pool.balance, estimated_contract_balance)
        scenario += savings_pool.withdraw().run(sender=bob, now=now)
        estimated_contract_balance -= sp.split_tokens(sp.tez(10), bobs_weight, total_weight)
        scenario.verify_equal(savings_pool.balance, estimated_contract_balance)
        scenario += savings_pool.withdraw().run(sender=dan, now=now)
        estimated_contract_balance -= sp.split_tokens(sp.tez(10), dans_weight, total_weight)
        scenario.verify_equal(savings_pool.balance, estimated_contract_balance + sp.mutez(1)) # flooring error of 2 mutez...

        scenario.verify_equal(staking_token.data.ledger[fa2.LedgerKey.make(0, alice.address)], alices_weight+4)
        scenario.verify_equal(staking_token.data.ledger[fa2.LedgerKey.make(0, bob.address)], bobs_weight+1)
        scenario.verify_equal(staking_token.data.ledger[fa2.LedgerKey.make(0, dan.address)], dans_weight)
        scenario.verify_equal(savings_pool.balance, sp.mutez(2)) # flooring error of 2 mutez...
