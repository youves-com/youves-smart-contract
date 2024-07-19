(* Contract to fetch the target price between given src/dst token pairs. This contract has the
functionality of an aggregator where these prices can be fetched. The actual values will be
calculated by other contracts using the generic on-demand-oracle prices. *)
module MultitokenOracle = struct
type price = nat * nat

// Token variant type. It represents the types of tokens the pool is able to
// interact with.

type token_variant = 
      Fa2 of address * nat 
    | Fa1 of address
    | Tez of unit

type price_fetching_lambda = unit -> price

type symbol_price_key = token_variant * token_variant

type storage = [@layout:comb] { 
    administrators: (address, unit) big_map ;
    price_fetching_lambdas: (symbol_price_key, price_fetching_lambda) big_map ;
}

type result = operation list * storage

(* =============================================================================
 * Entrypoint Functions
 * ============================================================================= *)
[@entry]
let add_admin (addr : address) (storage: storage) : result =
    match Big_map.find_opt (Tezos.get_sender ()) storage.administrators with
    | None -> (failwith "NotAdmin" : result)
    | Some _admin -> (([] : operation list), {storage with administrators = Big_map.add addr () storage.administrators})

[@entry]
let remove_admin (addr : address) (storage: storage) : result =
    match Big_map.find_opt (Tezos.get_sender ()) storage.administrators with
    | None -> (failwith "NotAdmin" : result)
    | Some _admin -> (([] : operation list), {storage with administrators = Big_map.remove addr storage.administrators})

[@entry]
let update_price_fetching_data (key, value: symbol_price_key * price_fetching_lambda) (storage: storage) : result =
    (([] : operation list), {storage with price_fetching_lambdas = Big_map.update key (Some(value)) storage.price_fetching_lambdas})

[@entry]
let remove_price_fetching_data (key: symbol_price_key) (storage: storage) : result =
    (([] : operation list), {storage with price_fetching_lambdas = Big_map.remove key storage.price_fetching_lambdas })

(* =============================================================================
 * Views
 * ============================================================================= *)
[@view]
let get_token_price (key : symbol_price_key) (storage : storage) : price =
    match Big_map.find_opt key storage.price_fetching_lambdas with
    | None -> (failwith "InvalidPair")
    | Some pfl -> begin
        let price = pfl () in
        price
    end
end