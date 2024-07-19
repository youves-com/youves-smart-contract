#!/usr/bin/env bash

set -euo pipefail

if [ -z "$2" ]; then
    echo "Usage: $0 <contract_folder> <output_folder>"
    exit 1
fi

# Create output folder if it does not exist
mkdir -p "$2"

# Compile contracts
docker run --rm -v "$1":"$1" -w "$1" ligolang/ligo:0.47.0 compile contract liquidity_pool.mligo > "$2/liquidity_pool.tz"
docker run --rm -v "$1":"$1" -w "$1" ligolang/ligo:0.47.0 compile contract fa2_flat_cfmm.mligo > "$2/fa2_flat_cfmm.tz"
docker run --rm -v "$1":"$1" -w "$1" ligolang/ligo:0.47.0 compile contract fa12_flat_cfmm.mligo > "$2/fa12_flat_cfmm.tz"
docker run --rm -v "$1":"$1" -w "$1" ligolang/ligo:0.47.0 compile contract multitoken_cfmm_with_rewards.mligo > "$2/multitoken_cfmm_with_rewards.tz"
