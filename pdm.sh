#!/bin/bash

# Check if the file exists and the variable does not (or it is empty)
SECRET_FILE=/run/secrets/secrets.env
if [ -f ${SECRET_FILE} ]; then
    echo "STATUS: Configuring Artifactory credentials"
    # shellcheck disable=SC2046
    eval export $(cat ${SECRET_FILE} | tr -d '\r')
else
    echo "WARNING: credentials file not found. Package manager may fail"
fi

if [ -z "${ARTIFACTORY_PYPI_USER}" ] || [ -z "${ARTIFACTORY_PYPI_PASS}" ]; then
    echo "WARNING: ARTIFACTORY_PYPI_USER or ARTIFACTORY_PYPI_PASS not set"
    echo "WARNING: your package manager will not find your private Python packages"
else
    echo "STATUS: Artifactory credentials for private packages are configured"
    export UV_INDEX_ARTIFACTORY_USERNAME=${ARTIFACTORY_PYPI_USER}
    export UV_INDEX_ARTIFACTORY_PASSWORD=${ARTIFACTORY_PYPI_PASS}
    export UV_INDEX_INNOVATION_USERNAME=${ARTIFACTORY_PYPI_USER}
    export UV_INDEX_INNOVATION_PASSWORD=${ARTIFACTORY_PYPI_PASS}
    export UV_INDEX_TECHNOLOGY_USERNAME=${ARTIFACTORY_PYPI_USER}
    export UV_INDEX_TECHNOLOGY_PASSWORD=${ARTIFACTORY_PYPI_PASS}
fi

if [ "$1" == "sync" ]; then
    # Check if pdm.lock exists and is not empty before failing
    if [ -s uv.lock ]; then
        echo "INFO: uv.lock found. Using UV as package manager"
        uv sync --frozen "${@:2}"
    elif [ -s pdm.lock ]; then
        echo "INFO: pdm.lock found. Using PDM as package manager"
        pdm sync "${@:2}"
    else
        echo "WARNING: no pdm.lock or uv.lock contents. Skipping sync"
    fi
elif [ "$1" == "publish" ]; then
    [ -s uv.lock ] && PACKAGE_MANAGER=uv || PACKAGE_MANAGER=pdm
    # Add username and password to the command line arguments
    ${PACKAGE_MANAGER} publish "${@:2}" \
        --username "${ARTIFACTORY_PYPI_USER}" \
        --password "${ARTIFACTORY_PYPI_PASS}"
else
    pdm "$@"
fi
