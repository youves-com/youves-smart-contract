#!/usr/bin/env bash

set -euo pipefail

if [ -z "$2" ]; then
    echo "Usage: $0 <contract_folder> <output_folder>"
    exit 1
fi

# Create output folder if it does not exist
mkdir -p "$2"

# Compile contracts
docker run --rm -v "$1":"$1" -w "$1" ligolang/ligo:0.34.0 run test flat_cfmm_test.mligo > "$2/flat_cfmm_test.result"
