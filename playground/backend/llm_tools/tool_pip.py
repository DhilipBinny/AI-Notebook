"""
Pip Utils Tools - Allows LLM to manage Python packages.

These tools execute pip operations through the Jupyter kernel to ensure
packages are installed in the correct environment that the notebook uses.
"""

import re
from backend.session_manager import get_current_session
from backend.utils.util_func import log


def _get_session_kernel():
    """Get kernel from current session. Raises if no session."""
    session = get_current_session()
    if not session:
        raise RuntimeError("No active session. Session is required for kernel operations.")
    return session.kernel


def _execute_in_kernel(code: str) -> dict:
    """
    Execute code in the Jupyter kernel.

    Args:
        code: Python/shell code to execute

    Returns:
        Dictionary with success, output, error
    """
    kernel = _get_session_kernel()

    # Auto-start kernel if not running
    if not kernel.is_alive():
        kernel.start()

    result = kernel.execute(code)

    # Format output
    output_text = ""
    if result["outputs"]:
        for output in result["outputs"]:
            if output.get("type") == "stream":
                output_text += output.get("text", "")
            elif output.get("type") == "execute_result":
                output_text += output.get("data", {}).get("text/plain", "")
            elif output.get("type") == "display_data":
                output_text += output.get("data", {}).get("text/plain", "")

    return {
        "success": result["success"],
        "output": output_text.strip(),
        "error": str(result["error"]) if result["error"] else None
    }


def pip_install(packages: str, upgrade: bool = False) -> dict:
    """
    Install Python packages using pip in the kernel environment.

    Use this tool when you need to:
    - Install missing dependencies that caused ImportError
    - Add new libraries for data analysis (pandas, numpy, etc.)
    - Install visualization libraries (matplotlib, seaborn, plotly)
    - Add machine learning packages (scikit-learn, tensorflow, torch)

    IMPORTANT: When a cell execution fails with ModuleNotFoundError or ImportError,
    use this tool to install the missing package, then re-execute the cell.

    Args:
        packages: Package name(s) to install. Can be:
                  - Single package: "pandas"
                  - Multiple packages (space-separated): "pandas numpy matplotlib"
                  - With version: "pandas==2.0.0"
                  - Multiple with versions: "pandas>=2.0 numpy<2.0"
        upgrade: Whether to upgrade if package already exists (default: False)

    Returns:
        Dictionary with:
        - success: Whether the installation succeeded
        - packages: List of packages that were requested
        - output: Installation output/logs
        - error: Error message if installation failed

    Example:
        To install pandas: pip_install("pandas")
        To install multiple: pip_install("pandas numpy matplotlib")
        To upgrade: pip_install("pandas", upgrade=True)
        To install specific version: pip_install("pandas==2.0.0")
    """
    log(f"==> pip_install({packages}, upgrade={upgrade}) called from LLM")

    if not packages or not packages.strip():
        return {
            "success": False,
            "packages": [],
            "error": "No packages specified"
        }

    # Parse packages (handle space-separated list)
    package_list = packages.strip().split()

    # Build pip install command using subprocess with sys.executable
    # This ensures we install to the same Python environment as the kernel
    upgrade_flag = ", '--upgrade'" if upgrade else ""
    packages_str = "', '".join(package_list)

    install_code = f'''
import subprocess
import sys
import site
import os

# Ensure user site-packages is in sys.path BEFORE installing
# This is critical because pip installs to user site when system site-packages is not writable
user_site = site.getusersitepackages()
if user_site and user_site not in sys.path:
    sys.path.insert(0, user_site)
    print(f"Added user site-packages to path: {{user_site}}")

# Run pip install using the same Python interpreter as the kernel
result = subprocess.run(
    [sys.executable, "-m", "pip", "install"{upgrade_flag}, '{packages_str}'],
    capture_output=True,
    text=True
)
print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)

# After install, ensure user site-packages is still in path and refresh
user_site = site.getusersitepackages()
if user_site and user_site not in sys.path:
    sys.path.insert(0, user_site)

# Invalidate import caches so new packages are immediately available
import importlib
importlib.invalidate_caches()

# Force reimport of site to pick up new packages
importlib.reload(site)

# If matplotlib was installed, configure it for inline display
if 'matplotlib' in '{packages_str}'.lower():
    try:
        import matplotlib
        matplotlib.use('agg')
        from IPython import get_ipython
        ipython = get_ipython()
        if ipython:
            ipython.run_line_magic('matplotlib', 'inline')
        print("Matplotlib configured for inline display")
    except Exception as e:
        print(f"Note: Could not configure matplotlib inline: {{e}}")

# Return code for success check
result.returncode
'''

    result = _execute_in_kernel(install_code)

    # Check if installation was successful
    output = result.get("output", "")
    success = result["success"] and ("Successfully installed" in output or "Requirement already satisfied" in output)

    if success:
        return {
            "success": True,
            "packages": package_list,
            "output": output,
            "note": "Packages installed. Import caches refreshed - packages are ready to import."
        }
    else:
        return {
            "success": False,
            "packages": package_list,
            "output": output,
            "error": result.get("error") or "Installation may have failed. Check output for details."
        }


