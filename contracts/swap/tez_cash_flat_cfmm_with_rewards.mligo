(* Pick one of TOKEN_IS_FA12, TOKEN_IS_FA2 *)
#define TOKEN_IS_FA2
// #define TOKEN_IS_FA12


(* ============================================================================
 * Useful types
 * ============================================================================ *)

type ratio = [@layout:comb] { 
    numerator : nat ;
    denominator : nat ;
}

type add_liquidity = [@layout:comb] { 
    owner : address ; (* address that will own the minted lqt *)
    minLqtMinted : nat ; (* minimum number of lqt that must be minter *)
    maxTokensDeposited : nat ; (* maximum number of tokens that may be deposited *)
    deadline : timestamp ; (* time before which the request must be completed *)
}

type remove_liquidity = [@layout:comb] { 
    [@annot:to] to_ : address ; (* recipient of the liquidity redemption *)
    lqtBurned : nat ;  (* amount of lqt owned by sender to burn *)
    minCashWithdrawn : nat ; (* minimum amount of cash to withdraw *)
    minTokensWithdrawn : nat ; (* minimum amount of tokens to withdraw *)
    deadline : timestamp ; (* time before which the request must be completed *)
}

type cash_to_token = [@layout:comb] {
    [@annot:to] to_ : address ;  (* where to send the tokens *)
    minTokensBought : nat ; (* minimum amount of tokens that must be bought *)
    deadline : timestamp ; (* time before which the request must be completed *)
}

type token_to_cash = [@layout:comb] {
    [@annot:to] to_ : address ; (* where to send the cash *)
    tokensSold : nat ; (* how many tokens are being sold *)
    minCashBought : nat ; (* minimum amount of cash desired *)
    deadline : timestamp ; (* time before which the request must be completed *)
}

type token_or_cash = Token | Cash

(* getbalance update types for fa12 and fa2 *)
type update_fa12_pool = nat
type update_fa2_pool = ((address * nat)  * nat) list

#if TOKEN_IS_FA2
type update_token_pool_internal = update_fa2_pool
#endif

#if TOKEN_IS_FA12
type update_token_pool_internal = update_fa12_pool
#endif

type price_callback = (nat contract)

type storage = [@layout:comb] { 
    tokenAddress : address ;
#if TOKEN_IS_FA2
    tokenId : nat ;
#endif
    tokenPool : nat ;
    tokenMultiplier : nat ;

    cashPool : nat ;
    cashMultiplier : nat ;
    
    admin: address ;
    proposedAdmin: address ;
    lqtTotal : nat ;
    lqtAddress : address ;
    rewardRecipient: address ;
    pendingPoolUpdates : nat;
    feeRatio : ratio ;
    targetPriceOracle: address ;
}

type entrypoint =
| Default                    of unit
| AddLiquidity               of add_liquidity
| AddLiquidityInternal       of add_liquidity * address
| RemoveLiquidity            of remove_liquidity
| RemoveLiquidityInternal    of remove_liquidity * address
| CashToToken                of cash_to_token
| CashToTokenInternal        of cash_to_token * address
| TokenToCash                of token_to_cash
| TokenToCashInternal        of token_to_cash * address
| SetLqtAddress              of address
| SetRewardRecipient         of address
| SetDelegate                of key_hash option
| ProposeNewAdmin            of address
| AcceptAdminProposal        of unit
| ChangeFee                  of ratio
| UpdatePools                of unit
| UpdateTokenPoolInternal    of update_token_pool_internal
| FetchLqtTokenPriceInToken  of price_callback
| FetchLqtTokenPriceInCash   of price_callback
| FetchLqtTokenPriceInternal of price_callback * token_or_cash

(*  Type Synonyms *)
type result = operation list * storage

(* FA2 *)
type token_id = nat
type balance_of = ((address * token_id) list * ((((address * nat) * nat) list) contract))
(* FA1.2 *)
type get_balance = address * (nat contract)

#if TOKEN_IS_FA2
type token_contract_transfer = (address * (address * (token_id * nat)) list) list
#else (*  FA1.2 *)
type token_contract_transfer = address * (address * nat)
#endif

(* custom entrypoint for LQT FA1.2 *)
type mintOrBurn = [@layout:comb] {
    quantity : int ;
    target : address 
}

(* =============================================================================
 * Error codes
 * ============================================================================= *)
