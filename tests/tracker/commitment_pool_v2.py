import smartpy as sp

import utils.constants as Constants
from utils.fa2 import AdministrableFA2, RecipientTokenAmount, LedgerKey, Transfer
from utils.contract_utils import Ratio

from contracts.tracker.commitment_pool_v2 import CommitmentPool, Stake, DEFAULT_TOKEN_INFO


def execute_fa2_token_transfer(token_address, to_, token_id, amount):
    """
    Create an operation that once executed will execute an FA2 transfer, sending from `token_address`
    contract, `value` amount of tokens of type `token_id` from the sender of the operation to the `to_` account.

    Args:
        token_address (sp.address): Contract from which to transfer the amount.
        to_ (sp.address): The receiver of the funds/amount.
        token_id (sp.nat): The id of the token to be transfered.
        value (sp.nat): Token amount to be transfered.

    Returns:
        sp.TOperation: The operation to transfer the given token amount from the sender to the given receiver.
    """
    transfer_token_contract = sp.contract(
        Transfer.get_batch_type(), token_address, entry_point="transfer"
    ).open_some()
    transfer_payload = [
        Transfer.item(sp.self_address, [sp.record(to_=to_, token_id=token_id, amount=amount)])
    ]

    return sp.transfer_operation(transfer_payload, sp.mutez(0), transfer_token_contract)


class DummyFA2(AdministrableFA2):
    @sp.entry_point
    def mint(self, recipient_token_amount):
        sp.set_type(recipient_token_amount, RecipientTokenAmount.get_type())
        with sp.if_(
            self.data.ledger.contains(
                LedgerKey.make(recipient_token_amount.token_id, recipient_token_amount.owner)
            )
        ):
            self.data.ledger[
                LedgerKey.make(recipient_token_amount.token_id, recipient_token_amount.owner)
            ] += recipient_token_amount.token_amount
        with sp.else_():
            self.data.ledger[
                LedgerKey.make(recipient_token_amount.token_id, recipient_token_amount.owner)
            ] = recipient_token_amount.token_amount

    @sp.entry_point
    def burn(self, recipient_token_amount):
        sp.set_type(recipient_token_amount, RecipientTokenAmount.get_type())
        self.data.ledger[
            LedgerKey.make(recipient_token_amount.token_id, recipient_token_amount.owner)
        ] = sp.as_nat(
            self.data.ledger[
                LedgerKey.make(recipient_token_amount.token_id, recipient_token_amount.owner)
            ]
            - recipient_token_amount.token_amount
        )


