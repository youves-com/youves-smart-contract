import smartpy as sp

Poll = sp.io.import_script_from_url("file:contracts/dao/types/poll.py")

"""
A historical result of a vote.
Params:
- outcome (sp.TNat): The outcome of the poll. Each outcome has an unique identifier
    See contracts/dao/constants.
- poll (Poll.POLL_TYPE): The poll and the results.
"""
PROPOSAL_OUTCOME_TYPE = sp.TRecord(
    outcome = sp.TNat,
    poll = Poll.POLL_TYPE
).layout(("outcome", "poll"))