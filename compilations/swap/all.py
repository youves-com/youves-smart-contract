import smartpy as sp

from contracts.swap.multitoken_swap import MultitokenCurveSwap, TokenData, NULL_ADDRESS
from utils.contract_utils import Ratio
from contracts.tracker.types import TokenVariant

sp.add_compilation_target(
    "MultitokenCurveSwap", 
    MultitokenCurveSwap(
        administrators=sp.big_map(
            l={
                sp.address('KT1Q8yKdJaU5VcBL8JcxUT9PU99m53ubERk4') : 1,
                sp.address('KT1T3BFEu9WSQyRuV9Fyd7SqTU4rW3ptJ3NN') : 1,
                sp.address('tz1YY1LvD6TFH4z74pvxPQXBjAKHE5tB5Q8f') : 1,
            },
            tkey=sp.TAddress,
            tvalue=sp.TNat
        ),
        tokens=sp.map(
            l={
                sp.variant("tez", sp.unit) : TokenData.make(1_412_829, 100),
                sp.variant("fa1", sp.address("KT1PWx2mnDueood7fEmfbBDKx1D9BAnnXitn")) : TokenData.make(1_633, 1),
                sp.variant("fa2", sp.record(contract=sp.address("KT1XnTn74bUtxHfDtBmm2bGZAQfhPbvKWR8o"), token_id=sp.nat(0))) : TokenData.make(999_231, 100),
            },
            tkey=TokenVariant.get_type(),
            tvalue=TokenData.get_type()
        ),
        target_oracle=sp.address('KT1KmkbTxMNfaFRWTK8CVSFUJE93TxyM2tPs'),
        lqt_address=NULL_ADDRESS,
        lqt_total=3_000_000,
        swap_fee=Ratio.make(5, 1000), # 0.1%
        rewards_receiver=sp.address('KT1FPmpucXoiX7ZLahj1V1E5tRah1XvcnkZB'),
        rewards_ratio=Ratio.make(50, 100), # 50%
        baking_rewards_receiver=sp.address('tz1YUUsbHBAEBFaa4XM11HUY2Quv3QH6Vjpd'),
        amplitude=sp.nat(100),
        enabled=sp.bool(False)
    )
)