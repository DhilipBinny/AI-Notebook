"""
Jupyter Kernel Manager
Handles starting, stopping, and communicating with IPython kernel
"""

import queue
from typing import Optional, Dict, Any

# Workaround for PyInstaller: Register the LocalProvisioner before importing KernelManager
# This fixes the "'module' object is not callable" error in compiled binaries
try:
    from jupyter_client.provisioning.local_provisioner import LocalProvisioner
    from jupyter_client.provisioning import factory as provisioning_factory

    # Patch the factory to directly return LocalProvisioner instead of using entry points
    _original_create = getattr(provisioning_factory, 'create_provisioner_instance', None)

    async def _patched_create_provisioner_instance(kernel_id, kernel_spec, parent):
        """Patched provisioner factory that directly uses LocalProvisioner."""
        return LocalProvisioner(kernel_id=kernel_id, kernel_spec=kernel_spec, parent=parent)

    if _original_create:
        provisioning_factory.create_provisioner_instance = _patched_create_provisioner_instance
        print("[Kernel] Applied PyInstaller provisioner workaround", flush=True)
except Exception as e:
    print(f"[Kernel] Could not apply provisioner workaround: {e}", flush=True)

from jupyter_client import KernelManager


class NotebookKernel:
    """Manages a single Jupyter kernel instance"""

    def __init__(self):
        self.km: Optional[KernelManager] = None
        self.kc = None  # Kernel client
        self.execution_count = 0

    def start(self) -> bool:
        """Start a new kernel"""
        try:
            import os
            import sys
            import traceback

            # Set unbuffered output for real-time streaming
            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'

            print("[Kernel] Creating KernelManager...", flush=True)
            self.km = KernelManager(kernel_name='python3')

            print("[Kernel] Starting kernel subprocess...", flush=True)
            self.km.start_kernel(env=env)

            print("[Kernel] Creating client...", flush=True)
            self.kc = self.km.client()
            self.kc.start_channels()

            # Wait for kernel to be ready
            print("[Kernel] Waiting for kernel to be ready...", flush=True)
            self.kc.wait_for_ready(timeout=30)

            # Set up auto-flush for print statements and matplotlib inline backend
            setup_code = '''
import functools
import builtins
_original_print = builtins.print
@functools.wraps(_original_print)
def _flushing_print(*args, **kwargs):
    kwargs.setdefault('flush', True)
    return _original_print(*args, **kwargs)
builtins.print = _flushing_print

# Configure matplotlib to use inline backend for image output
try:
    import matplotlib
    matplotlib.use('agg')  # Use non-GUI backend

    # Enable inline display
    from IPython import get_ipython
    ipython = get_ipython()
    if ipython:
        ipython.run_line_magic('matplotlib', 'inline')
except ImportError:
    pass  # matplotlib not installed yet

# Ensure user site-packages is in path for pip-installed packages
import site
import sys
user_site = site.getusersitepackages()
if user_site and user_site not in sys.path:
    sys.path.insert(0, user_site)
'''
            print("[Kernel] Running setup code...", flush=True)
            self.kc.execute(setup_code, silent=True)

            self.execution_count = 0
            print("[Kernel] Started successfully", flush=True)
            return True
        except Exception as e:
            print(f"[Kernel] Failed to start: {e}", flush=True)
            print(f"[Kernel] Traceback: {traceback.format_exc()}", flush=True)
            return False

    def stop(self) -> bool:
        """Stop the kernel"""
        try:
            if self.kc:
                self.kc.stop_channels()
            if self.km:
                self.km.shutdown_kernel(now=True)
            self.km = None
            self.kc = None
            self.execution_count = 0
            print("[Kernel] Stopped")
            return True
        except Exception as e:
            print(f"[Kernel] Failed to stop: {e}")
            return False

    def restart(self) -> bool:
        """Restart the kernel"""
        self.stop()
        return self.start()

    def is_alive(self) -> bool:
        """Check if kernel is running"""
        if self.km is None:
            return False
        return self.km.is_alive()

    def interrupt(self) -> bool:
        """Interrupt the currently running code"""
        try:
            if self.km and self.is_alive():
                self.km.interrupt_kernel()
                print("[Kernel] Interrupted")
                return True
            return False
        except Exception as e:
            print(f"[Kernel] Failed to interrupt: {e}")
            return False

    def execute(self, code: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Execute code in the kernel

        Returns:
            {
                "success": bool,
                "execution_count": int,
                "outputs": [{"type": "stream/execute_result/error", "content": ...}],
                "error": str or None
            }
        """
        if not self.is_alive():
            return {
                "success": False,
                "execution_count": None,
                "outputs": [],
                "error": "Kernel is not running"
            }

        self.execution_count += 1
        current_count = self.execution_count

        outputs = []
        error = None

        try:
            # Execute the code
            msg_id = self.kc.execute(code)

            # Track if we've seen the execution start
            execution_started = False

            # Collect outputs
            while True:
                try:
                    msg = self.kc.get_iopub_msg(timeout=timeout)
                    msg_type = msg['header']['msg_type']
                    content = msg['content']

                    # Check if this message belongs to our execution
                    parent_msg_id = msg.get('parent_header', {}).get('msg_id', '')
                    is_our_msg = (parent_msg_id == msg_id)

                    if msg_type == 'status' and is_our_msg:
                        execution_state = content.get('execution_state', '')
                        if execution_state == 'busy':
                            execution_started = True
                        elif execution_state == 'idle' and execution_started:
                            # Our execution is complete
                            break

                    elif msg_type == 'stream' and is_our_msg:
                        # stdout/stderr
                        outputs.append({
                            "type": "stream",
                            "name": content.get('name', 'stdout'),
                            "text": content.get('text', '')
                        })

                    elif msg_type == 'execute_result' and is_our_msg:
                        # Expression result
                        outputs.append({
                            "type": "execute_result",
                            "data": content.get('data', {}),
                            "execution_count": content.get('execution_count')
                        })

                    elif msg_type == 'display_data' and is_our_msg:
                        # Rich display (images, HTML, etc.)
                        outputs.append({
                            "type": "display_data",
                            "data": content.get('data', {})
                        })

                    elif msg_type == 'error' and is_our_msg:
                        # Execution error
                        error = {
                            "ename": content.get('ename', 'Error'),
                            "evalue": content.get('evalue', ''),
                            "traceback": content.get('traceback', [])
                        }
                        outputs.append({
                            "type": "error",
                            "ename": error['ename'],
                            "evalue": error['evalue'],
                            "traceback": error['traceback']
                        })

                except queue.Empty:
                    error = "Execution timed out"
                    break

            return {
                "success": error is None,
                "execution_count": current_count,
                "outputs": outputs,
                "error": error
            }

        except Exception as e:
            return {
                "success": False,
                "execution_count": current_count,
                "outputs": [],
                "error": str(e)
            }

    def _is_pip_install(self, code: str) -> bool:
        """Check if code contains a pip install command"""
        import re
        # Match !pip install, ! pip install, %pip install, or pip.main(['install'...])
        pip_patterns = [
            r'^\s*!\s*pip\s+install',      # !pip install or ! pip install
            r'^\s*%\s*pip\s+install',      # %pip install or % pip install
            r'pip\.main\s*\(\s*\[.*install',
            r'subprocess.*pip.*install',
        ]
        for pattern in pip_patterns:
            if re.search(pattern, code, re.MULTILINE | re.IGNORECASE):
                return True
        return False

    def _refresh_module_cache(self):
        """Refresh Python's module cache after pip install"""
        refresh_code = '''
import importlib
import sys
import site

# Invalidate all module caches - this is critical for newly installed packages
importlib.invalidate_caches()

# Clear any cached failed imports
_failed_modules = [name for name in sys.modules if sys.modules[name] is None]
for name in _failed_modules:
    del sys.modules[name]

# Refresh user site-packages path
try:
    user_site = site.getusersitepackages()
    if user_site:
        # Remove and re-add to ensure it's at the front
        if user_site in sys.path:
            sys.path.remove(user_site)
        sys.path.insert(0, user_site)
except Exception:
    pass

# Also refresh the standard site-packages
try:
    for path in site.getsitepackages():
        if path not in sys.path:
            sys.path.insert(0, path)
except Exception:
    pass

print("[Kernel] Module cache refreshed - new packages should now be importable")
'''
        try:
            # Execute and wait for completion (not silent, so we see the confirmation)
            msg_id = self.kc.execute(refresh_code)
            # Wait for execution to complete
            while True:
                try:
                    msg = self.kc.get_iopub_msg(timeout=5)
                    if msg['header']['msg_type'] == 'status':
                        if msg['content'].get('execution_state') == 'idle':
                            break
                except Exception:
                    break
            print("[Kernel] Module cache refreshed after pip install")
        except Exception as e:
            print(f"[Kernel] Failed to refresh module cache: {e}")

    def execute_streaming(self, code: str, timeout: int = 60):
        """
        Execute code and yield outputs as they come in (generator).

        Yields:
            {"type": "execution_count", "count": int}
            {"type": "stream", "name": "stdout/stderr", "text": str}
            {"type": "execute_result", "data": dict}
            {"type": "display_data", "data": dict}
            {"type": "error", "ename": str, "evalue": str, "traceback": list}
            {"type": "status", "status": "complete/error"}
        """
        if not self.is_alive():
            yield {"type": "error", "ename": "KernelError", "evalue": "Kernel is not running", "traceback": []}
            yield {"type": "status", "status": "error"}
            return

        # Check if this is a pip install command
        is_pip_install = self._is_pip_install(code)

        self.execution_count += 1
        current_count = self.execution_count

        # Send execution count first
        yield {"type": "execution_count", "count": current_count}

        try:
            # Execute the code
            msg_id = self.kc.execute(code)

            # Track if we've seen the execution start
            execution_started = False

            # Stream outputs as they arrive
            while True:
                try:
                    msg = self.kc.get_iopub_msg(timeout=timeout)
                    msg_type = msg['header']['msg_type']
                    content = msg['content']

                    # Check if this message belongs to our execution
                    parent_msg_id = msg.get('parent_header', {}).get('msg_id', '')
                    is_our_msg = (parent_msg_id == msg_id)

                    if msg_type == 'status' and is_our_msg:
                        execution_state = content.get('execution_state', '')
                        if execution_state == 'busy':
                            execution_started = True
                        elif execution_state == 'idle' and execution_started:
                            # If this was a pip install, refresh module cache
                            if is_pip_install:
                                self._refresh_module_cache()

                            # Check for pager output BEFORE sending complete status
                            # (for %pinfo, ?, ?? etc.)
                            # Need to loop through shell messages to find ours (queue may have old msgs)
                            try:
                                found_our_reply = False
                                max_attempts = 20  # Increased for busy queues
                                for attempt in range(max_attempts):
                                    try:
                                        reply = self.kc.get_shell_msg(timeout=0.2)
                                        reply_parent = reply.get('parent_header', {}).get('msg_id', '')

                                        if reply_parent == msg_id:
                                            reply_content = reply.get('content', {})
                                            payloads = reply_content.get('payload', [])

                                            for payload in payloads:
                                                if payload.get('source') == 'page':
                                                    data = payload.get('data', {})
                                                    text = data.get('text/plain', '')
                                                    if text:
                                                        yield {
                                                            "type": "stream",
                                                            "name": "stdout",
                                                            "text": text
                                                        }
                                            found_our_reply = True
                                            break  # Found our reply, stop looking
                                        # If not our message, continue looking
                                    except queue.Empty:
                                        if found_our_reply or attempt >= 5:
                                            break  # Give up after 5 empty attempts
                                        continue  # Keep trying
                            except Exception as e:
                                # Log error but don't fail the execution
                                from backend.utils.util_func import log_debug_message
                                log_debug_message(f"[Kernel] Shell msg error (non-fatal): {e}")

                            yield {"type": "status", "status": "complete"}
                            break

                    elif msg_type == 'stream' and is_our_msg:
                        yield {
                            "type": "stream",
                            "name": content.get('name', 'stdout'),
                            "text": content.get('text', '')
                        }

                    elif msg_type == 'execute_result' and is_our_msg:
                        yield {
                            "type": "execute_result",
                            "data": content.get('data', {}),
                            "execution_count": content.get('execution_count')
                        }

                    elif msg_type == 'display_data' and is_our_msg:
                        yield {
                            "type": "display_data",
                            "data": content.get('data', {})
                        }

                    elif msg_type == 'error' and is_our_msg:
                        yield {
                            "type": "error",
                            "ename": content.get('ename', 'Error'),
                            "evalue": content.get('evalue', ''),
                            "traceback": content.get('traceback', [])
                        }

                except queue.Empty:
                    yield {"type": "error", "ename": "TimeoutError", "evalue": "Execution timed out", "traceback": []}
                    yield {"type": "status", "status": "error"}
                    break

        except Exception as e:
            yield {"type": "error", "ename": "ExecutionError", "evalue": str(e), "traceback": []}
            yield {"type": "status", "status": "error"}
