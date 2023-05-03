import smartpy as sp

KEY_TYPE = sp.TRecord(
    voter = sp.TAddress,
    vote_id = sp.TNat,
    proposal_id = sp.TNat,
).layout(("voter", ("vote_id", "proposal_id")))

VALUE_TYPE = sp.TRecord(
    vote_value = sp.TNat,
    weight = sp.TNat,
).layout(("vote_value", "weight"))

VOTE_TRACKER_TYPE = sp.TBigMap(KEY_TYPE, VALUE_TYPE)