def pip_uninstall(packages: str) -> dict:
    """
    Uninstall Python packages using pip from the kernel environment.

    Use this tool when you need to:
    - Remove packages that are no longer needed
    - Uninstall conflicting packages
    - Clean up the environment

    Args:
        packages: Package name(s) to uninstall (space-separated for multiple)

    Returns:
        Dictionary with:
        - success: Whether the uninstallation succeeded
        - packages: List of packages that were requested
        - output: Uninstallation output
        - error: Error message if uninstallation failed

    Example:
        To uninstall: pip_uninstall("old-package")
        To uninstall multiple: pip_uninstall("pkg1 pkg2")
    """
    log(f"==> pip_uninstall({packages}) called from LLM")

    if not packages or not packages.strip():
        return {
            "success": False,
            "packages": [],
            "error": "No packages specified"
        }

    package_list = packages.strip().split()
    packages_str = "', '".join(package_list)

    uninstall_code = f'''
import subprocess
import sys

result = subprocess.run(
    [sys.executable, "-m", "pip", "uninstall", "-y", '{packages_str}'],
    capture_output=True,
    text=True
)
print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)
result.returncode
'''

    result = _execute_in_kernel(uninstall_code)
    output = result.get("output", "")

    if result["success"] and result["error"] is None:
        return {
            "success": True,
            "packages": package_list,
            "output": output
        }
    else:
        return {
            "success": False,
            "packages": package_list,
            "output": output,
            "error": result.get("error") or "Uninstallation failed"
        }


def pip_list() -> dict:
    """
    List installed Python packages in the kernel environment.

    Use this tool when you need to:
    - Check what packages are available
    - Verify a package was installed
    - See package versions

    Returns:
        Dictionary with:
        - success: Whether the listing succeeded
        - packages: List of installed packages with name and version
        - total: Total number of packages
        - output: Raw pip list output
        - error: Error message if listing failed

    Example:
        To list all packages: pip_list()
    """
    log("==> pip_list() called from LLM")

    list_code = '''
import subprocess
import sys

result = subprocess.run(
    [sys.executable, "-m", "pip", "list", "--format=freeze"],
    capture_output=True,
    text=True
)
print(result.stdout)
'''

    result = _execute_in_kernel(list_code)

    if not result["success"] or result["error"]:
        return {
            "success": False,
            "packages": [],
            "total": 0,
            "error": result.get("error") or "Failed to list packages"
        }

    packages = []
    # Parse freeze format: package==version
    for line in result.get("output", "").strip().split("\n"):
        line = line.strip()
        if line and "==" in line:
            parts = line.split("==")
            packages.append({
                "name": parts[0],
                "version": parts[1] if len(parts) > 1 else "unknown"
            })

    return {
        "success": True,
        "packages": packages,
        "total": len(packages),
        "output": result.get("output", "")
    }


def pip_show(package: str) -> dict:
    """
    Show information about an installed package in the kernel environment.

    Use this tool when you need to:
    - Check if a specific package is installed
    - See package version and details
    - Find package dependencies
    - Get package location

    Args:
        package: Name of the package to show information for

    Returns:
        Dictionary with:
        - success: Whether the package was found
        - name: Package name
        - version: Package version
        - summary: Package description
        - location: Installation location
        - requires: List of dependencies
        - required_by: List of packages that depend on this
        - error: Error message if package not found

    Example:
        To check pandas: pip_show("pandas")
    """
    log(f"==> pip_show({package}) called from LLM")

    if not package or not package.strip():
        return {
            "success": False,
            "error": "No package specified"
        }

    pkg = package.strip()
    show_code = f'''
import subprocess
import sys

result = subprocess.run(
    [sys.executable, "-m", "pip", "show", "{pkg}"],
    capture_output=True,
    text=True
)
print(result.stdout)
'''

    result = _execute_in_kernel(show_code)
    output = result.get("output", "").strip()

    if not result["success"] or result["error"] or not output:
        return {
            "success": False,
            "error": f"Package '{package}' not found or not installed"
        }

    # Parse the output
    info = {}
    for line in output.split("\n"):
        if ": " in line:
            key, value = line.split(": ", 1)
            key = key.lower().replace("-", "_")
            info[key] = value

    # Parse requires and required-by as lists
    requires = []
    if info.get("requires"):
        requires = [r.strip() for r in info["requires"].split(",") if r.strip()]

    required_by = []
    if info.get("required_by"):
        required_by = [r.strip() for r in info["required_by"].split(",") if r.strip()]

    return {
        "success": True,
        "name": info.get("name", package),
        "version": info.get("version", "unknown"),
        "summary": info.get("summary", ""),
        "location": info.get("location", ""),
        "requires": requires,
        "required_by": required_by
    }


