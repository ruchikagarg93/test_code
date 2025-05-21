# Deployment in CIS

In CIS 3.0, workers are deployed using GitHub Actions within the same repository. Right now there are two possible target clusters: CIS and NIQ. Depending on the target cluster, either kustomize or helm are used as rendering engines to generate the resource manifests that will be deployed. This detail will remain hidden to the developer.

## Requirements

In order to deploy the worker in CIS, you must complete these steps:

1. Release a new version of this repo in GitHub by running the appropriate workflow. Wait until the workflow is completed to get the image tagged in the container registry.
2. Tune your deployment settings, configuration files and secrets in a new branch called "feature/deployment".
3. Create a PR to merge the "feature/deployment" branch into the main branch.
4. Trigger the "deploy_cis_cluster.yaml" or "deploy_niq_cluster.yaml" workflow in that branch with the previously released version, region and environment.
5. Wait until the workflow is completed and check the output. If there is an error, you can check the logs in the GitHub Actions tab.

The next section will guide you from step 2 to step 4.

## Tune your deployment

In order to deploy this worker, you must follow these steps:

1. Define your configuration files within the `config` directory. This directory should contain two folders:

   - `base`: All the configuration files that are shared by to all the regions and environments.
   - `overlays`: All the configuration files that are specific to an environment should be in a folder under a subdirectory named after the region and then `prod` or `nonprod`. For example, the configuration files for the `us` region and the `prod` environment should be placed under `config/overlays/us/prod`.

   > The configuration files are nested in directories, but in the final deployment, the directory layout will be flattened and all the files will be mounted in the path `/etc/worker/config` within the container. This means that you cannot have two files with the same name in the `base` and `overlays` directories because the one in the `overlays` directory will take precedence. This may be useful to override the configuration files in the `base` directory with the ones in the `overlays` directory.

2. You can inject secret values in a configuration file using simple Python templated files with the extension `.tpl`. The file should contain a [templated string](https://www.geeksforgeeks.org/python-string-format-method/) using the name of the environment variables as placeholders that will hold the secret value at the time of the deployment. For example, to inject the value in the environment variable `CACHE_REDIS_PASSWORD` in the configuration key `executor.cache.redis_client.password`, you should create a file `config/.../my_secret.yaml.tpl` with the following content:

   ```yaml
   executor:
       cache:
           redis_client:
               password: {CACHE_REDIS_PASSWORD}
   ```

   During the deploy workflow, the placeholder will be replaced with the actual values to render a new file at `/etc/worker/secrets/my_secret.yaml` that you can use in the worker command line arguments or read within your code.

   You can add your own secrets (i.e. not managed by CIS) into your GitHub repository. For example, the secret environment variable called `AML_WORKSPACE_CLIENT_SECRET` can be set with the following command:

   ```bash
   gh secret set DPL_AML_WORKSPACE_CLIENT_SECRET -b "my_value"
   ```

   > Only the secrets starting with the prefix `DPL_` will be injected in the configuration files. This will avoid to accidentally inject other secrets from GitHub in the worker.

   This will make the secret available for all the deployment environments. You can choose an specific environment by adding the `--env` flag with the environment name. For example, to set the secret in the `us-nonprod` environment, you can use the following command:

   ```bash
   gh secret set DPL_AML_WORKSPACE_CLIENT_SECRET --env us-nonprod -b "my_value"
   ```

   You can check that your secrets are set correctly by running the following command:

   ```bash
   gh secret list --env us-nonprod
   ```

3. Optionally, when a file requires lot of secrets (not managed by CIS), you can build the secret file and push it to your GitHub repository. The secret name must start again with the prefix `DPL_` like in `DPL_WORKER_SECRET_CONFIG_YAML`. For instance, you can use the GitHub CLI to create the secret in the `us-nonprod` environment with the following command:

   ```bash
   gh secret set DPL_WORKER_SECRET_CONFIG_YAML --env us-nonprod < worker_secret_config.yaml
   ```

   > Pushing the `worker_secret_config.yaml` file as a secret into your GitHub repository will shadow the template `worker_secret_config.yaml.tpl` file in the `config` directory.

   The secret file will be mounted at runtime in `/etc/worker/secrets/worker_secret_config.yaml` path. You may want to have that secret file in all environments:

   ```bash
   gh secret set DPL_WORKER_SECRET_CONFIG_YAML < worker_secret_config.yaml
   ```

   WARNING: this `worker_secret_config.yaml` file is passed by default in the list of configuration files to the worker. If you don't want to use this file, you must remove it from the args in the `base/scaledjob.yaml` file.

4. Environment variables can also be configured for your worker at runtime in different ways:

   - Add them to your `config/base/run.env` file. This file contains the environment variables that are common to all the environments. You can overlay specific environment variables by creating a `run.env` file in the `config/overlays` directory with the same directory layout as the configuration files.

   - Add them to the GitHub repository variables so they will be merged later by the deploy workflow with the environment variables defined in the `.env` files within the `config` directory. Only variables starting with the prefix `DPL_` will be merged. For example, if you want to expose the environment variable `MY_ENV_VAR` to the worker, you should create a new repository variable with the name `DPL_MY_ENV_VAR`. You can use the GitHub CLI to create the variable with the following command:

     ```bash
     gh variable set DPL_MY_ENV_VAR -b "my_value"
     ```

   > The variable SCALEDJOB_QUEUE_NAME is mandatory and it has a special meaning. It defines the name of the queue to receive new requests from your consumer. This value will be set once you bootstrap your repo with copier in `config/base/run.env`.

5. Modify `base/scaledjob.yaml` to add additional command line arguments to your worker like the paths to configuration files. They must be added to the `spec.jobTargetRef.template.spec.containers[0].args` key of the YAML specification of the ScaledJob. For example, since the configuration files are exposed in the path `/etc/worker/config` and the secrets in `/etc/worker/secrets`, the command line arguments could be:

   ```yaml
   args:
     - ...
     - --config=/etc/worker/config/common.yaml
     - --config=/etc/worker/secrets/secret-config.yaml
     - ...
   ```

   > If you worker requires to mount an Azure File Share, you must remove the commented section in the `base/scaledjob.yaml` file for the volume `azure-fileshare` and your overlay `scaledjob-patch.yaml` file must patch the name of the volume. You can find an example in the `config/overlays/us/prod/scaledjob-patch.yaml` file. Please, contact the CIS team to get the required information to mount the Azure File Share.

6. Execute `pdm run deploy` locally to build the final bundle of Kubernetes resources before deploying the worker. This will create a new directory `.deployment` with a file `bundle.yaml` that you can inspect to debug potential issues with the deployment when you ask for support.

7. Finally, you can deploy an existing release of the worker to the cluster by running the deploy workflow in GitHub Actions. You can use the CLI to deploy the worker in `us` region and the `prod` environment with the version `1.0.0` with the following command:

   ```bash
   gh workflow run deploy_cis_cluster.yaml --ref "feature/deployment" -f region=us -f environment=prod -f version=1.0.0
   ```

   This command will trigger the deployment workflow using the latest changes in `feature/deployment`. You can inspect the logs of the workflow in the GitHub GUI or the CLI to see the progress of the deployment.

8. Optionally, you can test the new worker by sending a request to the CIS API. You have a[request example](deployment/create_request.rest) file that you must customize following the API contract agreed with your customer. You also have to install the [REST Client extension in Visual Studio Code](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) in order to run the request.
