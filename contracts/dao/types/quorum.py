import smartpy as sp


"""
A type representing a quorum cap. 
Params:
- lower (sp.TNat): The lower bound of the quorum.
- upper (sp.TNat): The upper bound of the quorum.
"""
QUORUM_CAP_TYPE = sp.TRecord(
    lower = sp.TNat, 
    upper = sp.TNat
).layout(("lower", "upper"))
