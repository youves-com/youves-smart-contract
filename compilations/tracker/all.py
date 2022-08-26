import smartpy as sp

import utils.constants as Constants
from utils.fa2 import AdministrableFA2
from utils.viewer import Viewer

from contracts.tracker.token_options_listing import TokenOptionsListing
from contracts.tracker.async_token_tracker_engine import AsyncTokenTrackerEngine
from contracts.tracker.auto_manager import AutoManager
from contracts.tracker.governance_token import GovernanceToken
from contracts.tracker.interest_rate_updater_exponential import (
    InterestRateUpdaterExponential,
)
from contracts.tracker.interest_rate_updater_linear import InterestRateUpdaterLinear
from contracts.tracker.liquidity_farm import LiquidityFarm
from contracts.tracker.long_staking_pool import LongStakingPool
from contracts.tracker.options_listing import OptionsListing
from contracts.tracker.savings_pool import SavingsPool
from contracts.tracker.stake_manager import StakeManager
from contracts.tracker.staking_pool import StakingPool
from contracts.tracker.token_collateral_tracker_engine import (
    TokenTrackerEngine as TokenTrackerEngineV2,
)
from contracts.tracker.tez_collateral_tracker_engine_v3 import TezCollateralTrackerEngine

from contracts.tracker.token_collateral_tracker_engine_v3 import (
    TokenTrackerEngine as TokenTrackerEngineV3,
)
from contracts.tracker.tracker_engine import TrackerEngine
from contracts.tracker.unified_staking_pool import UnifiedStakingPool
from contracts.tracker.vester import Vester

sp.add_compilation_target("SyntheticAssetToken", AdministrableFA2({}))
sp.add_compilation_target("GovernanceToken", GovernanceToken(Constants.DEFAULT_ADDRESS))
sp.add_compilation_target(
    "OptionsListing",
    OptionsListing(
        Constants.DEFAULT_ADDRESS,
        0,
        Constants.DEFAULT_ADDRESS,
        Constants.DEFAULT_ADDRESS,
    ),
)
sp.add_compilation_target(
    "SavingsPool",
    SavingsPool(Constants.DEFAULT_ADDRESS, 0, {}),
)
sp.add_compilation_target(
    "StakingPool",
    StakingPool(
        Constants.DEFAULT_ADDRESS,
        Constants.DEFAULT_ADDRESS,
        0,
        Constants.DEFAULT_ADDRESS,
        0,
    ),
)
sp.add_compilation_target(
    "TrackerEngine",
    TrackerEngine(Constants.DEFAULT_ADDRESS, 0, administrators=sp.big_map({})),
)
sp.add_compilation_target("Viewer", Viewer())
sp.add_compilation_target("Vester", Vester(Constants.DEFAULT_ADDRESS, 0))
sp.add_compilation_target(
    "StakeManager",
    StakeManager(Constants.DEFAULT_ADDRESS, administrators=sp.big_map({})),
)
sp.add_compilation_target(
    "LiquidityFarm",
    LiquidityFarm(
        Constants.DEFAULT_ADDRESS,
        0,
        Constants.DEFAULT_ADDRESS,
        administrators=sp.map({}),
    ),
)
sp.add_compilation_target(
    "FA2TrackerEngineV2",
    TokenTrackerEngineV2(
        Constants.DEFAULT_ADDRESS,
        0,
        Constants.DEFAULT_ADDRESS,
        0,
        Constants.TOKEN_TYPE_FA2,
        1,
        administrators=sp.big_map({}),
    ),
)

sp.add_compilation_target(
    "FA2TrackerEngineV3",
    TokenTrackerEngineV3(
        token_contract=Constants.DEFAULT_ADDRESS,
        token_id=0,
        collateral_token_contract=Constants.DEFAULT_ADDRESS,
        collateral_token_id=0,
        collateral_token_type=Constants.TOKEN_TYPE_FA2,
        price_extra_precision_factor=1,
        token_decimals=12,
        collateral_token_decimals=6,
        administrators=sp.big_map({}),
    ),
)

