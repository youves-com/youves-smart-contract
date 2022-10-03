import smartpy as sp

from utils.viewer import Viewer
import utils.constants as Constants
from contracts.oracle.signed_payload_oracle import SignedPayloadOracle, Price


@sp.add_test(name="Signed Payload Oracle Test")
def test():
    scenario = sp.test_scenario()
    scenario.h1("Signed Payload Oracle")
    scenario.h2("Bootstrapping")
    administrator = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob = sp.test_account("Robert")
    dan = sp.test_account("Dan")
    scenario.h2("Accounts")
    scenario.show([alice, bob, dan])

    certificate_1 = sp.bytes("0x01")
    certificate_2 = sp.bytes("0x02")
    certificate_3 = sp.bytes("0x03")

    signed_payload_oracle = SignedPayloadOracle(
        {alice.public_key: sp.unit, bob.public_key: sp.unit, dan.public_key: sp.unit},
        {certificate_1: sp.unit, certificate_2: sp.unit, certificate_3: sp.unit},
    )
    scenario += signed_payload_oracle

    scenario.h2("1 payload 3 signatures, change within threshold")
    now = sp.timestamp(Constants.ORACLE_EPOCH_INTERVAL)
    price_payload = sp.pack(Price.make("BNN", "XTZUSD", 100001, 1, now, certificate_1))
    alice_signature = sp.make_signature(alice.secret_key, price_payload)
    bob_signature = sp.make_signature(bob.secret_key, price_payload)
    dan_signature = sp.make_signature(dan.secret_key, price_payload)
    scenario += signed_payload_oracle.set_price(
        {
            alice.public_key: {
                price_payload: alice_signature,
            },
            bob.public_key: {
                price_payload: bob_signature,
            },
            dan.public_key: {
                price_payload: dan_signature,
            },
        }
    ).run(now=now, sender=administrator)
    scenario.verify_equal(signed_payload_oracle.data.price, 100001)
    scenario.verify_equal(signed_payload_oracle.data.last_epoch, 1)

    scenario.h2("1 payload 3 signatures, large change")
    now = sp.timestamp(Constants.ORACLE_EPOCH_INTERVAL * 2)
    price_payload = sp.pack(Price.make("BNN", "XTZUSD", 200001, 1, now, certificate_1))
    alice_signature = sp.make_signature(alice.secret_key, price_payload)
    bob_signature = sp.make_signature(bob.secret_key, price_payload)
    dan_signature = sp.make_signature(dan.secret_key, price_payload)
    scenario += signed_payload_oracle.set_price(
        {
            alice.public_key: {
                price_payload: alice_signature,
            },
            bob.public_key: {
                price_payload: bob_signature,
            },
            dan.public_key: {
                price_payload: dan_signature,
            },
        }
    ).run(now=now, sender=administrator)
    scenario.verify_equal(signed_payload_oracle.data.price, 100001 + (100001 >> 4))
    scenario.verify_equal(signed_payload_oracle.data.last_epoch, 2)

    scenario.h2("3 payloads 3 signatures, median test")
    now = sp.timestamp(Constants.ORACLE_EPOCH_INTERVAL * 3)
    price1_payload = sp.pack(Price.make("BNN", "XTZUSD", 100000, 1, now, certificate_1))
    price2_payload = sp.pack(Price.make("CBP", "XTZUSD", 100001, 1, now, certificate_2))
    price3_payload = sp.pack(Price.make("BFX", "XTZUSD", 100002, 1, now, certificate_3))

    alice_signature1 = sp.make_signature(alice.secret_key, price1_payload)
    bob_signature1 = sp.make_signature(bob.secret_key, price1_payload)
    dan_signature1 = sp.make_signature(dan.secret_key, price1_payload)
    alice_signature2 = sp.make_signature(alice.secret_key, price2_payload)
    bob_signature2 = sp.make_signature(bob.secret_key, price2_payload)
    dan_signature2 = sp.make_signature(dan.secret_key, price2_payload)
    alice_signature3 = sp.make_signature(alice.secret_key, price3_payload)
    bob_signature3 = sp.make_signature(bob.secret_key, price3_payload)
    dan_signature3 = sp.make_signature(dan.secret_key, price3_payload)
    scenario += signed_payload_oracle.set_price(
        {
            alice.public_key: {
                price1_payload: alice_signature1,
                price2_payload: alice_signature2,
                price3_payload: alice_signature3,
            },
            bob.public_key: {
                price1_payload: bob_signature1,
                price2_payload: bob_signature2,
                price3_payload: bob_signature3,
            },
            dan.public_key: {
                price1_payload: dan_signature1,
                price2_payload: dan_signature2,
                price3_payload: dan_signature3,
            },
        }
    ).run(now=now, sender=administrator)
    scenario.verify_equal(signed_payload_oracle.data.price, 100001)
    scenario.verify_equal(signed_payload_oracle.data.last_epoch, 3)

    scenario.h2("2 payloads 3 signatures, higher median test")
    now = sp.timestamp(Constants.ORACLE_EPOCH_INTERVAL * 4)
    price1_payload = sp.pack(Price.make("CBP", "XTZUSD", 100002, 1, now, certificate_2))
    price2_payload = sp.pack(Price.make("BFX", "XTZUSD", 100003, 1, now, certificate_3))

    alice_signature1 = sp.make_signature(alice.secret_key, price1_payload)
    bob_signature1 = sp.make_signature(bob.secret_key, price1_payload)
    dan_signature1 = sp.make_signature(dan.secret_key, price1_payload)
    alice_signature2 = sp.make_signature(alice.secret_key, price2_payload)
    bob_signature2 = sp.make_signature(bob.secret_key, price2_payload)
    dan_signature2 = sp.make_signature(dan.secret_key, price2_payload)
    scenario += signed_payload_oracle.set_price(
        {
            alice.public_key: {
                price1_payload: alice_signature1,
                price2_payload: alice_signature2,
            },
            bob.public_key: {
                price1_payload: bob_signature1,
                price2_payload: bob_signature2,
            },
            dan.public_key: {
                price1_payload: dan_signature1,
                price2_payload: dan_signature2,
            },
        }
    ).run(now=now, sender=administrator)
    scenario.verify_equal(signed_payload_oracle.data.price, 100003)
    scenario.verify_equal(signed_payload_oracle.data.last_epoch, 4)

    scenario.h2("non matching payloads are discarded")
    now = sp.timestamp(Constants.ORACLE_EPOCH_INTERVAL * 5)

    price1_payload = sp.pack(Price.make("BNN", "XTZUSD", 100013, 1, now, certificate_1))
    price2_payload = sp.pack(Price.make("CBP", "XTZUSD", 100014, 1, now, certificate_2))
    price3_payload = sp.pack(Price.make("BFX", "XTZUSD", 100015, 1, now, certificate_3))
    price4_payload = sp.pack(Price.make("CBP", "XTZUSD", 100001, 1, now, certificate_2))
    price5_payload = sp.pack(Price.make("BFX", "XTZUSD", 100002, 1, now, certificate_3))

    alice_signature1 = sp.make_signature(alice.secret_key, price1_payload)
    bob_signature1 = sp.make_signature(bob.secret_key, price1_payload)
    dan_signature1 = sp.make_signature(dan.secret_key, price1_payload)
    alice_signature2 = sp.make_signature(alice.secret_key, price2_payload)
    bob_signature2 = sp.make_signature(bob.secret_key, price4_payload)
    dan_signature2 = sp.make_signature(dan.secret_key, price5_payload)
    alice_signature3 = sp.make_signature(alice.secret_key, price3_payload)
    bob_signature3 = sp.make_signature(bob.secret_key, price4_payload)
    dan_signature3 = sp.make_signature(dan.secret_key, price5_payload)
    scenario += signed_payload_oracle.set_price(
        {
            alice.public_key: {
                price1_payload: alice_signature1,
                price2_payload: alice_signature2,
                price3_payload: alice_signature3,
            },
            bob.public_key: {
                price1_payload: bob_signature1,
                price2_payload: bob_signature2,
                price3_payload: bob_signature3,
            },
            dan.public_key: {
                price1_payload: dan_signature1,
                price2_payload: dan_signature2,
                price3_payload: dan_signature3,
            },
        }
    ).run(now=now, sender=administrator)
    scenario.verify_equal(signed_payload_oracle.data.price, 100013)
    scenario.verify_equal(signed_payload_oracle.data.last_epoch, 5)

    scenario.h2("needs threshold for setting")
    now = sp.timestamp(Constants.ORACLE_EPOCH_INTERVAL * 6)

    price1_payload = sp.pack(Price.make("BNN", "XTZUSD", 100018, 1, now, certificate_1))
    price2_payload = sp.pack(Price.make("CBP", "XTZUSD", 100019, 1, now, certificate_2))
    price3_payload = sp.pack(Price.make("BFX", "XTZUSD", 100020, 1, now, certificate_3))
    price4_payload = sp.pack(Price.make("CBP", "XTZUSD", 100001, 1, now, certificate_2))
    price5_payload = sp.pack(Price.make("BFX", "XTZUSD", 100002, 1, now, certificate_3))

    alice_signature1 = sp.make_signature(alice.secret_key, price1_payload)
    bob_signature1 = sp.make_signature(bob.secret_key, price2_payload)
    dan_signature1 = sp.make_signature(dan.secret_key, price3_payload)
    alice_signature2 = sp.make_signature(alice.secret_key, price2_payload)
    bob_signature2 = sp.make_signature(bob.secret_key, price4_payload)
    dan_signature2 = sp.make_signature(dan.secret_key, price5_payload)
    alice_signature3 = sp.make_signature(alice.secret_key, price3_payload)
    bob_signature3 = sp.make_signature(bob.secret_key, price4_payload)
    dan_signature3 = sp.make_signature(dan.secret_key, price5_payload)
    scenario += signed_payload_oracle.set_price(
        {
            alice.public_key: {
                price1_payload: alice_signature1,
                price2_payload: alice_signature2,
                price3_payload: alice_signature3,
            },
            bob.public_key: {
                price1_payload: bob_signature1,
                price2_payload: bob_signature2,
                price3_payload: bob_signature3,
            },
            dan.public_key: {
                price1_payload: dan_signature1,
                price2_payload: dan_signature2,
                price3_payload: dan_signature3,
            },
        }
    ).run(now=now, sender=administrator)
    scenario.verify_equal(signed_payload_oracle.data.price, 100013)
    scenario.verify_equal(signed_payload_oracle.data.last_epoch, 5)

    scenario.h2("cannot sign self multiple times")
    now = sp.timestamp(Constants.ORACLE_EPOCH_INTERVAL * 7)

    price1_payload = sp.pack(Price.make("BNN", "XTZUSD", 100000, 1, now, certificate_1))
    price2_payload = sp.pack(Price.make("CBP", "XTZUSD", 100001, 1, now, certificate_2))
    price3_payload = sp.pack(Price.make("BFX", "XTZUSD", 100002, 1, now, certificate_3))

    alice_signature1 = sp.make_signature(alice.secret_key, price1_payload)
    bob_signature1 = sp.make_signature(alice.secret_key, price1_payload)
    dan_signature1 = sp.make_signature(alice.secret_key, price1_payload)
    alice_signature2 = sp.make_signature(alice.secret_key, price2_payload)
    bob_signature2 = sp.make_signature(alice.secret_key, price2_payload)
    dan_signature2 = sp.make_signature(alice.secret_key, price2_payload)
    alice_signature3 = sp.make_signature(alice.secret_key, price3_payload)
    bob_signature3 = sp.make_signature(alice.secret_key, price3_payload)
    dan_signature3 = sp.make_signature(alice.secret_key, price3_payload)
    scenario += signed_payload_oracle.set_price(
        {
            alice.public_key: {
                price1_payload: alice_signature1,
                price2_payload: alice_signature2,
                price3_payload: alice_signature3,
            },
            bob.public_key: {
                price1_payload: bob_signature1,
                price2_payload: bob_signature2,
                price3_payload: bob_signature3,
            },
            dan.public_key: {
                price1_payload: dan_signature1,
                price2_payload: dan_signature2,
                price3_payload: dan_signature3,
            },
        }
    ).run(now=now, sender=administrator)
    scenario.verify_equal(signed_payload_oracle.data.price, 100013)
    scenario.verify_equal(signed_payload_oracle.data.last_epoch, 5)

    scenario.h2("1 payload 3 signatures, but too late")
    now = sp.timestamp(Constants.ORACLE_EPOCH_INTERVAL * 8)
    price_payload = sp.pack(Price.make("BNN", "XTZUSD", 100001, 1, now, certificate_1))
    alice_signature = sp.make_signature(alice.secret_key, price_payload)
    bob_signature = sp.make_signature(bob.secret_key, price_payload)
    dan_signature = sp.make_signature(dan.secret_key, price_payload)
    scenario += signed_payload_oracle.set_price(
        {
            alice.public_key: {
                price_payload: alice_signature,
            },
            bob.public_key: {
                price_payload: bob_signature,
            },
            dan.public_key: {
                price_payload: dan_signature,
            },
        }
    ).run(now=now.add_seconds(5 * 60 + 1), sender=administrator)
    scenario.verify_equal(signed_payload_oracle.data.price, 100013)
    scenario.verify_equal(signed_payload_oracle.data.last_epoch, 5)

    scenario.h2("get an old price")
    now = sp.timestamp(Constants.ORACLE_EPOCH_INTERVAL * 9)
    viewer = Viewer()
    scenario += viewer
    return_contract = sp.contract(
        sp.TNat, viewer.address, entry_point="set_nat"
    ).open_some()
    scenario += signed_payload_oracle.get_price(return_contract).run(
        now=now, sender=administrator, valid=False
    )

    scenario.h2("get up to date price")
    now = sp.timestamp(Constants.ORACLE_EPOCH_INTERVAL * 9)
    price_payload = sp.pack(Price.make("BNN", "XTZUSD", 100001, 1, now, certificate_1))
    alice_signature = sp.make_signature(alice.secret_key, price_payload)
    bob_signature = sp.make_signature(bob.secret_key, price_payload)
    dan_signature = sp.make_signature(dan.secret_key, price_payload)
    scenario += signed_payload_oracle.set_price(
        {
            alice.public_key: {
                price_payload: alice_signature,
            },
            bob.public_key: {
                price_payload: bob_signature,
            },
            dan.public_key: {
                price_payload: dan_signature,
            },
        }
    ).run(now=now.add_seconds(4 * 60), sender=administrator)
    scenario.verify_equal(signed_payload_oracle.data.price, 100001)
    scenario.verify_equal(signed_payload_oracle.data.last_epoch, 9)

    scenario += signed_payload_oracle.get_price(return_contract).run(
        now=now, sender=administrator
    )
    scenario.verify_equal(viewer.data.nat, Constants.PRECISION_FACTOR // 100001)

    scenario.h2("only allow if certificate matches")
    now = sp.timestamp(Constants.ORACLE_EPOCH_INTERVAL * 10)
    price_payload = sp.pack(
        Price.make("BNN", "XTZUSD", 100099, 1, now, sp.bytes("0x05"))
    )
    alice_signature = sp.make_signature(alice.secret_key, price_payload)
    bob_signature = sp.make_signature(bob.secret_key, price_payload)
    dan_signature = sp.make_signature(dan.secret_key, price_payload)
    scenario += signed_payload_oracle.set_price(
        {
            alice.public_key: {
                price_payload: alice_signature,
            },
            bob.public_key: {
                price_payload: bob_signature,
            },
            dan.public_key: {
                price_payload: dan_signature,
            },
        }
    ).run(now=now.add_seconds(4 * 60), sender=administrator)
    scenario.verify_equal(signed_payload_oracle.data.price, 100001)
    scenario.verify_equal(signed_payload_oracle.data.last_epoch, 9)

    scenario.h2("make sure the base/quote flip works")
    scenario += signed_payload_oracle.get_price(return_contract).run(
        now=now, sender=administrator
    )
    scenario.verify_equal(viewer.data.nat, Constants.PRECISION_FACTOR // 100001)
