(* Pick one of CASH_IS_FA2, CASH_IS_FA12  *)
#define CASH_IS_FA2
//#define CASH_IS_FA12

(* If the token uses the fa2 standard *)
#define TOKEN_IS_FA2

type ratio =
    [@layout:comb]
    { numerator : nat ;
      denominator : nat ;
    }

(* ============================================================================
 * Entrypoints
 * ============================================================================ *)

type add_liquidity =
  [@layout:comb]
  { owner : address ; (* address that will own the minted lqt *)
    minLqtMinted : nat ; (* minimum number of lqt that must be minter *)
    maxTokensDeposited : nat ; (* maximum number of tokens that may be deposited *)
    cashDeposited : nat ; (* if cash isn't tez, specifiy the amount to be deposited *)
    deadline : timestamp ; (* time before which the request must be completed *)
  }

type remove_liquidity =
  [@layout:comb]
  { [@annot:to] to_ : address ; (* recipient of the liquidity redemption *)
    lqtBurned : nat ;  (* amount of lqt owned by sender to burn *)
    minCashWithdrawn : nat ; (* minimum amount of cash to withdraw *)
    minTokensWithdrawn : nat ; (* minimum amount of tokens to withdraw *)
    deadline : timestamp ; (* time before which the request must be completed *)
  }

type cash_to_token =
  [@layout:comb]
  { [@annot:to] to_ : address ;  (* where to send the tokens *)
    minTokensBought : nat ; (* minimum amount of tokens that must be bought *)
    cashSold : nat ; (* if cash isn't tez, how much cash is sought to be sold *)
    deadline : timestamp ; (* time before which the request must be completed *)
  }

type token_to_cash =
  [@layout:comb]
  { [@annot:to] to_ : address ; (* where to send the cash *)
    tokensSold : nat ; (* how many tokens are being sold *)
    minCashBought : nat ; (* minimum amount of cash desired *)
    deadline : timestamp ; (* time before which the request must be completed *)
  }


type entrypoint =
| AddLiquidity    of add_liquidity
| RemoveLiquidity of remove_liquidity
| CashToToken     of cash_to_token
| TokenToCash     of token_to_cash
| SetLqtAddress   of address
| SetRewardRecipient of address
| ProposeNewAdmin of address
| AcceptAdminProposal of unit
| ChangeFee of ratio

(* =============================================================================
 * Storage
 * ============================================================================= *)

type storage =
  [@layout:comb]
  { tokenPool : nat ;
    tokenAddress : address ;
    tokenMultiplier : nat ;
#if TOKEN_IS_FA2
    tokenId : nat ;
#endif
    cashPool : nat ;
    cashAddress : address ;
    cashMultiplier : nat ;
#if CASH_IS_FA2
    cashId : nat ;
#endif
    admin: address ;
    proposedAdmin: address ;

    lqtTotal : nat ;
    lqtAddress : address ;
    rewardRecipient: address ;
    feeRatio : ratio ;
  }

(*  Type Synonyms *)

type result = operation list * storage

(* FA2 *)
type token_id = nat
type balance_of = ((address * token_id) list * ((((address * nat) * nat) list) contract))
(* FA1.2 *)
type get_balance = address * (nat contract)

#if TOKEN_IS_FA2
type token_contract_transfer = (address * (address * (token_id * nat)) list) list
#else
(*  FA1.2 *)
type token_contract_transfer = address * (address * nat)
#endif

#if CASH_IS_FA2
type cash_contract_transfer = (address * (address * (token_id * nat)) list) list
#else
(* FA12 *)
type cash_contract_transfer = address * (address * nat)
#endif

(* custom entrypoint for LQT FA1.2 *)
type mintOrBurn =
  [@layout:comb]
  { quantity : int ;
    target : address }

(* =============================================================================
 * Error codes
 * ============================================================================= *)

[@inline] let error_TOKEN_CONTRACT_MUST_HAVE_A_TRANSFER_ENTRYPOINT  = 0n
[@inline] let error_ASSERTION_VIOLATED_CASH_BOUGHT_SHOULD_BE_LESS_THAN_CASHPOOL = 1n
[@inline] let error_ASSERTION_VIOLATED_NEGATIVE_DIFFERENCE = 2n
[@inline] let error_THE_CURRENT_TIME_MUST_BE_LESS_THAN_THE_DEADLINE = 3n
[@inline] let error_MAX_TOKENS_DEPOSITED_MUST_BE_GREATER_THAN_OR_EQUAL_TO_TOKENS_DEPOSITED = 4n
[@inline] let error_LQT_MINTED_MUST_BE_GREATER_THAN_MIN_LQT_MINTED = 5n
(* 6n *)
[@inline] let error_ONLY_NEW_MANAGER_CAN_ACCEPT = 7n
[@inline] let error_CASH_BOUGHT_MUST_BE_GREATER_THAN_OR_EQUAL_TO_MIN_CASH_BOUGHT = 8n
[@inline] let error_INVALID_TO_ADDRESS = 9n
(* 10n *)
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
[@inline] let error_THIS_ENTRYPOINT_MAY_ONLY_BE_CALLED_BY_GETBALANCE_OF_CASHADDRESS = 30n
[@inline] let error_TEZ_DEPOSIT_WOULD_BE_BURNED = 32n
#if CASH_IS_FA2
[@inline] let error_INVALID_FA2_CASH_CONTRACT_MISSING_GETBALANCE = 33n
#else
[@inline] let error_INVALID_FA12_CASH_CONTRACT_MISSING_GETBALANCE = 33n
[@inline] let error_MISSING_APPROVE_ENTRYPOINT_IN_CASH_CONTRACT = 34n
#endif

(* =============================================================================
 * Constants
 * ============================================================================= *)

 [@inline] let null_address = ("tz1Ke2h7sDdakHJQh8WX4Z372du1KChsksyU" : address)

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

[@inline]
let cash_transfer (storage : storage) (from : address) (to_ : address) (cash_amount : nat) : operation=
    (* Cash transfer operation, in the case where cash is some fa2 or fa12 token *)
    let cash_contract: cash_contract_transfer contract =
    match (Tezos.get_entrypoint_opt "%transfer" storage.cashAddress : cash_contract_transfer contract option) with
    | None -> (failwith error_TOKEN_CONTRACT_MUST_HAVE_A_TRANSFER_ENTRYPOINT : cash_contract_transfer contract)
    | Some contract -> contract in
#if CASH_IS_FA2
    Tezos.transaction [(from, [(to_, (storage.cashId, cash_amount))])] 0mutez cash_contract
#else
    Tezos.transaction (from, (to_, cash_amount)) 0mutez cash_contract
#endif

(* =============================================================================
 * Entrypoint Functions
 * ============================================================================= *)

(* We assume the contract is originated with at least one liquidity
 * provider set up already, so lqtTotal, xtzPool and cashPool will
 * always be positive after the initial setup, unless all liquidity is
 * removed, at which point the contract is considered dead and stops working
 * properly. If this is a concern, at least one address should keep at least a
 * very small amount of liquidity in the contract forever. *)

let add_liquidity (param : add_liquidity) (storage: storage) : result =
    (* Adds liquidity to the contract, mints lqt in exchange for the deposited liquidity. *)
    let {
          owner = owner ;
          minLqtMinted = minLqtMinted ;
          maxTokensDeposited = maxTokensDeposited ;
          cashDeposited = cashDeposited ;
          deadline = deadline } = param in
    if Tezos.get_now () >= deadline then
        (failwith error_THE_CURRENT_TIME_MUST_BE_LESS_THAN_THE_DEADLINE : result)
    else
        (* The contract is initialized, use the existing exchange rate
          mints nothing if the contract has been emptied, but that's OK *)
        let cashPool   : nat = storage.cashPool in
        let lqt_minted : nat = cashDeposited * storage.lqtTotal / cashPool in
        let tokens_deposited : nat = ceildiv (cashDeposited * storage.tokenPool) cashPool in

        if tokens_deposited > maxTokensDeposited then
            (failwith error_MAX_TOKENS_DEPOSITED_MUST_BE_GREATER_THAN_OR_EQUAL_TO_TOKENS_DEPOSITED : result)
        else if lqt_minted < minLqtMinted then
            (failwith error_LQT_MINTED_MUST_BE_GREATER_THAN_MIN_LQT_MINTED : result)
        else
            let storage = {storage with
                lqtTotal  = storage.lqtTotal + lqt_minted ;
                tokenPool = storage.tokenPool + tokens_deposited ;
                cashPool  = storage.cashPool + cashDeposited} in

            (* send tokens from sender to self *)
            let op_token = token_transfer storage (Tezos.get_sender ()) (Tezos.get_self_address ()) tokens_deposited in
            (* send cash from sender to self *)
            let op_cash = cash_transfer storage (Tezos.get_sender ()) (Tezos.get_self_address ()) cashDeposited in
            (* mint lqt tokens for them *)
            let op_lqt = mint_or_burn storage owner (int lqt_minted) in

            ([op_token;
             op_cash;
             op_lqt], storage)

let remove_liquidity (param : remove_liquidity) (storage : storage) : result =
    (* Removes liquidity to the contract by burning lqt. *)
    let { to_ = to_ ;
          lqtBurned = lqtBurned ;
          minCashWithdrawn = minCashWithdrawn ;
          minTokensWithdrawn = minTokensWithdrawn ;
          deadline = deadline } = param in

    if Tezos.get_now () >= deadline then
      (failwith error_THE_CURRENT_TIME_MUST_BE_LESS_THAN_THE_DEADLINE : result)
    else begin
        let cash_withdrawn : nat = (lqtBurned * storage.cashPool) / storage.lqtTotal in
        let tokens_withdrawn : nat = (lqtBurned * storage.tokenPool) / storage.lqtTotal in

        (* Check that minimum withdrawal conditions are met *)
        if cash_withdrawn < minCashWithdrawn then
            (failwith error_THE_AMOUNT_OF_CASH_WITHDRAWN_MUST_BE_GREATER_THAN_OR_EQUAL_TO_MIN_CASH_WITHDRAWN : result)
        else if tokens_withdrawn < minTokensWithdrawn  then
            (failwith error_THE_AMOUNT_OF_TOKENS_WITHDRAWN_MUST_BE_GREATER_THAN_OR_EQUAL_TO_MIN_TOKENS_WITHDRAWN : result)
        (* Proceed to form the operations and update the storage *)
        else begin
            (* calculate lqtTotal, convert int to nat *)
            let new_lqtTotal = match is_nat (storage.lqtTotal - lqtBurned) with
                (* This check should be unecessary, the fa12 logic normally takes care of it *)
                | None -> (failwith error_CANNOT_BURN_MORE_THAN_THE_TOTAL_AMOUNT_OF_LQT : nat)
                | Some n -> n in
            (* Calculate tokenPool, convert int to nat *)
            let new_tokenPool = match is_nat (storage.tokenPool - tokens_withdrawn) with
                | None -> (failwith error_TOKEN_POOL_MINUS_TOKENS_WITHDRAWN_IS_NEGATIVE : nat)
                | Some n -> n in
            let new_cashPool = match is_nat (storage.cashPool - cash_withdrawn) with
                | None -> (failwith error_CASH_POOL_MINUS_CASH_WITHDRAWN_IS_NEGATIVE : nat)
                | Some n -> n in
            let op_lqt = mint_or_burn storage (Tezos.get_sender ()) (0 - lqtBurned) in
            let op_token = token_transfer storage(Tezos.get_self_address ()) to_ tokens_withdrawn in
            let op_cash = cash_transfer storage(Tezos.get_self_address ()) to_ cash_withdrawn in
            let storage = {storage with cashPool = new_cashPool ; lqtTotal = new_lqtTotal ; tokenPool = new_tokenPool} in
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
    (* since x > 0 and y > 0, x + y > x - y and therefore (x + y)^7 > (x - y)^7 and (x + y^7 - (x - y)^7 > 0 *)
    let difference_8 = match is_nat (plus_8 - minus_8) with
        | None -> (failwith error_ASSERTION_VIOLATED_NEGATIVE_DIFFERENCE: nat)
        | Some n -> n in
    let sum_7 = match is_nat (minus_7 + plus_7) with
        | None -> (failwith error_ASSERTION_VIOLATED_NEGATIVE_DIFFERENCE: nat)
        | Some n -> n in

    (difference_8, 8n * sum_7)

type newton_param =  {x : nat ; y : nat ; dx : nat ; dy : nat ; u : nat ; n : int}

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

let cashBought (cashPool : nat) (cashMultiplier : nat) (tokenPool : nat) (tokenMultiplier : nat) (tokenSold : nat) : nat =
    (* computes the cash bought using the newton approximation method given the cash/tokens pool and
    the amount of tokens sold. The (cash/token)Multipliers are used to make sure that x and y can be expressed in
    the same power of 10 (e.g if cash has 6 decimals and token has 12 decimals, we will multiple the cash by a factor
    of 10^6 *)
    let x = tokenPool * tokenMultiplier  in
    let y = cashPool * cashMultiplier in
    let u, _ = util x y in
    (newton {x = x; y = y ; dx = tokenSold * tokenMultiplier ; dy = 0n ; u = u ; n = 5}) / cashMultiplier

let cash_to_token (param : cash_to_token) (storage : storage) =
    (* Accepts a payment in cash and sends tokens to the caller. *)
   let { to_ = to_ ;
         minTokensBought = minTokensBought ;
         cashSold = cashSold ;
         deadline = deadline } = param in

    if Tezos.get_now () >= deadline then
        (failwith error_THE_CURRENT_TIME_MUST_BE_LESS_THAN_THE_DEADLINE : result)
    else begin
        (* We don't check that xtzPool > 0, because that is impossible
           unless all liquidity has been removed. *)
        let total_tokens_bought = tokensBought storage.cashPool storage.cashMultiplier storage.tokenPool storage.tokenMultiplier cashSold in
        let tokens_bought = (
            let bought = storage.feeRatio.numerator * total_tokens_bought / storage.feeRatio.denominator in
            if bought < minTokensBought then
                (failwith error_TOKENS_BOUGHT_MUST_BE_GREATER_THAN_OR_EQUAL_TO_MIN_TOKENS_BOUGHT : nat)
            else
                bought) in
        let recipient_reward_fee = (match is_nat ((total_tokens_bought - tokens_bought) / 2) with  (* 50% of the fee goes to *)
            | None -> (failwith error_TOKEN_POOL_MINUS_TOKENS_BOUGHT_IS_NEGATIVE: nat)
            | Some difference -> difference) in

        let new_tokenPool = (match is_nat (storage.tokenPool - (tokens_bought + recipient_reward_fee)) with
            | None -> (failwith error_TOKEN_POOL_MINUS_TOKENS_BOUGHT_IS_NEGATIVE : nat)
            | Some difference -> difference) in

        (* Update cashPool. *)
        let storage = { storage with cashPool = storage.cashPool + cashSold ; tokenPool = new_tokenPool } in
        (* Send cash from sender to self. *)
        let op_cash = cash_transfer storage (Tezos.get_sender ()) (Tezos.get_self_address ()) cashSold in
        (* Send tokens_withdrawn from exchange to sender. *)
        let op_token = token_transfer storage(Tezos.get_self_address ()) to_ tokens_bought in
        (* Send tokens_withdrawn from exchange to reward recipient. *)
        let op_token_reward = token_transfer storage(Tezos.get_self_address ()) storage.rewardRecipient recipient_reward_fee in
        ([
            op_cash;
            op_token;
            op_token_reward], storage)
    end


let token_to_cash (param : token_to_cash) (storage : storage) =
    (* Accepts a payment in token and sends cash to the caller. *)
    let { to_ = to_ ;
          tokensSold = tokensSold ;
          minCashBought = minCashBought ;
          deadline = deadline } = param in

    if Tezos.get_now () >= deadline then
        (failwith error_THE_CURRENT_TIME_MUST_BE_LESS_THAN_THE_DEADLINE : result)
    else
        (* We don't check that tokenPool > 0, because that is impossible
           unless all liquidity has been removed. *)
        let total_cash_bought = cashBought storage.cashPool storage.cashMultiplier storage.tokenPool storage.tokenMultiplier tokensSold in
        let cash_bought =
            let bought = storage.feeRatio.numerator * total_cash_bought / storage.feeRatio.denominator in
                if bought < minCashBought then (failwith error_CASH_BOUGHT_MUST_BE_GREATER_THAN_OR_EQUAL_TO_MIN_CASH_BOUGHT : nat) else bought in
        let recipient_reward_fee = (match is_nat ((total_cash_bought - cash_bought) / 2) with  (* 50% of the fee goes to *)
            | None -> (failwith error_ASSERTION_VIOLATED_CASH_BOUGHT_SHOULD_BE_LESS_THAN_CASHPOOL : nat)
            | Some difference -> difference) in

        let op_token = token_transfer storage (Tezos.get_sender ()) (Tezos.get_self_address ()) tokensSold in
        let op_cash = cash_transfer storage(Tezos.get_self_address ())  to_ cash_bought in
        let op_cash_reward = cash_transfer storage(Tezos.get_self_address ()) storage.rewardRecipient recipient_reward_fee in
        let new_cashPool = match is_nat (storage.cashPool - (cash_bought + recipient_reward_fee)) with
            | None -> (failwith error_ASSERTION_VIOLATED_CASH_BOUGHT_SHOULD_BE_LESS_THAN_CASHPOOL : nat)
            | Some n -> n in
        let storage = {storage with tokenPool = storage.tokenPool + tokensSold ;
                                    cashPool = new_cashPool} in
        ([op_token; op_cash; op_cash_reward], storage)

let set_reward_recipient (recipient: address) (storage : storage) : result =
    (* Set the recipient of the swap fees. Only an admin can call this entrypoint. *)
    if (Tezos.get_sender ()) <> storage.admin then
        (failwith error_NOT_ADMIN : result)
    else
        (([] : operation list), {storage with rewardRecipient = recipient})

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

let set_lqt_address (lqtAddress : address) (storage : storage) : result =
    (* Sets the address for the liquidity pool. This entrypoint can be called only once and set up
    correctly with the liquidity pool address. *)
    if storage.lqtAddress <> null_address then
        (failwith error_LQT_ADDRESS_ALREADY_SET : result)
    else
        (([] : operation list), {storage with lqtAddress = lqtAddress})

(* =============================================================================
 * Views
 * ============================================================================= *)
[@view] let tokensPool((), storage : unit * storage) : nat = (storage.tokenPool)
[@view] let cashPool((), storage : unit * storage) : nat = (storage.cashPool)
[@view] let liquidityTotal((), storage : unit * storage) : nat = (storage.lqtTotal)

(* =============================================================================
 * Main
 * ============================================================================= *)

let main ((entrypoint, storage) : entrypoint * storage) : result =
    begin
        if Tezos.get_amount () <> 0mutez
        then failwith "DontSendTez"
        else ();
        match entrypoint with
        | AddLiquidity param ->
            add_liquidity param storage
        | RemoveLiquidity param ->
            remove_liquidity param storage
        | CashToToken param ->
            (cash_to_token param storage)
        | TokenToCash param ->
            (token_to_cash param storage)
        | SetLqtAddress param ->
            set_lqt_address param storage
        | SetRewardRecipient recipient ->
            set_reward_recipient recipient storage
        | ProposeNewAdmin proposedAdmin ->
            propose_new_admin proposedAdmin storage
        | AcceptAdminProposal  ->
            accept_admin_proposal storage
        | ChangeFee newFee -> change_fee newFee storage
    end
