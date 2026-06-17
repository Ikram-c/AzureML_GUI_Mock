# cl_be/github_handler.py
import os
import shutil
import subprocess
import time
import webbrowser

import requests
from github import Github, GithubException

# Centralized application configuration
from config_loader import CONFIG


class GitHubHandler:
    """
    Handles all backend logic for GitHub operations including authentication,
    repository management, and Git operations.
    """

    def __init__(self):
        self.github_instance = None
        self.is_authenticated = False
        self.repos = []
        self._device_flow_state = {}

    def check_dependencies(self):
        """Check for required external tools."""
        missing_tools = []
        if shutil.which("git") is None:
            missing_tools.append("Git is not installed or not in the system's PATH.")
        if shutil.which("gh") is None:
            missing_tools.append("GitHub CLI (gh) is not installed or not in the system's PATH.")
        if missing_tools:
            raise FileNotFoundError("\n".join(missing_tools))

    def login_with_cli(self, line_callback):
        """Authenticate using the GitHub CLI with real-time feedback."""
        self.check_dependencies()
        line_callback("Starting GitHub CLI authentication...\n")

        process = subprocess.Popen(
            ["gh", "auth", "login", "--web"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, universal_newlines=True
        )

        for line in iter(process.stdout.readline, ''):
            line_callback(line)
            if "Open this URL to continue" in line:
                try:
                    url_part = line.split(':', 1)[-1].strip()
                    if url_part.startswith("https://"):
                        webbrowser.open(url_part)
                        line_callback(f"--> Opened browser automatically: {url_part}\n")
                except Exception as e:
                    line_callback(f"--> Could not open browser automatically: {e}\n")
        process.wait()

        if process.returncode != 0:
            raise Exception("GitHub CLI authentication failed or was canceled.")

        line_callback("\nLogin successful. Fetching auth token...\n")
        try:
            token = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
            if not token:
                raise RuntimeError("Auth token from GitHub CLI was empty.")
            return self.finish_authentication(token)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Could not get auth token after login: {getattr(e, 'stderr', e)}")

    def start_device_flow(self):
        """Start GitHub OAuth Device Flow authentication."""
        client_id = CONFIG['api']['github']['oauth_client_id']
        if client_id == "YOUR_GITHUB_APP_CLIENT_ID":
            raise ValueError("GitHub Client ID is not configured in cloud_config.yaml.")

        try:
            timeout = CONFIG['api']['timeouts']['default_http_seconds']
            response = requests.post(
                "https://github.com/login/device/code",
                headers={"Accept": "application/json"},
                data={"client_id": client_id, "scope": "repo read:user read:org"},
                timeout=timeout
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            raise Exception(f"Failed to start device flow: {str(e)}")

        self._device_flow_state = {
            "client_id": client_id, "device_code": data["device_code"],
            "interval": data["interval"], "expires_in": data["expires_in"]
        }
        webbrowser.open(data["verification_uri"])
        return {"verification_uri": data["verification_uri"], "user_code": data["user_code"]}

    def poll_for_token(self, success_callback, failure_callback):
        """Poll GitHub for the OAuth token after device flow is started."""
        if not self._device_flow_state:
            failure_callback(Exception("Device flow was not started."))
            return

        state = self._device_flow_state
        start_time = time.time()
        timeout = CONFIG['api']['timeouts']['default_http_seconds']

        try:
            while time.time() - start_time < state["expires_in"]:
                time.sleep(state["interval"])
                response = requests.post(
                    "https://github.com/login/oauth/access_token",
                    headers={"Accept": "application/json"},
                    data={
                        "client_id": state["client_id"], "device_code": state["device_code"],
                        "grant_type": "urn:ietf:params:oauth:grant-type:device_code"
                    },
                    timeout=timeout
                )
                data = response.json()

                if "access_token" in data:
                    success_callback(data["access_token"])
                    return
                error = data.get("error")
                if error == "authorization_pending": continue
                elif error == "slow_down": time.sleep(5)
                else: raise Exception(f"GitHub login error: {data.get('error_description', 'Unknown error')}")
            raise TimeoutError("GitHub authentication timed out.")
        except Exception as e:
            failure_callback(e)

    def finish_authentication(self, access_token):
        """Complete the authentication process with the received access token."""
        try:
            self.github_instance = Github(access_token)
            user = self.github_instance.get_user()
            self.is_authenticated = True
            self._device_flow_state = {}
            return f"Successfully authenticated as {user.login}."
        except GithubException as e:
            self.is_authenticated = False
            self.github_instance = None
            error_msg = e.data.get('message', str(e)) if hasattr(e, 'data') and e.data else str(e)
            raise IOError(f"GitHub Authentication failed: {error_msg}")

    def fetch_repos(self, line_callback):
        """Fetch all repositories accessible to the authenticated user."""
        if not self.is_authenticated or not self.github_instance:
            raise PermissionError("Must be authenticated to fetch repositories.")
        line_callback("Fetching GitHub repositories via API...\n")
        try:
            user = self.github_instance.get_user()
            fetched_repos = user.get_repos(affiliation='owner,collaborator,organization_member', sort='updated')
            self.repos = [{
                "name": repo.name, "nameWithOwner": repo.full_name,
                "visibility": "private" if repo.private else "public",
                "clone_url": repo.clone_url, "ssh_url": repo.ssh_url, "html_url": repo.html_url,
                "description": repo.description or "", "language": repo.language or "",
                "updated_at": repo.updated_at
            } for repo in fetched_repos]
            line_callback(f"Successfully loaded {len(self.repos)} repositories.\n")
            return self.repos
        except GithubException as e:
            error_msg = e.data.get('message', str(e)) if hasattr(e, 'data') and e.data else str(e)
            raise Exception(f"Failed to fetch repositories: {error_msg}")

    def clone_repo(self, repo_full_name, line_callback):
        """Clone a repository by its full name (owner/repo)."""
        repo_info = next((r for r in self.repos if r["nameWithOwner"] == repo_full_name), None)
        if not repo_info:
            raise ValueError(f"Repository {repo_full_name} not found.")
        return self._clone_from_url(repo_info["clone_url"], line_callback, repo_full_name)

    def clone_repo_from_url(self, repo_url, line_callback):
        """Clone a repository from a given URL."""
        return self._clone_from_url(repo_url, line_callback)

    def _clone_from_url(self, clone_url, line_callback, repo_full_name=None):
        """Internal method to clone from a URL."""
        repo_name = repo_full_name.split('/')[-1] if repo_full_name else clone_url.rstrip('/').split('/')[-1].replace('.git', '')
        clone_dir = os.path.join(os.getcwd(), "cloned_repos")
        os.makedirs(clone_dir, exist_ok=True)
        destination = os.path.join(clone_dir, repo_name)

        if os.path.exists(destination):
            raise FileExistsError(f"Directory {destination} already exists.")
        line_callback(f"Cloning {clone_url} to {destination}...\n")

        try:
            self.check_dependencies()
            process = subprocess.Popen(
                ["git", "clone", "--progress", clone_url, destination],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
            )
            for line in iter(process.stdout.readline, ''):
                if line.strip(): line_callback(line)
            process.wait()

            if process.returncode == 0:
                line_callback(f"\n✓ Successfully cloned to: {destination}\n")
                return f"Repository cloned to {destination}"
            else:
                if os.path.exists(destination): shutil.rmtree(destination, ignore_errors=True)
                raise subprocess.CalledProcessError(process.returncode, "git clone")
        except Exception as e:
            error_msg = f"Clone failed: {str(e)}"
            line_callback(f"ERROR: {error_msg}\n")
            raise RuntimeError(error_msg)

    def open_repo_in_browser(self, repo_full_name):
        """Open a repository in the default web browser."""
        url = f"https://github.com/{repo_full_name}"
        try:
            webbrowser.open(url)
            return f"Opening {url} in browser..."
        except Exception as e:
            return f"Failed to open browser: {str(e)}"

    def search_repos(self, query, line_callback):
        """Search for repositories using GitHub's search API."""
        if not self.is_authenticated or not self.github_instance:
            raise PermissionError("Must be authenticated to search repositories.")
        line_callback(f"Searching for repositories matching '{query}'...\n")
        try:
            limit = CONFIG['api']['limits']['github_search_results']
            search_results = self.github_instance.search_repositories(query, sort="updated")
            repos = [{
                "name": repo.name, "nameWithOwner": repo.full_name,
                "visibility": "private" if repo.private else "public",
                "clone_url": repo.clone_url, "ssh_url": repo.ssh_url, "html_url": repo.html_url,
                "description": repo.description or "", "language": repo.language or "",
                "stars": repo.stargazers_count, "updated_at": repo.updated_at
            } for repo in search_results[:limit]]
            line_callback(f"Found {len(repos)} repositories matching '{query}'.\n")
            return repos
        except GithubException as e:
            error_msg = e.data.get('message', str(e)) if hasattr(e, 'data') and e.data else str(e)
            raise Exception(f"Search failed: {error_msg}")

    def get_auth_status(self):
        """Get the current authentication status."""
        if not self.is_authenticated or not self.github_instance:
            return {"authenticated": False, "user": None}
        try:
            user = self.github_instance.get_user()
            return {"authenticated": True, "user": user.login, "name": user.name}
        except:
            return {"authenticated": False, "user": None}

    def logout(self):
        """Clear authentication state."""
        self.github_instance = None
        self.is_authenticated = False
        self.repos = []
        self._device_flow_state = {}
