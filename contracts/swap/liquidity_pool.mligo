let error_NOT_ENOUGH_BALANCE = "NotEnoughBalance"
let error_NOT_ENOUGH_ALLOWANCE = "NotEnoughAllowance"
let error_VULNERABLE_OPERATION = "UnsafeAllowanceChange"
let error_ADMIN_ONLY = "OnlyAdminAllowed"
let error_BURN_AMOUNT_EXCEEDING_FUNDS = "BurnAmountExceedingFunds"
let error_TEZ_NOT_ALLOWED = "TezNotAllowed"


type allowance = (address, nat) map
type ledger = (address, (nat * allowance)) big_map
type transfer = (address * (address * nat))
type approve = address * nat
type mintOrBurn = [@layout:comb] {
    quantity : int ;
    target : address 
}
type getAllowance = ((address * address) * nat contract)
type getBalance = address * nat contract 
type getTotalSupply = (unit * nat contract)
type single_token_metadata = {
    token_id : nat;
    token_info : (string, bytes) map;
}
type token_metadata = (nat, single_token_metadata) big_map
type metadata = (string, bytes) big_map

type storage = {
    admin : address;
    ledger : ledger;
    token_metadata : token_metadata;
    total_supply : nat;
    metadata : metadata;
   }

type parameter = 
| Transfer of transfer 
| Approve of approve 
| GetAllowance of getAllowance 
| GetBalance of getBalance 
| GetTotalSupply of getTotalSupply
| MintOrBurn of mintOrBurn

let get_allowed_amount (a:allowance) (spender:address) : nat =
    match Map.find_opt spender a with
    | Some v -> v 
    | None -> 0n

let set_allowed_amount (a:allowance) (spender:address) (allowed_amount: nat) : allowance =
        Map.add spender allowed_amount a

let decrease_allowance (a:allowance) (spender:address) (allowed_amount: nat) : allowance =
    match Map.find_opt spender a with
    | Some v -> 
        let _ = assert_with_error(v >= allowed_amount) error_NOT_ENOUGH_ALLOWANCE in
        let new_allowed_amount = abs(v - allowed_amount) in
        if new_allowed_amount > 0n then
            Map.update spender (Some(new_allowed_amount)) a
        else
            Map.remove spender a
    | None -> failwith(error_NOT_ENOUGH_ALLOWANCE)

let get_for_user (ledger:ledger) (owner: address) : (nat * allowance) =
    match Big_map.find_opt owner ledger with
    | Some tokens -> tokens
    | None -> (0n, (Map.empty : allowance))

let update_for_user (ledger:ledger) (owner: address) (amount_ : nat) (allowances : allowance) : ledger =
    Big_map.update owner (Some (amount_,allowances)) ledger

let set_approval (ledger:ledger) (owner: address) (spender : address) (allowed_amount: nat) : ledger =
      let (tokens, allowances) = get_for_user ledger owner in
      let previous_allowances = get_allowed_amount allowances spender in
      let _ = assert_with_error (previous_allowances = 0n || allowed_amount = 0n) error_VULNERABLE_OPERATION in
      let allowances = set_allowed_amount allowances spender allowed_amount in
      let ledger = update_for_user ledger owner tokens allowances in
      ledger

let decrease_token_amount_for_user (ledger : ledger) (spender : address) (from_ : address) (amount_ : nat) : ledger =
    let (tokens, allowances) = get_for_user ledger from_ in
    let allowed_amount = if (spender = from_) then 
        tokens
    else
        get_allowed_amount allowances spender 
    in
    let _ = assert_with_error (tokens >= amount_) error_NOT_ENOUGH_BALANCE in
    //  TZIP-7 specifies that it should fail with requested allowance and current allowance
    let _ = if (allowed_amount < amount_) then
        ([%Michelson ({| { FAILWITH } |} : string * (nat * nat) -> unit)]
            (error_NOT_ENOUGH_ALLOWANCE, (amount_, allowed_amount)) : unit)
    else 
        () 
    in
    let tokens = abs(tokens - amount_) in
    let allowances = decrease_allowance allowances spender amount_ in
    let ledger = update_for_user ledger from_ tokens allowances in
    ledger

