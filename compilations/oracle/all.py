import smartpy as sp

import utils.constants as Constants

from contracts.oracle.job_scheduler import JobScheduler
from contracts.oracle.generic_oracle import (
    PriceOracle,
    LegacyProxyOracle,
    ProxyOracle,
    RelativeProxyOracle,
)
from contracts.oracle.dummy_oracle import DummyOracle
from contracts.oracle.fail_oracle import FailOracle
from contracts.oracle.signed_payload_oracle import SignedPayloadOracle
from contracts.oracle.quipuswap_oracle import QuipuswapOracle
from contracts.oracle.plenty_oracle import PlentyOracle
from contracts.oracle.quipuswap_token_to_token_oracle import QuipuswapTokenToTokenOracle
from contracts.oracle.liquidity_pool_oracle import LPPriceOracle, RelativeLPPriceOracle
from contracts.oracle.generic_oracle import PriceOracle
from contracts.oracle.generic_oracle_v3 import PriceOracle as PriceOracleV3
from contracts.oracle.exchange_oracle import ExchangeOracle
from contracts.oracle.multitoken_swap_oracle import MultipoolOracle
from contracts.oracle.engine_oracle import EngineOracle, AsyncEngineOracle
from contracts.oracle.swap_oracle import FlatCurveTargetOracle 

sp.add_compilation_target(
    "JobScheduler", JobScheduler(sp.address("tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83"))
)
sp.add_compilation_target(
    "PriceOracle", PriceOracle(sp.address("tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83"))
)
sp.add_compilation_target(
    "LegacyProxyOracle",
    LegacyProxyOracle(sp.address("tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83"), "BTC", requires_flip=False, extra_precision_factor=sp.nat(1)),
)
sp.add_compilation_target(
    "FlippedLegacyProxyOracle",
    LegacyProxyOracle(
        sp.address("tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83"), "BTC", requires_flip=True, extra_precision_factor=sp.nat(1)
    ),
)
sp.add_compilation_target(
    "ExtraPrecisionLegacyProxyOracle",
    LegacyProxyOracle(sp.address("tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83"), "BTC", requires_flip=False, extra_precision_factor=sp.nat(1000000)),
)
sp.add_compilation_target(
    "ExtraPrecisionFlippedLegacyProxyOracle",
    LegacyProxyOracle(
        sp.address("tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83"), "BTC", requires_flip=True, extra_precision_factor=sp.nat(1000000)
    ),
)

sp.add_compilation_target(
    "ProxyOracle",
    ProxyOracle(sp.address("tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83"), "BTC", requires_flip=False, extra_precision_factor=sp.nat(1)),
)
sp.add_compilation_target(
    "FlippedProxyOracle",
    ProxyOracle(
        sp.address("tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83"), "BTC", requires_flip=True, extra_precision_factor=sp.nat(1)
    ),
)
sp.add_compilation_target(
    "ExtraPrecisionProxyOracle",
    ProxyOracle(sp.address("tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83"), "BTC", requires_flip=False, extra_precision_factor=sp.nat(1000000)),
)
sp.add_compilation_target(
    "ExtraPrecisionFlippedProxyOracle",
    ProxyOracle(
        sp.address("tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83"), "BTC", requires_flip=True, extra_precision_factor=sp.nat(1000000)
    ),
)
sp.add_compilation_target(
    "LPPriceOracle",
    LPPriceOracle(
        sp.address("tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83"),
        sp.address("tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83"),
        sp.address("tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83"),
        8,
        requires_flip=False,
    ),
)
sp.add_compilation_target(
    "FlippedLPPriceOracle",
    LPPriceOracle(
        sp.address("tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83"),
        sp.address("tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83"),
        sp.address("tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83"),
        8,
        requires_flip=True,
    ),
)
sp.add_compilation_target(
    "RelativeLPPriceOracle",
    RelativeLPPriceOracle(
        sp.address("tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83"),
        sp.address("tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83"),
        "BTC",
        requires_flip=False,
    ),
)
sp.add_compilation_target(
    "FlippedRelativeLPPriceOracle",
    RelativeLPPriceOracle(
        sp.address("tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83"),
        sp.address("tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83"),
        "BTC",
        requires_flip=True,
    ),
)
sp.add_compilation_target(
    "RelativeProxyOracle",
    RelativeProxyOracle(
        sp.address("tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83"), "BTC", "XTZ"
    ),
)

sp.add_compilation_target("DummyOracle", DummyOracle())
sp.add_compilation_target("SignedPayloadOracle", SignedPayloadOracle({}, {}))
sp.add_compilation_target("QuipuswapOracle", QuipuswapOracle(Constants.DEFAULT_ADDRESS, 12, 12))
sp.add_compilation_target("FailOracle", FailOracle())
sp.add_compilation_target(
    "PlentyOracle",
    PlentyOracle(
        Constants.DEFAULT_ADDRESS,
        Constants.DEFAULT_ADDRESS,
        0,
        Constants.DEFAULT_ADDRESS,
        0,
        12,
        12
    ),
)
sp.add_compilation_target(
    "QuipuswapTokenToTokenOracle",
    QuipuswapTokenToTokenOracle(Constants.DEFAULT_ADDRESS, 0, 12, 12),
)

sp.add_compilation_target(
    "GenericOracle",
    PriceOracle(Constants.DEFAULT_ADDRESS),
)
sp.add_compilation_target(
    "GenericOracleV3",
    PriceOracleV3(Constants.DEFAULT_ADDRESS),
)
sp.add_compilation_target(
    "ExchangeOracle",
    ExchangeOracle(sp.list([]), sp.nat(1), sp.nat(1), sp.big_map({}), 12, 12)
)

sp.add_compilation_target(
    "MultipoolOracle",
    MultipoolOracle(
        administrators=sp.big_map({}),
        price_fetching_lambda=sp.big_map({})
    ))

sp.add_compilation_target(
    "FlatCurveTargetOracle",
    FlatCurveTargetOracle(
        administrators=sp.big_map({}),
        aggregation_path=sp.list([]),
        price_precision_factor=sp.nat(Constants.PRICE_PRECISION_FACTOR),
    )
)

sp.add_compilation_target(
    "EngineOracle",
    EngineOracle(
        administrators=sp.big_map({}),
        aggregation_path=sp.list([]),
        price_precision_factor=sp.nat(Constants.PRICE_PRECISION_FACTOR),
        metadata=sp.big_map(
            l={
                "": sp.bytes(
                    "0x74657a6f732d73746f726167653a64617461"
                ),  # "tezos-storage:data"
                "data": sp.utils.bytes_of_string(
                    '{ "name": "Youves Engine Oracle", "authors": ["Youves <contact@youves.com>"], "homepage":  "https://app.youves.com" }'
                ),
            },
            tkey=sp.TString,
            tvalue=sp.TBytes,
        ),
    )
)

sp.add_compilation_target(
    "AsyncEngineOracle",
    AsyncEngineOracle(
        administrators=sp.big_map({}),
        aggregation_path=sp.list([]),
        price_precision_factor=sp.nat(Constants.PRICE_PRECISION_FACTOR),
        metadata=sp.big_map(
            l={
                "": sp.bytes(
                    "0x74657a6f732d73746f726167653a64617461"
                ),  # "tezos-storage:data"
                "data": sp.utils.bytes_of_string(
                    '{ "name": "Youves Async Engine Oracle", "authors": ["Youves <contact@youves.com>"], "homepage":  "https://app.youves.com" }'
                ),
            },
            tkey=sp.TString,
            tvalue=sp.TBytes,
        ),
    )
)