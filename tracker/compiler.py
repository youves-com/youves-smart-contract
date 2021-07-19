import smartpy as sp

import tracker.constants as Constants
from tracker.oracle import DummyOracle, SignedPayloadOracle, QuipuswapOracle
from tracker.fa2 import AdministrableFA2
from tracker.savings_pool import SavingsPool
from tracker.staking_pool import StakingPool
from tracker.options_listing import OptionsListing
from tracker.governance_token import GovernanceToken
from tracker.tracker_engine import TrackerEngine

def main():
    """
    This file is used for compiling all contract such that the :obj:`tracker.deployment` module can then be used to deploy and wire everything.
    """
    sp.add_compilation_target("SyntheticAssetToken", AdministrableFA2({}))
    sp.add_compilation_target("GovernanceToken", GovernanceToken(Constants.DEFAULT_ADDRESS))
    sp.add_compilation_target("OptionsListing", OptionsListing(Constants.DEFAULT_ADDRESS, 0, Constants.DEFAULT_ADDRESS, Constants.DEFAULT_ADDRESS))
    sp.add_compilation_target("DummyOracle", DummyOracle())
    sp.add_compilation_target("SavingsPool", SavingsPool(Constants.DEFAULT_ADDRESS, Constants.DEFAULT_ADDRESS, 0))
    sp.add_compilation_target("StakingPool", StakingPool(Constants.DEFAULT_ADDRESS, Constants.DEFAULT_ADDRESS, 0, Constants.DEFAULT_ADDRESS, 0))
    sp.add_compilation_target("TrackerEngine", TrackerEngine(Constants.DEFAULT_ADDRESS, 0, administrators=sp.big_map({})))
    sp.add_compilation_target("SignedPayloadOracle", SignedPayloadOracle({},{}))
    sp.add_compilation_target("QuipuswapOracle", QuipuswapOracle(Constants.DEFAULT_ADDRESS))
    
if __name__ == '__main__':
    main()