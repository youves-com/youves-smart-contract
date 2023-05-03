import smartpy as sp

Proposal = sp.io.import_script_from_url("file:contracts/dao/types/proposal.py")

"""
A item in the timelock
Params:
- id (sp.TNat): An automatically assigned identifier for the timelock item. This is the same ID that is
    used in polls.
- proposal (PROPOSAL_TYPE): The proposal
- execution_start_block (sp.TNat): The start block from which the item can be executed (by the proposer).
- cancelation_start_block (sp.TNat): The start block where the item can be cancelled (by anyone).
- author (sp.TAddress): The author of the proposal.
"""
TIMELOCK_TYPE = sp.TRecord(
    id = sp.TNat,
    proposal = Proposal.PROPOSAL_TYPE,
    execution_start_block = sp.TNat,
    cancelation_start_block = sp.TNat,
    author = sp.TAddress
).layout(("id", ("proposal", ("execution_start_block", ("cancelation_start_block", "author")))))