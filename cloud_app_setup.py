# cloud_app_setup.py
import importlib.util
import shutil
import subprocess
import sys

# Centralized application configuration
from config_loader import CONFIG

# This dictionary will hold the status of all checked dependencies.
DEPENDENCY_STATUS = {
    "azure_sdk": False,
    "git": False,
    "gh_cli": False,
    "pillow": False,
    "requests": False,
    "pygithub": False,
    "screeninfo": False,
    "python_version": False,
}

# Minimum Python version is now loaded from config
MIN_PYTHON_VERSION = tuple(CONFIG['validation']['python_min_version'])


def _check_python_version():
    """Checks if the current Python version meets minimum requirements."""
    current_version = sys.version_info[:2]

    if current_version >= MIN_PYTHON_VERSION:
        DEPENDENCY_STATUS["python_version"] = True
        return None
    else:
        DEPENDENCY_STATUS["python_version"] = False
        return (
            f"Python version {current_version[0]}.{current_version[1]} is not supported.\n\n"
            f"This application requires Python {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]} or higher."
        )


def _check_azure_sdk():
    """Checks for the presence of the required Azure SDK packages."""
    required_modules = [
        ('azure.identity', 'DefaultAzureCredential'),
        ('azure.storage.blob', 'BlobServiceClient'),
        ('azure.core.exceptions', 'ClientAuthenticationError'),
        ('azure.mgmt.storage', 'StorageManagementClient'),
        ('azure.mgmt.subscription', 'SubscriptionClient'),
        ('azure.mgmt.resource', 'ResourceManagementClient'),
        ('azure.ai.ml', 'MLClient')
    ]
    missing_modules = []
    for module_name, class_name in required_modules:
        try:
            module = importlib.import_module(module_name)
            if not hasattr(module, class_name):
                missing_modules.append(f"{module_name}.{class_name}")
        except ImportError:
            missing_modules.append(module_name)

    if not missing_modules:
        DEPENDENCY_STATUS["azure_sdk"] = True
        return None
    else:
        DEPENDENCY_STATUS["azure_sdk"] = False
        return (
            "Azure SDK components are missing or incomplete.\n\n"
            f"Missing: {', '.join(missing_modules)}\n\n"
            "To install, run: pip install azure-identity azure-mgmt-storage azure-storage-blob "
            "azure-mgmt-subscription azure-mgmt-resource azure-ai-ml"
        )


def _check_pillow():
    """Checks for PIL/Pillow for image processing."""
    try:
        from PIL import Image
        test_image = Image.new('RGB', (1, 1), color='red')
        if test_image.size != (1, 1):
            raise ImportError("Pillow functionality test failed")
        DEPENDENCY_STATUS["pillow"] = True
        return None
    except ImportError:
        DEPENDENCY_STATUS["pillow"] = False
        return "Pillow (PIL) is not installed. To install, run: pip install Pillow"


def _check_requests():
    """Checks for requests library."""
    try:
        import requests
        if not hasattr(requests, 'get') or not hasattr(requests, 'post'):
            raise ImportError("Requests functionality test failed")
        DEPENDENCY_STATUS["requests"] = True
        return None
    except ImportError:
        DEPENDENCY_STATUS["requests"] = False
        return "Requests library is not installed. To install, run: pip install requests"


def _check_pygithub():
    """Checks for PyGithub library."""
    try:
        from github import Github
        if not hasattr(Github, '__init__'):
            raise ImportError("PyGithub functionality test failed")
        DEPENDENCY_STATUS["pygithub"] = True
        return None
    except ImportError:
        DEPENDENCY_STATUS["pygithub"] = False
        return "PyGithub is not installed. To install, run: pip install PyGithub"


def _check_screeninfo():
    """Checks for screeninfo library."""
    try:
        from screeninfo import get_monitors
        if not isinstance(get_monitors(), list):
            raise ImportError("Screeninfo functionality test failed")
        DEPENDENCY_STATUS["screeninfo"] = True
        return None
    except ImportError:
        DEPENDENCY_STATUS["screeninfo"] = False
        return "screeninfo is not installed. To install, run: pip install screeninfo"


# --- START: MODIFIED SECTION FOR GIT INSTALLATION ---

