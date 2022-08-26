# See here for image contents: https://github.com/microsoft/vscode-dev-containers/tree/v0.163.1/containers/javascript-node/.devcontainer/base.Dockerfile

# [Choice] Node.js version: 14, 12, 10
ARG VARIANT="14-buster"
FROM mcr.microsoft.com/vscode/devcontainers/javascript-node:0-${VARIANT}

# [Optional] Uncomment this section to install additional OS packages.
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends python3-dev python3-pip python3-setuptools libsodium-dev libsecp256k1-dev 

# [Optional] Uncomment if you want to install an additional version of node using nvm
# ARG EXTRA_NODE_VERSION=10
# RUN su node -c "source /usr/local/share/nvm/nvm.sh && nvm install ${EXTRA_NODE_VERSION}"

# [Optional] Uncomment if you want to install more global node modules
RUN pip3 install sphinx pytezos

RUN su node -c "yes | bash <(curl -s https://smartpy.io/releases/20220802-a20c6dc7989710fe9adb666cb34f6ad5f1c9512f/cli/install.sh)" 