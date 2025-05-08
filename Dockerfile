ARG DOCKER_REGISTRY=python
ARG PYTHON_VERSION=3.9
ARG DOCKER_IMAGE_VARIANT=slim-bookworm
FROM ${DOCKER_REGISTRY}:${PYTHON_VERSION}-${DOCKER_IMAGE_VARIANT} AS base
ARG WORKSPACE_DIR=/workspace
WORKDIR ${WORKSPACE_DIR}/aimlops-pr-flyers-metrics-worker

# Load the .bashrc file even on non-interactive shells
ENV BASH_ENV=~/.bashrc

# Change the default umask to grant write permissions to the group
RUN sed -ri 's/^#?UMASK\s+.*/UMASK 003/' /etc/login.defs

# Install the essential packages
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        git \
        openssh-client && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Install ZScaler CA root certificate
RUN --mount=type=secret,id=secrets.env \
    eval export $(cat /run/secrets/secrets.env | tr -d '\r') && \
    mkdir -p /usr/local/share/ca-certificates && \
    curl -sSL https://${ARTIFACTORY_PYPI_USER}:${ARTIFACTORY_PYPI_PASS}@artifactory.adlm.nielseniq.com/artifactory/api/pypi/innovation-pypi-prod-ml-local/ca-certs/zscaler-root-ca.pem -o /usr/local/share/ca-certificates/zscaler-root-ca.pem && \
    update-ca-certificates

# Install UV
ARG UV_VERSION=0.5.25
ENV UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=never
ENV UV_UNMANAGED_INSTALL="/usr/local/bin"
RUN curl -LsSf https://astral.sh/uv/${UV_VERSION}/install.sh 2>&1 | bash

# Install PDM
ARG PDM_VERSION=2.22.3
RUN pip install --no-cache-dir pdm==${PDM_VERSION}

# Creating the virtual environment
# https://code.visualstudio.com/docs/python/environments#_where-the-extension-looks-for-environments
ENV VIRTUAL_ENV=/opt/virtualenv/pr-flyers-metrics-worker
ENV UV_PROJECT_ENVIRONMENT=${VIRTUAL_ENV}
RUN mkdir -p ${VIRTUAL_ENV} && chmod a+w ${VIRTUAL_ENV}
RUN pdm config check_update false && \
    pdm config python.use_venv true && \
    pdm config install.cache false
RUN uv venv -p /usr/local/bin/python ${VIRTUAL_ENV} && \
    pdm use -f ${VIRTUAL_ENV}

# Activate the virtual environment on the next RUN commands
RUN pdm completion bash > /etc/bash_completion.d/pdm.bash-completion && \
    pdm completion zsh > /usr/share/zsh/vendor-completions/_pdm && \
    echo "source ${VIRTUAL_ENV}/bin/activate" >> ~/.bashrc


# Install dependencies
COPY pyproject.toml *.lock README.md LICENSE ./
COPY pdm.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/pdm.sh
RUN --mount=type=secret,id=secrets.env \
    --mount=type=cache,target=/root/.cache \
    [ -s "uv.lock" ] && \
    pdm.sh sync --no-dev --no-install-project || pdm.sh sync --prod --no-self

# Stage with layers required in production
FROM base AS prod

# Copy the source code and local configuration
COPY src src
COPY config config
# This is the version of the package
ARG PDM_BUILD_SCM_VERSION
# This is the CIS application to install (worker, pipeline, publisher, etc)
# It is set on the main docker-compose.yaml of this repository
ARG CIS_APP
# Install extra dependency group for CIS_APP
RUN --mount=type=secret,id=secrets.env \
    --mount=type=cache,target=/root/.cache \
    [ -s "uv.lock" ] && \
    pdm.sh sync --no-dev --extra ${CIS_APP} || pdm.sh sync --prod --group ${CIS_APP}

# Set the entrypoint as a login shell to load the ~/.profile
# The entrypoint script allows to use string without quotes as commands
RUN echo "#!/bin/bash\nexec bash -l -c \"\$*\"" > /etc/docker-entrypoint.sh
RUN chmod +x /etc/docker-entrypoint.sh
ENTRYPOINT ["/etc/docker-entrypoint.sh"]