[@inline] let error_TOKEN_CONTRACT_MUST_HAVE_A_TRANSFER_ENTRYPOINT  = 0n
[@inline] let error_ASSERTION_VIOLATED_EXCEEDING_POOL_RESOURCES = 1n
[@inline] let error_ASSERTION_VIOLATED_NEGATIVE_DIFFERENCE = 2n
[@inline] let error_DEADLINE_EXCEEDED = 3n
[@inline] let error_MAX_TOKENS_DEPOSITED_MUST_BE_GREATER_THAN_OR_EQUAL_TO_TOKENS_DEPOSITED = 4n
[@inline] let error_LQT_MINTED_MUST_BE_GREATER_THAN_MIN_LQT_MINTED = 5n
[@inline] let error_PENDING_POOL_UPDATES_MUST_BE_ZERO = 6n
[@inline] let error_ONLY_NEW_MANAGER_CAN_ACCEPT = 7n
[@inline] let error_CASH_BOUGHT_MUST_BE_GREATER_THAN_OR_EQUAL_TO_MIN_CASH_BOUGHT = 8n
[@inline] let error_INVALID_TO_ADDRESS = 9n
[@inline] let error_AMOUNT_MUST_BE_ZERO = 10n
[@inline] let error_THE_AMOUNT_OF_CASH_WITHDRAWN_MUST_BE_GREATER_THAN_OR_EQUAL_TO_MIN_CASH_WITHDRAWN = 11n
[@inline] let error_LQT_CONTRACT_MUST_HAVE_A_MINT_OR_BURN_ENTRYPOINT = 12n
[@inline] let error_THE_AMOUNT_OF_TOKENS_WITHDRAWN_MUST_BE_GREATER_THAN_OR_EQUAL_TO_MIN_TOKENS_WITHDRAWN = 13n
[@inline] let error_CANNOT_BURN_MORE_THAN_THE_TOTAL_AMOUNT_OF_LQT = 14n
[@inline] let error_TOKEN_POOL_MINUS_TOKENS_WITHDRAWN_IS_NEGATIVE = 15n
[@inline] let error_CASH_POOL_MINUS_CASH_WITHDRAWN_IS_NEGATIVE = 16n
[@inline] let error_CASH_POOL_MINUS_CASH_BOUGHT_IS_NEGATIVE = 17n
[@inline] let error_TOKENS_BOUGHT_MUST_BE_GREATER_THAN_OR_EQUAL_TO_MIN_TOKENS_BOUGHT = 18n
[@inline] let error_TOKEN_POOL_MINUS_TOKENS_BOUGHT_IS_NEGATIVE = 19n
[@inline] let error_ONLY_MANAGER_CAN_SET_BAKER = 20n
[@inline] let error_ONLY_MANAGER_CAN_SET_MANAGER = 21n
[@inline] let error_BAKER_PERMANENTLY_FROZEN = 22n
[@inline] let error_LQT_ADDRESS_ALREADY_SET = 24n
[@inline] let error_CALL_NOT_FROM_AN_IMPLICIT_ACCOUNT = 25n
[@inline] let error_NOT_ADMIN = 26n
[@inline] let error_NOT_PROPOSED_ADMIN = 27n
#if TOKEN_IS_FA2
[@inline] let error_INVALID_FA2_TOKEN_CONTRACT_MISSING_BALANCE_OF = 28n
#else
[@inline] let error_INVALID_FA12_TOKEN_CONTRACT_MISSING_GETBALANCE = 28n
#endif
[@inline] let error_THIS_ENTRYPOINT_MAY_ONLY_BE_CALLED_BY_GETBALANCE_OF_TOKENADDRESS = 29n
[@inline] let error_INVALID_FA2_BALANCE_RESPONSE = 30n
[@inline] let error_INVALID_INTERMEDIATE_CONTRACT = 31n
[@inline] let error_THIS_ENTRYPOINT_MAY_ONLY_BE_CALLED_BY_GETBALANCE_OF_CASHADDRESS = 32n
[@inline] let error_TEZ_DEPOSIT_WOULD_BE_BURNED = 33n
[@inline] let error_INVALID_RECEIVER = 35n
[@inline] let error_THIS_ENTRYPOINT_MAY_ONLY_BE_CALLED_BY_THE_CONTRACT = 36n
[@inline] let error_MISSING_ORACLE_VIEW = 37n
[@inline] let error_PENDING_POOL_UPDATES_CANNOT_DROP_BELOW_ZERO = 38n

(* =============================================================================
 * Constants
 * ============================================================================= *)

[@inline] let null_address = ("tz1Ke2h7sDdakHJQh8WX4Z372du1KChsksyU" : address)
[@inline] let price_precision_factor = 1000000n

(* =============================================================================
 * Functions
 * ============================================================================= *)

(* this is slightly inefficient to inline, but, nice to have a clean stack for
   the entrypoints for the Coq verification *)
[@inline]
let mutez_to_natural (a: tez) : nat =  a / 1mutez

[@inline]
let natural_to_mutez (a: nat): tez = a * 1mutez

(* round up division. *)
[@inline]
let ceildiv (numerator : nat) (denominator : nat) : nat = abs ((- numerator) / (int denominator))

[@inline]
let mint_or_burn (storage : storage) (target : address) (quantity : int) : operation =
    (* Returns an operation that mints or burn lqt from the lqt FA1.2 contract. A negative quantity
       corresponds to a burn, a positive one to a mint. *)
    let lqt_admin : mintOrBurn contract = 
        match (Tezos.get_entrypoint_opt "%mintOrBurn" storage.lqtAddress :  mintOrBurn contract option) with
            | None -> (failwith error_LQT_CONTRACT_MUST_HAVE_A_MINT_OR_BURN_ENTRYPOINT : mintOrBurn contract)
            | Some contract -> contract in
    Tezos.transaction {quantity = quantity ; target = target} 0mutez lqt_admin

[@inline]
let token_transfer (storage : storage) (from : address) (to_ : address) (token_amount : nat) : operation =
    (* Returns an operation that transfers tokens between from and to. *)
    let token_contract: token_contract_transfer contract =
        match (Tezos.get_entrypoint_opt "%transfer" storage.tokenAddress : token_contract_transfer contract option) with
            | None -> (failwith error_TOKEN_CONTRACT_MUST_HAVE_A_TRANSFER_ENTRYPOINT : token_contract_transfer contract)
            | Some contract -> contract in

#if TOKEN_IS_FA2
    Tezos.transaction [(from, [(to_, (storage.tokenId, token_amount))])] 0mutez token_contract
#else
    Tezos.transaction (from, (to_, token_amount)) 0mutez token_contract
#endif

(* =============================================================================
 * Entrypoint Functions
 * ============================================================================= *)

