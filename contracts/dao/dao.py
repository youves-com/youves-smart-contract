import smartpy as sp

import contracts.dao.constants as Constants
import contracts.dao.errors as Errors
from utils.contract_utils import Utils

Escrow = sp.io.import_script_from_url("file:contracts/dao/types/escrow.py")
GovernanceParams = sp.io.import_script_from_url("file:contracts/dao/types/governance_params.py")
Poll = sp.io.import_script_from_url("file:contracts/dao/types/poll.py")
Proposal = sp.io.import_script_from_url("file:contracts/dao/types/proposal.py")
ProposalOutcome = sp.io.import_script_from_url("file:contracts/dao/types/proposal_outcome.py")
Quorum = sp.io.import_script_from_url("file:contracts/dao/types/quorum.py")
Timelock = sp.io.import_script_from_url("file:contracts/dao/types/timelock.py")
Vote = sp.io.import_script_from_url("file:contracts/dao/types/vote.py")
VoteTracker = sp.io.import_script_from_url("file:contracts/dao/types/vote_tracker.py")
FA2Transfer = sp.io.import_script_from_url("file:utils/fa2.py")

"""
The DAO contract for Youves. This is suppose to be the administrator for all other contracts
on the platform.
Storage:
    - escrow_contract (ESCROW_CONTRACT_TYPE) - contract used for the escrow amount.
        This can be tez, FA1.2 or FA2 contract.
    - voting_contract (sp.TAddress) - contract used for the DAO votes.
    - community_fund_address (sp.TAddress) - address of a contract controlled by the DAO.
    - governance_params (GOVERNANCE_PARAMS_TYPE) - parameters used by the DAO contract.
    - quorum (sp.TNat) - DAO quorum
    - poll (sp.TOption(POLL_TYPE)) - the underway poll (can be empty if no poll is underway)
    - timelock (sp.TOption(TIMELOCK_ITEM)) - the item in timelock (can be empty).
    - next_proposal_id (sp.TNat) - index used to count the number of proposals.
    - vote_tracker (VOTE_TRACKER_TYPE) - big map that keeps track of votes. Used to claim back the
        stakes used in voting.
    - historical_outcomes (sp.TBigMap(sp.TNat, PROPOSAL_OUTCOME_TYPE)) - history of the proposals
        and their outcomes.
    - break_glass_contract (sp.TOption(sp.TAddress)) - break glass contract used to expedite certain proposals
        or veto proposals.
    - metadata (sp.TBigMap(sp.TString, sp.TBytes)) - contract metadata.
"""
class DAOContract(sp.Contract):
    def __init__(
        self,
        governance_params = sp.record(
            escrow_amount = sp.nat(0),
            vote_delay_blocks = sp.nat(0),
            vote_length_blocks = sp.nat(0),
            min_yes_votes_percentage_for_escrow_return = sp.nat(0),
            timelock_execution_delay_blocks = sp.nat(0),
            timelock_cancelation_delay_blocks = sp.nat(0),
            super_majority_percentage = sp.nat(0),
            quorum_cap = sp.record(lower = sp.nat(0), upper = sp.nat(0)),
        ),
        poll = sp.none,
        timelock = sp.none,
        escrow_contract = sp.variant("fa2", sp.record(contract=Constants.DEFAULT_ADDRESS, token_id=sp.nat(0))),
        voting_contract = Constants.DEFAULT_ADDRESS,
        quorum = sp.nat(0),
        community_fund_address = Constants.DEFAULT_ADDRESS,
        historical_outcomes = sp.big_map(l={}, tkey = sp.TNat, tvalue = ProposalOutcome.PROPOSAL_OUTCOME_TYPE),
        vote_tracker = sp.big_map(l={}, tkey = VoteTracker.KEY_TYPE, tvalue = VoteTracker.VALUE_TYPE),
        break_glass_contract = sp.some(Constants.DEFAULT_ADDRESS),
    ):
        metadata = sp.big_map(
            l = {
                "": sp.bytes('0x74657a6f732d73746f726167653a64617461'), # "tezos-storage:data"
                "data": sp.utils.bytes_of_string('{ "name": "Youves Governance DAO", "authors": ["Youves <contact@youves.com>"], "homepage":  "https://app.youves.com" }')
            },
            tkey = sp.TString,
            tvalue = sp.TBytes
        )

        self.init_type(
            sp.TRecord(
                escrow_contract = Escrow.ESCROW_CONTRACT_TYPE,
                voting_contract = sp.TAddress,
                community_fund_address = sp.TAddress,
                governance_params = GovernanceParams.GOVERNANCE_PARAMS_TYPE,
                quorum = sp.TNat,
                poll = sp.TOption(Poll.POLL_TYPE),
                timelock = sp.TOption(Timelock.TIMELOCK_TYPE),
                next_proposal_id = sp.TNat,
                vote_tracker = sp.TBigMap(VoteTracker.KEY_TYPE, VoteTracker.VALUE_TYPE),
                historical_outcomes = sp.TBigMap(sp.TNat, ProposalOutcome.PROPOSAL_OUTCOME_TYPE),
                break_glass_contract = sp.TOption(sp.TAddress),
                metadata = sp.TBigMap(sp.TString, sp.TBytes)
            )
        )

        self.init(
            escrow_contract = escrow_contract,
            voting_contract = voting_contract,
            community_fund_address = community_fund_address,
            governance_params = governance_params,
            quorum = quorum,
            poll = poll,
            timelock = timelock,
            next_proposal_id = sp.nat(0),
            vote_tracker = vote_tracker,
            historical_outcomes = historical_outcomes,
            break_glass_contract = break_glass_contract,
            metadata = metadata,
        )
    
    @sp.private_lambda(with_storage="read-only", with_operations=False, wrap_call=True)
    def fetch_current_poll(self, params):
        """Lambda to fetch the current poll.
        Returns: current poll if it is a voting period, or error if not.
        """
        sp.set_type(params, Vote.VOTE_PARAMS_TYPE)

        poll = sp.local("poll", self.data.poll.open_some(message=Errors.ERROR_NO_POLL))
        sp.verify(sp.level <= poll.value.voting_end_block, Errors.ERROR_VOTING_FINISHED)
        sp.verify(sp.level >= poll.value.voting_start_block, Errors.ERROR_VOTING_NOT_STARTED)
        sp.verify(params.vote < Constants.START_OF_INVALID_VOTE_VALUES, Errors.ERROR_BAD_VOTE_VALUE)

        sp.result(poll.value)

    """
    Entrypoint that allows a user to proposal an imporovement for the platform.
    Requirements:
        - No other polls should be running.
    Params:
        - proposal (PROPOSAL_TYPE) - the proposal for the improvement.
    Effects:
        - creates a new proposal that users can vote on after an initial delay has passed.
        - escrow tokens/tez that will be returned to the proposer if the proposal passes.
    """
    @sp.entry_point
    def propose(self, proposal):
        sp.set_type(proposal, Proposal.PROPOSAL_TYPE)

        sp.verify(self.data.poll.is_none(), Errors.ERROR_POLL_UNDERWAY)

        with self.data.escrow_contract.match_cases() as escrow_contract:
            with escrow_contract.match("fa2") as fa2:
                Utils.execute_fa2_token_transfer(fa2.contract, sp.sender, sp.self_address, fa2.token_id, self.data.governance_params.escrow_amount)
            with escrow_contract.match("fa1") as contract:
                Utils.execute_fa1_token_transfer(contract, sp.sender, sp.self_address, self.data.governance_params.escrow_amount)
            with escrow_contract.match("tez") as tez:
                sp.verify(sp.amount == sp.utils.nat_to_mutez(self.data.governance_params.escrow_amount), Errors.ERROR_NOT_ENOUGH_ESCROW)
        start_block = sp.local("start_block", sp.level + self.data.governance_params.vote_delay_blocks)
        end_block = sp.local("end_block", start_block.value + self.data.governance_params.vote_length_blocks)

        self.data.poll = sp.some(
            sp.record(
                id = self.data.next_proposal_id,
                proposal = proposal,
                voting_start_block = start_block.value,
                voting_end_block = end_block.value,
                votes = Constants.INITIAL_VOTING_MAP,
                total_votes = sp.nat(0),
                author = sp.sender,
                escrow_amount = self.data.governance_params.escrow_amount,
                quorum = self.data.quorum,
                quorum_cap = self.data.governance_params.quorum_cap
            )
        )
        self.data.next_proposal_id = self.data.next_proposal_id + 1

    """
    Entrypoint that allows a user to vote on an ongoing proposal with yes/no/abstain.
    Requirements:
        - a poll for a proposal is running.
        - currently it is the voting period for the proposal.
        - the sender must be the owner of the stake with which they voted.
        - it is the first time they vote with the stake.
    Params:
        - params (VOTE_PARAMS_TYPE) - the vote for the current on-going proposal
    Effects:
        - adds the vote to the poll.
        - adds the total votes of the poll.
        - transfers the stake from the voter to the DAO to avoid double counting.
    """
    @sp.entry_point(check_no_incoming_transfer=True)
    def vote(self, params):
        sp.set_type(params, Vote.VOTE_PARAMS_TYPE)
        poll = sp.local("poll", self.fetch_current_poll(params))

        # Check if the sender has not voted before.
        vote_key = sp.record(voter=sp.sender, proposal_id=poll.value.id, vote_id=params.vote_id)
        sp.verify(~self.data.vote_tracker.contains(vote_key), Errors.ERROR_ALREADY_VOTED)

        # Check if the sender owns the stake they are voting with.
        sender_stakes = sp.local(
            "sender_stakes",
            sp.view("view_owner_stakes", self.data.voting_contract, sp.sender, t = sp.TSet(sp.TNat)).open_some("Invalid View: view_owner_stakes"))
        sp.verify(sender_stakes.value.contains(params.vote_id), Errors.ERROR_NOT_OWNER)

        # Fetch the weight of the vote.
        stake = sp.local(
            "stake",
            sp.view("view_stake", self.data.voting_contract, params.vote_id, t = Vote.VOTE_STAKE_TYPE).open_some("Invalid View: view_stake"))
        
        # Update the local poll value.
        poll.value.votes[params.vote] += stake.value.stake
        poll.value.total_votes += stake.value.stake

        # Update the poll, vote tracker and ownership of the stake.
        self.data.poll = sp.some(poll.value)
        self.data.vote_tracker[vote_key] = sp.record(vote_value=params.vote, weight=stake.value.stake)
        voting_token_contract_handle = sp.contract(
            FA2Transfer.Transfer.get_batch_type(),
            self.data.voting_contract,
            "transfer"
        ).open_some(message=Errors.ERROR_NOT_TOKEN_CONTRACT)
        voting_token_contract_arg = sp.list([
            FA2Transfer.Transfer.item(
                from_=sp.sender,
                txs=[sp.record(to_=sp.self_address, token_id=params.vote_id, amount=sp.nat(1))]
            )
        ])
        sp.transfer(voting_token_contract_arg, sp.mutez(0), voting_token_contract_handle)
    
    """
    Entrypoint that allows a user to change their vote on an ongoing proposal with yes/no/abstain.
    Requirements:
        - a poll for a proposal is running.
        - currently it is the voting period for the proposal.
        - the sender must have voted before with the stake.
    Params:
        - params (VOTE_PARAMS_TYPE) - the vote for the current on-going proposal
    Effects:
        - changes the vote to the poll.
    """
    @sp.entry_point(check_no_incoming_transfer=True)
    def change_vote(self, params):
        sp.set_type(params, Vote.VOTE_PARAMS_TYPE)
        poll = sp.local("poll", self.fetch_current_poll(params))

        # Check if the sender has voted.
        vote_key = sp.record(voter=sp.sender, proposal_id=poll.value.id, vote_id=params.vote_id)
        sp.verify(self.data.vote_tracker.contains(vote_key), Errors.ERROR_MUST_VOTE_FIRST)

        old_vote_entry = sp.local("old_vote", self.data.vote_tracker[vote_key])
        sp.verify(old_vote_entry.value.vote_value != params.vote, Errors.ERROR_BAD_VOTE_VALUE)

        # Update the local poll value.
        poll.value.votes[params.vote] += old_vote_entry.value.weight
        poll.value.votes[old_vote_entry.value.vote_value] = sp.as_nat(
            poll.value.votes[old_vote_entry.value.vote_value] - old_vote_entry.value.weight)
         
        # Update the vote tracker and the poll.
        self.data.vote_tracker[vote_key] = sp.record(vote_value=params.vote, weight=old_vote_entry.value.weight)
        self.data.poll = sp.some(poll.value)
    
    """
    Entrypoint that returns the specified stakes back to their owners once a proposal has passed. 
    Requirements:
        - the stakes must have voted on previous proposals.
    Params:
        - params (List(VoteTracker.KEY_TYPE)) - a list of stakes to be returned to their user.
    Effects:
        - transfers all the specified stakes back to their users.
    """
    @sp.entry_point(check_no_incoming_transfer=True)
    def return_stakes(self, params):
        sp.set_type(params, sp.TList(VoteTracker.KEY_TYPE))
        sp.verify(sp.len(params) <= Constants.MAX_STAKES_ALLOWED_TO_BE_RETURNED, Errors.ERROR_TOO_MANY_STAKES_TO_RETURN)

        # An user cannot withdraw a stake if they voted for a proposal with an id that is higher or equal to this limit.
        # This is to make sure that an user can only get back the stakes for proposals that already ended.
        proposal_id_exclusive_limit = sp.local("proposal_id_exclusive_limit", self.data.next_proposal_id)
        with sp.if_(self.data.poll.is_some()):
            proposal_id_exclusive_limit.value = self.data.poll.open_some().id

        transfers = sp.local("transfers", sp.list(l=[], t=FA2Transfer.Transfer.get_type()))
        voting_token_contract_handle = sp.contract(
            FA2Transfer.Transfer.get_batch_type(),
            self.data.voting_contract,
            "transfer"
        ).open_some(message=Errors.ERROR_NOT_TOKEN_CONTRACT)
        with sp.for_("tracker_key", params) as tracker_key:
            sp.verify(tracker_key.proposal_id < proposal_id_exclusive_limit.value, Errors.ERROR_NOT_ALLOWED)
            sp.verify(self.data.vote_tracker.contains(tracker_key), Errors.ERROR_NOT_ALLOWED)

            transfer = FA2Transfer.Transfer.item(
                from_=sp.self_address,
                txs=[sp.record(to_=tracker_key.voter, token_id=tracker_key.vote_id, amount=sp.nat(1))]
            )
            transfers.value = sp.cons(transfer, transfers.value)
            del self.data.vote_tracker[tracker_key]

        voting_token_contract_handle = sp.contract(
            FA2Transfer.Transfer.get_batch_type(),
            self.data.voting_contract,
            "transfer"
        ).open_some(message=Errors.ERROR_NOT_TOKEN_CONTRACT)
        sp.transfer(transfers.value, sp.mutez(0), voting_token_contract_handle)

    """
    Entrypoint that ends the ongoing voting period of the current proposal if enough
    blocks have passed.
    Requirements:
        - there is no item in the timelock currently.
        - there is a poll for whoch the voting period has ended.
    Params:
        - unit (sp.TUnit)
    Effects:
        - Ends the voting period for the current poll and either moves it in the timelock for it to
        be executed if the votes limit has been meet or moves it into history if the quorum
        has not been met.
        - Returns the escrow amount to the user if the conditions have meet or it
        transfers it to the community address.
        - Calculates the new quorum for future proposal.
    """
    @sp.entry_point(check_no_incoming_transfer=True)
    def end_vote(self, unit):
        sp.set_type(unit, sp.TUnit)

        sp.verify(self.data.timelock.is_none(), Errors.ERROR_ITEM_IN_TIMELOCK)
        poll = sp.local('poll', self.data.poll.open_some(message=Errors.ERROR_NO_POLL))
        sp.verify(sp.level > poll.value.voting_end_block, Errors.ERROR_VOTING_NOT_FINISHED)

        disc_factor = sp.local(
            "disc_factor", 
            sp.view("view_disc_factor", self.data.voting_contract, sp.unit, t = sp.TNat).open_some("Invalue View: view_disc_factor"))

        yes_votes = poll.value.votes[Constants.YES_VOTE_VALUE] * disc_factor.value // Constants.PRECISION_FACTOR
        no_votes = poll.value.votes[Constants.NO_VOTE_VALUE] * disc_factor.value // Constants.PRECISION_FACTOR

        total_votes = poll.value.total_votes * disc_factor.value // Constants.PRECISION_FACTOR
        total_opinionated_votes = yes_votes + no_votes

        min_yes_votes_for_escrow_return = sp.local(
            "min_yes_votes_for_escrow_return",
            total_opinionated_votes * self.data.governance_params.min_yes_votes_percentage_for_escrow_return // Constants.PERCENTAGE_SCALE)
        min_yes_votes_for_super_majority = sp.local(
            "min_yes_votes_for_super_majority",
            total_opinionated_votes * self.data.governance_params.super_majority_percentage // Constants.PERCENTAGE_SCALE)

        escrow_recipient = sp.local('escrow_recipient', self.data.community_fund_address)
        with sp.if_(yes_votes >= min_yes_votes_for_escrow_return.value):
            escrow_recipient.value = poll.value.author
        
        with self.data.escrow_contract.match_cases() as escrow_contract:
            with escrow_contract.match("fa2") as fa2:
                Utils.execute_fa2_token_transfer(fa2.contract, sp.self_address, escrow_recipient.value, fa2.token_id, self.data.governance_params.escrow_amount)
            with escrow_contract.match("fa1") as contract:
                Utils.execute_fa1_token_transfer(contract, sp.self_address, escrow_recipient.value, self.data.governance_params.escrow_amount)
            with escrow_contract.match("tez") as tez:
                sp.send(escrow_recipient.value, sp.utils.nat_to_mutez(self.data.governance_params.escrow_amount))
        
        with sp.if_((yes_votes >= min_yes_votes_for_super_majority.value) & (total_votes >= self.data.quorum)):
            self.data.timelock = sp.some(
                sp.record(
                    id = poll.value.id,
                    proposal = poll.value.proposal,
                    execution_start_block = sp.level + self.data.governance_params.timelock_execution_delay_blocks,
                    cancelation_start_block = sp.level + self.data.governance_params.timelock_cancelation_delay_blocks,
                    author = poll.value.author,
                )
            )
            self.data.historical_outcomes[poll.value.id] = sp.record(
                outcome = Constants.PROPOSAL_OUTCOME_IN_TIMELOCK,
                poll = poll.value
            )
        with sp.else_():
            self.data.historical_outcomes[poll.value.id] = sp.record(
                outcome = Constants.PROPOSAL_OUTCOME_FAILED,
                poll = poll.value
            ) 

        new_quorum = sp.local("new_quorum", (poll.value.quorum * 80 + total_votes * 20) // Constants.PERCENTAGE_SCALE)
        new_quorum.value = sp.max(
            poll.value.quorum_cap.lower,
            sp.min(poll.value.quorum_cap.upper, new_quorum.value)
        )
        self.data.quorum = new_quorum.value
        self.data.poll = sp.none

    """
    Executes the operation in the timelock.
    Requirements:
        - Timelock is not empty.
        - Sender is the author of the proposal in the timelock.
        - Enough time has passed for the proposal to be executed.
    Params:
        - unit (sp.TUnit)
    Effects:
        - Executes the operation in the timelock.
        - Updates the historical outcomes map.
        - Clears the timelock.
    """
    @sp.entry_point(check_no_incoming_transfer=True)
    def execute_timelock(self, unit):
        sp.set_type(unit, sp.TUnit)

        timelock = sp.local("timelock", self.data.timelock.open_some(message=Errors.ERROR_NO_ITEM_IN_TIMELOCK))
        sp.verify(sp.sender == timelock.value.author, Errors.ERROR_NOT_AUTHOR)
        sp.verify(sp.level >= timelock.value.execution_start_block, Errors.ERROR_TOO_SOON)

        operations = timelock.value.proposal.proposal_lambda(sp.unit)
        sp.set_type(operations, sp.TList(sp.TOperation))
        sp.add_operations(operations)

        poll_id = sp.local("poll_id", timelock.value.id)
        historical_outcome = sp.local("historical_outcome", self.data.historical_outcomes[poll_id.value])
        self.data.historical_outcomes[poll_id.value] = sp.record(
            outcome = Constants.PROPOSAL_OUTCOME_EXECUTED,
            poll = historical_outcome.value.poll,
        )
        self.data.timelock = sp.none
    
    """
    Cancels the operation in the timelock.
    Requirements:
        - Timelock is not empty.
        - Enough time has passed for the proposal to be cancelled.
    Params:
        - unit (sp.TUnit)
    Effects:
        - Updates the historical outcomes map.
        - Clears the timelock.
    """
    @sp.entry_point(check_no_incoming_transfer=True)
    def cancel_timelock(self, unit):
        sp.set_type(unit, sp.TUnit)

        timelock = sp.local("timelock", self.data.timelock.open_some(message=Errors.ERROR_NO_ITEM_IN_TIMELOCK))
        sp.verify(sp.level >= timelock.value.cancelation_start_block, Errors.ERROR_TOO_SOON)

        # Update the historical historical_outcomes.
        poll_id = sp.local('poll_id', timelock.value.id)
        historical_outcome = sp.local('historical_outcome', self.data.historical_outcomes[poll_id.value])
        self.data.historical_outcomes[poll_id.value] = sp.record(
          outcome = Constants.PROPOSAL_OUTCOME_CANCELLED,
          poll = historical_outcome.value.poll, 
        )
        # Clear the timelock
        self.data.timelock = sp.none

    """
    Vetos the operation in the timelock.
    Requirements:
        - Timelock is not empty.
        - Sender is the break glass contract.
        - The voting has ended but not enough time has passed for the operation to be executed.
    Params:
        - unit (sp.TUnit)
    Effects:
        - Updates the historical outcomes map.
        - Clears the timelock.
    """
    @sp.entry_point(check_no_incoming_transfer=True)
    def veto_timelock(self, unit):
        sp.set_type(unit, sp.TUnit)

        break_glass_contract = sp.local("break_glass_contract", self.data.break_glass_contract.open_some(message=Errors.ERROR_NO_BREAK_GLASS_CONTRACT_SET))
        sp.verify(sp.sender == break_glass_contract.value, Errors.ERROR_NOT_ALLOWED)
        timelock = sp.local("timelock", self.data.timelock.open_some(message=Errors.ERROR_NO_ITEM_IN_TIMELOCK))
        sp.verify(sp.level < timelock.value.execution_start_block, Errors.ERROR_TOO_LATE)

        # Update the historical historical_outcomes.
        poll_id = sp.local('poll_id', timelock.value.id)
        historical_outcome = sp.local('historical_outcome', self.data.historical_outcomes[poll_id.value])
        self.data.historical_outcomes[poll_id.value] = sp.record(
          outcome = Constants.PROPOSAL_OUTCOME_VETOED,
          poll = historical_outcome.value.poll, 
        )
        # Clear the timelock
        self.data.timelock = sp.none

    """
    Updates the governance params for the current contract.
    Requirements:
        - Sender is the contract itself or the breakglass contract.
    Params:
        - params (GOVERNANCE_PARAMS_TYPE): The new parameters of the DAO.
    Effects:
        - Updates the parameters of the dao.
    """
    @sp.entry_point(check_no_incoming_transfer=True)
    def set_governance_params(self, params):
        sp.set_type(params, GovernanceParams.GOVERNANCE_PARAMS_TYPE)
        with sp.if_(self.data.break_glass_contract.is_some()):
            break_glass_contract = sp.local("break_glass_contract", self.data.break_glass_contract.open_some(message=Errors.ERROR_NO_BREAK_GLASS_CONTRACT_SET))
            sp.verify((sp.sender == sp.self_address) | (sp.sender == break_glass_contract.value), Errors.ERROR_NOT_ALLOWED)
        with sp.else_():
            sp.verify(sp.sender == sp.self_address, Errors.ERROR_NOT_ALLOWED)

        self.data.governance_params = params

    """
    Updates the community fund address for the current contract.
    Requirements:
        - Sender is the contract itself.
    Params:
        - community_fund_address (sp.TAddress): The new community fund address of the DAO.
    Effects:
        - Updates the community fund address of the DAO.
    """
    @sp.entry_point(check_no_incoming_transfer=True)
    def set_community_fund_address(self, community_fund_address):
        sp.set_type(community_fund_address, sp.TAddress)
        sp.verify(sp.sender == sp.self_address, Errors.ERROR_NOT_ALLOWED)
        self.data.community_fund_address = community_fund_address

    """
    Updates the break glass contract for the DAO.
    Requirements:
        - Sender is the contract itself.
    Params:
        - break_glass_contract (sp.TOption(sp.TAddress)): The new break_glass_contract of the DAO.
    Effects:
        - Updates the break_glass_contract of the DAO.
    """
    @sp.entry_point(check_no_incoming_transfer=True)
    def set_break_glass_contract(self, break_glass_contract):
        sp.set_type(break_glass_contract, sp.TOption(sp.TAddress))
        sp.verify(sp.sender == sp.self_address, Errors.ERROR_NOT_ALLOWED)
        self.data.break_glass_contract = break_glass_contract
    
    """
    Returns the stats (number of yes/no/abstain) of the current poll.
    Params:
        - unit (sp.TUnit)
    """
    @sp.onchain_view()
    def get_current_poll_stats(self):
        
        with sp.if_(self.data.poll.is_none()):
            sp.result(sp.none)
        with sp.else_():
            votes = sp.local("votes", self.data.poll.open_some().votes)

            disc_factor = sp.local(
                "disc_factor", 
                sp.view("view_disc_factor", self.data.voting_contract, sp.unit, t = sp.TNat).open_some("Invalue View: view_disc_factor"))
            votes.value[Constants.YES_VOTE_VALUE] = votes.value[Constants.YES_VOTE_VALUE] * disc_factor.value // Constants.PRECISION_FACTOR
            votes.value[Constants.NO_VOTE_VALUE] = votes.value[Constants.NO_VOTE_VALUE] * disc_factor.value // Constants.PRECISION_FACTOR
            votes.value[Constants.ABSTAIN_VOTE_VALUE] = votes.value[Constants.ABSTAIN_VOTE_VALUE] * disc_factor.value // Constants.PRECISION_FACTOR
            sp.result(sp.some(votes.value))