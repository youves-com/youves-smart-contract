module MultitokenFlatCurve = struct

// Ratio type. Represents the fraction: numerator / denominator.
type ratio = [@layout:comb] { 
    numerator : nat ;
    denominator : nat ;
}

// Status of an admin. Set admins can execute all admin protected entrypoints.
// Proposed admins, must first accept the proposal before being able to call
// any admin protected entrypoints.
type admin_status = Proposed | Set

// Token variant type. It represents the types of tokens the pool is able to
// interact with.
type token_variant = 
      Fa2 of address * nat 
    | Fa1 of address
    | Tez of unit

// Token information type. It stores the funds for the given token and the multiplier
type token_info = [@layout:comb] {
    funds: nat ;
    multiplier: nat ;
}

type flat_curve_exponent =
    | Exponent8 of unit
    | Exponent6 of unit
    | Exponent4 of unit

type add_liquidity = [@layout:comb] {
    owner : address ; 
    min_lqt_minted : nat ; 
    src_token : token_variant ;
    src_token_amount : nat ;
    remaining_tokens_max_deposited : (token_variant, nat) map ;
    deadline : timestamp ; 
}

type remove_liquidity = [@layout:comb] { 
    receiver : address ; 
    lqt_burned : nat ; 
    min_tokens_withdrawn: (token_variant, nat) map ;
    deadline : timestamp ; 
}

type token_swap = [@layout:comb] {
    src_token : token_variant ;
    dst_token : token_variant ;
    amount_sold : nat ;
    min_amount_bought : nat ;
    receiver : address ;
    deadline : timestamp ;
}

type mint_or_burn = [@layout:comb] { 
    quantity : int ;
    target : address 
}

type storage = [@layout:comb] { 
    administrators: (address, admin_status) big_map ;
    lqt_total: nat ;
    lqt_address: address ;
    swap_fee_ratio : ratio ;
    rewards_receiver : address ;
    rewards_receiver_ratio : ratio ;
    baking_rewards_receiver : address ;
    tokens_info : (token_variant, token_info) map ;
    target_oracle: address ;
    curve_exponent : flat_curve_exponent ;
}

type result = operation list * storage

type fa2_token_transfer = (address * (address * (nat * nat)) list) list
type fa1_token_transfer = address * (address * nat)
type tez_transfer = unit

[@inline] let null_address = ("tz1Ke2h7sDdakHJQh8WX4Z372du1KChsksyU" : address)

[@inline] let error_TOKEN_INFO_NOT_SET = 0n
[@inline] let error_LQT_CONTRACT_MUST_HAVE_A_MINT_OR_BURN_ENTRYPOINT = 1n
[@inline] let error_TOKEN_CONTRACT_MUST_HAVE_A_TRANSFER_ENTRYPOINT = 2n
[@inline] let error_ASSERTION_VIOLATED_TOKEN_POOL_WOULD_BE_NEGATIVE = 3n
[@inline] let error_INVALID_TOKEN_ID = 4n
[@inline] let error_THE_CURRENT_TIME_MUST_BE_LESS_THAN_THE_DEADLINE = 5n
[@inline] let error_INVALID_NUMBER_OF_TOKENS = 6n
[@inline] let error_ASSERTION_VIOLATED_SRC_TOKEN_IN_OTHER_TOKENS = 7n
[@inline] let error_MAX_TOKENS_DEPOSITED_MUST_BE_GREATER_THAN_OR_EQUAL_TO_TOKENS_DEPOSITED = 8n
[@inline] let error_LQT_MINTED_MUST_BE_GREATER_THAN_MIN_LQT_MINTED = 9n
[@inline] let error_THE_AMOUNT_OF_TOKENS_WITHDRAWN_MUST_BE_GREATER_THAN_OR_EQUAL_TO_MIN_TOKENS_WITHDRAWN = 10n
[@inline] let error_CANNOT_BURN_MORE_THAN_THE_TOTAL_AMOUNT_OF_LQT = 11n
[@inline] let error_NOT_ADMIN = 12n
[@inline] let error_ASSERTION_VIOLATED_NEGATIVE_DIFFERENCE = 13n
[@inline] let error_MISSING_ORACLE_VIEW = 14n
[@inline] let error_CASH_BOUGHT_MUST_BE_GREATER_THAN_OR_EQUAL_TO_MIN_CASH_BOUGHT = 15n
[@inline] let error_NOT_PROPOSED_ADMIN = 16n
[@inline] let error_ADMIN_ALREADY_SET = 17n
[@inline] let error_LQT_ADDRESS_ALREADY_SET = 18n
[@inline] let error_AMOUNT_MUST_BE_ZERO = 19n
[@inline] let error_ADDRESS_DOES_NOT_HAVE_DEFAULT_ENTRYPOINT = 20n
[@inline] let error_TOKEN_INFO_NOT_IN_STORAGE = 21n
[@inline] let error_MISSING_ORACLE_VIEW = 22n
[@inline] let error_SENT_TEZ_AMOUNT_DOES_NOT_CORRESPOND_TO_AMOUNT = 23n
[@inline] let error_SENDING_TEZ_NOT_ALLOWED = 24n
[@inline] let error_NOT_ALLOWED_TO_EXECUTE_OPERATION = 25n
[@inline] let error_INVALID_FA1_TOKEN_CONTRACT_MISSING_BALANCE_OF = 26n
[@inline] let error_INVALID_FA2_TOKEN_CONTRACT_MISSING_BALANCE_OF = 27n
[@inline] let error_INVALID_FA2_BALANCE_RESPONSE = 28n
[@inline] let error_INVALID_RECEIVER = 29n
[@inline] let error_UNKNOWN_TOKEN = 30n
[@inline] let error_THIS_ENTRYPOINT_MAY_ONLY_BE_CALLED_BY_THE_CONTRACT = 31n
[@inline] let error_BALANCE_LOWER_THAN_RECEIVED_AMOUNT = 32n