(* We assume the contract is originated with at least one liquidity
 * provider set up already, so lqtTotal, tokenPool and cashPool will
 * always be positive after the initial setup, unless all liquidity is
 * removed, at which point the contract is considered dead and stops working
 * properly. If this is a concern, at least one address should keep at least a
 * very small amount of liquidity in the contract forever. *)

let add_liquidity (param: add_liquidity) (storage: storage) : result =
    (* Entrypoint to add liqduity to the CFMM. First the pools of the CFMM are updated with the latest
    values and then the liquidity is added to the contract *)
    let update_pools_ep : unit contract  = Tezos.self "%updatePools" in
    let internal_call_ep: (add_liquidity * address) contract = Tezos.self "%addLiquidityInternal" in

    let update_pools_operation =  (Tezos.transaction () 0mutez update_pools_ep) in
    let internal_param = (param, Tezos.get_sender ()) in
    let amount = (Tezos.get_amount ()) in
    let internal_call_operation = (Tezos.transaction internal_param amount internal_call_ep) in

    ([update_pools_operation; internal_call_operation], storage) 

let add_liquidity_internal (param : add_liquidity) (sender : address) (storage: storage) : result =
    (* Adds liquidity to the contract, mints lqt tokens in exchange for the deposited liquidity. *)
    let {
        owner = owner ;
        minLqtMinted = minLqtMinted ;
        maxTokensDeposited = maxTokensDeposited ;
        deadline = deadline
    } = param in
    let cashDeposited = mutez_to_natural (Tezos.get_amount ()) in

    if storage.pendingPoolUpdates > 0n then
        (failwith error_PENDING_POOL_UPDATES_MUST_BE_ZERO : result)
    else if Tezos.get_now () >= deadline then
        (failwith error_DEADLINE_EXCEEDED : result)
    else if Tezos.get_sender () <> Tezos.get_self_address () then
        (failwith error_THIS_ENTRYPOINT_MAY_ONLY_BE_CALLED_BY_THE_CONTRACT : result)
    else
        (* The contract is initialized, use the existing exchange rate mints nothing if the contract has been emptied, but that's OK *)
        (* We need to have this workaround for the cashPool because the amount of deposited cash (tez) is
           immediately sent to the contract and we need to not take it into account *)
        let cashPool   : nat = match is_nat (storage.cashPool - cashDeposited) with
            | None -> (failwith error_ASSERTION_VIOLATED_NEGATIVE_DIFFERENCE : nat)
            | Some val -> val in
        let lqtMinted : nat = cashDeposited * storage.lqtTotal / cashPool in
        let tokensDeposited : nat = ceildiv (cashDeposited * storage.tokenPool) cashPool in

        if tokensDeposited > maxTokensDeposited then
            (failwith error_MAX_TOKENS_DEPOSITED_MUST_BE_GREATER_THAN_OR_EQUAL_TO_TOKENS_DEPOSITED : result)
        else if lqtMinted < minLqtMinted then
            (failwith error_LQT_MINTED_MUST_BE_GREATER_THAN_MIN_LQT_MINTED : result)
        else
            let storage = { storage with
                lqtTotal  = storage.lqtTotal + lqtMinted ;
                tokenPool = storage.tokenPool + tokensDeposited ;
            } in

            (* send tokens from sender to self *)
            let op_token = token_transfer storage sender (Tezos.get_self_address ()) tokensDeposited in
            (* mint lqt tokens for them *)
            let op_lqt = mint_or_burn storage owner (int lqtMinted) in
            ([op_token; op_lqt], storage)

let remove_liquidity (param: remove_liquidity) (storage: storage) : result =
    (* Entrypoint to remove liqduity to the CFMM. First the pools of the CFMM are updated with the latest
    values and then the liquidity is removed from the contract *)
    if (Tezos.get_amount ()) > 0mutez then
        (failwith error_AMOUNT_MUST_BE_ZERO : result)
    else begin
        let update_pools_ep : unit contract  = Tezos.self "%updatePools" in
        let internal_call_ep: (remove_liquidity * address) contract = Tezos.self "%removeLiquidityInternal" in

        let update_pools_operation =  (Tezos.transaction () 0mutez update_pools_ep) in
        let internal_param = (param, Tezos.get_sender ()) in
        let internal_call_operation = (Tezos.transaction internal_param 0mutez internal_call_ep) in

        ([update_pools_operation; internal_call_operation], storage) 
    end

let remove_liquidity_internal (param : remove_liquidity) (sender : address) (storage : storage) : result =
    (* Removes liquidity to the contract by burning lqt. *)
    let { 
        to_ = to_ ;
        lqtBurned = lqtBurned ;
        minCashWithdrawn = minCashWithdrawn ;
        minTokensWithdrawn = minTokensWithdrawn ;
        deadline = deadline
    } = param in

    if storage.pendingPoolUpdates > 0n then
        (failwith error_PENDING_POOL_UPDATES_MUST_BE_ZERO : result)
    else if Tezos.get_now () >= deadline then
        (failwith error_DEADLINE_EXCEEDED : result)
    else if Tezos.get_sender () <> Tezos.get_self_address () then
        (failwith error_THIS_ENTRYPOINT_MAY_ONLY_BE_CALLED_BY_THE_CONTRACT : result)
    else begin
        let cashWithdrawn : nat = (lqtBurned * storage.cashPool) / storage.lqtTotal in
        let tokensWithdrawn : nat = (lqtBurned * storage.tokenPool) / storage.lqtTotal in

        (* Check that minimum withdrawal conditions are met *)
        if cashWithdrawn < minCashWithdrawn then
            (failwith error_THE_AMOUNT_OF_CASH_WITHDRAWN_MUST_BE_GREATER_THAN_OR_EQUAL_TO_MIN_CASH_WITHDRAWN : result)
        else if tokensWithdrawn < minTokensWithdrawn  then
            (failwith error_THE_AMOUNT_OF_TOKENS_WITHDRAWN_MUST_BE_GREATER_THAN_OR_EQUAL_TO_MIN_TOKENS_WITHDRAWN : result)
        (* Proceed to form the operations and update the storage *)
        else begin
            (* calculate lqtTotal, convert int to nat *)
            let newLqtTotal = match is_nat (storage.lqtTotal - lqtBurned) with
                (* This check should be unecessary, the fa12 logic normally takes care of it *)
                | None -> (failwith error_CANNOT_BURN_MORE_THAN_THE_TOTAL_AMOUNT_OF_LQT : nat)
                | Some n -> n in
            (* Calculate tokenPool, convert int to nat *)
            let newTokenPool = match is_nat (storage.tokenPool - tokensWithdrawn) with
                | None -> (failwith error_TOKEN_POOL_MINUS_TOKENS_WITHDRAWN_IS_NEGATIVE : nat)
                | Some n -> n in
            let newCashPool = match is_nat (storage.cashPool - cashWithdrawn) with
                | None -> (failwith error_CASH_POOL_MINUS_CASH_WITHDRAWN_IS_NEGATIVE : nat)
                | Some n -> n in
            let op_lqt = mint_or_burn storage sender (0 - lqtBurned) in
            let op_token = token_transfer storage (Tezos.get_self_address ()) to_ tokensWithdrawn in

            let cashWithdrawnInMutez = natural_to_mutez cashWithdrawn in
            let receiver : unit contract =
                match (Tezos.get_contract_opt to_ : unit contract option) with
                    | Some (contract) -> contract
                    | None -> (failwith error_INVALID_RECEIVER : unit contract) in
            let op_cash = Tezos.transaction () cashWithdrawnInMutez receiver in
            let storage = { storage with 
                cashPool = newCashPool ; 
                lqtTotal = newLqtTotal ;
                tokenPool = newTokenPool
            } in
            ([op_lqt; op_token; op_cash], storage)
        end
    end

let change_fee (newFee: ratio) (storage : storage) : result =
    (* Change the swap fee. Only an admin can call this entrypoint *)
    if (Tezos.get_sender ()) <> storage.admin then
        (failwith error_NOT_ADMIN : result)
    else
        (([] : operation list), {storage with feeRatio = newFee})

let util (x: nat) (y: nat) : nat * nat =
    (* Computes the following values (x+y)^8 - (x-y)^8 and the derivitative of it 8 * ((x-y)^7 + (x+y)^7) *)
    let plus = x + y in
    let minus = x - y  in
    let plus_2 = plus * plus in
    let plus_4 = plus_2 * plus_2 in
    let plus_8 = plus_4 * plus_4 in
    let plus_7 = plus_8 / plus in
    let minus_2 = minus * minus in
    let minus_4 = minus_2 * minus_2 in
    let minus_8 = minus_4 * minus_4 in
    let minus_7 = if minus = 0 then 0 else minus_8 / minus in
    (* minus_7 + plus_7 should always be positive *)
    (* since x > 0 and y > 0, x + y > x - y and therefore (x + y)^7 > (x - y)^7 and ((x + y)^7 - (x - y)^7 > 0 *)
    let difference_8 = match is_nat (plus_8 - minus_8) with
        | None -> (failwith error_ASSERTION_VIOLATED_NEGATIVE_DIFFERENCE: nat)
        | Some n -> n in
    let sum_7 = match is_nat (minus_7 + plus_7) with
        | None -> (failwith error_ASSERTION_VIOLATED_NEGATIVE_DIFFERENCE: nat)
        | Some n -> n in

    (difference_8, 8n * sum_7)

type newton_param = {
    x : nat ; 
    y : nat ; 
    dx : nat ; 
    dy : nat ; 
    u : nat ; 
    n : int
}

let rec newton (p : newton_param) : nat =
    if p.n = 0 then
        p.dy
    else
        let diff_y = match is_nat (p.y - p.dy) with
            | None -> (failwith error_ASSERTION_VIOLATED_NEGATIVE_DIFFERENCE: nat)
            | Some n -> n in
        let new_u, new_du_dy = util (p.x + p.dx) (diff_y) in
        (* new_u - p.u > 0 because dy remains an underestimate *)
        
        let dy = match is_nat (new_u - p.u) with
            | None -> (failwith error_ASSERTION_VIOLATED_NEGATIVE_DIFFERENCE: nat)
            | Some n -> p.dy + n / new_du_dy in
        (* dy is an underestimate because we start at 0 and the utility curve is convex *)
        newton {p with dy = dy ; n = p.n - 1}

let tokensBought (cashPool : nat) (cashMultiplier : nat) (tokenPool : nat) (tokenMultiplier : nat) (cashSold : nat) : nat =
    (* computes the tokens bought using the newton approximation method given the cash/tokens pool and
    the amount of cash sold. The (cash/token)Multipliers are used to make sure that x and y can be expressed in
    the same power of 10 (e.g if cash has 6 decimals and token has 12 decimals, we will multiple the cash by a factor
    of 10^6 *)
    let x = cashPool * cashMultiplier in
    let y = tokenPool * tokenMultiplier in
    (* 4 round is enough for most cases and underestimates the true payoff, so the user
        can always break up a trade for better terms *)
    let u, _ = util x y in
    (newton {x = x; y = y ; dx = cashSold * cashMultiplier ; dy = 0n ; u = u ; n = 5}) / tokenMultiplier

let cashBought (cashPool : nat) (cashMultiplier : nat) (tokenPool : nat) (tokenMultiplier : nat) (tokensSold : nat) : nat =
    (* computes the cash bought using the newton approximation method given the cash/tokens pool and
    the amount of tokens sold. The (cash/token)Multipliers are used to make sure that x and y can be expressed in
    the same power of 10 (e.g if cash has 6 decimals and token has 12 decimals, we will multiple the cash by a factor
    of 10^6 *)
    let x = tokenPool * tokenMultiplier  in
    let y = cashPool * cashMultiplier in
    let u, _ = util x y in
    (newton {x = x; y = y ; dx = tokensSold * tokenMultiplier ; dy = 0n ; u = u ; n = 5}) / cashMultiplier

let cash_to_token (param: cash_to_token) (storage: storage) : result =
    (* Swaps cash to tokens. First the pools of the CFMM are updated with the latest values, then
    swaps the given cash to tokens and gives them to the receiver. *)
    let update_pools_ep : unit contract  = Tezos.self "%updatePools" in
    let internal_call_ep: (cash_to_token * address) contract = Tezos.self "%cashToTokenInternal" in

    let update_pools_operation =  (Tezos.transaction () 0mutez update_pools_ep) in
    let internal_param = (param, Tezos.get_sender ()) in
    let amount = (Tezos.get_amount ()) in
    let internal_call_operation = (Tezos.transaction internal_param amount internal_call_ep) in

    ([update_pools_operation; internal_call_operation], storage) 

let cash_to_token_internal (param : cash_to_token) (_sender : address) (storage : storage) =
    (* Accepts a payment in cash and sends tokens to the recipient. *)
   let { 
        to_ = to_ ;
        minTokensBought = minTokensBought ;
        deadline = deadline 
    } = param in

    let cashSold = mutez_to_natural (Tezos.get_amount ()) in
    if storage.pendingPoolUpdates > 0n then
        (failwith error_PENDING_POOL_UPDATES_MUST_BE_ZERO : result)
    else if Tezos.get_now () >= deadline then
        (failwith error_DEADLINE_EXCEEDED : result)
    else if Tezos.get_sender () <> Tezos.get_self_address () then
        (failwith error_THIS_ENTRYPOINT_MAY_ONLY_BE_CALLED_BY_THE_CONTRACT : result)
    else begin
        (* We don't check that xtzPool > 0, because that is impossible unless all liquidity has been removed. *)
        (* We need to have this workaround for the cashPool because the amount of deposited cash (tez) is
           immediately sent to the contract and we need to not take it into account *)
        let cashPool   : nat = match is_nat (storage.cashPool - cashSold) with
            | None -> (failwith error_ASSERTION_VIOLATED_NEGATIVE_DIFFERENCE : nat)
            | Some val -> val in
        let token_price_in_cash_opt : nat option = Tezos.call_view "get_token_price_in_cash" () storage.targetPriceOracle in
        let token_price_in_cash = match token_price_in_cash_opt with
            | None -> (failwith error_MISSING_ORACLE_VIEW : nat)
            | Some price -> price
        in
        let cashMultiplier = storage.cashMultiplier * price_precision_factor in
        let tokenMultiplier = storage.tokenMultiplier * token_price_in_cash in
        let totalTokensBought = tokensBought cashPool cashMultiplier storage.tokenPool tokenMultiplier cashSold in
        let tokensBought = (
            let bought = storage.feeRatio.numerator * totalTokensBought / storage.feeRatio.denominator in
            if bought < minTokensBought then
                (failwith error_TOKENS_BOUGHT_MUST_BE_GREATER_THAN_OR_EQUAL_TO_MIN_TOKENS_BOUGHT : nat)
            else
                bought) in
        let rewardRecipientFee = (match is_nat ((totalTokensBought - tokensBought) / 2) with  (* 50% of the fee goes to *)
            | None -> (failwith error_TOKEN_POOL_MINUS_TOKENS_BOUGHT_IS_NEGATIVE: nat)
            | Some diff -> diff) in

        let newTokenPool = (match is_nat (storage.tokenPool - (tokensBought + rewardRecipientFee)) with
            | None -> (failwith error_TOKEN_POOL_MINUS_TOKENS_BOUGHT_IS_NEGATIVE : nat)
            | Some diff -> diff) in

        (* Update cashPool. *)
        let storage = { storage with 
            tokenPool = newTokenPool 
        } in
        (* Send tokens_withdrawn from exchange to sender. *)
        let op_token = token_transfer storage (Tezos.get_self_address ()) to_ tokensBought in
        (* Send tokens_withdrawn from exchange to reward recipient. *)
        let op_token_reward = token_transfer storage (Tezos.get_self_address ()) storage.rewardRecipient rewardRecipientFee in
        
        ([op_token; op_token_reward], storage)
    end


let token_to_cash (param: token_to_cash) (storage: storage) : result =
    (* Swaps tokens to cash. First the pools of the CFMM are updated with the latest values, then
    swaps the given tokens to cash and sends it to the receiver. *)
    if (Tezos.get_amount ()) > 0mutez then
        (failwith error_AMOUNT_MUST_BE_ZERO : result)
    else begin
        let update_pools_ep : unit contract  = Tezos.self "%updatePools" in
        let internal_call_ep : (token_to_cash * address) contract = Tezos.self "%tokenToCashInternal" in

        let update_pools_operation =  (Tezos.transaction () 0mutez update_pools_ep) in
        let internal_param = (param, Tezos.get_sender ()) in
        let internal_call_operation = (Tezos.transaction internal_param 0mutez internal_call_ep) in

        ([update_pools_operation; internal_call_operation], storage) 
    end


let token_to_cash_internal (param : token_to_cash) (sender : address) (storage : storage) =
    (* Accepts a payment in token and sends cash to the recipient. *)
    let { 
        to_ = to_ ;
        tokensSold = tokensSold ;
        minCashBought = minCashBought ;
        deadline = deadline 
    } = param in

    if storage.pendingPoolUpdates > 0n then
        (failwith error_PENDING_POOL_UPDATES_MUST_BE_ZERO : result)
    else if (Tezos.get_now ()) >= deadline then
        (failwith error_DEADLINE_EXCEEDED : result)
    else if Tezos.get_sender () <> Tezos.get_self_address () then
        (failwith error_THIS_ENTRYPOINT_MAY_ONLY_BE_CALLED_BY_THE_CONTRACT : result)
    else
        (* We don't check that tokenPool > 0, because that is impossible unless all liquidity has been removed. *)
        let token_price_in_cash_opt : nat option = Tezos.call_view "get_token_price_in_cash" () storage.targetPriceOracle in
        let token_price_in_cash = match token_price_in_cash_opt with
            | None -> (failwith error_MISSING_ORACLE_VIEW : nat)
            | Some price -> price
        in
        let cashMultiplier = storage.cashMultiplier * price_precision_factor in
        let tokenMultiplier = storage.tokenMultiplier * token_price_in_cash in
        let totalCashBought = cashBought storage.cashPool cashMultiplier storage.tokenPool tokenMultiplier tokensSold in
        let cashBought = (
            let bought = storage.feeRatio.numerator * totalCashBought / storage.feeRatio.denominator in
                if bought < minCashBought then 
                    (failwith error_CASH_BOUGHT_MUST_BE_GREATER_THAN_OR_EQUAL_TO_MIN_CASH_BOUGHT : nat) 
                else bought) in
        let rewardRecipientFee = (match is_nat ((totalCashBought - cashBought) / 2) with  (* 50% of the fee goes to *)
            | None -> (failwith error_ASSERTION_VIOLATED_EXCEEDING_POOL_RESOURCES : nat)
            | Some diff -> diff) in

        let cashBoughtInMutez = natural_to_mutez cashBought in
        let rewardRecipientFeeInMutez = natural_to_mutez rewardRecipientFee in

        let op_token = token_transfer storage sender (Tezos.get_self_address ()) tokensSold in
        let cashReceiver = 
            match (Tezos.get_contract_opt to_ : unit contract option) with
                | None -> (failwith error_INVALID_RECEIVER : unit contract)
                | Some contract -> contract in
        let op_cash = Tezos.transaction () cashBoughtInMutez cashReceiver in

        let newCashPool = match is_nat (storage.cashPool - (cashBought + rewardRecipientFee)) with
            | None -> (failwith error_ASSERTION_VIOLATED_EXCEEDING_POOL_RESOURCES : nat)
            | Some diff -> diff in
        let storage = {storage with 
            tokenPool = storage.tokenPool + tokensSold ;
            cashPool = newCashPool
        } in

        if rewardRecipientFeeInMutez > 0mutez then
            let rewardReceiver = 
                match (Tezos.get_contract_opt storage.rewardRecipient : unit contract option) with
                    | None -> (failwith error_INVALID_RECEIVER : unit contract)
                    | Some contract -> contract in
            let op_cash_reward = Tezos.transaction () rewardRecipientFeeInMutez rewardReceiver in
            ([op_token; op_cash; op_cash_reward], storage)
        else
            ([op_token; op_cash], storage)

let set_reward_recipient (recipient: address) (storage : storage) : result =
    (* Set the recipient of the swap fees. Only an admin can call this entrypoint. *)
    if (Tezos.get_sender ()) <> storage.admin then
        (failwith error_NOT_ADMIN : result)
    else
        (([] : operation list), {storage with rewardRecipient = recipient})

let set_cfmm_delegate (keyhash_option: key_hash option) (storage : storage) : result =
    (* Set the delegate of the contract. Only an admin can call this entrypoint. *)
    if (Tezos.get_sender ()) <> storage.admin then
        (failwith error_NOT_ADMIN : result)
    else
        ([Tezos.set_delegate keyhash_option], storage)

let propose_new_admin (proposedAdmin: address) (storage : storage) : result =
    (* Propose a new admin for the contract. Only an existing admin can call this entrypoint. *)
    if (Tezos.get_sender ()) <> storage.admin then
        (failwith error_NOT_ADMIN : result)
    else
        (([] : operation list), {storage with proposedAdmin = proposedAdmin})

let accept_admin_proposal (storage : storage) : result =
    (* Accept an admin proposal. Only a proposed admin can call this entrypoint. *)
    if (Tezos.get_sender ()) <> storage.proposedAdmin then
        (failwith error_NOT_PROPOSED_ADMIN : result)
    else
        (([] : operation list), {storage with admin = storage.proposedAdmin})

let default (storage : storage) : result =
    (* The default entrypoint of the contract to accept tez payments. *)
    ([], storage)

let set_lqt_address (lqtAddress : address) (storage : storage) : result =
    (* Sets the address for the liquidity pool. This entrypoint can be called only once and set up
    correctly with the liquidity pool address. *)
    if storage.lqtAddress <> null_address then
        (failwith error_LQT_ADDRESS_ALREADY_SET : result)
    else
        (([] : operation list), {storage with lqtAddress = lqtAddress})

let update_pools (storage : storage) : result =
    (* Update the token pool and potentially the cash pool if cash is a token. *)
    if ((Tezos.get_sender () <> Tezos.get_source()) && (Tezos.get_sender () <> Tezos.get_self_address ())) then
        (failwith error_CALL_NOT_FROM_AN_IMPLICIT_ACCOUNT : result)
    else if (Tezos.get_amount ()) > 0mutez then
      (failwith error_AMOUNT_MUST_BE_ZERO : result)
    else
        let update_token_pool_internal : update_token_pool_internal contract = Tezos.self "%updateTokenPoolInternal"  in
#if TOKEN_IS_FA2
        let token_balance_of : balance_of contract = 
            (match (Tezos.get_entrypoint_opt "%balance_of" storage.tokenAddress : balance_of contract option) with
                | None -> (failwith error_INVALID_FA2_TOKEN_CONTRACT_MISSING_BALANCE_OF : balance_of contract)
                | Some contract -> contract) in
        let op_token = Tezos.transaction ([((Tezos.get_self_address ()), storage.tokenId)], update_token_pool_internal) 0mutez token_balance_of in
#else
        let token_get_balance : get_balance contract = 
            (match (Tezos.get_entrypoint_opt "%getBalance" storage.tokenAddress : get_balance contract option) with
                | None -> (failwith error_INVALID_FA12_TOKEN_CONTRACT_MISSING_GETBALANCE : get_balance contract)
                | Some contract -> contract) in
        let op_token = Tezos.transaction ((Tezos.get_self_address ()), update_token_pool_internal) 0mutez token_get_balance in
#endif
        (* update the cashPool by fetching the tez balance of the contract *)
        let storage = {storage with cashPool = mutez_to_natural (Tezos.get_balance ())} in
        ([op_token], {storage with pendingPoolUpdates = 1n})

[@inline]
let update_fa12_pool_internal (pool_update : update_fa12_pool) : nat =
    pool_update

[@inline]
let update_fa2_pool_internal (pool_update : update_fa2_pool) : nat =
    (* We trust the FA2 to provide the expected balance. there are no BFS
      shenanigans to worry about unless the token contract misbehaves. *)
    match pool_update with
        | [] -> (failwith error_INVALID_FA2_BALANCE_RESPONSE : nat)
        | x :: _xs -> x.1

let update_token_pool_internal (pool_update : update_token_pool_internal) (storage : storage) : result =
    if (storage.pendingPoolUpdates = 0n or (Tezos.get_sender ()) <> storage.tokenAddress) then
      (failwith error_THIS_ENTRYPOINT_MAY_ONLY_BE_CALLED_BY_GETBALANCE_OF_TOKENADDRESS : result)
    else
#if TOKEN_IS_FA2
        let pool = update_fa2_pool_internal (pool_update) in
#else
        let pool = update_fa12_pool_internal (pool_update) in
#endif
        let pendingPoolUpdates = match is_nat (storage.pendingPoolUpdates - 1n) with
            | None -> (failwith error_PENDING_POOL_UPDATES_CANNOT_DROP_BELOW_ZERO : nat)
            | Some val -> val in
        (([] : operation list), {storage with tokenPool = pool ; pendingPoolUpdates = pendingPoolUpdates})

let calculate_lqt_price_in_token (tokenPool : nat) (tokenMultiplier : nat) (cashPool : nat) (cashMultiplier: nat) (lqtPool : nat) (targetOracle : address) : nat =
    (* Calculates the price: 1 lqt token = x tokens with a precison of price_precision_factor. This assumes the price
       returned by the targetOracle has a precision of price_precision_factor. *)
    let cash_price_in_token_opt : nat option = Tezos.call_view "get_cash_price_in_token" () targetOracle in
    let cash_price_in_token = match cash_price_in_token_opt with
        | None -> (failwith error_MISSING_ORACLE_VIEW : nat)
        | Some price -> price
    in
    let tokenData = tokenPool * tokenMultiplier * price_precision_factor in
    let cashData = cashPool * cashMultiplier * cash_price_in_token in
    ceildiv (tokenData + cashData) lqtPool

let calculate_lqt_price_in_cash (tokenPool : nat) (tokenMultiplier : nat) (cashPool : nat) (cashMultiplier : nat) (lqtPool : nat) (targetOracle : address) : nat =
    (* Calculates the price: 1 lqt token = y cash with a precison of price_precision_factor. This assumes the price
       returned by the targetOracle has a precision of price_precision_factor. *)
    let token_price_in_cash_opt : nat option = Tezos.call_view "get_token_price_in_cash" () targetOracle in
    let token_price_in_cash = match token_price_in_cash_opt with
        | None -> (failwith error_MISSING_ORACLE_VIEW : nat)
        | Some price -> price
    in
    let tokenData = tokenPool * tokenMultiplier * token_price_in_cash in
    let cashData = cashPool * cashMultiplier * price_precision_factor in
    ceildiv (tokenData + cashData) lqtPool

let fetch_lqt_token_price_internal (callback : price_callback) (token_or_cash : token_or_cash) (storage : storage) : result =
    if (Tezos.get_sender ()) <> (Tezos.get_self_address ()) then
        (failwith error_THIS_ENTRYPOINT_MAY_ONLY_BE_CALLED_BY_THE_CONTRACT : result)
    else begin
        let lqt_price = match token_or_cash with
            | Token -> calculate_lqt_price_in_token storage.tokenPool storage.tokenMultiplier storage.cashPool storage.cashMultiplier storage.lqtTotal storage.targetPriceOracle
            | Cash -> calculate_lqt_price_in_cash storage.tokenPool storage.tokenMultiplier storage.cashPool storage.cashMultiplier storage.lqtTotal storage.targetPriceOracle
        in
        let op = Tezos.transaction lqt_price 0mutez callback in
        ([op], storage) 
    end

let fetch_lqt_token_price_in_token (callback : price_callback) (storage : storage) : result =
    (* Calculate the price of the liquidity token and returns it through the provided callback *)
    if (Tezos.get_amount ()) > 0mutez then
        (failwith error_AMOUNT_MUST_BE_ZERO : result)
    else begin
        let update_pools_ep : unit contract  = Tezos.self "%updatePools" in
        let fetch_price_ep : (price_callback * token_or_cash) contract = Tezos.self "%fetchLqtTokenPriceInternal" in

        let op_update_pools = Tezos.transaction () 0mutez update_pools_ep in
        let op_internal = Tezos.transaction (callback, Token)  0mutez fetch_price_ep in
        ([op_update_pools; op_internal], storage) 
    end

let fetch_lqt_token_price_in_cash (callback : price_callback) (storage : storage) : result =
    (* Calculate the price of the liquidity token and returns it through the provided callback *)
    if (Tezos.get_amount ()) > 0mutez then
        (failwith error_AMOUNT_MUST_BE_ZERO : result)
    else begin
        let update_pools_ep : unit contract  = Tezos.self "%updatePools" in
        let fetch_price_ep : (price_callback * token_or_cash) contract = Tezos.self "%fetchLqtTokenPriceInternal" in

        let op_update_pools = Tezos.transaction () 0mutez update_pools_ep in
        let op_internal = Tezos.transaction (callback, Cash) 0mutez fetch_price_ep in
        ([op_update_pools; op_internal], storage) 
    end


(* =============================================================================
 * Views
 * ============================================================================= *)
[@view] let tokensPool((), storage : unit * storage) : nat = (storage.tokenPool)
[@view] let cashPool((), storage : unit * storage) : nat = (storage.cashPool)
[@view] let liquidityTotal((), storage : unit * storage) : nat = (storage.lqtTotal)
(* View to calculate the price of the LQT token in the cash token (tez in this case, e.g. 1LQT = 1.2 tez)
   NOTE: The price returned by the view might not be the correct one as the balances might not
   be updated yet (for up to date prices, we recommend using the callback equivalent of this view
   which does update the pool balances before calculating the price).
   In practice, we don't expect this to happen often because a bot will call the updatePools
   entrypoint every x minutes. *)
[@view] let lazyLqtPriceInCash((), storage : unit * storage) : nat = (calculate_lqt_price_in_cash storage.tokenPool storage.tokenMultiplier storage.cashPool storage.cashMultiplier storage.lqtTotal storage.targetPriceOracle)
(* View to calculate the price of the LQT token in token (e.g 1LQT = 1.2 tokens)
   NOTE: The price returned by the view might not be the correct one as the balances might not
   be updated yet (for up to date prices, we recommend using the callback equivalent of this view
   which does update the pool balances before calculating the price).
   In practice, we don't expect this to happen often because a bot will call the updatePools
   entrypoint every x minutes. *)
[@view] let lazyLqtPriceInToken((), storage : unit * storage) : nat = (calculate_lqt_price_in_token storage.tokenPool storage.tokenMultiplier storage.cashPool storage.cashMultiplier storage.lqtTotal storage.targetPriceOracle)

(* =============================================================================
 * Main
 * ============================================================================= *)

let main ((entrypoint, storage) : entrypoint * storage) : result =
    begin
        match entrypoint with
        | Default -> default storage
        | AddLiquidity param ->
            add_liquidity param storage
        | AddLiquidityInternal (param, addr) ->
            add_liquidity_internal param addr storage
        | RemoveLiquidity param ->
            remove_liquidity param storage
        | RemoveLiquidityInternal (param, addr) ->
            remove_liquidity_internal param addr storage
        | CashToToken param ->
            (cash_to_token param storage)
        | CashToTokenInternal (param, addr) ->
            (cash_to_token_internal param addr storage)
        | TokenToCash param ->
            (token_to_cash param storage)
        | TokenToCashInternal (param, addr) ->
            (token_to_cash_internal param addr storage)
        | SetLqtAddress param ->
            set_lqt_address param storage
        | SetRewardRecipient recipient ->
            set_reward_recipient recipient storage
        | SetDelegate keyhash_option ->
            set_cfmm_delegate keyhash_option storage
        | ProposeNewAdmin proposedAdmin ->
            propose_new_admin proposedAdmin storage
        | AcceptAdminProposal  ->
            accept_admin_proposal storage
        | ChangeFee newFee -> change_fee newFee storage
        | UpdatePools -> update_pools storage
        | UpdateTokenPoolInternal token_pool -> 
            update_token_pool_internal token_pool storage
        | FetchLqtTokenPriceInToken callback -> 
            fetch_lqt_token_price_in_token callback storage
        | FetchLqtTokenPriceInCash callback -> 
            fetch_lqt_token_price_in_cash callback storage
        | FetchLqtTokenPriceInternal (callback, token_or_cash) -> 
            fetch_lqt_token_price_internal callback token_or_cash storage
    end
