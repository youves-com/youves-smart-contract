# Synthetic Asset Platform Contracts

## Structure

This project provides the following contracts:

- constants.py: holds constants used throughout the project
- errors.py: acts as a constant error map used throughout the project. Non-project specific errors (i.e. fa2 errors) are covered in the respective files.
- fa2.py: a simple and reusable sceleton for FA2 tokens.
- oracle.py: a dummy oracle implementation used for testing.
- viewer.py: a dummy contract used as storage for callbacks.
- utils.py: helper classes and syntactic sugar
- governance_token.py: the governance token the minter receives for locking his/her collateral
- staking_pool.py: used for rewards and savings distribution
- options_listing.py: used to advertise and execute options
- tracker_engine.py: this is where the tracker logic is implemented

## Build/Basic Usage

### Dependencies

This project depends only on SmartPy (which depends on python and node), you can install SmartPy by doing a:

```
$ sh <(curl -s https://smartpy.io/releases/20210604-7f97dba13e914cb1915b7cea16b844208abf51e9/cli/install.sh)
```

You can read more about the installation here: https://smartpy.io/cli/

If you want to compile docs and deploy you also will need a sphinx and pytezos, these are the dependencies:

```
apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends python3-pip libsodium-dev libsecp256k1-dev
pip3 install sphinx pytezos
```

There is a ".devcontainer" which creates a dockerized environment and installs everything needed for you. You can checkout ".devcontainer/Dockerfile" to understand
the dependencies. I.e. VSCode will just ask you to open in container and within 5 minutes you are good to go.

Please note that in order to be able to "find" the Python modules you will have to export "PYTHONPATH" to include the main smartpy folder _and_ this very folder.

```
export PYTHONPATH=/home/node/smartpy-cli/:$(pwd)
```

The command above expects you to be on the root of this project and smartpy-cli to be installed in /home/node/smartpy-cli/. Also while you are at it, might aswell 
export the smartpy PATH.

```
export PATH=$PATH:/home/node/smartpy-cli/
```

## Testing

The tests are easiest to run using 

```
cd tracker
SmartPy.sh test vault.py out --html
SmartPy.sh test tracker_engine.py out --html
SmartPy.sh test staking_pool.py out --html
SmartPy.sh test savings_pool.py out --html
SmartPy.sh test options_listing.py out --html
SmartPy.sh test governance_token.py out --html
```

## Deployment

### Platform

Once you are happy with the local test you can deploy to the network (this will take +-20 minutes)

```
cd tracker
SmartPy.sh compile compiler.py out
python3 deployment.py 
```

### Multisig Deployment

The multisig is deployed using this:

```
tezos-client import secret key admin unencrypted:edsk...
tezos-client import public key ubinetic unencrypted:edpk...
tezos-client --endpoint https://florencenet.smartpy.io deploy multisig msig transferring 1 from admin with threshold 1 on public keys ubinetic --burn-cap 1
```

## Documentation

The entrypoints are documented, you can generate the sphinx doc by doing a 

```
cd docs
sphinx-build -b html ./ doc_out
```



