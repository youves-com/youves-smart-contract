import smartpy as sp

DEFAULT_ADDRESS = sp.address("tz1RKmJwoAiaqFdjQYSbFy1j7u7UhEFsqXq7")

# Allowed values for a vote. All other vote values will be ignored.
NO_VOTE_VALUE = sp.nat(0)
YES_VOTE_VALUE = sp.nat(1)
ABSTAIN_VOTE_VALUE = sp.nat(2)
START_OF_INVALID_VOTE_VALUES = sp.nat(3)

# Map to keep track of the votes.
INITIAL_VOTING_MAP = sp.map(
    l = {
        NO_VOTE_VALUE : sp.nat(0),
        YES_VOTE_VALUE : sp.nat(0),
        ABSTAIN_VOTE_VALUE : sp.nat(0),
    }
)

# Proposal outcome codes.
PROPOSAL_OUTCOME_FAILED = 0
PROPOSAL_OUTCOME_IN_TIMELOCK = 1
PROPOSAL_OUTCOME_EXECUTED = 2
PROPOSAL_OUTCOME_CANCELLED = 3
PROPOSAL_OUTCOME_VETOED = 4

# Percentage scale
PERCENTAGE_SCALE = sp.nat(100)

# Limit the number of stakes returned in one operation
MAX_STAKES_ALLOWED_TO_BE_RETURNED = 50

PRECISION_FACTOR = sp.nat(10**12)