def _install_git_windows():
    """Attempts to install Git using winget on Windows."""
    try:
        print("Attempting to install Git using winget...")
        # Use --accept-source-agreements to prevent interactive prompts
        command = [
            "winget", "install", "--id", "Git.Git", "-e",
            "--source", "winget", "--accept-source-agreements"
        ]
        result = subprocess.run(
            command, capture_output=True, text=True, check=True, encoding='utf-8'
        )
        print(result.stdout)
        return True, "Git installed successfully via winget."
    except FileNotFoundError:
        return False, "winget command not found. Please install Git manually."
    except subprocess.CalledProcessError as e:
        error_details = e.stderr or e.stdout
        return False, f"winget installation failed:\n{error_details}"


def _install_git_macos():
    """Attempts to install Git using Homebrew on macOS."""
    if not shutil.which("brew"):
        return False, "Homebrew (brew) not found. Please install Git manually or install Homebrew first."
    try:
        print("Attempting to install Git using Homebrew...")
        result = subprocess.run(
            ["brew", "install", "git"],
            capture_output=True, text=True, check=True, encoding='utf-8'
        )
        print(result.stdout)
        return True, "Git installed successfully via Homebrew."
    except subprocess.CalledProcessError as e:
        error_details = e.stderr or e.stdout
        return False, f"Homebrew installation failed:\n{error_details}"


def _install_git_linux():
    """Attempts to install Git using a common Linux package manager."""
    managers = {
        "apt-get": "sudo apt-get install -y git",
        "dnf": "sudo dnf install -y git",
        "yum": "sudo yum install -y git",
    }
    for manager, command in managers.items():
        if shutil.which(manager):
            try:
                print(f"Attempting to install Git using {manager}...")
                print(f"Executing: '{command}'. You may be prompted for your password.")
                # Run command, allowing user to see output and enter password
                subprocess.run(command.split(), check=True)
                return True, f"Git installed successfully via {manager}."
            except subprocess.CalledProcessError:
                return False, f"{manager} command failed. Please run '{command}' manually."
    return False, "Could not find a supported package manager (apt, dnf, yum). Please install Git manually."


def _check_git():
    """
    Checks if 'git' is in the system's PATH. If not, attempts to install it.
    """
    if shutil.which("git"):
        try:
            timeout = CONFIG['api']['timeouts']['subprocess_seconds']
            result = subprocess.run(['git', '--version'], capture_output=True, text=True, timeout=timeout)
            if result.returncode == 0 and 'git version' in result.stdout.lower():
                DEPENDENCY_STATUS["git"] = True
                return None
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
            pass  # Fall through to return the generic error

    # If Git is not found, attempt an automated installation
    print("Git not found in PATH. Attempting automated installation...")
    installed = False
    message = ""

    if sys.platform == "win32":
        installed, message = _install_git_windows()
    elif sys.platform == "darwin":
        installed, message = _install_git_macos()
    elif sys.platform.startswith("linux"):
        installed, message = _install_git_linux()
    else:
        message = f"Unsupported OS '{sys.platform}'. Please install Git manually."

    print(message)

    # After attempting installation, re-check if it's in the PATH
    if installed and shutil.which("git"):
        print("Git is now available in PATH.")
        DEPENDENCY_STATUS["git"] = True
        return None
    elif installed:
        # This can happen if the current shell session needs to be restarted
        DEPENDENCY_STATUS["git"] = False
        return (
            "Git was installed, but it is not available in the current PATH.\n\n"
            "Please RESTART your terminal/shell and run the application again."
        )
    else:
        # Installation failed or was not attempted
        DEPENDENCY_STATUS["git"] = False
        return f"Git installation failed. Please install it manually from: https://git-scm.com/downloads"

# --- END: MODIFIED SECTION ---


def _check_github_cli():
    """Checks if 'gh' executable is in the system's PATH."""
    if shutil.which("gh"):
        try:
            timeout = CONFIG['api']['timeouts']['subprocess_seconds']
            result = subprocess.run(['gh', '--version'], capture_output=True, text=True, timeout=timeout)
            if result.returncode == 0 and 'gh version' in result.stdout.lower():
                DEPENDENCY_STATUS["gh_cli"] = True
                return None
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
            pass
    DEPENDENCY_STATUS["gh_cli"] = False
    return "GitHub CLI (gh) is not installed. Please install from: https://cli.github.com/"


