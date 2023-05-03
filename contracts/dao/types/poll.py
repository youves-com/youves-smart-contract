import smartpy as sp

Vote = sp.io.import_script_from_url("file:contracts/dao/types/vote.py")
Quorum = sp.io.import_script_from_url("file:contracts/dao/types/quorum.py")
Proposal = sp.io.import_script_from_url("file:contracts/dao/types/proposal.py")

"""
Poll type for a proposal.
Params:
- id (sp.TNat): An automatically assigned identifier for the poll.
- proposal (PROPOSAL_TYPE): The proposal to be voted on.
- voting_start_block (sp.TNat): The first block of voting.
- voting_end_block (sp.TNat): The last block of voting.
- votes (sp.TMap(sp.TNat, sp.TNat)): A map for the total votes weight for either yes/no/abstain
    each with an unique identifier (see contracts/dao/constants.py)
- total_votes (sp.TNat): The total weight of all votes.
- author (sp.TAddress): The author of the proposal.
- escrow_amount (sp.TNat): The amount of tokens/tez escrowed for the proposal.
- quorum (sp.TNat): The quorum the poll needs to achieve. 
- quorumCap (QUORUM_CAP_TYPE): The quorum lower and upper bounds of the proposal.
"""
POLL_TYPE = sp.TRecord(
  id = sp.TNat,
  proposal = Proposal.PROPOSAL_TYPE,
  voting_start_block = sp.TNat,
  voting_end_block = sp.TNat,
  votes = sp.TMap(sp.TNat, sp.TNat),
  total_votes = sp.TNat,
  author = sp.TAddress,
  escrow_amount = sp.TNat,
  quorum = sp.TNat,
  quorum_cap = Quorum.QUORUM_CAP_TYPE
).layout(("id", ("proposal", ("voting_start_block", ("voting_end_block", ("votes", ("total_votes", ("author", ("escrow_amount", ("quorum", "quorum_cap"))))))))))