let increase_token_amount_for_user (ledger : ledger) (to_ : address) (amount_ : nat) : ledger =
    let (tokens, allowances) = get_for_user ledger to_ in
    let tokens = tokens + amount_ in
    let ledger = update_for_user ledger to_ tokens allowances in
    ledger

let get_amount_for_owner (s:storage) (owner : address) : nat =
    let (amount_, _) = get_for_user s.ledger owner in
    amount_

let get_allowances_for_owner (s:storage) (owner : address) : allowance =
    let (_, allowances) = get_for_user s.ledger owner in
    allowances

let get_ledger (s:storage) : ledger = s.ledger

let set_ledger (s:storage) (ledger:ledger) : storage =
    {s with ledger=ledger}

let transfer ((from_, to_value), s : transfer * storage) : operation list * storage =
   let (to_, value) = to_value in
   let ledger1 = get_ledger s in
   let ledger2 = decrease_token_amount_for_user ledger1 (Tezos.get_sender ()) from_ value in
   let ledger = increase_token_amount_for_user ledger2 to_ value in
   let s1 = set_ledger s ledger in
   (([] : operation list), s1)

// /** approve */
let approve ((spender,value), s : approve * storage) : operation list * storage =
   let ledger1 = get_ledger s in
   let ledger = set_approval ledger1 (Tezos.get_sender ()) spender value in
   let s1 = set_ledger s ledger in
   (([] : operation list), s1)

// /** getAllowance entrypoint */
let getAllowance ((owner_spender,callback), s: getAllowance * storage) : operation list * storage =
   let (owner,spender) = owner_spender in
   let a = get_allowances_for_owner s owner in
   let allowed_amount = get_allowed_amount a spender in
   let operation = Tezos.transaction allowed_amount 0tez callback in
   ([operation], s)

// /** getBalance entrypoint */
let getBalance ((owner,callback), s : getBalance * storage) : operation list * storage =
   let balance_ = get_amount_for_owner s owner in
   let operation = Tezos.transaction balance_ 0tez callback in
   ([operation], s)

// /** getTotalSupply entrypoint */
let getTotalSupply ((_,callback), s : getTotalSupply * storage) : operation list * storage =
   let operation = Tezos.transaction s.total_supply 0tez callback in
   ([operation], s)

// /** mintOrBurn entrypoint */
let mintOrBurn (param, s: mintOrBurn * storage) : operation list * storage =
  begin
    if (Tezos.get_sender ()) <> s.admin
    then failwith error_ADMIN_ONLY
    else ();
    let ledger = get_ledger s in
    let (old_balance, allowances) = get_for_user ledger param.target in
    let new_balance = match is_nat (old_balance + param.quantity) with
      | None -> (failwith error_BURN_AMOUNT_EXCEEDING_FUNDS : nat)
      | Some bal -> bal in
    let ledger = update_for_user ledger param.target new_balance allowances in
    let total_supply = match is_nat (s.total_supply + param.quantity) with
        | None -> (failwith error_BURN_AMOUNT_EXCEEDING_FUNDS : nat)
        | Some val -> val in
    (([] : operation list), { s with ledger = ledger ; total_supply = total_supply })
  end


let main ((parameter, storage) : parameter * storage) : operation list * storage =
    begin
        if Tezos.get_amount () <> 0mutez
        then failwith error_TEZ_NOT_ALLOWED
        else ();
        match parameter with
        | Transfer param -> transfer (param, storage)
        | Approve param -> approve (param, storage)
        | GetAllowance param -> getAllowance (param, storage)
        | GetBalance param -> getBalance (param, storage)
        | GetTotalSupply param -> getTotalSupply (param, storage)
        | MintOrBurn param -> mintOrBurn (param, storage)
    end