sp.add_compilation_target(
    "FA2OptionsListing",
    TokenOptionsListing(
        Constants.DEFAULT_ADDRESS,
        0,
        Constants.DEFAULT_ADDRESS,
        0,
        Constants.DEFAULT_ADDRESS,
        Constants.DEFAULT_ADDRESS,
    ),
)
sp.add_compilation_target(
    "InterestRateUpdaterLinear",
    InterestRateUpdaterLinear(
        [Constants.DEFAULT_ADDRESS],
        Constants.DEFAULT_ADDRESS,
        Constants.DEFAULT_ADDRESS,
        administrators=sp.big_map({}),
    ),
)
sp.add_compilation_target(
    "FA1TrackerEngine",
    AsyncTokenTrackerEngine(
        Constants.DEFAULT_ADDRESS,
        0,
        Constants.DEFAULT_ADDRESS,
        0,
        Constants.TOKEN_TYPE_FA1,
        administrators=sp.big_map({}),
        token_decimals=12,
        collateral_token_decimals=0,
    ),
)
sp.add_compilation_target(
    "FA1OptionsListing",
    TokenOptionsListing(
        Constants.DEFAULT_ADDRESS,
        0,
        Constants.DEFAULT_ADDRESS,
        0,
        Constants.DEFAULT_ADDRESS,
        Constants.DEFAULT_ADDRESS,
        collateral_token_type=Constants.TOKEN_TYPE_FA1,
        token_decimals=12,
        collateral_token_decimals=0,
    ),
)
sp.add_compilation_target(
    "InterestRateUpdaterExponential",
    InterestRateUpdaterExponential(
        [Constants.DEFAULT_ADDRESS],
        Constants.DEFAULT_ADDRESS,
        Constants.DEFAULT_ADDRESS,
        administrators=sp.big_map({}),
    ),
)
sp.add_compilation_target(
    "FA2LongStakingPool",
    LongStakingPool(
        Constants.DEFAULT_ADDRESS,
        0,
        Constants.TOKEN_TYPE_FA2,
        Constants.DEFAULT_ADDRESS,
        0,
    ),
)
sp.add_compilation_target(
    "FA1LongStakingPool",
    LongStakingPool(
        Constants.DEFAULT_ADDRESS,
        0,
        Constants.TOKEN_TYPE_FA1,
        Constants.DEFAULT_ADDRESS,
        0,
    ),
)
sp.add_compilation_target(
    "UnifiedStakingPool",
    UnifiedStakingPool(
        Constants.DEFAULT_ADDRESS,
        sp.nat(0),
        sp.nat(180 * 24 * 60 * 60),
        administrators=sp.big_map({}),
    ),
)
sp.add_compilation_target("AutoManager", AutoManager(sp.big_map({})))
sp.add_compilation_target(
    "FA1TrackerEngineExtraPrecisionOracle",
    AsyncTokenTrackerEngine(
        Constants.DEFAULT_ADDRESS,
        0,
        Constants.DEFAULT_ADDRESS,
        0,
        Constants.TOKEN_TYPE_FA1,
        administrators=sp.big_map({}),
        token_decimals=12,
        collateral_token_decimals=8,
        price_extra_precision_factor=1000000,
    ),
)
sp.add_compilation_target(
    "FA1OptionsListingExtraPrecisionOracle",
    TokenOptionsListing(
        Constants.DEFAULT_ADDRESS,
        0,
        Constants.DEFAULT_ADDRESS,
        0,
        Constants.DEFAULT_ADDRESS,
        Constants.DEFAULT_ADDRESS,
        collateral_token_type=Constants.TOKEN_TYPE_FA1,
        token_decimals=12,
        collateral_token_decimals=8,
        price_extra_precision_factor=1000000,
    ),
)

sp.add_compilation_target(
    "TezCollateralTrackerEngine",
    TezCollateralTrackerEngine(
        Constants.DEFAULT_ADDRESS,
        0,
        Constants.DEFAULT_ADDRESS,
        0,
        1,
        12, # token decimals
        6, # collateral decimals
        administrators=sp.big_map({}),
    ),
)