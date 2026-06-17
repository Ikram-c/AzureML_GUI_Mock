# cl_be/azure_ml_handler.py
import os
import shutil
import tempfile

# The dependency status is now imported from the central setup script
from app_setup import DEPENDENCY_STATUS

# Conditionally import Azure SDK modules
if DEPENDENCY_STATUS["azure_sdk"]:
    from azure.ai.ml import MLClient
    from azure.ai.ml.entities import CommandJob, Environment
    from azure.mgmt.resource import ResourceManagementClient
    from azure.mgmt.subscription import SubscriptionClient
    from azure.identity import DefaultAzureCredential


class AzureMLHandler:
    """
    Handles all backend logic for interacting with Azure Machine Learning services.
    """

    def __init__(self):
        self.ml_client = None
        self._resource_client = None
        self._subscription_client = None

    def _get_resource_client(self, credential: 'DefaultAzureCredential', subscription_id: str = None):
        """Initializes and returns a resource management client."""
        if not DEPENDENCY_STATUS["azure_sdk"]:
            raise ImportError("Azure SDK is not available")

        if self._resource_client is None or (
                subscription_id and getattr(self._resource_client, 'subscription_id', None) != subscription_id):
            sub_id = subscription_id or "default-subscription"
            self._resource_client = ResourceManagementClient(credential, sub_id)
        return self._resource_client

    def _get_subscription_client(self, credential: 'DefaultAzureCredential'):
        """Initializes and returns a subscription client."""
        if not DEPENDENCY_STATUS["azure_sdk"]:
            raise ImportError("Azure SDK is not available")

        if self._subscription_client is None:
            self._subscription_client = SubscriptionClient(credential)
        return self._subscription_client

    def get_subscriptions(self, credential: 'DefaultAzureCredential'):
        """Lists all subscriptions available to the user."""
        if not DEPENDENCY_STATUS["azure_sdk"]:
            raise ImportError("Azure SDK is not available")
        sub_client = self._get_subscription_client(credential)
        subscriptions = list(sub_client.subscriptions.list())
        return [{'name': sub.display_name, 'id': sub.subscription_id} for sub in subscriptions]

    def get_resource_groups(self, credential: 'DefaultAzureCredential', subscription_id: str):
        """Lists all resource groups within a specific subscription."""
        if not DEPENDENCY_STATUS["azure_sdk"]:
            raise ImportError("Azure SDK is not available")
        rg_client = ResourceManagementClient(credential, subscription_id).resource_groups
        return sorted([rg.name for rg in rg_client.list()])

    def get_workspaces(self, credential: 'DefaultAzureCredential', subscription_id: str, resource_group: str):
        """Lists all Azure ML workspaces within a resource group."""
        if not DEPENDENCY_STATUS["azure_sdk"]:
            raise ImportError("Azure SDK is not available")
        res_client = ResourceManagementClient(credential, subscription_id).resources
        filter_str = f"resourceType eq 'Microsoft.MachineLearningServices/workspaces' and resourceGroup eq '{resource_group}'"
        workspaces = res_client.list(filter=filter_str)
        return [{'name': ws.name, 'id': ws.id} for ws in workspaces]

    def connect_to_workspace(self, credential: 'DefaultAzureCredential', subscription_id: str, resource_group: str,
                             workspace_name: str):
        """Connects to a specific Azure ML workspace and initializes the MLClient."""
        if not DEPENDENCY_STATUS["azure_sdk"]:
            raise ImportError("Azure SDK is not available")
        try:
            self.ml_client = MLClient(
                credential=credential,
                subscription_id=subscription_id,
                resource_group_name=resource_group,
                workspace_name=workspace_name
            )
            workspace_details = self.ml_client.workspaces.get(workspace_name)
            return f"Connected to workspace: {workspace_details.display_name}"
        except Exception as e:
            self.ml_client = None
            raise Exception(f"Failed to connect to workspace: {str(e)}")

    def list_computes(self):
        """Lists all compute targets in the connected workspace."""
        if not self.ml_client:
            raise ConnectionError("Not connected to an Azure ML workspace.")
        return list(self.ml_client.compute.list())

    def list_models(self):
        """Lists all registered models in the connected workspace."""
        if not self.ml_client:
            raise ConnectionError("Not connected to an Azure ML workspace.")
        return list(self.ml_client.models.list())

    def submit_job(self, job_name: str, code_path: str, compute_target: str, command: str, environment_details: dict):
        """Configures and submits a command job to the Azure ML workspace."""
        if not self.ml_client:
            raise ConnectionError("Not connected to an Azure ML workspace.")
        if not DEPENDENCY_STATUS["azure_sdk"]:
            raise ImportError("Azure SDK is not available")

        job_environment = "AzureML-sklearn-1.0-ubuntu20.04-py38-cpu@latest"  # Default
        if 'conda_file' in environment_details:
            conda_file_path = environment_details['conda_file']
            if not os.path.exists(conda_file_path):
                raise FileNotFoundError(f"Conda file not found: {conda_file_path}")
            job_environment = Environment(
                name=f"{job_name}-env",
                conda_file=conda_file_path,
                image="mcr.microsoft.com/azureml/openmpi3.1.2-ubuntu18.04"
            )
        elif 'docker_image' in environment_details:
            job_environment = Environment(name=f"{job_name}-env", image=environment_details['docker_image'])

        command_job = CommandJob(
            display_name=job_name,
            code=code_path,
            command=command,
            environment=job_environment,
            compute=compute_target,
            experiment_name="local-ui-submissions"
        )
        return self.ml_client.jobs.create_or_update(command_job)

    def list_jobs(self, filter_by_user: bool = True):
        """Lists recent jobs in the connected workspace."""
        if not self.ml_client:
            raise ConnectionError("Not connected to an Azure ML workspace.")
        return list(self.ml_client.jobs.list())

    def get_job_details(self, job_name: str):
        """Retrieves the full details for a specific job."""
        if not self.ml_client:
            raise ConnectionError("Not connected to an Azure ML workspace.")
        return self.ml_client.jobs.get(job_name)

    def get_job_logs(self, job_name: str) -> str:
        """Downloads the logs for a specific job and returns them as a string."""
        if not self.ml_client:
            raise ConnectionError("Not connected to an Azure ML workspace.")
        log_dir = tempfile.mkdtemp()
        try:
            self.ml_client.jobs.download(name=job_name, download_path=log_dir, output_name=None)
            log_file_path = os.path.join(log_dir, 'user_logs/std_log.txt')
            if os.path.exists(log_file_path):
                with open(log_file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            return "No std_log.txt found in job logs."
        finally:
            shutil.rmtree(log_dir, ignore_errors=True)

    def download_job_outputs(self, job_name: str):
        """Downloads all outputs for a specific job to a temporary directory."""
        if not self.ml_client:
            raise ConnectionError("Not connected to an Azure ML workspace.")

        temp_dir = os.path.join(tempfile.gettempdir(), f"aml_job_{job_name}")
        os.makedirs(temp_dir, exist_ok=True)

        self.ml_client.jobs.download(name=job_name, download_path=temp_dir, all=True)
        output_files = []
        for root, _, files in os.walk(temp_dir):
            for file in files:
                full_path = os.path.join(root, file)
                relative_path = os.path.relpath(full_path, temp_dir)
                output_files.append(relative_path.replace("\\", "/"))
        return output_files, temp_dir