def pip_search_installed(query: str) -> dict:
    """
    Search for packages matching a query in installed packages.

    Use this tool when you need to:
    - Find if a package or similar package is installed
    - Search for packages by partial name
    - Check for related packages

    Args:
        query: Search term (case-insensitive partial match)

    Returns:
        Dictionary with:
        - success: Whether the search succeeded
        - query: The search term
        - matches: List of matching packages with name and version
        - total: Number of matches

    Example:
        To find data-related packages: pip_search_installed("data")
        To check for scikit packages: pip_search_installed("scikit")
    """
    log(f"==> pip_search_installed({query}) called from LLM")

    if not query or not query.strip():
        return {
            "success": False,
            "error": "No search query specified"
        }

    # Get all packages first
    list_result = pip_list()

    if not list_result["success"]:
        return {
            "success": False,
            "query": query,
            "matches": [],
            "total": 0,
            "error": "Failed to get package list"
        }

    # Filter by query (case-insensitive)
    query_lower = query.lower().strip()
    matches = [
        pkg for pkg in list_result["packages"]
        if query_lower in pkg["name"].lower()
    ]

    return {
        "success": True,
        "query": query,
        "matches": matches,
        "total": len(matches)
    }


def extract_missing_modules(error_message: str) -> dict:
    """
    Extract missing module names from an error message.

    Use this tool when you need to:
    - Parse an ImportError or ModuleNotFoundError message
    - Identify which package to install from an error
    - Automatically determine missing dependencies

    This is a helper function that parses common Python import error formats.

    Args:
        error_message: The error message from a failed cell execution

    Returns:
        Dictionary with:
        - success: Whether parsing succeeded
        - modules: List of module names that appear to be missing
        - suggested_packages: Suggested package names to install
                             (may differ from module names, e.g., sklearn -> scikit-learn)

    Example:
        error = "ModuleNotFoundError: No module named 'pandas'"
        result = extract_missing_modules(error)
        # result: {"modules": ["pandas"], "suggested_packages": ["pandas"]}
    """
    log("==> extract_missing_modules called from LLM")

    if not error_message:
        return {
            "success": False,
            "modules": [],
            "suggested_packages": [],
            "error": "No error message provided"
        }

    modules = []

    # Pattern 1: ModuleNotFoundError: No module named 'xxx'
    pattern1 = r"ModuleNotFoundError: No module named ['\"]([^'\"]+)['\"]"
    matches1 = re.findall(pattern1, error_message)
    modules.extend(matches1)

    # Pattern 2: ImportError: No module named xxx
    pattern2 = r"ImportError: No module named ['\"]?([^\s'\"]+)['\"]?"
    matches2 = re.findall(pattern2, error_message)
    modules.extend(matches2)

    # Pattern 3: cannot import name 'xxx' from 'yyy'
    pattern3 = r"cannot import name ['\"]([^'\"]+)['\"] from ['\"]([^'\"]+)['\"]"
    matches3 = re.findall(pattern3, error_message)
    for name, module in matches3:
        modules.append(module.split(".")[0])  # Get top-level module

    # Remove duplicates while preserving order
    seen = set()
    unique_modules = []
    for m in modules:
        # Get top-level module name
        top_level = m.split(".")[0]
        if top_level not in seen:
            seen.add(top_level)
            unique_modules.append(top_level)

    # Map common module names to package names
    module_to_package = {
        "sklearn": "scikit-learn",
        "cv2": "opencv-python",
        "PIL": "Pillow",
        "yaml": "PyYAML",
        "bs4": "beautifulsoup4",
        "dateutil": "python-dateutil",
        "dotenv": "python-dotenv",
        "jwt": "PyJWT",
        "magic": "python-magic",
        "serial": "pyserial",
        "usb": "pyusb",
        "skimage": "scikit-image",
        "tables": "pytables",
        "Bio": "biopython",
        "wx": "wxPython",
        "gi": "PyGObject",
    }

    suggested_packages = []
    for module in unique_modules:
        package = module_to_package.get(module, module)
        suggested_packages.append(package)

    return {
        "success": True,
        "modules": unique_modules,
        "suggested_packages": suggested_packages
    }