// Transformer functions from mutez to nat. 1mutez = 1.
[@inline]
let mutez_to_natural (a: tez) : nat =  a / 1mutez

// Transformer function from nat to mutez. 1 = 1mutez.
[@inline]
let natural_to_mutez (a: nat): tez = a * 1mutez

// Rounds up the division numerator / denominator 
[@inline]
let ceildiv (numerator : nat) (denominator : nat) : nat = abs ((- numerator) / (int denominator))

// Creates an operation that will mint or burn liquidity from the liquidity contract. The liquidity
// contract is a FA1.2 contract and the mintOrBurn entrypoint respects the FA1.2 standard.
// A negative quantity corresponds to a burn, while a positive one corresponds to a mint.
[@inline]
let mint_or_burn (storage : storage) (target : address) (quantity : int) : operation =
    let mint_or_burn_ep: mint_or_burn contract =
    match (Tezos.get_entrypoint_opt "%mintOrBurn" storage.lqt_address:  mint_or_burn contract option) with
    | None -> (failwith error_LQT_CONTRACT_MUST_HAVE_A_MINT_OR_BURN_ENTRYPOINT : mint_or_burn contract)
    | Some contract -> contract in
    Tezos.Next.Operation.transaction {quantity = quantity ; target = target} 0mutez mint_or_burn_ep

type transfer_type =
    | Send
    | Receive

type transfer_info = [@layout:comb] {
    from : address;
    to_: address;
    amount : nat ;
    transfer_type : transfer_type;
}
// Creates an operation to transfers the given token amount between from and to accounts.
let token_transfer (token_contract: token_variant) (from : address) (to_ : address) (amount : nat) (t : transfer_type): operation option =
    match token_contract with
    | Fa2 (token_address, token_id) -> begin
        let transfer_ep: fa2_token_transfer contract =
        match (Tezos.get_entrypoint_opt "%transfer" token_address : fa2_token_transfer contract option) with
        | None -> (failwith error_TOKEN_CONTRACT_MUST_HAVE_A_TRANSFER_ENTRYPOINT : fa2_token_transfer contract)
        | Some contract -> contract in
        let transaction = Tezos.Next.Operation.transaction [(from, [(to_, (token_id, amount))])] 0mutez transfer_ep in
        Some (transaction)
    end
    | Fa1 token_address -> begin
        let transfer_ep: fa1_token_transfer contract =
        match (Tezos.get_entrypoint_opt "%transfer" token_address : fa1_token_transfer contract option) with
        | None -> (failwith error_TOKEN_CONTRACT_MUST_HAVE_A_TRANSFER_ENTRYPOINT : fa1_token_transfer contract)
        | Some contract -> contract in
        let transaction = Tezos.Next.Operation.transaction (from, (to_, amount)) 0mutez transfer_ep in
        Some (transaction)
    end
    | Tez _unit -> begin
        match t with
        | Receive -> None
        | Send ->
            let receiver: tez_transfer contract =
                match (Tezos.get_contract_opt to_ : tez_transfer contract option) with
                | None -> (failwith error_TOKEN_CONTRACT_MUST_HAVE_A_TRANSFER_ENTRYPOINT : tez_transfer contract)
                | Some addr -> addr in
            let transaction = Tezos.Next.Operation.transaction () (natural_to_mutez amount) receiver in
            Some (transaction)
    end

// Default entrypoint of the contract. It forwards the received tez to the baking_rewards_receiver
// stored in the contract storage.
[@entry]
let default (_unit: unit) (s : storage) : result =
    if s.baking_rewards_receiver <> Tezos.get_self_address () then
        let baking_rewards_receiver =
            match (Tezos.get_contract_opt s.baking_rewards_receiver : unit contract option) with
            | Some (address) -> address
            | None -> (failwith error_ADDRESS_DOES_NOT_HAVE_DEFAULT_ENTRYPOINT : unit contract) in
        let op = Tezos.Next.Operation.transaction () (Tezos.get_amount ()) baking_rewards_receiver in
        ([op], s)
    else
        ([], s)

(* Returns token data as found in the tokens map for the given token or fails if the token does not
exist. *) 
[@inline]
let get_token_info (tokens_info: ((token_variant, token_info) map)) (token : token_variant) : token_info =
    match Map.find_opt token tokens_info with
    | None -> (failwith error_TOKEN_INFO_NOT_IN_STORAGE : token_info)
    | Some info -> info

[@inline]
let compute_proportionality (src_numerator: nat) (src_denominator: nat) (dst_denominator: nat) : nat =
    src_numerator * dst_denominator / src_denominator

[@inline]
let get_tokens_deposited_or_fail (tokens_info : ((token_variant, token_info) map)) (max_deposited_amounts: ((token_variant, nat) map)) (src_token_amount : nat) (src_token_funds : nat) : ((token_variant, nat) map) =
    let restriction_map = Map.map (fun (token, max_deposit) -> 
        let dst_token_info = get_token_info tokens_info token in
        let deposit = compute_proportionality src_token_amount src_token_funds dst_token_info.funds in
        (deposit, max_deposit)
    ) max_deposited_amounts in

    let restriction_condition = fun (acc, item : bool * (token_variant * (nat * nat))) ->
        let (_, value) = item in
        let (deposit, max_deposit) = value in
        acc && (deposit <= max_deposit)
    in
    let all_deposits_lower = Map.fold restriction_condition restriction_map True in
    if all_deposits_lower <> True then
        (failwith error_MAX_TOKENS_DEPOSITED_MUST_BE_GREATER_THAN_OR_EQUAL_TO_TOKENS_DEPOSITED : ((token_variant, nat) map))
    else
        Map.map (fun (_, (deposit, _)) -> deposit) restriction_map

