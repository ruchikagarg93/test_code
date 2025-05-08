#!/usr/bin/python3
from __future__ import annotations

import contextlib
import getpass
import inspect
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from argparse import REMAINDER, ArgumentParser
from functools import wraps
from pathlib import Path
from typing import Any, Literal

try:
    import yaml
except ImportError:
    print("PyYAML is not installed. Some commands may fail")

DEFAULT_VCS_VERSION = "0.0.1"
DEPLOYMENT_TMP_DIR = Path(".deployment")
DEPLOYMENT_PREFIX = "DPL_"
VARS_JSON_FILE = Path(".tmp") / "vars.json"
SECRETS_JSON_FILE = Path(".tmp") / "secrets.json"
TPL_NIQ_CLUSTER_SUFFIX = "_niq_cluster.yaml"

task_registry = {}


def get_cwd() -> Path:
    """Gets the current working directory."""
    return Path.cwd()


def _load_json(
    json_path: str | Path | None = None,
    data_type: Literal["vars", "secrets"] = "any",
) -> dict[str, str]:
    """Loads a JSON file with a dict for variables or secrets.

    Args:
        json_path: The path to the JSON file with a dict to load.
        data_type: The type of data to load (vars or secrets).
    """
    if json_path is None:
        json_path = {
            "vars": VARS_JSON_FILE,
            "secrets": SECRETS_JSON_FILE,
        }.get(data_type)

    if json_path is None:
        raise ValueError("Please, provide a valid `data_type` or `json_path`")

    json_path = Path(json_path).resolve()
    if json_path.exists():
        print(f"Reading {data_type} from {json_path}")
        return json.loads(json_path.read_text()) or {}

    print(f"File {json_path} not found. Returning an empty dictionary.")
    return {}


@contextlib.contextmanager
def _augment_environ():
    """Augments the environment with GitHub variables and secrets, and config."""
    old_environ = dict(os.environ)
    region = os.environ["DEPLOYMENT_REGION"]
    environment = os.environ["DEPLOYMENT_ENVIRONMENT"]

    # Add the environment from config
    base_path = get_cwd() / "config" / "base"
    overlay_path = get_cwd() / "config" / "overlays" / region / environment
    for path in (base_path, overlay_path):
        for file in path.rglob("*.env"):
            os.environ.update(
                dict(
                    line.strip().split("=", 1)
                    for line in file.read_text().splitlines()
                    if not line.startswith("#")
                )
            )

    # Add all the variables from the GitHub environment
    all_vars = _load_json(data_type="vars")
    all_vars = {
        k.replace(DEPLOYMENT_PREFIX, ""): v
        for k, v in all_vars.items()
        if k.startswith(DEPLOYMENT_PREFIX)
    }
    os.environ.update(all_vars)

    # Add all the secrets from the GitHub environment
    all_secrets = _load_json(data_type="secrets")
    all_secrets = {
        k.replace(DEPLOYMENT_PREFIX, ""): v
        for k, v in all_secrets.items()
        if k.startswith(DEPLOYMENT_PREFIX)
    }
    os.environ.update(all_secrets)

    # Sanitize the names of the environment variables for the deployment
    new_environ = _sanitize_environment(dict(os.environ), region, environment)
    os.environ.clear()
    os.environ.update(new_environ)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(old_environ)


