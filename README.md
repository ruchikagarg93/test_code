# pr-flyers-metrics-worker

[![Actions status](https://github.com/niq-enterprise/aimlops-pr-flyers-metrics-worker/actions/workflows/build.yaml/badge.svg)](https://github.com/niq-enterprise/aimlops-pr-flyers-metrics-worker/actions)
[![pdm-managed](https://img.shields.io/badge/pdm-managed-blueviolet)](https://pdm-project.org)

This is a project generated for promoflyers metrics worker.

## Requirements

pr-flyers-metrics-worker requires Python >=3.9,\<3.11.


## Usage

Get help about the allowed subcommands of the CLI using:

```bash
pr_flyers_metrics_worker --help
```

## Development in a container

Whether you want to contribute/develop or just use pr-flyers-metrics-worker for testing, we encourage you to use the same python environment where the package has been tested. Docker containers allow us to build reproducible environments that can be used as a [development container](#development-containers) or as a [SSH container](#ssh-containers).

```{warning}
In Windows, we recommend the use of [development containers](#development-containers).
```

pr-flyers-metrics-worker provides a very simple script to bootstrap your development environment using some environment variables that can be copied from the [.env.example](../../../.env.example) file:

| Variable          | Meaning                                       | Path in the container |
| ----------------- | --------------------------------------------- | --------------------- |
| COMPOSE_CACHE_DIR | directory to saved cached data (like HF_HOME) | /cache                |
| COMPOSE_DATA_DIR  | directory with dataset splits and experiments | /data                 |
| COMPOSE_HOME_DIR  | directory with your user $HOME folder         | /home                 |

You should copy that file into `.env` and fill the variables with the correct values, suited to your needs. This file is used by the `Makefile` to set the environment variables for the docker containers.

### Container image

The package comes with a multi-stage Dockerfile with the following stages:

| Stage         | Goal                                                                                  |
| ------------- | ------------------------------------------------------------------------------------- |
| base          | Python and tools, including [PDM](https://pdm-project.org/) and a virtual environment |
| prod          | The source code is copied and the package is installed in editable mode               |
| testing       | Used only at CICD to run the test suite                                               |
| devel         | Base image for dev and ssh containers. Includes the local user in the container       |
| devel-ssh     | SSH container image with an SSH server                                                |
| devel-linux   | DevContainers in Linux                                                                |
| devel-windows | DevContainers in Windows                                                              |

```bash
TARGET=<stage-name> pdm run docker-build
```

### SSH containers

A new SSH-accessible container can be started usually with:

```bash
pdm run sshcontainer
```

Then connect to the container port `$COMPOSE_SSH_PORT` using the [Visual Studio Code SSH extension](https://code.visualstudio.com/docs/remote/ssh-tutorial)

### Development containers

1. Install the [Dev Containers extension](https://code.visualstudio.com/docs/devcontainers/tutorial) in your [Visual Studio Code](https://code.visualstudio.com/).

2. Copy [.devcontainer/devcontainer.example.json](.devcontainer/devcontainer.example.json) into `.devcontainer/devcontainer.json`.

   > **IMPORTANT**: make sure that `remoteUser` matches your username in `.env`

3. Set your default shell interpreter by adding `"terminal.integrated.shell.linux": "bash"` to your `.vscode/settings.json`.

4. Run `Dev Containers: Reopen in Container` in your VSC command palette (Ctrl + Shift + P).

A new window will be open with the repository code on your workspace within the container.

Check more information about devcontainers on the official [specification](https://containers.dev/)

### Activate the virtual environment

Once your container has started, set the path to the Python interpreter for Visual Studio Code in the `python.defaultInterpreterPath` option of your `settings.json` file (see [settings.example.json](.vscode/settings.example.json)) or using `pdm use`.

The environment should be automatically activated in a new integrated terminal too. In other terminals, you should check that your environment is available with `pdm venv list` and activate it with `eval $(pdm venv activate <venv_name>)`.

The package can be installed in that virtual environment in editable mode with:

```bash
pdm install
```

## Contributing

Please, read the guidelines about [how to contribute](CONTRIBUTING.md) to this project.