[@inline]
let check_tez_amount (amounts : ((token_variant, nat) map)) : bool =
    let restriction_func = fun (acc, item : bool * (token_variant * nat)) ->
        let (token, amount) = item in
        match token with
        | Fa2 (_token_address, _token_id) -> acc
        | Fa1 _token_address -> acc
        | Tez _unit -> 
            let tez_amount = mutez_to_natural (Tezos.get_amount ()) in
            acc && tez_amount = amount
    in
    Map.fold restriction_func amounts True           

[@inline]
let get_tokens_withdrawn_or_fail (tokens_info : ((token_variant, token_info) map)) (min_tokens_withdrawn: ((token_variant, nat) map)) (src_token_amount : nat) (src_token_funds : nat) : ((token_variant, nat) map) =
    let restriction_map = Map.map (fun (token, min_withdrawn) -> 
        let dst_token_info = get_token_info tokens_info token in
        let withdrawn = compute_proportionality src_token_amount src_token_funds dst_token_info.funds in
        (withdrawn, min_withdrawn)
    ) min_tokens_withdrawn in

    let restriction_condition = fun (acc, item : bool * (token_variant * (nat * nat))) ->
        let (_, value) = item in
        let (withdrawn, min_withdrawn) = value in
        acc && (withdrawn >= min_withdrawn)
    in
    let all_withdraw_higher = Map.fold restriction_condition restriction_map True in
    if all_withdraw_higher <> True then
        (failwith error_THE_AMOUNT_OF_TOKENS_WITHDRAWN_MUST_BE_GREATER_THAN_OR_EQUAL_TO_MIN_TOKENS_WITHDRAWN: ((token_variant, nat) map))
    else
        Map.map (fun (_, (withdraw, _)) -> withdraw) restriction_map

[@inline]
let update_token_info (token_info : token_info) (amount: int) : token_info =
    let new_funds = match is_nat (token_info.funds + amount) with
        | None -> (failwith error_ASSERTION_VIOLATED_TOKEN_POOL_WOULD_BE_NEGATIVE : nat)
        | Some n -> n in
    { token_info with funds = new_funds }

(* Computes the following values (x+y)^8 - (x-y)^8 and the derivitative of it 8 * ((x-y)^7 + (x+y)^7) *)
let util8 (x: nat) (y: nat) : nat * nat =
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
    (* since x > 0 and y > 0, x + y > x - y and therefore (x + y)^7 > (x - y)^7 and (x + y)^7 - (x - y)^7 > 0 *)
    let difference_8 = match is_nat (plus_8 - minus_8) with
        | None -> (failwith error_ASSERTION_VIOLATED_NEGATIVE_DIFFERENCE: nat)
        | Some n -> n in
    let sum_7 = match is_nat (minus_7 + plus_7) with
        | None -> (failwith error_ASSERTION_VIOLATED_NEGATIVE_DIFFERENCE: nat)
        | Some n -> n in

    (difference_8, 8n * sum_7)

(* Computes the following values (x+y)^6 - (x-y)^6 and the derivitative of it 6 * ((x-y)^5 + (x+y)^5) *)
let util6 (x: nat) (y: nat) : nat * nat =
    let plus = x + y in
    let minus = x - y  in
    let plus_2 = plus * plus in
    let plus_6 = plus_2 * plus_2 * plus_2 in
    let plus_5 = plus_6 / plus in
    let minus_2 = minus * minus in
    let minus_6 = minus_2 * minus_2 * minus_2 in
    let minus_5 = if minus = 0 then 0 else minus_6 / minus in
    (* minus_5 + plus_5 should always be positive, same reasoning as util8*)
    let difference_6 = match is_nat (plus_6 - minus_6) with
        | None -> (failwith error_ASSERTION_VIOLATED_NEGATIVE_DIFFERENCE: nat)
        | Some n -> n in
    let sum_5 = match is_nat (minus_5 + plus_5) with
        | None -> (failwith error_ASSERTION_VIOLATED_NEGATIVE_DIFFERENCE: nat)
        | Some n -> n in

    (difference_6, 6n * sum_5)

(* Computes the following values (x+y)^4 - (x-y)^4 and the derivitative of it 4 * ((x-y)^3 + (x+y)^3) *)
let util4 (x: nat) (y: nat) : nat * nat =
    let plus = x + y in
    let minus = x - y  in
    let plus_2 = plus * plus in
    let plus_4 = plus_2 * plus_2 in
    let plus_3 = plus_2 * plus in
    let minus_2 = minus * minus in
    let minus_4 = minus_2 * minus_2 in
    let minus_3 = minus_2 * minus in
    (* minus_3 + plus_3 should always be positive, same reasoning as util8 *)
    let difference_4 = match is_nat (plus_4 - minus_4) with
        | None -> (failwith error_ASSERTION_VIOLATED_NEGATIVE_DIFFERENCE: nat)
        | Some n -> n in
    let sum_3 = match is_nat (minus_3 + plus_3) with
        | None -> (failwith error_ASSERTION_VIOLATED_NEGATIVE_DIFFERENCE: nat)
        | Some n -> n in

    (difference_4, 4n * sum_3)

type newton_param = {
    x : nat ; 
    y : nat ; 
    dx : nat ; 
    dy : nat ; 
    u : nat ; 
    n : int ;
    exponent : flat_curve_exponent ;
}

let rec newton (p : newton_param) : nat =
    if p.n = 0 then
        p.dy
    else
        let diff_y = match is_nat (p.y - p.dy) with
            | None -> (failwith error_ASSERTION_VIOLATED_NEGATIVE_DIFFERENCE: nat)
            | Some n -> n in
        let new_u, new_du_dy = match p.exponent with
            | Exponent4 -> util4 (p.x + p.dx) (diff_y)
            | Exponent6 -> util6 (p.x + p.dx) (diff_y)
            | Exponent8 -> util8 (p.x + p.dx) (diff_y)
        in
        (* new_u - p.u > 0 because dy remains an underestimate *)
        
        let dy = match is_nat (new_u - p.u) with
            | None -> (failwith error_ASSERTION_VIOLATED_NEGATIVE_DIFFERENCE: nat)
            | Some n -> p.dy + n / new_du_dy in
        (* dy is an underestimate because we start at 0 and the utility curve is convex *)
        newton {p with dy = dy ; n = p.n - 1}

