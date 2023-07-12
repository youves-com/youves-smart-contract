#include "fa2_flat_cfmm.mligo"

let test =
  let initial_storage = 
  { tokenPool = 103n ;
    tokenAddress = ("tz1Ke2h7sDdakHJQh8WX4Z372du1KChsksyU" : address) ;
    tokenMultiplier = 1n ;
#if TOKEN_IS_FA2
    tokenId = 0n ;
#endif
    cashPool = 204n ;
    cashAddress = ("tz1Ke2h7sDdakHJQh8WX4Z372du1KChsksyU" : address) ;
#if CASH_IS_FA2
    cashId = 0n ;
#endif
    cashMultiplier = 1n ;
    admin = ("tz1Ke2h7sDdakHJQh8WX4Z372du1KChsksyU" : address) ;
    proposedAdmin = ("tz1Ke2h7sDdakHJQh8WX4Z372du1KChsksyU" : address) ;
    lqtTotal = 10n ;
    lqtAddress = ("tz1Ke2h7sDdakHJQh8WX4Z372du1KChsksyU" : address) ;
    rewardRecipient = ("tz1Ke2h7sDdakHJQh8WX4Z372du1KChsksyU" : address) ;
    feeRatio = ({ numerator = 1n; denominator = 100n } : ratio) ;
  } in
  let (taddr, _, _) = Test.originate main initial_storage 0tez in
  assert (Bytes.pack (Test.get_storage taddr) = Bytes.pack (initial_storage))