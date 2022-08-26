# Ubinetic Oracles Contract

## Structure

This project provides the following contracts:

- job_scheduler.py: Schedules jobs for the datatransmitter.
- generic_oracle.py: Shows an implementation that takes the data transmitter price and validates it on-chain.
errors 

## Generic oracles
The purpose of the generic oracles is to be a unified source of truth where one can
query the price of a token, cryptocurency or real curency (usually in USD).

### Generic oracle
The generic oracle serves the purpose described above and it is limited to only a few
curencies (symbols): XTZ, DEFI and BTC price in USD with a 6 decimal precision. The
validation and aggregation of these prices is static (a lambda part of the contract's
code).

### Generic oracle V3
The generic oracle v3 is an improvement over the initial generic oracle. This version
allows for a variable number of symbols as well as updatable aggregation and validation
lambdas.

The contract contains the following entrypoints:
- touch
- set_valid_script
- set_administrator
- add_valid_source
- remove_valid_source
- update_aggregation_lambda
- update_validation_lambda
- fulfill

The contract will provide the prices using `get_price` onchain view.

#### Touch
- **entrypoint** - `def touch(self)`
 - **arguments** - unit : sp.TUnit
 - **description** - entrypoint used to cache the smart contract if it is not cached. 
It updates the counter which stores how many times the contract was outside the cache.
In reality this entrypoint can be called by anyone, therefore the counter serves
as an approximation and not the real value.

#### Set valid script
 - **entrypoint** - `def set_valid_script(self, script)`
 - **arguments** - script - sp.TBytes
 - **description** - entrypoint used by the admin to set the script to be executed by the
data transmitters (also known as valid sources). Only admin is allowed to call this entrypoint.

#### Set administrator
 - **entrypoint** - `def set_administrator(self, administrator)`
 - **arguments** - administrator : sp.TAddress
 - **description** - entrypoint used by the admin to set the new admin.
Only admin is allowed to call this entrypoint.

#### Add valid source
 - **entrypoint** - `def add_valid_source(self, source)`
 - **arguments** - source : sp.TAddress 
 - **description** - entrypoint used by the admin to add a new source.
Only admin is allowed to call this entrypoint.

#### Remove valid source
 - **entrypoint** - `def remove_valid_source(self, source)`
 - **arguments** - source : sp.TAddress 
 - **description** - entrypoint used by the admin to remove a source if present.
Only admin is allowed to call this entrypoint.

#### Update aggregation lambda
 - **entrypoint** - `def update_aggregation_lambda(self, _lambda)`
 - **arguments** - _lambda : sp.TLambda(sp.TPair(sp.TString, sp.TPair(sp.TNat, sp.TNat)), sp.TNat)
 - **description** - entrypoint used by the admin to update the aggregation lambda. The aggregation
lambda can contain symbol specific logic as well as generic logic. Only admin is allowed
to call this entrypoint.

#### Update validation lambda
 - **entrypoint** - `def update_validation_lambda(self, _lambda)`
 - **arguments** - _lambda : sp.TLambda(sp.TPair(sp.TString, sp.TPair(sp.TNat, sp.TNat)), sp.TBool)
 - **description** - entrypoint used by the admin to update the validation lambda. The validation 
lambda can contain symbol specific logic as well as generic logic. Only admin is allowed
to call this entrypoint.

#### Fulfill
 - **entrypoint** - `def fulfill(self, fulfill)`
 - **arguments** - fulfill : sp.TRecord(script=sp.TBytes, payload=sp.TBytes)
 - **description** - entrypoint called by the data transmitter directly. It needs to be as efficient
as possible (it has a gas and storage limit of 11000). While the sp.sender of this entrypoint will
always be the JobScheduler contract, the sp.source will always be the data transmitter. This
entrypoint checks if the source and script is valid, then if the answer fits in the current epoch,
comes from a new source and matches with some minor precision margin checked by the validation
lambda logic, the value set by a previous source the response is counted as +1. If the response
counter reaches the threshold the price in storage is set and ready to be used by the get_price view.

#### Get price
 - **onchain view** - `def get_price(self, symbol)`
 - **arguments** - symbol : sp.TString
 - **description** - onchain_view used to read the price out of storage. The view takes the symbol 
as parameter and reads the respective entry from storage to then return it. The price is only 
returned if it is not older than the validity window set in storage expressed it interval integer.
