#!/bin/bash

mkdir -p /var/run/sshd

# Add environment variables to user session
{ \
    echo "export $(env | grep HF_HOME)"; \
    echo "export $(env | grep PATH)"; \
    echo "export $(env | grep VIRTUAL_ENV)"; \
} > /etc/profile.d/10-container.sh
cat /etc/profile.d/10-container.sh

# Exec the command from the remaining arguments
echo "Running $*"
exec "$@"
