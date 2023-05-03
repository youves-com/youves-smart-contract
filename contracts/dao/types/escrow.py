import smartpy as sp

"""
A type representing possible variations of escrow paid by the proposer of a poll.
"""
ESCROW_CONTRACT_TYPE = sp.TVariant(
    fa2 = sp.TRecord(contract = sp.TAddress, token_id = sp.TNat).layout(("contract", "token_id")),
    fa1 = sp.TAddress,
    tez = sp.TUnit
)
