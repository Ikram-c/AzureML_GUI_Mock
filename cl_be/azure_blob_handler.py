# cl_be/azure_blob_handler.py
import os
import tempfile
import uuid
from pathlib import Path

# Centralized application configuration
from config_loader import CONFIG
# Dependency status from the central setup script
from app_setup import DEPENDENCY_STATUS

# Conditionally import Azure SDK modules
if DEPENDENCY_STATUS["azure_sdk"]:
    from azure.storage.blob import BlobServiceClient, ContentSettings


class AzureBlobHandler:
    """
    Handles all backend logic for Azure Blob Storage operations like
    listing, uploading, and downloading blobs.
    """

    def _get_blob_service_client(self, auth_handler):
        """
        Helper to get an authenticated BlobServiceClient from the auth handler.
        """
        if auth_handler.blob_service_client:
            return auth_handler.blob_service_client

        if auth_handler.credential and auth_handler.account_name:
            account_url = f"https://{auth_handler.account_name}.blob.core.windows.net"
            return BlobServiceClient(account_url, credential=auth_handler.credential)

        raise ConnectionError("Not connected to any Azure Storage account.")

    def get_folder_structure(self, auth_handler, container_name: str):
        """
        Lists all blobs in a container and returns them in a nested dictionary
        representing the folder structure.
        """
        if not container_name:
            raise ValueError("Container name must be provided.")

        blob_service_client = self._get_blob_service_client(auth_handler)
        container_client = blob_service_client.get_container_client(container_name)

        structure = {}
        for blob in container_client.list_blobs():
            parts = blob.name.split('/')
            current_level = structure
            for part in parts[:-1]:
                current_level = current_level.setdefault(part, {})
            current_level[parts[-1]] = blob.size

        return structure

    def create_folder(self, auth_handler, container_name: str, folder_path: str):
        """
        Creates a 'folder' in blob storage by uploading an empty marker file.
        """
        if not folder_path.endswith('/'):
            folder_path += '/'
        marker_blob_name = f"{folder_path}.folder_marker"

        blob_service_client = self._get_blob_service_client(auth_handler)
        blob_client = blob_service_client.get_blob_client(
            container=container_name, blob=marker_blob_name
        )
        blob_client.upload_blob(b'', overwrite=True)
        return f"Folder '{folder_path}' created successfully."

    def upload_blob(
            self, auth_handler, container_name: str, local_file_path: str, remote_blob_path: str, progress_callback
    ):
        """
        Uploads a single file to Azure Blob Storage with progress tracking.
        """
        blob_service_client = self._get_blob_service_client(auth_handler)
        blob_client = blob_service_client.get_blob_client(
            container=container_name, blob=remote_blob_path
        )

        file_extension = Path(local_file_path).suffix.lower()
        content_types = {'.jpg': 'image/jpeg', '.png': 'image/png', '.gif': 'image/gif'}
        content_settings = ContentSettings(content_type=content_types.get(file_extension))
        file_size = os.path.getsize(local_file_path)

        with open(local_file_path, "rb") as data:
            result = blob_client.upload_blob(
                data,
                overwrite=True,
                content_settings=content_settings,
                max_concurrency=CONFIG['api']['azure']['blob_upload_concurrency'],
                raw_response_hook=lambda response: progress_callback(
                    response.context["upload_stream_current"], file_size
                )
            )
        return result

    def download_blob_for_preview(self, auth_handler, container_name: str, blob_name: str):
        """
        Downloads a blob to a temporary local file for previewing.
        Returns the path to the temporary file and the blob's size.
        """
        blob_service_client = self._get_blob_service_client(auth_handler)
        blob_client = blob_service_client.get_blob_client(
            container=container_name, blob=blob_name
        )

        properties = blob_client.get_blob_properties()
        file_size = properties.size

        temp_dir = tempfile.gettempdir()
        file_extension = Path(blob_name).suffix
        temp_file_path = os.path.join(temp_dir, f"preview_{uuid.uuid4().hex}{file_extension}")

        with open(temp_file_path, "wb") as download_file:
            download_stream = blob_client.download_blob()
            download_file.write(download_stream.readall())

        return temp_file_path, file_size

    def download_blobs(
            self, auth_handler, container_name: str, blob_names: list, local_dir: str, progress_callback
    ):
        """
        Downloads a list of blobs to a specified local directory.
        """
        blob_service_client = self._get_blob_service_client(auth_handler)
        total_files = len(blob_names)

        for i, blob_name in enumerate(blob_names):
            local_path = os.path.join(local_dir, os.path.basename(blob_name))
            blob_client = blob_service_client.get_blob_client(
                container=container_name, blob=blob_name
            )
            with open(local_path, "wb") as download_file:
                download_stream = blob_client.download_blob()
                download_file.write(download_stream.readall())
            progress_callback(i + 1, total_files)

        return f"Successfully downloaded {total_files} files."