(* Computes the tokens bought using the newton approximation method given the src/dst tokens pool
and the amount of src tokens sold. The (src/dst) multipliers are used to make sure that x and y can
be expressed in the same power of 10 (e.g if src token has 6 decimals and dst token has 12 decimals,
we will multiple the src token by a factor of 10^6 *)
let tokens_bought (src_token_funds: nat) (src_multiplier: nat) (dst_token_funds: nat) (dst_multiplier: nat) (amount_sold: nat) (exponent : flat_curve_exponent) : nat =
    let x = src_token_funds * src_multiplier in
    let y = dst_token_funds * dst_multiplier in
    (* 4 round is enough for most cases and underestimates the true payoff, so the user
        can always break up a trade for better terms *)
    let u, _du_dy = match exponent with
        | Exponent4 -> util4 x y
        | Exponent6 -> util6 x y
        | Exponent8 -> util8 x y
    in
    (newton { x = x; y = y ; dx = amount_sold * src_multiplier; dy = 0n ; u = u ; n = 5 ; exponent = exponent}) / dst_multiplier 

[@entry]
let add_liquidity (param: add_liquidity) (s: storage) : result =
    let {
        owner = _owner ;
        min_lqt_minted = _min_lqt_minted ;
        src_token = src_token ;
        src_token_amount = src_token_amount ;
        remaining_tokens_max_deposited = remaining_tokens_max_deposited ;
        deadline = deadline ;
    } = param in
    let deposited_amounts = Map.add src_token src_token_amount remaining_tokens_max_deposited in

    if Tezos.get_now () >= deadline then
        (failwith error_THE_CURRENT_TIME_MUST_BE_LESS_THAN_THE_DEADLINE : result)
    else if (Map.size deposited_amounts) <> (Map.size s.tokens_info) then
        (failwith error_INVALID_NUMBER_OF_TOKENS : result)
    else if (check_tez_amount deposited_amounts <> True) then
        (failwith error_SENT_TEZ_AMOUNT_DOES_NOT_CORRESPOND_TO_AMOUNT : result)
    else 
        let tez_balance = mutez_to_natural (Tezos.get_balance ()) in
        let received_amount =  mutez_to_natural (Tezos.get_amount ()) in
        let balance = match is_nat (tez_balance - received_amount) with
            | None -> (failwith error_BALANCE_LOWER_THAN_RECEIVED_AMOUNT: nat)
            | Some s -> s
        in
        let arg = Tez (unit: unit) in
        let new_s = match Map.find_opt arg s.tokens_info with
            | None -> s
            | Some old_info -> begin
                let new_info = { old_info with funds = balance } in
                let new_tokens_info = Map.update arg (Some new_info) s.tokens_info in
                { s with tokens_info = new_tokens_info ; }
            end
        in
        let update_pools_ep : unit contract  = Tezos.self "%request_balance" in
        let internal_call_ep: (add_liquidity * address) contract = Tezos.self "%add_liquidity_internal" in

        let update_pools_operation =  (Tezos.Next.Operation.transaction () 0mutez update_pools_ep) in
        let internal_param = (param, Tezos.get_sender ()) in
        let internal_call_operation = (Tezos.Next.Operation.transaction internal_param 0mutez internal_call_ep) in

        ([update_pools_operation; internal_call_operation], new_s) 

[@entry]
let add_liquidity_internal (param, sender: add_liquidity * address) (s: storage) : result =
    let {
        owner = owner ;
        min_lqt_minted = min_lqt_minted ;
        src_token = src_token ;
        src_token_amount = src_token_amount ;
        remaining_tokens_max_deposited = remaining_tokens_max_deposited ;
        deadline = _deadline ;
    } = param in
    let deposited_amounts = Map.add src_token src_token_amount remaining_tokens_max_deposited in

    if Tezos.get_sender () <> Tezos.get_self_address () then
        (failwith error_THIS_ENTRYPOINT_MAY_ONLY_BE_CALLED_BY_THE_CONTRACT : result)
    else
        let src_token_info = get_token_info s.tokens_info src_token in
        let lqt_minted = compute_proportionality src_token_amount src_token_info.funds s.lqt_total in
        if lqt_minted < min_lqt_minted then
            (failwith error_LQT_MINTED_MUST_BE_GREATER_THAN_MIN_LQT_MINTED : result)
        else
            let deposited_amounts = get_tokens_deposited_or_fail s.tokens_info deposited_amounts src_token_amount src_token_info.funds in
            let token_funds_update_func = fun (acc, item : ((token_variant, token_info) map) * (token_variant * nat)) ->
                let (token, amount) = item in
                let token_info = get_token_info s.tokens_info token in
                let new_token_info = update_token_info token_info (int amount) in
                Map.update token (Some new_token_info) acc
            in
            let new_tokens_info = Map.fold token_funds_update_func deposited_amounts Map.empty in
            let s = { s with
                lqt_total = s.lqt_total + lqt_minted ;
                tokens_info = new_tokens_info ;
            } in

            let lqt_mint_op = mint_or_burn s owner (int lqt_minted) in
            let build_transfers_func = fun (acc, item : (operation list) * (token_variant * nat)) ->
                let (token, amount) = item in
                let t : transfer_type = Receive in
                match (token_transfer token sender (Tezos.get_self_address ()) amount t) with
                    | None -> acc
                    | Some op -> (op :: acc) 
            in
            let transfers_op = Map.fold build_transfers_func deposited_amounts [] in
            ((lqt_mint_op :: transfers_op), s)

[@entry]
let remove_liquidity (param: remove_liquidity) (s: storage) : result =
    if Tezos.get_now () >= param.deadline then
        (failwith error_THE_CURRENT_TIME_MUST_BE_LESS_THAN_THE_DEADLINE : result)
    else if (Map.size param.min_tokens_withdrawn) <> (Map.size s.tokens_info) then
        (failwith error_INVALID_NUMBER_OF_TOKENS : result)
    else
        let tez_balance = mutez_to_natural (Tezos.get_balance ()) in
        let received_amount =  mutez_to_natural (Tezos.get_amount ()) in
        let balance = match is_nat (tez_balance - received_amount) with
            | None -> (failwith error_BALANCE_LOWER_THAN_RECEIVED_AMOUNT: nat)
            | Some s -> s
        in
        let arg = Tez (unit: unit) in
        let new_s = match Map.find_opt arg s.tokens_info with
            | None -> s
            | Some old_info -> begin
                let new_info = { old_info with funds = balance } in
                let new_tokens_info = Map.update arg (Some new_info) s.tokens_info in
                { s with tokens_info = new_tokens_info ; }
            end
        in
        let update_pools_ep : unit contract  = Tezos.self "%request_balance" in
        let internal_call_ep: (remove_liquidity * address) contract = Tezos.self "%remove_liquidity_internal" in

        let update_pools_operation =  (Tezos.Next.Operation.transaction () 0mutez update_pools_ep) in
        let internal_param = (param, Tezos.get_sender ()) in
        let internal_call_operation = (Tezos.Next.Operation.transaction internal_param 0mutez internal_call_ep) in

        ([update_pools_operation; internal_call_operation], new_s) 

[@entry]
let remove_liquidity_internal (param, sender: remove_liquidity * address) (s: storage) : result =
    let {
        receiver = receiver ;
        lqt_burned = lqt_burned ;
        min_tokens_withdrawn = min_tokens_withdrawn ;
        deadline = _deadline ;
    } = param in
    
    if Tezos.get_sender () <> Tezos.get_self_address () then
        (failwith error_THIS_ENTRYPOINT_MAY_ONLY_BE_CALLED_BY_THE_CONTRACT : result)
    else
        let tokens_withdrawn = get_tokens_withdrawn_or_fail s.tokens_info min_tokens_withdrawn lqt_burned s.lqt_total in
        let tokens_funds_update_func = fun (acc, item : ((token_variant, token_info) map) * (token_variant * nat)) ->
            let (token, amount) = item in
            let token_info = get_token_info s.tokens_info token in
            let new_token_info = update_token_info token_info (0 - amount) in
            Map.update token (Some new_token_info) acc
        in
        let new_tokens_info = Map.fold tokens_funds_update_func tokens_withdrawn Map.empty in
        let remaining_lqt = match is_nat (s.lqt_total - lqt_burned) with
            | None -> (failwith error_CANNOT_BURN_MORE_THAN_THE_TOTAL_AMOUNT_OF_LQT : nat)
            | Some lqt -> lqt in
        let s = { s with
            lqt_total = remaining_lqt ;
            tokens_info = new_tokens_info ;
        } in

        let lqt_burn_op = mint_or_burn s sender (0 - lqt_burned) in
        let build_transfers_func = fun (acc, item : (operation list) * (token_variant * nat)) ->
            let (token, amount) = item in
            let t : transfer_type = Send in
            match (token_transfer token (Tezos.get_self_address ()) receiver amount t) with
                | None -> acc
                | Some op -> (op :: acc) 
        in
        let transfers_op = Map.fold build_transfers_func tokens_withdrawn [] in
        ((lqt_burn_op :: transfers_op), s)

[@entry]
let token_swap (param: token_swap) (s: storage) : result =
    let src_token_sold = Map.add param.src_token param.amount_sold Map.empty in
    if (Tezos.get_now ()) >= param.deadline then
        (failwith error_THE_CURRENT_TIME_MUST_BE_LESS_THAN_THE_DEADLINE : result)
    else if (check_tez_amount src_token_sold <> True) then
        (failwith error_SENT_TEZ_AMOUNT_DOES_NOT_CORRESPOND_TO_AMOUNT : result)
    else
        let tez_balance = mutez_to_natural (Tezos.get_balance ()) in
        let received_amount =  mutez_to_natural (Tezos.get_amount ()) in
        let balance = match is_nat (tez_balance - received_amount) with
            | None -> (failwith error_BALANCE_LOWER_THAN_RECEIVED_AMOUNT: nat)
            | Some s -> s
        in
        let arg = Tez (unit: unit) in
        let new_s = match Map.find_opt arg s.tokens_info with
            | None -> s
            | Some old_info -> begin
                let new_info = { old_info with funds = balance } in
                let new_tokens_info = Map.update arg (Some new_info) s.tokens_info in
                { s with tokens_info = new_tokens_info ; }
            end
        in
        let update_pools_ep : unit contract  = Tezos.self "%request_balance" in
        let internal_call_ep: (token_swap * address) contract = Tezos.self "%token_swap_internal" in

        let update_pools_operation =  (Tezos.Next.Operation.transaction () 0mutez update_pools_ep) in
        let internal_param = (param, Tezos.get_sender ()) in
        let internal_call_operation = (Tezos.Next.Operation.transaction internal_param 0mutez internal_call_ep) in

        ([update_pools_operation; internal_call_operation], new_s) 

[@entry]
let token_swap_internal (param, sender: token_swap * address) (s: storage) : result =
    let {
        src_token = src_token ;
        dst_token = dst_token ;
        amount_sold = amount_sold ;
        min_amount_bought = min_amount_bought ;
        receiver = receiver ;
        deadline = _deadline ;
    } = param in

    if Tezos.get_sender () <> Tezos.get_self_address () then
        (failwith error_THIS_ENTRYPOINT_MAY_ONLY_BE_CALLED_BY_THE_CONTRACT : result)
    else
        let src_token_info = get_token_info s.tokens_info src_token in
        let dst_token_info = get_token_info s.tokens_info dst_token in
        let price_opt : (nat * nat) option = Tezos.call_view "get_token_price" (src_token, dst_token) s.target_oracle in
        let (num, denum) = match price_opt with
            | None -> (failwith error_MISSING_ORACLE_VIEW : nat * nat)
            | Some r -> r in
        
        let src_multiplier = src_token_info.multiplier * num in
        let dst_multiplier = dst_token_info.multiplier * denum in
        let total_tokens_bought = tokens_bought src_token_info.funds src_multiplier dst_token_info.funds dst_multiplier amount_sold s.curve_exponent in
        let swap_fee = s.swap_fee_ratio.numerator * total_tokens_bought / s.swap_fee_ratio.denominator in
        let tokens_bought = (
            match is_nat (total_tokens_bought - swap_fee) with
            | None -> (failwith error_CASH_BOUGHT_MUST_BE_GREATER_THAN_OR_EQUAL_TO_MIN_CASH_BOUGHT : nat)
            | Some value -> if value < min_amount_bought then
                (failwith error_CASH_BOUGHT_MUST_BE_GREATER_THAN_OR_EQUAL_TO_MIN_CASH_BOUGHT : nat)
                else value) in
        let partial_swap_fee = s.rewards_receiver_ratio.numerator * swap_fee / s.rewards_receiver_ratio.denominator in
        
        let src_new_token_info = update_token_info src_token_info (int amount_sold) in
        let dst_new_token_info = update_token_info dst_token_info (0-(tokens_bought+partial_swap_fee)) in
        let new_tokens_info = Map.update src_token (Some src_new_token_info) s.tokens_info in
        let new_tokens_info = Map.update dst_token (Some dst_new_token_info) new_tokens_info in

        let s = { s with
            tokens_info = new_tokens_info ;
        } in

        let transfers_op = [] in
        let transfers_op = 
            match (token_transfer src_token sender (Tezos.get_self_address ()) amount_sold Receive) with
            | None -> transfers_op
            | Some op -> (op :: transfers_op)
        in
        let transfers_op = 
            match (token_transfer dst_token (Tezos.get_self_address ()) receiver tokens_bought Send) with
            | None -> transfers_op
            | Some op -> (op :: transfers_op) in
        let transfers_op = 
            match (token_transfer dst_token (Tezos.get_self_address ()) s.rewards_receiver partial_swap_fee Send) with
            | None -> transfers_op
            | Some op -> (op :: transfers_op) in
        (transfers_op, s)

(* Sets the address of the liquidity token contract. Once the liquidity address has been set
to another value than the null address, this entrypoint cannot be called again.

Parameters:
- lqt_address (address): The address of the liquidity token.
*)
[@entry]
let set_lqt_address (addr: address) (s: storage) : result =
    if s.lqt_address <> null_address then
        (failwith error_LQT_ADDRESS_ALREADY_SET : result)
    else
        (([] : operation list), {s with lqt_address = addr })

(* Set the recipient of the partial swap fees. Only an admin can call this entrypoint. *)
[@entry]
let set_rewards_receiver (addr: address) (s: storage) : result =
    match Big_map.find_opt (Tezos.get_sender ()) s.administrators with
    | None -> (failwith error_NOT_ADMIN: result)
    | Some status -> begin
        match status with
        | Proposed -> (failwith error_NOT_ADMIN : result)
        | Set -> (([] : operation list), {s with rewards_receiver = addr })
    end

(* Set the recipient of the partial swap fees. Only an admin can call this entrypoint. *)
[@entry]
let set_rewards_receiver_ratio (p: ratio) (s: storage) : result =
    match Big_map.find_opt (Tezos.get_sender ()) s.administrators with
    | None -> (failwith error_NOT_ADMIN: result)
    | Some status -> begin
        match status with
        | Proposed -> (failwith error_NOT_ADMIN : result)
        | Set -> (([] : operation list), {s with rewards_receiver_ratio = p })
    end

(* Sets the recipient of the baking rewards. Only an admin can call this entrypoint. *)
[@entry]
let set_baking_rewards_receiver (addr : address) (s: storage) : result =
    match Big_map.find_opt (Tezos.get_sender ()) s.administrators with
    | None -> (failwith error_NOT_ADMIN: result)
    | Some status -> begin
        match status with
        | Proposed -> (failwith error_NOT_ADMIN : result)
        | Set -> (([] : operation list), {s with baking_rewards_receiver = addr })
    end

(* Propose a new admin of the contract. Only an admin can execute this operation.
Parameters:
- addr (address): The new proposed admin. (The proposed admin must accept before becoming full
    rights admin)
*)
[@entry]
let propose_admin (addr : address) (s: storage) : result =
    match Big_map.find_opt (Tezos.get_sender ()) s.administrators with
    | None -> (failwith error_NOT_ADMIN : result)
    | Some status -> begin
         match status with
        | Proposed -> (failwith error_NOT_ADMIN : result)
        | Set -> (([] : operation list), {s with administrators = Big_map.update addr (Some Proposed) s.administrators })
    end

(* Accepts the admin proposal. The caller must be a proposed admin to be allowed to execute this operation. *)
[@entry]
let accept_admin_proposal (_unit : unit) (s: storage) : result =
    match Big_map.find_opt (Tezos.get_sender ()) s.administrators with
    | None -> (failwith error_NOT_PROPOSED_ADMIN : result)
    | Some status -> begin
        match status with
        | Set -> (failwith error_ADMIN_ALREADY_SET : result)
        | Proposed -> (([] : operation list), {s with administrators = Big_map.update (Tezos.get_sender ()) (Some Set) s.administrators })
    end

(* Remove an existing admin of the contract. Only an admin can execute this operation.
Parameters:
- addr (address): The admin to be removed. 
*)
[@entry]
let remove_admin (addr : address) (s: storage) : result =
    match Big_map.find_opt (Tezos.get_sender ()) s.administrators with
    | None -> (failwith error_NOT_ADMIN: result)
    | Some status -> begin
        match status with
        | Proposed -> (failwith error_NOT_ADMIN : result)
        | Set -> (([] : operation list), {s with administrators = Big_map.remove addr s.administrators })
    end

(* Sets the swap fee. Only an admin can call this entrypoint.

Parameters:
- fee_ratio (ratio): The new swap fee ratio to be used in exchanges.
*)
[@entry]
let set_swap_fee_ratio (fee_ratio : ratio) (s: storage) : result =
    match Big_map.find_opt (Tezos.get_sender ()) s.administrators with
    | None -> (failwith error_NOT_ADMIN: result)
    | Some status -> begin
        match status with
        | Proposed -> (failwith error_NOT_ADMIN : result)
        | Set -> (([] : operation list), {s with swap_fee_ratio = fee_ratio})
    end

(* Set the address of the target price oracle. The target price oracle is used to
fetch off-chain prices for all token pairs in the pool.
Only an admin can call this entrypoint.

Parameters:
- addr (address): The new target oracle to be used by the swap.
*)
[@entry]
let set_target_oracle (addr: address) (s: storage) : result =
    match Big_map.find_opt (Tezos.get_sender ()) s.administrators with
    | None -> (failwith error_NOT_ADMIN: result)
    | Some status -> begin
        match status with
        | Proposed -> (failwith error_NOT_ADMIN : result)
        | Set -> (([] : operation list), {s with target_oracle = addr}) 
    end

(* Set the exponent of the flat curve used for calculations. 
Only an admin can call this entrypoint.

Parameters:
- p (flat_curve_exponent): The new exponent for the flat curve (can be 4, 6 or 8)
*)
[@entry]
let set_flat_curve_exponent (p: flat_curve_exponent) (s: storage) : result =
    match Big_map.find_opt (Tezos.get_sender ()) s.administrators with
    | None -> (failwith error_NOT_ADMIN: result)
    | Some status -> begin
        match status with
        | Proposed -> (failwith error_NOT_ADMIN : result)
        | Set -> (([] : operation list), {s with curve_exponent = p})
    end

(* Set the delegate of the contract. Only an admin can call this entrypoint. *)
[@entry]
let set_pool_delegate (baker: key_hash option) (s: storage) : result =
    match Big_map.find_opt (Tezos.get_sender ()) s.administrators with
    | None -> (failwith error_NOT_ADMIN: result)
    | Some status -> begin
        match status with
        | Proposed -> (failwith error_NOT_ADMIN : result)
        | Set -> (([Tezos.Next.Operation.set_delegate baker] : operation list), s)
    end

type set_fa1_token_balance = nat
type set_fa2_token_balance = ((address * nat) * nat) list
type fa2_balance = ((address * nat) list * ((((address * nat) * nat) list) contract))
type fa1_balance = address * (nat contract)

let fetch_balance_op (token_contract: token_variant): operation option =
    match token_contract with
    | Fa2 (token_address, token_id) -> begin
        let set_fa2_balance : set_fa2_token_balance contract = Tezos.self "%set_fa2_balance" in
        let balance_of : fa2_balance contract =
            (match (Tezos.get_entrypoint_opt "%balance_of" token_address : fa2_balance contract option) with
                | None -> (failwith error_INVALID_FA2_TOKEN_CONTRACT_MISSING_BALANCE_OF: fa2_balance contract)
                | Some c -> c) in
        let arg =  ([((Tezos.get_self_address ()), token_id)], set_fa2_balance) in
        let op = Tezos.Next.Operation.transaction arg 0mutez balance_of in
        Some (op)
    end
    | Fa1 token_address -> begin
        let set_fa1_balance : set_fa1_token_balance contract = Tezos.self "%set_fa1_balance" in
        let balance : fa1_balance contract =
            (match (Tezos.get_entrypoint_opt "%getBalance" token_address : fa1_balance contract option) with
                | None -> (failwith error_INVALID_FA1_TOKEN_CONTRACT_MISSING_BALANCE_OF: fa1_balance contract)
                | Some c -> c) in
        let arg =  (Tezos.get_self_address (), set_fa1_balance) in
        let op = Tezos.Next.Operation.transaction arg 0mutez balance in
        Some (op)
    end
    | Tez _unit -> None

[@entry]
let set_fa2_balance (fa2_balance: set_fa2_token_balance) (s: storage) : result =
    // verify if the sender is the token contract.
    // set the balance
    let (owner, token_id, balance) = match fa2_balance with
        | [] -> (failwith error_INVALID_FA2_BALANCE_RESPONSE : address * nat * nat)
        | x :: _xs -> (x.0.0, x.0.1, x.1)
    in
    if (owner <> Tezos.get_self_address ()) then
        (failwith error_INVALID_RECEIVER: result)
    else begin
        let arg = Fa2 (Tezos.get_sender (), token_id) in
        match Map.find_opt arg s.tokens_info with
            | None -> (failwith error_UNKNOWN_TOKEN : result)
            | Some old_info -> begin
                let new_info = { old_info with funds = balance } in
                let new_tokens_info = Map.update arg (Some new_info) s.tokens_info in
                ([], { s with tokens_info = new_tokens_info ; })
            end
    end

[@entry]
let set_fa1_balance (balance: set_fa1_token_balance) (s: storage) : result =
    // verify if the sender is the token contract.
    // set the balance
    let arg = Fa1 (Tezos.get_sender ()) in
    match Map.find_opt arg s.tokens_info with
        | None -> (failwith error_UNKNOWN_TOKEN : result)
        | Some old_info -> begin
            let new_info = { old_info with funds = balance} in
            let new_tokens_info = Map.update arg (Some new_info) s.tokens_info in
            ([], { s with tokens_info = new_tokens_info ; })
        end

[@entry]
let request_balance (_unit: unit) (s: storage) : result =
    if ((Tezos.get_sender () <> Tezos.get_source()) && (Tezos.get_sender () <> Tezos.get_self_address ())) then
        (failwith error_NOT_ALLOWED_TO_EXECUTE_OPERATION: result)
    else if (Tezos.get_amount ()) > 0mutez then
      (failwith error_SENDING_TEZ_NOT_ALLOWED : result)
    else begin
        let update_pool_func = fun (acc, item : (operation list) * (token_variant * token_info)) ->
            let (token, _token_info) = item in
            match token with
                | Fa2 (token_address, token_id) -> begin
                    let set_fa2_balance : set_fa2_token_balance contract = Tezos.self "%set_fa2_balance" in
                    let balance_of : fa2_balance contract =
                        (match (Tezos.get_entrypoint_opt "%balance_of" token_address : fa2_balance contract option) with
                            | None -> (failwith error_INVALID_FA2_TOKEN_CONTRACT_MISSING_BALANCE_OF: fa2_balance contract)
                            | Some c -> c) in
                    let arg =  ([((Tezos.get_self_address ()), token_id)], set_fa2_balance) in
                    let op = Tezos.Next.Operation.transaction arg 0mutez balance_of in
                    (op :: acc)
                end
                | Fa1 token_address -> begin
                    let set_fa1_balance : set_fa1_token_balance contract = Tezos.self "%set_fa1_balance" in
                    let balance : fa1_balance contract =
                        (match (Tezos.get_entrypoint_opt "%getBalance" token_address : fa1_balance contract option) with
                            | None -> (failwith error_INVALID_FA1_TOKEN_CONTRACT_MISSING_BALANCE_OF: fa1_balance contract)
                            | Some c -> c) in
                    let arg =  (Tezos.get_self_address (), set_fa1_balance) in
                    let op = Tezos.Next.Operation.transaction arg 0mutez balance in
                    (op :: acc)
                end
                | Tez _unit -> acc
        in
        let update_pool_op_list = Map.fold update_pool_func s.tokens_info [] in
        (update_pool_op_list, s)
    end
end

let default_storage_ghostnet : MultitokenFlatCurve.storage = {
    administrators = Big_map.literal [ 
        (("tz1YY1LvD6TFH4z74pvxPQXBjAKHE5tB5Q8f" : address), Set (unit: unit)) ;
        (("tz1MC1c3JJqdwHswMPMLZte8zzAyRFwnWEme" : address), Set (unit: unit)) ;
    ] ;
    lqt_total = 900000000n;
    lqt_address = ("tz1Ke2h7sDdakHJQh8WX4Z372du1KChsksyU" : address) ;
    swap_fee_ratio = { numerator = 1n ; denominator = 100n ; } ;
    baking_rewards_receiver = ("tz1YUUsbHBAEBFaa4XM11HUY2Quv3QH6Vjpd" : address) ;
    rewards_receiver = ("tz1YY1LvD6TFH4z74pvxPQXBjAKHE5tB5Q8f" : address) ;
    rewards_receiver_ratio = { numerator = 50n ; denominator = 100n ; } ;
    target_oracle = ("" : address) ;
    tokens_info = Map.literal [
        (Fa2 (("KT1J2iy42X6TkRMzX7TJiHh8vibg84fAerPc" : address), 0n), { funds = 300000000n; multiplier = 100n}) ;
        (Tez (unit : unit), { funds = 450450450n; multiplier = 100n }) ;
        (Fa1 ("KT18jqS6maEXL8AWvc2x2bppHNRQNqPq8axP" : address), { funds = 553856n ; multiplier = 1n}) ;
    ] ;
    curve_exponent = Exponent8 (unit: unit);
}

let default_storage_mainnet : MultitokenFlatCurve.storage = {
    administrators = Big_map.literal [ 
        (("tz1YY1LvD6TFH4z74pvxPQXBjAKHE5tB5Q8f" : address), Set (unit: unit)) ;
        (("tz1MC1c3JJqdwHswMPMLZte8zzAyRFwnWEme" : address), Set (unit: unit)) ;
    ] ;
    lqt_total = 1200000n; 
    lqt_address = ("tz1Ke2h7sDdakHJQh8WX4Z372du1KChsksyU" : address) ;
    swap_fee_ratio = { numerator = 1n ; denominator = 100n ; } ;
    baking_rewards_receiver = ("KT1FPmpucXoiX7ZLahj1V1E5tRah1XvcnkZB" : address) ;
    rewards_receiver = ("KT1FPmpucXoiX7ZLahj1V1E5tRah1XvcnkZB" : address) ;
    rewards_receiver_ratio = { numerator = 50n ; denominator = 100n ; } ;
    target_oracle = ("KT1FGE8xhmtVZBhQH9x2oxV4rB2QMJKdzqkd" : address) ;
    tokens_info = Map.literal [
        (Fa2 (("KT1XnTn74bUtxHfDtBmm2bGZAQfhPbvKWR8o" : address), 0n), { funds = 4000000n; multiplier = 100n}) ;
        (Tez (unit : unit), { funds = 5841975n; multiplier = 100n }) ;
        (Fa1 ("KT1PWx2mnDueood7fEmfbBDKx1D9BAnnXitn" : address), { funds = 7243n ; multiplier = 1n}) ;
    ] ;
    curve_exponent = Exponent8 (unit: unit);
}