#include "flat_cfmm.mligo"



let test =
  let initial_storage = 
  { tokenPool = 103n ;
    cashPool = 204n ;
    lqtTotal = 10n ;
    pendingPoolUpdates = 0n ;
    tokenAddress = ("tz1Ke2h7sDdakHJQh8WX4Z372du1KChsksyU" : address) ;
#if TOKEN_IS_FA2
    tokenId = 0n ;
#endif
    cashAddress = ("tz1Ke2h7sDdakHJQh8WX4Z372du1KChsksyU" : address) ;
#if CASH_IS_FA2
    cashId = 0n ;
#endif
    lqtAddress = ("tz1Ke2h7sDdakHJQh8WX4Z372du1KChsksyU" : address) ;
  } in
  let (taddr, _, _) = Test.originate main initial_storage 0tez in
  assert (Bytes.pack (Test.get_storage taddr) = Bytes.pack (initial_storage))

