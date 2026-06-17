# cl_be/azure_auth_handler.py
from azure.core.exceptions import ClientAuthenticationError
from azure.identity import DefaultAzureCredential, InteractiveBrowserCredential
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.subscription import SubscriptionClient
from azure.storage.blob import BlobServiceClient

# Centralized application configuration
from config_loader import CONFIG
# Dependency status from the central setup script
from app_setup import DEPENDENCY_STATUS


class AzureAuthHandler:
    """Handles all backend logic for Azure authentication and resource management."""

    def __init__(self):
        self.credential = None
        self.storage_accounts = []
        self.container_name = None
        self.account_name = None
        self.blob_service_client = None

    def check_cached_login(self):
        """Checks for cached credentials and validates them by making a lightweight API call."""
        if not DEPENDENCY_STATUS["azure_sdk"]:
            raise ConnectionError("Azure SDK not installed.")

        try:
            self.credential = DefaultAzureCredential()
            sub_client = SubscriptionClient(self.credential)
            tenants = list(sub_client.tenants.list())
            if not tenants:
                raise ConnectionError("Authenticated, but no accessible tenants found.")
            return f"Signed in to tenant: {tenants[0].tenant_id}"
        except (ClientAuthenticationError, Exception) as e:
            self.credential = None
            raise ConnectionError(f"Authentication failed: {e}")

    def start_interactive_login(self):
        """Starts the interactive browser login flow using the configured client ID."""
        if not DEPENDENCY_STATUS["azure_sdk"]:
            raise ConnectionError("Azure SDK not installed.")

        try:
            client_id = CONFIG['api']['azure']['cli_client_id']
            self.credential = InteractiveBrowserCredential(client_id=client_id)
            self.credential.get_token("https://management.azure.com/.default")
            return self.check_cached_login()
        except Exception as e:
            self.credential = None
            raise ConnectionError(f"Interactive login failed: {e}")

    def connect_with_key(self, account_name, account_key):
        """Connects to a storage account using a key and lists its containers."""
        if not account_name or not account_key:
            raise ValueError("Account Name and Key are required.")

        connection_string = (
            f"DefaultEndpointsProtocol=https;AccountName={account_name};"
            f"AccountKey={account_key};EndpointSuffix=core.windows.net"
        )
        self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        self.account_name = account_name
        self.credential = None  # Using key, not a credential object

        containers = self.blob_service_client.list_containers()
        return [c['name'] for c in containers]

    def fetch_storage_accounts(self):
        """Fetches all storage accounts accessible by the current credential."""
        if not self.credential:
            raise PermissionError("Must be signed in to fetch accounts.")

        sub_client = SubscriptionClient(self.credential)
        accounts_list = []
        rg_index = CONFIG['api']['azure']['storage_account_id_rg_index']

        for sub in sub_client.subscriptions.list():
            storage_client = StorageManagementClient(self.credential, sub.subscription_id)
            for acc in storage_client.storage_accounts.list():
                resource_group = acc.id.split('/')[rg_index] if 'resourceGroups' in acc.id else 'N/A'
                accounts_list.append({
                    'name': acc.name,
                    'resource_group': resource_group,
                    'subscription_id': sub.subscription_id
                })
        self.storage_accounts = sorted(accounts_list, key=lambda x: x['name'])
        return self.storage_accounts

    def fetch_containers(self, account_name):
        """Fetches all containers for a given storage account."""
        if not self.credential:
            raise PermissionError("Must be signed in to fetch containers.")

        self.account_name = account_name
        account_url = f"https://{account_name}.blob.core.windows.net"
        self.blob_service_client = BlobServiceClient(account_url, self.credential)

        containers = self.blob_service_client.list_containers()
        return [c['name'] for c in containers]

    def sign_out(self):
        """Clears the current session's credential state."""
        self.credential = None
        self.blob_service_client = None
