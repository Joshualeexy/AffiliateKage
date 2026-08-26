import requests
import json
import time
import subprocess
import os
import signal
from pathlib import Path

class ComfyClient:
    """
    Client for interacting with a local ComfyUI server with automated process management and retries.
    """

    def __init__(
        self,
        workflow_path: str = "workflow.json",
        output_dir: str = "generated",
        comfy_server_process=None,  # For backward compatibility
    ):
        from config import COMFY_URL, COMFY_TIMEOUT, COMFY_STEPS, COMFY_MAX_RETRIES
        self.server = COMFY_URL or "http://127.0.0.1:8188"
        self.timeout_seconds = COMFY_TIMEOUT
        self.default_steps = COMFY_STEPS
        self.max_retries = COMFY_MAX_RETRIES
        self.client_id = "comfy_client_" + str(int(time.time()))
        self.session = requests.Session()

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        self.logs_dir = Path("logs")
        self.logs_dir.mkdir(exist_ok=True)
        self.log_file_path = self.logs_dir / "comfyui.log"

        with open(workflow_path, "r", encoding="utf-8") as f:
            self.workflow = json.load(f)

    def is_server_running(self) -> bool:
        """Check if ComfyUI server responds to HTTP requests."""
        try:
            response = self.session.get(self.server, timeout=2)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def start_server(self):
        """Starts the ComfyUI server as a background process and waits for it to become available."""
        from config import COMFY_START_CMD

        # If already responsive, reuse running server
        if self.is_server_running():
            print("ComfyUI server is already running and responsive.")
            return

        print("Starting ComfyUI server...")
        self.log_file = open(self.log_file_path, "a", encoding="utf-8")
        self.comfy_process = subprocess.Popen(
            COMFY_START_CMD,
            shell=True,
            executable="/bin/bash",
            stdout=self.log_file,
            stderr=subprocess.STDOUT,
            preexec_fn=os.setsid,  # To allow killing the whole process group
        )

        # Poll until server is up
        max_attempts = 120  # Can take a moment to load weights
        for i in range(max_attempts):
            if self.is_server_running():
                print("ComfyUI server is ready.")
                time.sleep(2)  # Extra moment to initialize endpoints
                return
            time.sleep(1)

        print("Warning: ComfyUI server did not respond in time. Attempting anyway.")

    def stop_server(self):
        """Stops the ComfyUI server and closes logs."""
        if hasattr(self, "comfy_process") and self.comfy_process:
            print("Stopping ComfyUI server...")
            try:
                os.killpg(os.getpgid(self.comfy_process.pid), signal.SIGTERM)
                self.comfy_process.wait(timeout=10)
            except Exception as e:
                print(f"Failed to cleanly stop ComfyUI: {e}")
                try:
                    os.killpg(os.getpgid(self.comfy_process.pid), signal.SIGKILL)
                except Exception:
                    pass
            self.comfy_process = None
            print("ComfyUI server stopped.")

        if hasattr(self, "log_file") and self.log_file and not self.log_file.closed:
            try:
                self.log_file.close()
            except Exception:
                pass
            self.log_file = None

    def generate(
        self,
        prompt: str,
        negative_prompt: str | None = None,
        checkpoint: str = "juggernautXL_ragnarok.safetensors",
        width: int = 1344,
        height: int = 768,
        steps: int | None = None,
        cfg: float = 7,
        sampler: str = "euler",
        scheduler: str = "normal",
        denoise: float = 1.0,
        batch_size: int = 1,
        seed: int | None = None,
        filename_prefix: str = "featured",
        max_retries: int | None = None,
    ) -> str:
        """
        Generate an image using ComfyUI with automatic process restart on failure or timeout.

        Returns:
            Local path to the generated image.
        """
        target_steps = steps if steps is not None else self.default_steps
        retries = max_retries if max_retries is not None else self.max_retries

        workflow = self.workflow.copy()
        workflow["4"]["inputs"]["ckpt_name"] = checkpoint

        # Positive Prompt
        workflow["6"]["inputs"]["text"] = prompt

        # Negative Prompt (optional override)
        if negative_prompt:
            workflow["7"]["inputs"]["text"] = negative_prompt

        # Image Size
        workflow["5"]["inputs"]["width"] = width
        workflow["5"]["inputs"]["height"] = height
        workflow["5"]["inputs"]["batch_size"] = batch_size

        # Sampler Settings
        workflow["3"]["inputs"]["steps"] = target_steps
        workflow["3"]["inputs"]["cfg"] = cfg
        workflow["3"]["inputs"]["sampler_name"] = sampler
        workflow["3"]["inputs"]["scheduler"] = scheduler
        workflow["3"]["inputs"]["denoise"] = denoise

        # Random Seed
        workflow["3"]["inputs"]["seed"] = (
            seed if seed is not None else int(time.time()) % (2**63 - 1)
        )

        # Output filename
        workflow["9"]["inputs"]["filename_prefix"] = filename_prefix

        # Attempt generation with automatic process restart on failure
        for attempt in range(1, retries + 1):
            try:
                self.start_server()
                print(f"Submitting image generation prompt (attempt {attempt}/{retries}, {target_steps} steps)...")
                response = self.session.post(
                    f"{self.server}/prompt",
                    json={
                        "prompt": workflow,
                        "client_id": self.client_id,
                    },
                    timeout=30,
                )
                response.raise_for_status()
                prompt_id = response.json()["prompt_id"]
                image_path = self._wait_for_image(prompt_id, timeout_seconds=self.timeout_seconds)
                return image_path
            except Exception as e:
                print(f"ComfyUI generation attempt {attempt}/{retries} failed: {e}")
                self.stop_server()
                if attempt < retries:
                    print("Restarting ComfyUI process in 5 seconds...")
                    time.sleep(5)
                else:
                    raise
            finally:
                self.stop_server()

    def _wait_for_image(self, prompt_id: str, timeout_seconds: int = 600) -> str:
        """
        Wait until ComfyUI finishes generation, monitoring progress and errors.
        """
        start_time = time.time()
        last_progress_log = 0

        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                raise TimeoutError(
                    f"ComfyUI generation timed out after {timeout_seconds}s for prompt {prompt_id}"
                )

            # Periodic progress heartbeat
            if elapsed - last_progress_log >= 20:
                print(f"Rendering image in ComfyUI... ({int(elapsed)}s elapsed / {timeout_seconds}s max)")
                last_progress_log = elapsed

            try:
                response = self.session.get(
                    f"{self.server}/history/{prompt_id}",
                    timeout=30,
                )
                response.raise_for_status()
                history = response.json()
            except requests.exceptions.RequestException:
                time.sleep(2)
                continue

            if prompt_id not in history:
                time.sleep(1)
                continue

            item = history[prompt_id]

            # Check for error status reported by ComfyUI
            status_info = item.get("status", {})
            if status_info.get("status_str") == "error":
                messages = status_info.get("messages", [])
                raise RuntimeError(f"ComfyUI execution error: {messages}")

            outputs = item.get("outputs", {})
            for node in outputs.values():
                if "images" not in node or not node["images"]:
                    continue
                image = node["images"][0]
                return self._download(image)

            time.sleep(1)

    def _download(self, image: dict) -> str:
        """
        Download generated image from ComfyUI.
        """
        response = self.session.get(
            f"{self.server}/view",
            params={
                "filename": image["filename"],
                "subfolder": image["subfolder"],
                "type": image["type"],
            },
            timeout=60,
        )
        response.raise_for_status()

        output = self.output_dir / image["filename"]
        output.write_bytes(response.content)
        return str(output.resolve())