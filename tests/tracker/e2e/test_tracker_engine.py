from pytezos.operation.result import OperationResult


from pytezos import pytezos
import settings

pytezos_alice_client = pytezos.using(key=settings.ALICE_KEY, shell=settings.SHELL)
pytezos_dan_client = pytezos.using(key=settings.DAN_KEY, shell=settings.SHELL)


def test_tracker_engine(tracker_engine_address, viewer_address):
    print("Do the mint flow")
    print("1. create the vault")
    tracker_engine_contract = pytezos_alice_client.contract(tracker_engine_address)
    tracker_engine_contract.create_vault(
        baker=None, contract_address_callback=f"{viewer_address}%set_address"
    ).send(min_confirmations=1)
    view_contract = pytezos_alice_client.contract(f"{viewer_address}")
    vault_address = view_contract.storage()["address"]

    print("2. fund the vault")
    pytezos_alice_client.transaction(destination=vault_address, amount=2000000).send(
        min_confirmations=1
    )

    print("3. mint the tokens (after setting a price of 5)")
    tracker_engine_contract.mint(5 * 10**12).send(min_confirmations=1)

    print("4. transfer minted token to alice's account")
    token_id = tracker_engine_contract.storage["token_id"]()
    token_contract = pytezos_alice_client.contract(
        tracker_engine_contract.storage["token_contract"]()
    )
    token_contract.transfer(
        [
            {
                "from_": pytezos_alice_client.key.public_key_hash(),
                "txs": [
                    {
                        "to_": pytezos_alice_client.key.public_key_hash(),
                        "token_id": token_id,
                        "amount": 2 * 10**11,
                    }
                ],
            }
        ]
    ).send(min_confirmations=1)

    print("5. claim governance tokens")
    stake_manager_contract = pytezos_alice_client.contract(
        tracker_engine_contract.storage["governance_token_contract"]()
    )
    governance_token_contract = pytezos_alice_client.contract(
        stake_manager_contract.storage["governance_token_contract"]()
    )
    governance_token_contract.claim().send(min_confirmations=1)

    print("6. stake governance tokens for reward")
    governance_token_contract.update_operators(
        [
            {
                "add_operator": {
                    "owner": pytezos_alice_client.key.public_key_hash(),
                    "operator": tracker_engine_contract.storage[
                        "reward_pool_contract"
                    ](),
                    "token_id": token_id,
                }
            }
        ]
    ).send(min_confirmations=1)
    staking_pool_contract = pytezos_alice_client.contract(
        tracker_engine_contract.storage["reward_pool_contract"]()
    )
    staking_pool_contract.deposit(1**9).send(min_confirmations=1)

    print("7. claim rewards")
    staking_pool_contract.claim().send(min_confirmations=1)

    print("8. withdraw stake")
    staking_pool_contract.withdraw().send(min_confirmations=1)

    print("9. put money in the savings account")
    savings_pool_contract = pytezos_alice_client.contract(
        tracker_engine_contract.storage["savings_pool_contract"]()
    )
    token_contract.update_operators(
        [
            {
                "add_operator": {
                    "owner": pytezos_alice_client.key.public_key_hash(),
                    "operator": tracker_engine_contract.storage[
                        "savings_pool_contract"
                    ](),
                    "token_id": token_id,
                }
            }
        ]
    ).send(min_confirmations=1)
    savings_pool_contract.deposit(10**12).send(min_confirmations=1)

    print("10. savings account withdraw")
    savings_pool_contract.withdraw().send(min_confirmations=1)

    print("11. put back to savings")
    savings_pool_contract.deposit(10**12).send(min_confirmations=1)

    print("13. advertise intent")
    options_contract = pytezos_alice_client.contract(
        tracker_engine_contract.storage["options_contract"]()
    )
    # options_contract.remove_intent().send(min_confirmations=1)
    token_contract.update_operators(
        [
            {
                "add_operator": {
                    "owner": pytezos_alice_client.key.public_key_hash(),
                    "operator": tracker_engine_contract.storage["options_contract"](),
                    "token_id": token_id,
                }
            }
        ]
    ).send(min_confirmations=1)
    options_contract.advertise_intent(10**11).send(min_confirmations=1)

    print("14. fulfill intent")
    options_contract.fulfill_intent(
        pytezos_alice_client.key.public_key_hash()
    ).with_amount(10000).send()


if __name__ == "__main__":
    test_tracker_engine(settings.TRACKER_ENGINE_ADDRESS, settings.VIEWER_ADDRESS)
