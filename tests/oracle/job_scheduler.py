import smartpy as sp

from contracts.oracle.job_scheduler import JobScheduler, Job, Fulfill


class Fulfiller(sp.Contract):
    """This is a dummy contract that can be used to 'receive' and inspect the payload you receive from
    the data transmitter.
    """

    def __init__(self):
        """This has only the payload as storage"""
        self.init(payload=sp.bytes("0x00"))

    @sp.entry_point
    def default(self):
        """This entrypoint is there because single entrypoint is not allowed."""
        with sp.if_(sp.amount > sp.mutez(0)):
            sp.failwith("don't send me money")

    @sp.entry_point
    def fulfill(self, fulfill):
        """This entrypoint needs to be "fulfill" and accept a bytes payload (you can unpack in the implementation)."""
        sp.set_type(fulfill, Fulfill.get_type())
        self.data.payload = fulfill.payload


@sp.add_test(name="Job Scheduler")
def test():
    scenario = sp.test_scenario()
    scenario.h1("Job Scheduler")

    scenario.h2("Bootstrapping")
    administrator = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob = sp.test_account("Robert")
    dan = sp.test_account("Dan")
    executor = sp.test_account("Executor")

    scenario.h2("Accounts")
    scenario.show([administrator, alice, bob, dan, executor])

    scheduler = JobScheduler(administrator.address)
    scenario += scheduler

    fulfiller = Fulfiller()
    scenario += fulfiller

    scenario.h2("Publishing jobs")
    script = sp.bytes("0x00")
    interval = 900
    fee = 1700
    gas_limit = 11000
    storage_limit = 12000
    start = sp.timestamp(0)
    end = sp.timestamp(1800)

    job = Job.make_publish(
        executor.address,
        script,
        start,
        end,
        interval,
        fee,
        gas_limit,
        storage_limit,
        fulfiller.address,
    )
    scenario.p("Alice cannot publish, she is not admin")
    scenario += scheduler.publish(job).run(sender=alice.address, valid=False)

    scenario.p("Admin can publish")
    scenario += scheduler.publish(job).run(sender=administrator.address)

    scenario.verify_equal(
        scheduler.data.jobs[executor.address][script].contract, fulfiller.address
    )
    scenario.verify_equal(scheduler.data.jobs[executor.address][script].fee, fee)
    scenario.verify_equal(
        scheduler.data.jobs[executor.address][script].gas_limit, gas_limit
    )
    scenario.verify_equal(
        scheduler.data.jobs[executor.address][script].storage_limit, storage_limit
    )
    scenario.verify_equal(
        scheduler.data.jobs[executor.address][script].interval, interval
    )

    scenario.p("Same script<>executor overrides")
    job = Job.make_publish(
        executor.address,
        script,
        start,
        end,
        interval,
        fee,
        gas_limit,
        storage_limit,
        sp.address("tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83"),
    )
    scenario += scheduler.publish(job).run(sender=administrator.address)
    scenario.verify_equal(
        scheduler.data.jobs[executor.address][script].contract,
        sp.address("tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83"),
    )

    job = Job.make_publish(
        executor.address,
        script,
        start,
        end,
        interval,
        fee,
        gas_limit,
        storage_limit,
        fulfiller.address,
    )
    scenario += scheduler.publish(job).run(sender=administrator.address)
    scenario.verify_equal(
        scheduler.data.jobs[executor.address][script].contract, fulfiller.address
    )

    scenario.p("Same executor new script is new entry")
    script = sp.bytes("0x01")
    job = Job.make_publish(
        executor.address,
        script,
        start,
        end,
        interval,
        fee,
        gas_limit,
        storage_limit,
        sp.address("tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83"),
    )
    scenario += scheduler.publish(job).run(sender=administrator.address)
    scenario.verify_equal(
        scheduler.data.jobs[executor.address][script].contract,
        sp.address("tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83"),
    )
    script = sp.bytes("0x00")
    scenario.verify_equal(
        scheduler.data.jobs[executor.address][script].contract, fulfiller.address
    )

    scenario.h2("Delete Jobs")
    scenario.p("Alice cannot delete, she is not admin")
    script = sp.bytes("0x01")
    scenario += scheduler.delete(executor=executor.address, script=script).run(
        sender=alice.address, valid=False
    )
    scenario.verify_equal(scheduler.data.jobs[executor.address].contains(script), True)

    scenario.p("Admin can delete")
    scenario += scheduler.delete(executor=executor.address, script=script).run(
        sender=administrator.address
    )
    scenario.verify_equal(scheduler.data.jobs[executor.address].contains(script), False)

    scenario.h2("Ack Jobs")
    script = sp.bytes("0x00")
    scenario.p("Alice cannot acknowledge a job")
    scenario += scheduler.ack(script).run(sender=alice.address, valid=False)
    scenario.verify_equal(scheduler.data.jobs[executor.address][script].status, 0)
    scenario.p("Admin cannot acknowledge a job")
    scenario += scheduler.ack(script).run(sender=administrator.address, valid=False)
    scenario.verify_equal(scheduler.data.jobs[executor.address][script].status, 0)
    scenario.p("Only an executor can acknowledge a job")
    scenario += scheduler.ack(script).run(sender=executor.address)
    scenario.verify_equal(scheduler.data.jobs[executor.address][script].status, 1)

    scenario.h2("Fulfill Jobs")
    payload = sp.pack(sp.address("tz3S9uYxmGahffYfcYURijrCGm1VBqiH4mPe"))

    scenario.p("Alice cannot fulfill a job")
    scenario += scheduler.fulfill(Fulfill.make(script, payload)).run(
        sender=alice.address, valid=False
    )
    scenario.verify_equal(fulfiller.data.payload, sp.bytes("0x00"))
    scenario.p("Admin cannot fulfill a job")
    scenario += scheduler.fulfill(Fulfill.make(script, payload)).run(
        sender=administrator.address, valid=False
    )
    scenario.verify_equal(fulfiller.data.payload, sp.bytes("0x00"))
    scenario.p("Only an executor can fulfill a job")
    scenario += scheduler.fulfill(Fulfill.make(script, payload)).run(
        sender=executor.address
    )
    scenario.verify_equal(fulfiller.data.payload, payload)

    scenario.p("Job is deleted when we passed end")
    payload = sp.pack(sp.address("tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83"))
    scenario += scheduler.fulfill(Fulfill.make(script, payload)).run(
        sender=executor.address, now=end
    )
    scenario.verify_equal(fulfiller.data.payload, payload)
    scenario.verify_equal(scheduler.data.jobs[executor.address].contains(script), False)

    scenario.p("Propose/accept admin")
    scenario += scheduler.propose_admin(alice.address).run(sender=alice, valid=False)
    scenario += scheduler.propose_admin(alice.address).run(sender=administrator)
    scenario.verify_equal(scheduler.data.proposed_admin, alice.address)

    scenario += scheduler.set_admin(sp.unit).run(sender=bob, valid=False)
    scenario += scheduler.set_admin(sp.unit).run(sender=alice)
    scenario.verify_equal(scheduler.data.admin, alice.address)