@sp.add_test(name="CommitmentPool")
def test():
    scenario = sp.test_scenario()
    scenario.h1("Commitment Pool Test")
    scenario.table_of_contents()

    scenario.h2("Bootstrapping")

    administrator = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob = sp.test_account("Robert")
    dan = sp.test_account("Dan")

    source = sp.test_account("Source")

    scenario.show([administrator, alice, bob, dan, source])

    token_id = sp.nat(0)
    epoch_length = 4 * 7 * 24 * 60 * 60
    max_cooldown_duration = 32 * epoch_length
    max_withdraw_delay = 2 * 24 * 60 * 60  # 2 days

    # Token Metadatas (stake metadata)
    stake_0_metadata = sp.record(token_id=0, token_info={"": sp.bytes("0x00")})
    stake_1_metadata = sp.record(token_id=1, token_info={"": sp.bytes("0x01")})
    stake_2_metadata = sp.record(token_id=2, token_info={"": sp.bytes("0x02")})

    staking_token = DummyFA2({LedgerKey.make(token_id, administrator.address): sp.unit})
    scenario += staking_token
    scenario += staking_token.set_token_metadata(token_id=token_id, token_info=sp.map()).run(
        sender=administrator
    )
    staking_token_key = LedgerKey.make(0, staking_token.address)

    commitment_pool = CommitmentPool(
        administrators=sp.big_map(l={administrator.address: 1}),
        allowed_sources=sp.big_map(l={source.address: sp.unit}),
        max_cooldown_duration=max_cooldown_duration,
        epoch_length=epoch_length,
        max_withdraw_delay=max_withdraw_delay,
        kicker_reward_ratio=Ratio.make(10, 100),  # 10%
        token_address=staking_token.address,
        token_id=sp.nat(0),
    )
    scenario += commitment_pool

    initial_balance = 1000 * Constants.PRECISION_FACTOR
    scenario += staking_token.mint(
        owner=alice.address, token_id=token_id, token_amount=initial_balance
    )
    scenario += staking_token.mint(
        owner=bob.address, token_id=token_id, token_amount=initial_balance
    )
    scenario += staking_token.mint(
        owner=dan.address, token_id=token_id, token_amount=initial_balance
    )
    scenario += staking_token.mint(
        owner=administrator.address, token_id=token_id, token_amount=initial_balance
    )
    scenario += staking_token.update_operators(
        [
            sp.variant(
                "add_operator",
                sp.record(
                    owner=alice.address,
                    operator=commitment_pool.address,
                    token_id=token_id,
                ),
            )
        ]
    ).run(sender=alice.address)
    scenario += staking_token.update_operators(
        [
            sp.variant(
                "add_operator",
                sp.record(
                    owner=dan.address,
                    operator=commitment_pool.address,
                    token_id=token_id,
                ),
            )
        ]
    ).run(sender=dan.address)
    scenario += staking_token.update_operators(
        [
            sp.variant(
                "add_operator",
                sp.record(
                    owner=bob.address,
                    operator=commitment_pool.address,
                    token_id=token_id,
                ),
            )
        ]
    ).run(sender=bob.address)

    alice_ledger_key = LedgerKey.make(0, alice.address)
    bob_ledger_key = LedgerKey.make(0, bob.address)
    dan_ledger_key = LedgerKey.make(0, dan.address)
    commitment_pool_key = LedgerKey.make(0, commitment_pool.address)

    scenario.h2("Commitments")
    # Alice tries to commit, but can't because she is not staking enough.
    scenario += commitment_pool.commit(
        sp.record(
            amount=99_999_999_999,
            cooldown_duration=max_cooldown_duration,
            stake_id=sp.none,
        )
    ).run(sender=alice.address, valid=False)

    # Alice commits 100 YOUs for the full period.
    scenario += commitment_pool.commit(
        sp.record(
            amount=100 * Constants.PRECISION_FACTOR,
            cooldown_duration=max_cooldown_duration,
            stake_id=sp.none,
        )
    ).run(sender=alice.address)
    alice_stake_id = 0
    scenario.verify_equal(commitment_pool.data.ledger[alice_stake_id], alice.address)
    scenario.verify_equal(commitment_pool.data.token_metadata[alice_stake_id], sp.record(token_id=0, token_info=DEFAULT_TOKEN_INFO))
    scenario.verify_equal(
        commitment_pool.data.stakes[alice_stake_id],
        Stake.make(
            amount=100 * Constants.PRECISION_FACTOR,
            reward_weight=100 * Constants.PRECISION_FACTOR,
            bailout_weight=100 * Constants.PRECISION_FACTOR,
            accumulated_rewards=0,
            accumulated_bailouts=0,
            cooldown_duration=max_cooldown_duration,
            cooldown_start_timestamp=sp.none,
            reward_factor=Constants.PRECISION_FACTOR,
            bailout_factor=Constants.PRECISION_FACTOR,
        ),
    )
    scenario.verify_equal(commitment_pool.data.stake_id_counter, 1)
    scenario.verify_equal(
        commitment_pool.data.total_reward_stake_weight, 100 * Constants.PRECISION_FACTOR
    )
    scenario.verify_equal(
        commitment_pool.data.total_bailout_stake_weight,
        100 * Constants.PRECISION_FACTOR,
    )

    # Alice commits another 100 YOUs for the full period for the same stake.
    scenario += commitment_pool.commit(
        sp.record(
            amount=100 * Constants.PRECISION_FACTOR,
            cooldown_duration=max_cooldown_duration,
            stake_id=sp.some(alice_stake_id),
        )
    ).run(sender=alice.address)
    scenario.verify_equal(commitment_pool.data.ledger[alice_stake_id], alice.address)
    scenario.verify_equal(commitment_pool.data.token_metadata[alice_stake_id], sp.record(token_id=0, token_info=DEFAULT_TOKEN_INFO))
    scenario.verify_equal(
        commitment_pool.data.stakes[alice_stake_id],
        Stake.make(
            amount=200 * Constants.PRECISION_FACTOR,
            reward_weight=200 * Constants.PRECISION_FACTOR,
            bailout_weight=200 * Constants.PRECISION_FACTOR,
            accumulated_rewards=0,
            accumulated_bailouts=0,
            cooldown_duration=max_cooldown_duration,
            cooldown_start_timestamp=sp.none,
            reward_factor=commitment_pool.data.reward_factor,
            bailout_factor=commitment_pool.data.bailout_factor,
        ),
    )
    scenario.verify_equal(commitment_pool.data.stake_id_counter, 1)
    scenario.verify_equal(
        commitment_pool.data.total_reward_stake_weight, 200 * Constants.PRECISION_FACTOR
    )
    scenario.verify_equal(
        commitment_pool.data.total_bailout_stake_weight,
        200 * Constants.PRECISION_FACTOR,
    )

    # Alice commits another 100 YOUs for a lower period for the same stake (should fail)
    scenario += commitment_pool.commit(
        sp.record(
            amount=100 * Constants.PRECISION_FACTOR,
            cooldown_duration=sp.as_nat(max_cooldown_duration - 1),
            stake_id=sp.some(alice_stake_id),
        )
    ).run(sender=alice.address, valid=False)

    # Alice commits 100 YOUs to a stake id inexistent. (should fail)
    scenario += commitment_pool.commit(
        sp.record(
            amount=100 * Constants.PRECISION_FACTOR,
            cooldown_duration=max_cooldown_duration,
            stake_id=sp.some(1),
        )
    ).run(sender=alice.address, valid=False)

    # Bob tries commit 100 YOUs to a stake he does not own (should fail)
    scenario += commitment_pool.commit(
        sp.record(
            amount=100 * Constants.PRECISION_FACTOR,
            cooldown_duration=max_cooldown_duration,
            stake_id=sp.some(alice_stake_id),
        )
    ).run(sender=bob.address, valid=False)

    # Reward of 20 YOUs come in.
    scenario += staking_token.mint(
        owner=commitment_pool.address,
        token_id=token_id,
        token_amount=20 * Constants.PRECISION_FACTOR,
    ).run(sender=administrator.address)

    # Bob tries to commit 100 YOUs for a longer period than max period (should fail)
    scenario += commitment_pool.commit(
        sp.record(
            amount=100 * Constants.PRECISION_FACTOR,
            cooldown_duration=max_cooldown_duration + 1,
            stake_id=sp.none,
        )
    ).run(sender=bob.address, valid=False)

    # Bob commits 100 YOUs for half the max period.
    scenario += commitment_pool.commit(
        sp.record(
            amount=100 * Constants.PRECISION_FACTOR,
            cooldown_duration=max_cooldown_duration // 2,
            stake_id=sp.none,
        )
    ).run(sender=bob.address)
    bob_stake_id = 1
    scenario.verify_equal(commitment_pool.data.ledger[bob_stake_id], bob.address)
    scenario.verify_equal(commitment_pool.data.token_metadata[bob_stake_id], sp.record(token_id=1, token_info=DEFAULT_TOKEN_INFO))
    scenario.verify_equal(
        commitment_pool.data.stakes[bob_stake_id],
        Stake.make(
            amount=100 * Constants.PRECISION_FACTOR,
            reward_weight=50 * Constants.PRECISION_FACTOR,
            bailout_weight=50 * Constants.PRECISION_FACTOR,
            accumulated_rewards=0,
            accumulated_bailouts=0,
            cooldown_duration=max_cooldown_duration // 2,
            cooldown_start_timestamp=sp.none,
            reward_factor=220 * Constants.PRECISION_FACTOR // 200,
            bailout_factor=Constants.PRECISION_FACTOR,
        ),
    )
    scenario.verify_equal(commitment_pool.data.stake_id_counter, 2)
    scenario.verify_equal(
        commitment_pool.data.total_reward_stake_weight, 250 * Constants.PRECISION_FACTOR
    )
    scenario.verify_equal(
        commitment_pool.data.total_bailout_stake_weight,
        250 * Constants.PRECISION_FACTOR,
    )

    # Dan commits 100 YOUs for the max period after the reward came in so he is not entitled to it.
    scenario += commitment_pool.commit(
        sp.record(
            amount=100 * Constants.PRECISION_FACTOR,
            cooldown_duration=max_cooldown_duration,
            stake_id=sp.none,
        )
    ).run(sender=dan.address)
    dan_stake_id = 2
    scenario.verify_equal(commitment_pool.data.ledger[dan_stake_id], dan.address)
    scenario.verify_equal(commitment_pool.data.token_metadata[dan_stake_id], sp.record(token_id=2, token_info=DEFAULT_TOKEN_INFO))
    scenario.verify_equal(
        commitment_pool.data.stakes[dan_stake_id],
        Stake.make(
            amount=100 * Constants.PRECISION_FACTOR,
            reward_weight=100 * Constants.PRECISION_FACTOR,
            bailout_weight=100 * Constants.PRECISION_FACTOR,
            accumulated_rewards=0,
            accumulated_bailouts=0,
            cooldown_duration=max_cooldown_duration,
            cooldown_start_timestamp=sp.none,
            reward_factor=11 * Constants.PRECISION_FACTOR // 10,
            bailout_factor=Constants.PRECISION_FACTOR,
        ),
    )
    scenario.verify_equal(commitment_pool.data.stake_id_counter, 3)
    scenario.verify_equal(
        commitment_pool.data.total_reward_stake_weight, 350 * Constants.PRECISION_FACTOR
    )
    scenario.verify_equal(
        commitment_pool.data.total_bailout_stake_weight,
        350 * Constants.PRECISION_FACTOR,
    )

    scenario.h2("Modifying token metadata")
    # Alice tries to change metadata, but can't because is not an allowed source.
    scenario += commitment_pool.set_token_metadata(
        sp.record(
            token_id=0,
            token_info={"": sp.bytes("0x5468697320697320416C6963652773207374616B652E")} # This is Alice's stake.
        )
    ).run(sender=alice.address, valid=False)

    # Source tries to set the metadata for stake 3, but failse because it does not exist.
    scenario += commitment_pool.set_token_metadata(
        sp.record(
            token_id=3,
            token_info={"": sp.bytes("0x5468697320697320416C6963652773207374616B652E")} # This is Alice's stake.
        )
    ).run(sender=source.address, valid=False)

    # Source sets the metadata for stake 0.
    scenario += commitment_pool.set_token_metadata(
        sp.record(
            token_id=0,
            token_info={"": sp.bytes("0x5468697320697320416C6963652773207374616B652E")} # This is Alice's stake.
        )
    ).run(sender=source.address)
    scenario.verify_equal(
        commitment_pool.data.token_metadata[0],
        sp.record(
            token_id=0,
            token_info={"": sp.bytes("0x5468697320697320416C6963652773207374616B652E")} # This is Alice's stake.
        ))

    # Alice tries to remove metadata for token 0, but can't because it is not an allowed source.
    scenario += commitment_pool.remove_token_metadata(alice_stake_id).run(sender=alice.address, valid=False)

    # Source tries to remove metadata for token 0, but can't because it is still in use.
    scenario += commitment_pool.remove_token_metadata(alice_stake_id).run(sender=source.address, valid=False)

    scenario.h2("Start cooldowns")
    # Alice tries to enter in cooldown a stake id invalid.
    scenario += commitment_pool.enter_cooldown(commitment_pool.data.stake_id_counter + 1).run(
        sender=alice.address, valid=False
    )
    # Alice tries to enter in cooldown a stake id she does not own.
    scenario += commitment_pool.enter_cooldown(bob_stake_id).run(sender=alice.address, valid=False)
    # Alice enters in cooldown
    scenario += commitment_pool.enter_cooldown(alice_stake_id).run(
        sender=alice.address, now=sp.timestamp(1)
    )
    scenario.verify_equal(
        commitment_pool.data.stakes[alice_stake_id],
        Stake.make(
            amount=200 * Constants.PRECISION_FACTOR,
            reward_weight=100 * Constants.PRECISION_FACTOR,
            bailout_weight=200 * Constants.PRECISION_FACTOR,
            accumulated_rewards=20 * Constants.PRECISION_FACTOR,
            accumulated_bailouts=0,
            cooldown_duration=max_cooldown_duration,
            cooldown_start_timestamp=sp.some(sp.timestamp(1)),
            reward_factor=220 * Constants.PRECISION_FACTOR // 200,
            bailout_factor=Constants.PRECISION_FACTOR,
        ),
    )
    scenario.verify_equal(
        commitment_pool.data.total_reward_stake_weight, 250 * Constants.PRECISION_FACTOR
    )
    scenario.verify_equal(
        commitment_pool.data.total_bailout_stake_weight,
        350 * Constants.PRECISION_FACTOR,
    )

    # Alice tries to enter in cooldown again (should fail)
    scenario += commitment_pool.enter_cooldown(alice_stake_id).run(
        sender=alice.address, valid=False
    )

    scenario.h2("Bailouts")

    # Lambda for the bailout
    def token_transfer(amount):
        sp.set_type(amount, sp.TNat)
        sp.result(
            sp.list(
                [
                    execute_fa2_token_transfer(
                        commitment_pool.data.token_address,
                        administrator.address,
                        commitment_pool.data.token_id,
                        amount,
                    )
                ]
            )
        )

    scenario.show(sp.build_lambda(token_transfer))

    # Alice tries to execute a bailout of 35 YOUs (should fail)
    scenario += commitment_pool.bailout(
        sp.record(amount=35 * Constants.PRECISION_FACTOR, execution_lambda=token_transfer)
    ).run(sender=alice.address, valid=False)

    # Admin executes a bailout of 35 YOUs
    scenario += commitment_pool.bailout(
        sp.record(amount=35 * Constants.PRECISION_FACTOR, execution_lambda=token_transfer)
    ).run(sender=administrator.address)
    scenario.verify_equal(
        commitment_pool.data.bailout_factor, 11 * Constants.PRECISION_FACTOR // 10
    )
    scenario.verify_equal(
        staking_token.data.ledger[commitment_pool_key], 385 * Constants.PRECISION_FACTOR
    )

    # Reward of 25 YOUs come in
    scenario += staking_token.mint(
        owner=commitment_pool.address,
        token_id=token_id,
        token_amount=25 * Constants.PRECISION_FACTOR,
    ).run(sender=administrator.address)

    scenario.h2("Recommits")
    # Alice tries to recommit an innexistend stake id (shoul fail)
    scenario += commitment_pool.recommit(commitment_pool.data.stake_id_counter + 1).run(
        sender=alice.address, valid=False
    )
    # Bob tries to recommit alice's stake (should fail)
    scenario += commitment_pool.recommit(alice_stake_id).run(sender=bob.address, valid=False)
    # Bob tries to recommit his stake which is not in cooldown (should fail)
    scenario += commitment_pool.recommit(bob_stake_id).run(sender=bob.address, valid=False)
    # Alice recommits her stake and accumulates half the rewards, but pays the bailout in full.
    scenario += commitment_pool.recommit(alice_stake_id).run(sender=alice.address)
    scenario.verify_equal(
        commitment_pool.data.stakes[alice_stake_id],
        Stake.make(
            amount=200 * Constants.PRECISION_FACTOR,
            reward_weight=200 * Constants.PRECISION_FACTOR,
            bailout_weight=200 * Constants.PRECISION_FACTOR,
            accumulated_rewards=30 * Constants.PRECISION_FACTOR,
            accumulated_bailouts=20 * Constants.PRECISION_FACTOR,
            cooldown_duration=max_cooldown_duration,
            cooldown_start_timestamp=sp.none,
            reward_factor=12 * Constants.PRECISION_FACTOR // 10,
            bailout_factor=11 * Constants.PRECISION_FACTOR // 10,
        ),
    )
    scenario.verify_equal(
        commitment_pool.data.total_reward_stake_weight, 350 * Constants.PRECISION_FACTOR
    )
    scenario.verify_equal(
        commitment_pool.data.total_bailout_stake_weight,
        350 * Constants.PRECISION_FACTOR,
    )
    scenario.verify_equal(commitment_pool.data.reward_factor, 12 * Constants.PRECISION_FACTOR // 10)
    scenario.verify_equal(
        commitment_pool.data.bailout_factor, 11 * Constants.PRECISION_FACTOR // 10
    )

    scenario.h2("Withdraw")
    # Setup for withdraw
    scenario += commitment_pool.enter_cooldown(alice_stake_id).run(sender=alice.address)
    scenario += commitment_pool.enter_cooldown(bob_stake_id).run(sender=bob.address)
    scenario.verify_equal(
        commitment_pool.data.total_reward_stake_weight, 225 * Constants.PRECISION_FACTOR
    )
    scenario.verify_equal(
        commitment_pool.data.total_bailout_stake_weight,
        350 * Constants.PRECISION_FACTOR,
    )

    # Reward of 45 YOUs come in (20%)
    scenario += staking_token.mint(
        owner=commitment_pool.address,
        token_id=token_id,
        token_amount=45 * Constants.PRECISION_FACTOR,
    ).run(sender=administrator.address)

    # Admin executes a bailout of 35 YOUs (10%)
    scenario += commitment_pool.bailout(
        sp.record(amount=35 * Constants.PRECISION_FACTOR, execution_lambda=token_transfer)
    ).run(sender=administrator.address)

    # Alice tries to withdraw an inexisting stake (should fail)
    scenario += commitment_pool.withdraw(commitment_pool.data.stake_id_counter + 1).run(
        sender=alice.address, valid=False, now=sp.timestamp(max_cooldown_duration + 1)
    )
    # Alice tries to withdraw a stake she does not own (should fail)
    scenario += commitment_pool.withdraw(bob_stake_id).run(
        sender=alice.address,
        valid=False,
        now=sp.timestamp(max_cooldown_duration // 2 + 1),
    )
    # Dan tries to withdraw his stake (not in cooldown, should fail)
    scenario += commitment_pool.withdraw(dan_stake_id).run(
        sender=dan.address, valid=False, now=sp.timestamp(max_cooldown_duration + 1)
    )
    # Alice tries to withdraw her stake to soon (should fail)
    scenario += commitment_pool.withdraw(alice_stake_id).run(
        sender=alice.address, valid=False, now=sp.timestamp(max_cooldown_duration - 1)
    )

    # Bob withdraws his stake.
    scenario += commitment_pool.withdraw(bob_stake_id).run(
        sender=bob.address, now=sp.timestamp(max_cooldown_duration // 2 + 1)
    )
    scenario.verify(~commitment_pool.data.ledger.contains(bob_stake_id))
    scenario.verify(~commitment_pool.data.stakes.contains(bob_stake_id))
    scenario.verify_equal(
        commitment_pool.data.total_reward_stake_weight, 200 * Constants.PRECISION_FACTOR
    )
    scenario.verify_equal(
        commitment_pool.data.total_bailout_stake_weight,
        300 * Constants.PRECISION_FACTOR,
    )
    # while in the pool bob received 10 YOUs and payed 10 YOUs
    scenario.verify_equal(staking_token.data.ledger[bob_ledger_key], initial_balance)
    scenario.verify_equal(
        staking_token.data.ledger[commitment_pool_key], 320 * Constants.PRECISION_FACTOR
    )

    # Alice withdraws her stake.
    scenario += commitment_pool.withdraw(alice_stake_id).run(
        sender=alice.address, now=sp.timestamp(max_cooldown_duration + 1)
    )
    scenario.verify_equal(commitment_pool.data.ledger.contains(alice_stake_id), False)
    scenario.verify_equal(commitment_pool.data.stakes.contains(alice_stake_id), False)
    scenario.verify_equal(
        commitment_pool.data.total_reward_stake_weight, 100 * Constants.PRECISION_FACTOR
    )
    scenario.verify_equal(
        commitment_pool.data.total_bailout_stake_weight,
        100 * Constants.PRECISION_FACTOR,
    )
    # while in the pool alice received 20+10+20 YOUs and payed 20+20 YOUs
    scenario.verify_equal(
        staking_token.data.ledger[alice_ledger_key],
        initial_balance + 10 * Constants.PRECISION_FACTOR,
    )
    scenario.verify_equal(
        staking_token.data.ledger[commitment_pool_key], 110 * Constants.PRECISION_FACTOR
    )

    scenario += commitment_pool.remove_token_metadata(alice_stake_id).run(sender=source.address)
    scenario.verify_equal(
        commitment_pool.data.token_metadata.contains(alice_stake_id), False
    )

    scenario.h2("Kickout")
    # Alice tries to kickout Dan stake (not in cooldown, should fail)
    scenario += commitment_pool.kickout(dan_stake_id).run(
        sender=alice.address,
        valid=False,
        now=sp.timestamp(max_cooldown_duration + max_withdraw_delay + 1),
    )
    # Setup for kickout
    scenario += commitment_pool.enter_cooldown(dan_stake_id).run(
        sender=dan.address, now=sp.timestamp(0)
    )
    scenario.verify_equal(
        commitment_pool.data.total_reward_stake_weight, 50 * Constants.PRECISION_FACTOR
    )
    scenario.verify_equal(
        commitment_pool.data.total_bailout_stake_weight,
        100 * Constants.PRECISION_FACTOR,
    )

    # Reward of 5 YOUs come in (10%)
    scenario += staking_token.mint(
        owner=commitment_pool.address,
        token_id=token_id,
        token_amount=5 * Constants.PRECISION_FACTOR,
    ).run(sender=administrator.address)
    # Admin executes a bailout of 10 YOUs (20%)
    scenario += commitment_pool.bailout(
        sp.record(amount=10 * Constants.PRECISION_FACTOR, execution_lambda=token_transfer)
    ).run(sender=administrator.address)
    # Reward of 5 YOUs come in (10%)
    scenario += staking_token.mint(
        owner=commitment_pool.address,
        token_id=token_id,
        token_amount=5 * Constants.PRECISION_FACTOR,
    ).run(sender=administrator.address)

    # Alice tries to kickout an inexisting stake (should fail)
    scenario += commitment_pool.kickout(commitment_pool.data.stake_id_counter + 1).run(
        sender=alice.address,
        valid=False,
        now=sp.timestamp(max_cooldown_duration + max_withdraw_delay + 1),
    )
    # Alice tries to kickout Dan stake to soon (should fail)
    scenario += commitment_pool.kickout(dan_stake_id).run(
        sender=alice.address,
        valid=False,
        now=sp.timestamp(max_cooldown_duration + max_withdraw_delay - 1),
    )

    # Alice kickouts Dan stake
    scenario += commitment_pool.kickout(dan_stake_id).run(
        sender=alice.address,
        now=sp.timestamp(max_cooldown_duration + max_withdraw_delay + 1),
    )

    scenario.verify_equal(commitment_pool.data.ledger.contains(dan_stake_id), False)
    scenario.verify_equal(commitment_pool.data.stakes.contains(dan_stake_id), False)
    scenario.verify_equal(commitment_pool.data.total_reward_stake_weight, 0)
    scenario.verify_equal(commitment_pool.data.total_bailout_stake_weight, 0)
    # while in the pool dan received 10+20+5+5 YOUs (but 10% goes to alice) and payed 10+10+10 YOUs
    # so in total dan received 90% of 40=36 YOUs and payed 30 YOUs
    scenario.verify_equal(
        staking_token.data.ledger[dan_ledger_key],
        initial_balance + 6 * Constants.PRECISION_FACTOR,
    )
    scenario.verify_equal(
        staking_token.data.ledger[alice_ledger_key],
        initial_balance + 14 * Constants.PRECISION_FACTOR,
    )