def check_all_dependencies():
    """Runs all dependency checks and returns lists of error and warning messages."""
    error_messages = []
    warning_messages = []

    critical_checks = [
        ("Python Version", _check_python_version),
        ("Pillow (Image Processing)", _check_pillow),
    ]
    optional_checks = [
        ("Azure SDK", _check_azure_sdk),
        ("Requests Library", _check_requests),
        ("PyGithub Library", _check_pygithub),
        ("Screen Info Library", _check_screeninfo),
        ("Git Executable", _check_git),
        ("GitHub CLI", _check_github_cli),
    ]

    print("\nCRITICAL DEPENDENCIES:")
    for check_name, check_func in critical_checks:
        try:
            error = check_func()
            if error:
                error_messages.append(error)
                print(f"  [FAILED] {check_name}: {error.splitlines()[0]}")
            else:
                print(f"  [OK]     {check_name}")
        except Exception as e:
            error_messages.append(f"{check_name} check failed: {e}")
            print(f"  [ERROR]  {check_name}: {e}")

    print("\nOPTIONAL DEPENDENCIES:")
    for check_name, check_func in optional_checks:
        try:
            error = check_func()
            if error:
                warning_messages.append(error)
                print(f"  [WARN]   {check_name}: {error.splitlines()[0]}")
            else:
                print(f"  [OK]     {check_name}")
        except Exception as e:
            warning_messages.append(f"{check_name} check failed: {e}")
            print(f"  [ERROR]  {check_name}: {e}")

    return error_messages, warning_messages


def run_startup_checks(root_tk_window=None):
    """
    Performs startup checks, shows error/warning messages, and exits if critical dependencies are missing.
    """
    error_messages, warning_messages = check_all_dependencies()

    if error_messages:
        import tkinter as tk
        from tkinter import messagebox
        root = root_tk_window or tk.Tk()
        if not root_tk_window: root.withdraw()

        full_error_message = (
                "CRITICAL DEPENDENCIES MISSING\n"
                "The application cannot start.\n\n" + "\n\n".join(error_messages)
        )
        messagebox.showerror("Critical Dependencies Missing", full_error_message)
        sys.exit(CONFIG['app']['exit_codes']['critical_error'])

    if warning_messages:
        import tkinter as tk
        from tkinter import messagebox
        root = root_tk_window or tk.Tk()
        if not root_tk_window: root.withdraw()

        full_warning_message = (
                "OPTIONAL DEPENDENCIES MISSING\n"
                "Some features will be disabled.\n\n" + "\n\n".join(warning_messages)
        )
        messagebox.showwarning("Optional Dependencies Missing", full_warning_message)


def get_dependency_report() -> dict:
    """Gets a detailed report of all dependency statuses."""
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    req_version = f"{MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]}+"

    return {
        "python_version": {"status": DEPENDENCY_STATUS["python_version"], "current": py_version,
                           "required": req_version, "critical": True},
        "pillow": {"status": DEPENDENCY_STATUS["pillow"], "features": ["Image preview"], "critical": True},
        "azure_sdk": {"status": DEPENDENCY_STATUS["azure_sdk"], "features": ["Azure auth, Blob storage, ML workspace"],
                      "critical": False},
        "requests": {"status": DEPENDENCY_STATUS["requests"], "features": ["GitHub OAuth", "Web API calls"],
                     "critical": False},
        "pygithub": {"status": DEPENDENCY_STATUS["pygithub"], "features": ["GitHub API access"], "critical": False},
        "screeninfo": {"status": DEPENDENCY_STATUS["screeninfo"], "features": ["Multi-monitor support"],
                       "critical": False},
        "git": {"status": DEPENDENCY_STATUS["git"], "features": ["Repository cloning"], "critical": False},
        "gh_cli": {"status": DEPENDENCY_STATUS["gh_cli"], "features": ["GitHub CLI authentication"], "critical": False}
    }


if __name__ == "__main__":
    print("Running Cloud Tools dependency checker...\n")
    errors, warnings = check_all_dependencies()

    exit_code = CONFIG['app']['exit_codes']['success']
    if errors:
        print("\nERROR: Critical dependencies are missing. Application cannot start.")
        exit_code = CONFIG['app']['exit_codes']['critical_error']
    elif warnings:
        print("\nWARNING: Some optional dependencies are missing. Limited functionality.")
        exit_code = CONFIG['app']['exit_codes']['warning']
    else:
        print("\nSUCCESS: All dependencies are satisfied!")

    sys.exit(exit_code)