# Add a non-root user to the container
RUN addgroup --gid 7655 dmleuser && \
    adduser --disabled-password --gecos '' --uid 7655 --gid 7655 dmleuser && \
    echo "source ${VIRTUAL_ENV}/bin/activate" > /home/dmleuser/.bashrc && \
    chown -R dmleuser:dmleuser .
USER dmleuser
CMD ["pr_flyers_metrics_worker"]

# Stage with layers to run the tests
FROM prod AS testing
ARG CI=false
COPY tests tests
USER root
# Run tests during CI only
RUN --mount=type=secret,id=secrets.env \
    --mount=type=cache,target=/root/.cache \
    if [ "${CI}" = "true" ]; then \
        [ -s "uv.lock" ] && \
        pdm.sh sync --all-extras --no-dev --group test || pdm.sh sync -dG test -G :all && \
        pdm.sh run tests tests/${CIS_APP}; \
    fi && \
    rm -rf tests /tmp/*
USER dmleuser

# Development layers
FROM base AS devel
# Additional tooling
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        byobu \
        htop \
        less \
        openssh-server \
        sudo \
        tree \
        vim \
        zsh && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*



# Install GitHub CLI
ENV GH_CLI_VERSION=2.63.2
RUN curl -LJO https://github.com/cli/cli/releases/download/v${GH_CLI_VERSION}/gh_${GH_CLI_VERSION}_linux_amd64.deb && \
    apt install -y ./gh_${GH_CLI_VERSION}_linux_amd64.deb && \
    rm -rf gh_${GH_CLI_VERSION}_linux_amd64.deb && \
    gh completion -s bash > /etc/bash_completion.d/gh.bash-completion && \
    gh completion -s zsh > /usr/share/zsh/vendor-completions/_gh

# Install Helm
ENV HELM_VERSION=3.17.1
RUN curl -LJO https://get.helm.sh/helm-v${HELM_VERSION}-linux-amd64.tar.gz && \
    tar -xzf helm-v${HELM_VERSION}-linux-amd64.tar.gz && \
    mv linux-amd64/helm /usr/local/bin && \
    rm -rf helm-v${HELM_VERSION}-linux-amd64.tar.gz linux-amd64

# Install Kustomize
ENV KUSTOMIZE_VERSION=5.5.0
RUN curl -LJO https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize%2Fv${KUSTOMIZE_VERSION}/kustomize_v${KUSTOMIZE_VERSION}_linux_amd64.tar.gz && \
    tar -xzf kustomize_v${KUSTOMIZE_VERSION}_linux_amd64.tar.gz && \
    mv kustomize /usr/local/bin && \
    rm -rf kustomize_v${KUSTOMIZE_VERSION}_linux_amd64.tar.gz

# Install additional development dependencies
ARG PDM_BUILD_SCM_VERSION
RUN --mount=type=secret,id=secrets.env \
    --mount=type=cache,target=/root/.cache \
    [ -s "uv.lock" ] && \
    pdm.sh sync --all-extras --all-groups || pdm.sh sync -dG :all

# Add local user to the image
ARG USERNAME=ainn
ARG GROUPNAME=ainn-sentrum
ARG USERUID=1001
ARG USERGID=1006
ARG USERSHELL=/bin/bash
RUN groupadd --gid ${USERGID} ${GROUPNAME} && \
    useradd -l -u ${USERUID} -g ${USERGID} -m ${USERNAME} -s ${USERSHELL} && \
    echo "umask 003" | tee -a /etc/profile.d/01-umask.sh

# SSH containers
FROM devel AS devel-ssh
EXPOSE 22
COPY docker-entrypoint.sh /etc/docker-entrypoint.sh
RUN chmod +x /etc/docker-entrypoint.sh
ENTRYPOINT ["/etc/docker-entrypoint.sh"]
CMD ["/usr/sbin/sshd", "-D"]

# DevContainers in Linux
FROM devel AS devel-linux
ARG USERNAME=ainn
USER $USERNAME

# DevContainers in Windows
FROM devel-linux AS devel-windows
ARG USERNAME=ainn
USER root
RUN mkdir -p /etc/sudoers.d && \
    echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$USERNAME && \
    chmod 0440 /etc/sudoers.d/$USERNAME
USER $USERNAME
