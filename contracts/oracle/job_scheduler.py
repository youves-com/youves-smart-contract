import smartpy as sp

import utils.error_codes as Errors

class Job:
    """Type used to specify Jobs later used by the scheduler.
    """
    def get_publish_type():
        """Type used for the publish entrypoint.
        """
        return sp.TRecord(
                executor=sp.TAddress, 
                script=sp.TBytes, 
                start=sp.TTimestamp, 
                end=sp.TTimestamp, 
                interval=sp.TNat, 
                fee=sp.TNat,
                gas_limit=sp.TNat,
                storage_limit=sp.TNat, 
                contract=sp.TAddress).layout(("executor",("script", ("start", ("end", ("interval", ("fee", ("gas_limit", ("storage_limit","contract")))))))))
    
    def make_publish(executor, script, start, end, interval, fee, gas_limit, storage_limit, contract):
        """Courtesy function typing a record to Job.get_publish_type() for us
        """
        return sp.set_type_expr(sp.record(executor=executor, 
                script=script,
                start=start, 
                end=end, 
                interval=interval, 
                fee=fee, 
                gas_limit=gas_limit,
                storage_limit=storage_limit,
                contract=contract), Job.get_publish_type())

    def get_type():
        """Type used for the storage
        """
        return sp.TRecord(status=sp.TNat, 
                start=sp.TTimestamp, 
                end=sp.TTimestamp, 
                interval=sp.TNat, 
                fee=sp.TNat, 
                gas_limit=sp.TNat,
                storage_limit=sp.TNat,
                contract=sp.TAddress).layout(("status", ("start", ("end", ("interval", ("fee", ("gas_limit", ("storage_limit", "contract"))))))))

    def make(status, start, end, interval, fee, gas_limit, storage_limit, contract):
        """Courtesy function typing a record to Job.get_type() for us
        """
        return sp.set_type_expr(sp.record(status=status, 
                start=start, 
                end=end, 
                interval=interval, 
                fee=fee, 
                gas_limit=gas_limit,
                storage_limit=storage_limit,
                contract=contract), Job.get_type())

class Fulfill:
    """Type used by the datatransmitter to fulfill a Job
    """
    def get_type():
        """Type used in the fulfill entrypoint.
        """
        return sp.TRecord(script=sp.TBytes, payload=sp.TBytes).layout(("script","payload"))
    
    def make(script, payload):
        """Courtesy function typing a record to Fulfill.get_type() for us
        """
        return sp.set_type_expr(sp.record(script=script, 
                payload=payload), Fulfill.get_type())

class JobScheduler(sp.Contract):
    """Scheduler used to point the data transmitter to. This is where they fetch jobs and fulfill them.
    """
    def __init__(self, admin):
        """Initialises the storage with jobs and the admin mechanism
        """
        self.init(
            admin=admin,
            proposed_admin=admin,
            jobs=sp.big_map(tkey=sp.TAddress, tvalue=sp.TMap(sp.TBytes, Job.get_type()))
        )

    @sp.entry_point(check_no_incoming_transfer=True)
    def publish(self, job):
        """Publish a job. Jobs are per executor and require an IPFS uri where the script is located. Jobs with the same executor and script
        will overwrite the previous definition. Once it's published the data transmitter first ack's the job and then at the requested
        timestamp will fulfill it. Only Admin can do this.
        """
        sp.set_type(job, Job.get_publish_type())
        sp.verify(sp.sender==self.data.admin, message=Errors.NOT_ADMIN)

        with sp.if_(~self.data.jobs.contains(job.executor)):
            self.data.jobs[job.executor] = {}
        self.data.jobs[job.executor][job.script] = Job.make(0, job.start, job.end, job.interval, job.fee, job.gas_limit, job.storage_limit, job.contract)

    @sp.entry_point(check_no_incoming_transfer=True)
    def delete(self, executor, script):
        """Delete a job. Only Admin can do this.
        """
        sp.verify(sp.sender==self.data.admin, message=Errors.NOT_ADMIN)
        
        del self.data.jobs[executor][script]

    @sp.entry_point(check_no_incoming_transfer=True)
    def propose_admin(self, proposed_admin):
        """Propose a new administrator. Only Admin can do this.
        """
        sp.verify(sp.sender==self.data.admin, message=Errors.NOT_ADMIN)        
        self.data.proposed_admin = proposed_admin

    @sp.entry_point(check_no_incoming_transfer=True)
    def set_admin(self):
        """Set the proposed admin. Only proposed admin can do this.
        """
        sp.verify(sp.sender==self.data.proposed_admin)
        self.data.admin = self.data.proposed_admin

    @sp.entry_point(check_no_incoming_transfer=True)
    def ack(self, script):
        """Acknowledge a job. Sender needs to be an executor and script needs to match the published jobs.
        """
        self.data.jobs[sp.sender][script].status = 1

    @sp.entry_point(check_no_incoming_transfer=True)
    def fulfill(self, fulfill):
        """Fulfill a job and provide the expected payload to the receiving contract.
        """
        sp.set_type(fulfill, Fulfill.get_type())
        job = sp.local("job", self.data.jobs[sp.sender][fulfill.script])  
        callback_contract = sp.contract(Fulfill.get_type(), job.value.contract, "fulfill").open_some()
        sp.transfer(fulfill, sp.mutez(0), callback_contract)
        with sp.if_(job.value.end <= sp.now.add_seconds(sp.to_int(job.value.interval))):
            del self.data.jobs[sp.sender][fulfill.script]
    

class Fulfiller(sp.Contract):
    """This is a dummy contract that can be used to 'receive' and inspect the payload you receive from 
    the data transmitter.
    """
    def __init__(self):
        """This has only the payload as storage
        """
        self.init(
            payload=sp.bytes("0x00")
        )
        
    @sp.entry_point(check_no_incoming_transfer=True)
    def default(self):
        """This entrypoint is there because single entrypoint is not allowed.
        """
        pass

    @sp.entry_point(check_no_incoming_transfer=True)
    def fulfill(self, fulfill):
        """This entrypoint needs to be "fulfill" and accept a bytes payload (you can unpack in the implementation).
        """
        sp.set_type(fulfill, Fulfill.get_type())
        self.data.payload = fulfill.payload