def run_in_gh_environ(func):
    """A decorator to augment the environment with GitHub environment variables."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        with _augment_environ():
            return func(*args, **kwargs)

    return wrapper


def _render_file_contents(file_path: Path, env: dict[str, Any]) -> str:
    """Renders the file contents with the given environment variables."""
    text = file_path.read_text()
    return text.format(**env)


def _copy_files(
    src: Path,
    dest: Path,
    recursive: bool = True,
    excluded_suffices: list[str] | None = None,
):
    """Copies the files from the source to the destination directory."""
    dest.mkdir(parents=True, exist_ok=True)
    excluded_suffices = excluded_suffices or []
    for file_name in src.iterdir():
        if file_name.suffix in excluded_suffices:
            continue
        target = dest / file_name.name
        if file_name.is_dir():
            if recursive:
                target.mkdir(exist_ok=True)
                _copy_files(file_name, target, recursive, excluded_suffices)
        else:
            print(f"Copying {file_name} to {target}")
            if target.exists():
                version = 1
                original = target
                while target.exists():
                    new_name = f"{target.stem}_{version:02d}{target.suffix}"
                    target = target.with_name(new_name)
                    version += 1
                print(f"WARNING: File {original} exists. Renaming to {target}")
            target.write_text(file_name.read_text())


def register_task(func):
    """Registers a task in the task registry."""
    func_name = func.__name__.replace("_", "-")
    task_registry[func_name] = func
    return func


def get_compose_project_name(ssh: bool) -> str:
    """Gets the compose project name based on the current environment variables."""
    user_name = os.environ["COMPOSE_USER_NAME"].lower()
    project_name = get_cwd().name
    platform = os.environ["COMPOSE_PLATFORM"].lower()
    if ssh:
        ssh_port = os.environ["COMPOSE_SSH_PORT"]
        return f"{user_name}-{ssh_port}-{project_name}-{platform}"
    return f"{user_name}-{project_name}-{platform}"


def run_cmd(
    cmd: str | list,
    cwd: Path | None = None,
    capture_output: bool = True,
) -> str | None:
    """Runs a command in the shell and returns the output.

    Args:
        cmd: The command to run.
        cwd: The working directory to run the command in.
        capture_output: Whether to capture the output of the command.

    Returns:
        The output of the command if `capture_output` is `True`. None otherwise.

    Raises:
        subprocess.CalledProcessError: If the command returns a non-zero exit code.
    """
    if isinstance(cmd, list):
        # subprocess.run command requires a string when running through a shell
        cmd = " ".join([f'"{s}"' for s in cmd])
    try:
        print(f"Running command: {cmd}")
        process = subprocess.run(
            args=cmd,
            cwd=cwd or Path(__file__).parent,
            check=True,
            shell=True,
            encoding=sys.stdout.encoding,
            capture_output=capture_output,
        )
    except subprocess.CalledProcessError as error:
        if capture_output:
            print(error.stdout)
            print(error.stderr)
        raise error
    return process.stdout.strip() if capture_output else None


def docker_compose_cli() -> list[str]:
    """Gets the docker-compose CLI command."""
    docker_cmd = shutil.which("docker")
    if docker_cmd:
        # Try to use compose as a plugin
        docker_compose_cmd = [docker_cmd, "compose"]
        try:
            run_cmd(docker_compose_cmd)
            return docker_compose_cmd
        except subprocess.CalledProcessError:
            print("docker compose plugin is not available.")
            print("Falling back to docker-compose command.")

    docker_compose_cmd = shutil.which("docker-compose")
    if not docker_compose_cmd:
        raise RuntimeError("docker-compose is not installed in the host.")

    return [docker_compose_cmd]


def git_cli():
    """Gets the git CLI command."""
    cmd = shutil.which("git")
    if cmd is None:
        raise ValueError("git is not installed.")
    return cmd


def az_cli_cmd(az_cli_version: str = "2.54.0") -> list[str]:
    """Gets the Azure CLI command."""
    az_cli_version = os.environ.get("AZ_CLI_VERSION", az_cli_version)
    user_uid = os.environ["COMPOSE_USER_UID"]
    user_gid = os.environ["COMPOSE_USER_GID"]
    user_name = os.environ["COMPOSE_USER_NAME"]
    home_dir = os.environ["COMPOSE_HOME_DIR"]
    cmd = [
        "docker",
        "run",
        "--rm",
        "--user",
        f"{user_uid}:{user_gid}",
        "-e",
        f"HOME=/home/{user_name}",
        "-v",
        f"{home_dir}/{user_name}:/home/{user_name}",
        f"mcr.microsoft.com/azure-cli:{az_cli_version}",
        "az",
    ]
    return cmd


def get_project_version() -> str:
    """Gets the current version of this project from the VCS.

    Returns:
        The VCS version of the repository or DEFAULT_VCS_VERSION if not found.
    """
    try:
        tags = run_cmd([git_cli(), "rev-list", "--tags", "--max-count=1"])
        version = run_cmd([git_cli(), "describe", "--tags", tags])
        return version or DEFAULT_VCS_VERSION
    except subprocess.CalledProcessError:
        print(
            f"Could not get the project version from git. Default to {DEFAULT_VCS_VERSION}"
        )
        return DEFAULT_VCS_VERSION


def get_compose_platform(ssh: bool = False) -> str:
    """Gets the compose platform based on the current environment variables."""
    return "ssh" if ssh else platform.system().lower()


def get_uid() -> int:
    """Gets the current user ID, returning always 1000 in Windows."""
    return os.getuid() if get_compose_platform() != "windows" else 1000


def setup_docker_env(extra_env: dict | None = None):
    """Prepares the current environment variables for docker."""
    # Add the environment variables in the extra_env dictionary
    os.environ.update(extra_env or {})
    # Set the CI environment variable used by GitHub Actions
    os.environ.setdefault("CI", "false")
    # Use docker buildkit by default
    os.environ.setdefault("DOCKER_BUILDKIT", "1")
    os.environ.setdefault("COMPOSE_DOCKER_CLI_BUILD", "1")
    # In Windows, support forward slashes in paths
    os.environ.setdefault("COMPOSE_CONVERT_WINDOWS_PATHS", "1")
    # Set the current user
    os.environ.setdefault("COMPOSE_USER_NAME", getpass.getuser())
    os.environ.setdefault("COMPOSE_USER_UID", str(get_uid()))
    os.environ.setdefault("COMPOSE_USER_GID", "1006")
    os.environ.setdefault("COMPOSE_GROUP_NAME", "ainn")
    # Set the shell
    os.environ.setdefault("COMPOSE_USER_SHELL", os.environ.get("SHELL", "/bin/bash"))
    # Write credentials to pass as build arguments
    contents = (
        f"ARTIFACTORY_PYPI_USER={os.getenv('ARTIFACTORY_PYPI_USER')}\n"
        f"ARTIFACTORY_PYPI_PASS={os.getenv('ARTIFACTORY_PYPI_PASS')}"
    )
    Path(".secrets.env").write_bytes(contents.encode())

    # Set the docker runtime
    os.environ.setdefault("COMPOSE_RUNTIME", "runc")

    # Set the project version (support empty values from .env file)
    if not os.environ.get("PROJECT_VERSION"):
        os.environ["PROJECT_VERSION"] = get_project_version()

    # Set docker image details
    tag = os.environ.setdefault("DOCKER_TAG", os.environ["PROJECT_VERSION"])
    print(f"Using current image container tag: {tag}")

    # Set the home directory
    home_dir = Path.home().parent.resolve()
    os.environ.setdefault("COMPOSE_HOME_DIR", home_dir.as_posix())
    # Set the cache and data directories
    os.environ.setdefault("COMPOSE_CACHE_DIR", "/tmp")  # noqa: S108
    os.environ.setdefault("COMPOSE_DATA_DIR", "/data")
    # Set the current directory as the code directory
    os.environ.setdefault(
        "COMPOSE_CODE_DIR", Path(__file__).parent.resolve().as_posix()
    )
    # Set artifactory user
    os.environ.setdefault("ARTIFACTORY_PYPI_USER", getpass.getuser())

    # Set the platform (container type)
    os.environ.setdefault("COMPOSE_PLATFORM", "linux")
    # Check that the environment variables are set correctly
    if os.environ["COMPOSE_PLATFORM"] == "ssh" and "COMPOSE_SSH_PORT" not in os.environ:
        raise ValueError("COMPOSE_SSH_PORT environment variable is not set.")


def get_container_image_uri() -> str:
    """Gets the container image URI for the current project."""
    return (
        os.environ["DOCKER_REGISTRY"]
        + "/"
        + os.environ["PROJECT_NAME"]
        + ":"
        + os.environ["DOCKER_TAG"]
    )


@register_task
def azure_login():
    """Logs in to Azure using az CLI."""
    setup_docker_env()
    try:
        run_cmd([*az_cli_cmd(), "ad", "signed-in-user", "show"], capture_output=False)
    except subprocess.CalledProcessError:
        run_cmd([*az_cli_cmd(), "login", "--use-device-code"], capture_output=False)
    print("Azure login successful.")


@register_task
def docker_login():
    """Logs in to the docker registry."""
    azure_login()
    az_token = run_cmd(
        [
            *az_cli_cmd(),
            "acr",
            "login",
            "--name",
            os.environ["DOCKER_REGISTRY"],
            "--expose-token",
            "--output",
            "tsv",
            "--query",
            "accessToken",
        ],
    )
    cmd = [
        "docker",
        "login",
        os.environ["DOCKER_REGISTRY"],
        "--username",
        "00000000-0000-0000-0000-000000000000",
        "--password-stdin",
    ]
    proc = subprocess.Popen(  # noqa: S603
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    output, stderr = proc.communicate(input=az_token.encode())
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(
            cmd=cmd,
            returncode=proc.returncode,
            output=output,
            stderr=stderr,
        )
    print("Docker login successful.")


@register_task
def docker_cmd(action: str):
    """Runs an specific action using compose CLI."""
    setup_docker_env()
    if action in ("login", "push"):
        docker_login()
    if action in ("push"):
        docker_cmd("build")
    run_cmd(
        cmd=[*docker_compose_cli(), action, os.environ.get("TARGET", "prod")],
        capture_output=False,
    )


@register_task
def docker_run(cmd: str = "bash"):
    """Runs a container with the image of this project."""
    docker_cmd("build")
    run_cmd(
        cmd=["docker", "run", "--rm", "-it", get_container_image_uri(), cmd],
        capture_output=False,
    )


def manage_dev_container(action: str, ssh: bool = False):
    """Manages the lifecycle of dev and ssh containers."""
    # Always setup the environment before running any command
    setup_docker_env(extra_env={"COMPOSE_PLATFORM": get_compose_platform(ssh)})
    action = os.environ.setdefault("COMPOSE_ACTION", action)
    with tempfile.NamedTemporaryFile(suffix=".yaml") as tmp_file:
        dev_path = get_cwd() / ".devcontainer" / "docker-compose.yaml"
        if not ssh and os.getenv("MOUNT_HOME_DIR", "0") == "1":
            # Inject the volumes to mount the home directory
            dev_yaml = "\n".join(
                [
                    dev_path.read_text(),
                    "    volumes:",
                    '    - "${COMPOSE_HOME_DIR}/${COMPOSE_USER_NAME}:/home/${COMPOSE_USER_NAME}"',
                ]
            )
            dev_path = Path(tmp_file.name)
            dev_path.write_text(dev_yaml)

        command = [
            *docker_compose_cli(),
            "-f",
            "docker-compose.yaml",
            "-f",
            "docker-compose.ssh.yaml" if ssh else str(dev_path),
            "-p",
            get_compose_project_name(ssh),
            *action.split(),
        ]
        if action != "down":
            command.append("devel")
        run_cmd(command, capture_output=False)


def show_pdm_bootstrap_help():
    """Shows the help message for the pdm bootstrap command."""
    caller = inspect.stack()[1].function
    print("🚨 You can add more Python dependencies and pin them with:")
    print("   pdm lock --dev --group :all")
    print(f"🛠  Then, exec again `pdm run {caller}` to get your virtualenv updated")


@register_task
def devcontainer(action: str = "up -d --build"):
    """Manages a devcontainer to attach to using Visual Studio Code."""
    manage_dev_container(action, ssh=False)
    print("🏗️ Run: Ctrl + Shift + P: 'Dev Containers: Attach to Running Container'")
    print("🐚 Open the folder with your project in /workspace and start coding")
    print("🏗️ Run: Ctrl + Shift + P: 'Show recommended extensions' and install them")
    show_pdm_bootstrap_help()


@register_task
def sshcontainer(action: str = "up -d --build"):
    """Manages the sshcontainer."""
    manage_dev_container(action, ssh=True)
    ssh_port = os.environ["COMPOSE_SSH_PORT"]
    print(f"🏗️ Connect your your Visual Studio Code to the port {ssh_port}.")
    print("🚨 Make sure your public SSH key is authorized in the host.")
    show_pdm_bootstrap_help()


@register_task
def copy(src: str, dest: str):
    """Copies files from the source to the destination without overwriting."""
    src = Path(src).resolve(strict=True)
    dest = Path(dest).resolve(strict=False)
    if dest.exists():
        print(f"Destination {dest} already exists. Skipping.")
    else:
        print(f"Copying {src} to {dest}")
        shutil.copyfile(src, dest)


def copy_configuration(deployment_path: Path, region: str, environment: str):
    """Copies the config files in the base and overlay directories."""
    config_dir = get_cwd() / "config" / "base"
    base_dir = deployment_path / "base" / "config"
    _copy_files(config_dir, base_dir)

    config_dir = get_cwd() / "config" / "overlays" / region / environment
    overlay_dir = deployment_path / "overlays" / region / environment / "config"
    _copy_files(config_dir, overlay_dir)


def write_environment_variables(deployment_path: Path) -> Path:
    """Writes the environment variables to a single merged run.env file."""

    def _update_dot_env(env: dict, env_path: Path) -> dict:
        print(f"Reading environment variables from {env_path}")
        if env_path.exists():
            lines = env_path.read_text().split("\n")
            for line in lines:
                if line.startswith("#") or not line.strip():
                    continue
                key, value = line.strip().split("=", 1)
                env[key] = value
        return env

    dot_env = {}
    config_dir = deployment_path / "config"
    for env_file in config_dir.rglob("run*.env"):
        dot_env = _update_dot_env(dot_env, env_file)

    # Update with the variables in the GitHub environment
    all_vars = _load_json(data_type="vars")
    dpl_vars = {
        k.replace(DEPLOYMENT_PREFIX, ""): v
        for k, v in all_vars.items()
        if k.startswith(DEPLOYMENT_PREFIX)
    }
    dot_env.update(dpl_vars)

    # Dump the environment variables to the run.env file
    base_env_path = deployment_path / "config" / "run.env"
    base_env_path.parent.mkdir(parents=True, exist_ok=True)
    base_env_path.write_text("\n".join([f"{k}={v}" for k, v in dot_env.items()]))
    print(f"Written {len(dot_env)} environment variables in {base_env_path}")
    return base_env_path


def _sanitize_environment(env: dict[str, str], region: str, environment: str) -> dict:
    """Sanitizes keys starting with the prefix for the environment.

    These keys will usually come from a keyvault where overlays are not supported.
    """
    prefix = f"{region}_{environment}_".upper()
    for key in list(env.keys()):
        if key.startswith(prefix):
            env[key.replace(prefix, "")] = env.pop(key)
    return env


def write_secrets_for_environment(deployment_path: Path) -> Path:
    """Renders the templates that use secrets and add secrets from GitHub.

    All the files in the config directory with the .tpl extension are rendered
    and written to the secrets directory. The secrets ending with _YAML in GitHub
    are written as files in the secrets directory.

    Args:
        deployment_path: The path where the current deployment files are located.
            Be sure to not include here tpl files that are not required.
    """
    # Render all files ending with .yaml.tpl as kubernetes secrets
    secret_dir = deployment_path / "secrets"
    for path in deployment_path.rglob("*.yaml.tpl"):
        if path.name.startswith("_"):
            continue
        if (
            path.stem.endswith(TPL_NIQ_CLUSTER_SUFFIX)
            and os.environ["DEPLOYMENT_CLUSTER"] != "NIQ"
        ):
            print(f"Skipping template for NIQ cluster in {path}")
            continue

        # Render the template with the environment variables
        secret_path = secret_dir / path.name.replace(".tpl", "")
        secret_path.parent.mkdir(exist_ok=True)
        secret_path.write_text(_render_file_contents(path, os.environ))
        print(f"Secret config template {path} rendered to {secret_path}")

    # Write the secrets ending with YAML as files
    all_secrets = _load_json(data_type="secrets")
    all_secrets = {
        k.replace(DEPLOYMENT_PREFIX, "").replace("_YAML", ".yaml").lower(): v
        for k, v in all_secrets.items()
        if k.startswith(DEPLOYMENT_PREFIX) and k.endswith("_YAML")
    }
    for key, value in all_secrets.items():
        secret_path = secret_dir / key
        secret_path.parent.mkdir(parents=True, exist_ok=True)
        secret_path.write_text(value)
        print(f"Secret file {key} written to {secret_path}")

    return secret_dir


@register_task
@run_in_gh_environ
def setup_kustomize(
    region: str,
    environment: str,
    deployment_path: str = DEPLOYMENT_TMP_DIR,
):
    """Processes the configuration and secrets required for kustomize."""
    print(f"Setting up kustomization in {deployment_path}")
    _copy_files(get_cwd() / "deployment", deployment_path)

    # Copy the required config files for this region and environment
    copy_configuration(deployment_path, region, environment)

    # Write environment variables and secrets in the deployment directory
    write_environment_variables(deployment_path)
    write_secrets_for_environment(deployment_path)


def setup_helm(
    region: str,
    environment: str,
    deployment_path: str | Path = DEPLOYMENT_TMP_DIR,
):
    """Processes the config and secrets for rendering the resources with Helm."""
    print("Copying the chart to the deployment directory")
    _copy_files(get_cwd() / "deployment" / "aks" / "chart", deployment_path)

    def _copy_files_to_sink(config_dir: Path, deployment_dir: Path):
        """Copies all the files in config_dir to deployment_dir/config."""
        config_dir_dst = deployment_dir / "config"
        print(f"Copying config files from {config_dir} to {config_dir_dst}")
        _copy_files(config_dir, config_dir_dst, recursive=False)

    config_dirs = [
        get_cwd() / "config" / "base",
        get_cwd() / "config" / "overlays" / region / environment,
    ]
    for config_dir in config_dirs:
        _copy_files_to_sink(config_dir, deployment_path)
        for sub_dir in config_dir.rglob("*"):
            if sub_dir.is_dir():
                _copy_files_to_sink(sub_dir, deployment_path)

    # Add GitHub variables to the ones un run.env
    write_environment_variables(deployment_path)

    # Fetch and prepare the secret files if they do not exist
    write_secrets_for_environment(deployment_path)


def _patch_kustomize_image_name(
    kustomization_path: Path,
    image_name: str,
    image_registry: str,
    image_repository: str,
    image_tag: str,
):
    """Patches the image name in the kustomization file."""
    kmz_path = kustomization_path / "kustomization.yaml"
    kustomization: dict = yaml.safe_load(kmz_path.read_text())
    kustomization.setdefault("images", []).append(
        {
            "name": image_name,
            "newName": f"{image_registry}/{image_repository}",
            "newTag": image_tag,
        }
    )
    kmz_path.write_text(yaml.dump(kustomization))


def _get_values_filename(region: str, environment: str) -> str:
    """Returns the filename to the helm values for the region and environment."""
    _env = "dev" if environment == "nonprod" else "prod"
    return f"{region}{_env}.values.yaml"


def _patch_helm_values(
    deployment_path: Path,
    environment: str,
    region: str,
    image_registry: str,
    image_repository: str,
    image_tag: str,
):
    """Patches the image name in the values.yaml file."""
    values_path = deployment_path / _get_values_filename(region, environment)
    values: dict = yaml.safe_load(values_path.read_text())
    values.setdefault("scaledjob", {})["image"] = {
        "registry": image_registry,
        "repository": image_repository,
        "tag": image_tag,
    }
    values_path.write_text(yaml.dump(values))


def _add_generated_files_to_kustomization(
    name: str,
    kustomization_path: Path,
    generator: Literal["secrets", "config"],
    behavior: Literal["create", "merge", "replace"] = "create",
):
    """Adds the config map to the kustomization file."""
    data_path = kustomization_path / generator
    paths = [file.relative_to(data_path) for file in data_path.glob("**/*.yaml")]

    # Find duplicated base filenames
    filenames = [p.name for p in paths]
    duplicates = {f for f in filenames if filenames.count(f) > 1}
    if duplicates:
        raise ValueError(f"Duplicate filenames found in {data_path}: {duplicates}")

    # Add generator to the kustomization file
    if generator == "config":
        generator_type = "configMapGenerator"
        generator_dict = {
            "name": name,
            "behavior": behavior,
            "files": [f"{generator}/{file}" for file in paths],
        }
    elif generator == "secrets":
        generator_type = "secretGenerator"
        generator_dict = {
            "name": name,
            "type": "Opaque",
            "behavior": behavior,
            "files": [f"{generator}/{p}" for p in paths],
        }
    else:
        raise ValueError(f"Unknown generator type {generator}")

    kmz_path = kustomization_path / "kustomization.yaml"
    kustomization: dict = yaml.safe_load(kmz_path.read_text())
    kustomization.setdefault(generator_type, []).append(generator_dict)
    kmz_path.write_text(yaml.dump(kustomization))


def render_with_helm(
    region: str,
    environment: str,
    deployment_path: str,
    image_registry: str,
    image_repository: str,
    image_tag: str,
) -> str:
    """Renders the Helm chart with the given configuration."""
    print("Deploying with Helm into the NIQ cluster")
    setup_helm(region, environment, deployment_path)

    _patch_helm_values(
        deployment_path=deployment_path,
        environment=environment,
        region=region,
        image_registry=image_registry,
        image_repository=image_repository,
        image_tag=image_tag,
    )

    # Render the templates with Helm
    bundle = run_cmd(
        [
            shutil.which("helm"),
            "template",
            "worker",
            ".",
            "-f",
            _get_values_filename(region, environment),
            "--set",
            f"scaledjob.image.registry={image_registry}",
            "--set",
            f"scaledjob.image.repository={image_repository}",
            "--set",
            f"scaledjob.image.tag={image_tag}",
            "--debug",
        ],
        cwd=deployment_path,
    )
    return bundle


def render_with_kustomize(
    region: str,
    environment: str,
    deployment_path: str,
    image_registry: str,
    image_repository: str,
    image_tag: str,
) -> str:
    """Renders the resources with kustomize."""
    print("Deploying with Kustomize into CIS cluster")
    setup_kustomize(region, environment, deployment_path)

    base_path = deployment_path / "base"
    overlay_path = deployment_path / "overlays" / region / environment

    _patch_kustomize_image_name(
        kustomization_path=base_path,
        image_name="worker-image",
        image_registry=image_registry,
        image_repository=image_repository,
        image_tag=image_tag,
    )

    print("Updating base configuration files")
    _add_generated_files_to_kustomization(
        name="config-files",
        kustomization_path=base_path,
        generator="config",
    )

    print("Updating overlay configuration files")
    _add_generated_files_to_kustomization(
        name="config-files",
        kustomization_path=overlay_path,
        generator="config",
        behavior="merge",
    )

    print("Updating overlay secret files")
    shutil.move(deployment_path / "secrets", overlay_path / "secrets")
    _add_generated_files_to_kustomization(
        name="config-secrets",
        kustomization_path=overlay_path,
        generator="secrets",
    )

    print(run_cmd([shutil.which("tree"), "-h", base_path, overlay_path]))
    bundle = run_cmd([shutil.which("kustomize"), "build"], cwd=overlay_path)
    return bundle


@register_task
@run_in_gh_environ
def deploy():
    """Deploys the application to the kubernetes cluster."""
    setup_docker_env()

    region = os.environ["DEPLOYMENT_REGION"]
    environment = os.environ["DEPLOYMENT_ENVIRONMENT"]
    cluster = os.getenv("DEPLOYMENT_CLUSTER", "CIS")
    dry_run = os.getenv("DEPLOYMENT_DRY_RUN", "true").lower() == "true"
    image_registry = os.environ["DOCKER_REGISTRY"]
    image_repository = os.environ["PROJECT_NAME"] + "-worker"
    image_tag = os.environ["DOCKER_TAG"]
    print(f"Deploying worker image {image_registry}/{image_repository}:{image_tag}")

    deployment_path = Path(DEPLOYMENT_TMP_DIR).resolve()
    if deployment_path.exists():
        print(f"Removing existing deployment directory: {deployment_path}")
        shutil.rmtree(deployment_path)

    render_kwargs = {
        "region": region,
        "environment": environment,
        "deployment_path": deployment_path,
        "image_registry": image_registry,
        "image_repository": image_repository,
        "image_tag": image_tag,
    }
    if cluster == "NIQ":
        bundle = render_with_helm(**render_kwargs)
    elif cluster == "CIS":
        bundle = render_with_kustomize(**render_kwargs)
    else:
        raise ValueError(f"Unknown DEPLOYMENT_CLUSTER value {cluster}")

    bundle_path = deployment_path / "bundle.yaml"
    bundle_path.write_text(bundle)
    print(f"Resources written to {bundle_path.resolve()}")

    if not dry_run:
        print(f"Deploying to {region}-{environment}")
        run_cmd([shutil.which("kubectl"), "apply", "-f", bundle_path])


def run(task: str, *args, **kwargs):
    """Runs the task with the given name."""
    if task not in task_registry:
        raise ValueError(f"Task {task} not found.")
    task_registry[task](*args, **kwargs)


if __name__ == "__main__":
    parser = ArgumentParser(description="Runner for the project.")
    parser.add_argument("task", help="The task to run.")
    parser.add_argument("rest", nargs=REMAINDER)
    args = parser.parse_args()

    # Extract the additional keyword arguments from the CLI
    kwargs = {}
    if args.rest:
        args.rest = [arg.replace("--", "") for arg in args.rest]
        kwargs = dict(zip(args.rest[::2], args.rest[1::2]))
    run(args.task.lower(), **kwargs)
