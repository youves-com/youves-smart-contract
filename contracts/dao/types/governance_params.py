import smartpy as sp

Quorum = sp.io.import_script_from_url("file:contracts/dao/types/quorum.py")

"""
Governance parameters of the DAO.
Params:
- escrow_amount (sp.TNat): The amount to escrow when a proposal is submitted.
- vote_delay_blocks (sp.TNat): The number of blocks to delay the voting once a proposal is submitted.
- vote_length_blocks (sp.TNat): The number of blocks a vote takes.
- min_yes_votes_percentage_for_escrow_return (sp.TNat): The minimum percentage
    yes votes needed to receive the escrow back. Represented with scale = 2.
    Example: 20 = .20 = 20%.
- timelock_execution_delay_blocks (sp.TNat): The number of blocks that needs to pass
    after a vote has ended in order for it to be eligible for execution by the proposer.
- timelock_cancelation_delay_blocks (sp.TNat): The number of blocks that needs to pass
    after a vote has ended in order for it to be eligible for cancelation by anyone.
    This allows to clear a timelock if the proposer has not executed the operation.
    Always needs to be true: timelock_cancelation_delay_blocks > timelock_execution_delay_blocks.
- super_majority_percentage (sp.TNat): The percentage of votes needed for a suprt
    majority. Represented with scale = 2. Example: 20 = .20 = 20%.
- quorum_cap (QUORUM_CAP_TYPE): The lower and upper bounds for the quorum.
"""
GOVERNANCE_PARAMS_TYPE = sp.TRecord(
    escrow_amount = sp.TNat,
    vote_delay_blocks = sp.TNat,
    vote_length_blocks = sp.TNat,
    min_yes_votes_percentage_for_escrow_return = sp.TNat,
    timelock_execution_delay_blocks = sp.TNat,
    timelock_cancelation_delay_blocks = sp.TNat,
    super_majority_percentage = sp.TNat,
    quorum_cap = Quorum.QUORUM_CAP_TYPE,
).layout(("escrow_amount", ("vote_delay_blocks", ("vote_length_blocks", ("min_yes_votes_percentage_for_escrow_return", ("timelock_execution_delay_blocks", ("timelock_cancelation_delay_blocks", ("super_majority_percentage", "quorum_cap"))))))))