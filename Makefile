BUILD_FOLDER := _build
SNAPSHOTS_FOLDER := __SNAPSHOTS__
SMARTPY_CLI_PATH := $(BUILD_FOLDER)/smartpy-cli
PYTHONPATH := $(SMARTPY_CLI_PATH):$(shell pwd)
FLEXTESA_IMAGE=oxheadalpha/flextesa:latest
FLEXTESA_SCRIPT=jakartabox
CONTAINER_NAME=youves-sandbox


ORACLE_COMPILATIONS := $(filter-out %/__init__.py, $(wildcard compilations/oracle/*.py))
ORACLE_TESTS := $(filter-out %/__init__.py, $(wildcard tests/oracle/*.py))
TRACKER_COMPILATIONS := $(filter-out %/__init__.py, $(wildcard compilations/tracker/*.py))
TRACKER_TESTS := $(filter-out %/__init__.py, $(wildcard tests/tracker/*.py))

touch_done=@mkdir -p $(@D) && touch $@;

all: install-dependencies

##
## + Compilations
##
compilations/%: compilations/%.py install-dependencies
	@$(SMARTPY_CLI_PATH)/SmartPy.sh compile $< $(SNAPSHOTS_FOLDER)/compilation/$*

compile-oracle-contracts: $(ORACLE_COMPILATIONS:%.py=%) setup_env
	@echo "Compiled oracle contracts."

compile-tracker-contracts: $(TRACKER_COMPILATIONS:%.py=%) setup_env
	@echo "Compiled tracker contracts."

compile-swap-contracts:
	@compilations/swap/all.sh $(shell pwd)/contracts/swap $(shell pwd)/$(SNAPSHOTS_FOLDER)/compilation/swap
	@echo "Compiled swap contracts."

compile-contracts: compile-oracle-contracts compile-tracker-contracts compile-swap-contracts
##
## - Compilations
##

##
## + Tests
##
tests/%: tests/%.py install-dependencies
	@$(SMARTPY_CLI_PATH)/SmartPy.sh test $< $(SNAPSHOTS_FOLDER)/test/$* --html

test-oracle-contracts: $(ORACLE_TESTS:%.py=%) setup_env
	@echo "Tested oracle contracts."

test-tracker-contracts: $(TRACKER_TESTS:%.py=%) setup_env
	@echo "Tested tracker contracts."

# TODO: Fix test (types are not matching)
test-swap-contracts:
	@tests/swap/all.sh $(shell pwd)/contracts/swap $(shell pwd)/$(SNAPSHOTS_FOLDER)/test/swap
	@echo "Tested swap contracts."

test-contracts: test-oracle-contracts test-tracker-contracts
##
## - Tests
##

##
## + Deployment
##
export CONFIG_PATH ?= configs/long_staking_pool.yaml
deploy: install-dependencies
	@python3 deployment/apply.py $(SNAPSHOTS_FOLDER)/deployment-$(notdir $(basename $(CONFIG_PATH))).yaml
##
## + Deployment
##

fmt-check:
	python3 -m black --check .

fmt-fix:
	python3 -m black .

start-sandbox:
	@docker run -v $(shell pwd):$(shell pwd) --rm --name "$(CONTAINER_NAME)" --detach \
		-p 20000:20000 \
		-e block_time=1 \
		"$(FLEXTESA_IMAGE)" "$(FLEXTESA_SCRIPT)" start

stop-sandbox:
	@docker stop "$(CONTAINER_NAME)"

export PYTHONPATH
setup_env: # Setup environment variables

clean:
	@rm -rf $(BUILD_FOLDER)

##
## + Install Dependencies
##
install-smartpy: $(BUILD_FOLDER)/install-smartpy
$(BUILD_FOLDER)/install-smartpy:
	@rm -rf $(SMARTPY_CLI_PATH)
	@bash -c "bash <(curl -s https://smartpy.io/cli/install.sh) --prefix $(SMARTPY_CLI_PATH) --yes"
	$(touch_done)

install-dependencies: install-smartpy
	@pip install -r requirements.txt --quiet
##
## - Install dependencies
##
