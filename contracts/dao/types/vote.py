import smartpy as sp

"""
A type representing a vote.
Params:
- vote (sp.TNat): The value of the vote. The allow vote values are 0 for no,
    1 for yes and 2 for abstain. Other values will be ignored. See contracts/dao/constants.py.
- vote_id (sp.TNat): The id of the stake used for the vote. An user can only
    vote with his staked YOUs.
"""
VOTE_PARAMS_TYPE = sp.TRecord(
    vote = sp.TNat,
    vote_id = sp.TNat,
).layout(("vote", "vote_id"))

"""
A type representing a vote stake. The stake is modeled by the one from the UnifiedStakingPool,
see contracts/tracker/unified_staking_pool.py. The stake weight is used to calculate the vote
weight.

Params:
- token_amount (sp.TNat): The token_amount deposited by the user for the stake.
- stake (sp.TNat): The stake weight. This will be used as a vote weight.
- age_timestamp (sp.TTimestamp): A timestamp used to calculate the age of the stake.
"""
VOTE_STAKE_TYPE = sp.TRecord(
    token_amount=sp.TNat,
    stake=sp.TNat,
    age_timestamp=sp.TTimestamp,
).layout(("token_amount", ("stake", "age_timestamp")))  