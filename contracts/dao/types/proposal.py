import smartpy as sp

""" The type of a lambda that will be executed with a proposal. """
PROPOSAL_LAMBDA_TYPE = sp.TLambda(sp.TUnit, sp.TList(sp.TOperation))

"""
The type of a proposal.
Params:
- title (sp.TString): The title of the proposal
- description_link (sp.TString): A link to the proposals description.
- description_hash (sp.TString): A digest of the content at subscription link.
- proposal (PROPOSAL_LAMBDA_TYPE): The code to execute.
"""
PROPOSAL_TYPE = sp.TRecord(
    title = sp.TString,
    description_link = sp.TString,
    description_hash = sp.TString,
    proposal_lambda = PROPOSAL_LAMBDA_TYPE
).layout(("title", ("description_link", ("description_hash", "proposal_lambda"))))
