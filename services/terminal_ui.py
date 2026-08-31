import time
import os
from urllib.parse import urlparse

# ANSI Color Codes
CYAN = "\033[0;36m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
MAGENTA = "\033[0;35m"
BOLD = "\033[1m"
DIM = "\033[2m"
NC = "\033[0m"


class TerminalUI:
    """Zero-dependency terminal dashboard and progress reporter for AffiliateKage."""

    def __init__(self):
        self.pipeline_start_time = None
        self.step_start_times = {}

    @staticmethod
    def format_duration(seconds: float) -> str:
        """Format seconds into human-readable minutes and seconds (e.g., '8m 42s')."""
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}h {m}m {s}s"
        elif m > 0:
            return f"{m}m {s}s"
        else:
            return f"{s}s"

    def render_worker_card(
        self, 
        model: str = "", 
        mode: str = "Production", 
        target: str = "", 
        images: str = ""
    ):
        """Render the stylish AFFILIATEKAGE WORKER status box."""
        self.pipeline_start_time = time.time()

        # Parse target domain cleanly from API_URL if not provided
        if not target:
            api_url = os.getenv("API_URL", "")
            target = urlparse(api_url).netloc.replace("api.", "") or "ejiroinspire.com"

        model = model or os.getenv("OLLAMA_MODEL", "qwen3-coder:30b")
        images = images or os.getenv("IMAGE_PROVIDER", "comfyui").upper()

        inner_width = 39

        def pad_line(label: str, val: str) -> str:
            val_str = str(val)[:inner_width - 12]
            text = f" {label:<9} {val_str}"
            spaces = inner_width - len(text)
            return f"│{text}{' ' * max(0, spaces)}│"

        print()
        print(f"{CYAN}╭{'─' * inner_width}╮{NC}")
        print(f"{CYAN}│{BOLD}         AFFILIATEKAGE WORKER          {NC}{CYAN}│{NC}")
        print(f"{CYAN}├{'─' * inner_width}┤{NC}")
        print(f"{CYAN}{pad_line('Model:', model)}{NC}")
        print(f"{CYAN}{pad_line('Mode:', mode)}{NC}")
        print(f"{CYAN}{pad_line('Target:', target)}{NC}")
        print(f"{CYAN}{pad_line('Images:', images)}{NC}")
        print(f"{CYAN}╰{'─' * inner_width}╯{NC}")
        print()

    def start_step(self, step_num: int, label: str):
        """Record start time and display in-progress step."""
        self.step_start_times[step_num] = time.time()
        num_str = f"[{step_num:02d}]"
        print(f"{CYAN}{num_str}{NC} {label}...", flush=True)

    def complete_step(self, step_num: int, label: str, detail: str = ""):
        """Mark a step as completed with elapsed time and clean details."""
        elapsed = ""
        if step_num in self.step_start_times:
            secs = time.time() - self.step_start_times[step_num]
            elapsed = f" {DIM}({self.format_duration(secs)}){NC}"

        num_str = f"[{step_num:02d}]"
        if detail:
            print(f"{GREEN}{num_str} ✓{NC} {label}: {BOLD}{detail}{NC}{elapsed}", flush=True)
        else:
            print(f"{GREEN}{num_str} ✓{NC} {label}{elapsed}", flush=True)

    def render_publish_card(self, title: str, slug: str = ""):
        """Display the final published accomplishment card with total elapsed time."""
        total_time_str = "0s"
        if self.pipeline_start_time:
            total_seconds = time.time() - self.pipeline_start_time
            total_time_str = self.format_duration(total_seconds)

        inner_width = 56
        top_border = "─" * inner_width
        
        # Word wrap title if longer than inner width - 4
        title_lines = []
        words = title.split()
        curr_line = ""
        for w in words:
            if len(curr_line) + len(w) + 1 <= inner_width - 4:
                curr_line = f"{curr_line} {w}".strip()
            else:
                title_lines.append(curr_line)
                curr_line = w
        if curr_line:
            title_lines.append(curr_line)

        print()
        print(f"{GREEN}╭{top_border}╮{NC}")
        print(f"{GREEN}│{NC} {BOLD}✓ Published:{NC}{' ' * (inner_width - 13)}{GREEN}│{NC}")
        for tl in title_lines:
            spaces = inner_width - len(tl) - 3
            print(f"{GREEN}│{NC}   {BOLD}{tl}{NC}{' ' * max(0, spaces)}{GREEN}│{NC}")
        print(f"{GREEN}│{' ' * inner_width}│{NC}")
        
        total_line = f"Total: {total_time_str}"
        spaces_total = inner_width - len(total_line) - 2
        print(f"{GREEN}│{NC} {CYAN}{total_line}{NC}{' ' * max(0, spaces_total)}{GREEN}│{NC}")
        print(f"{GREEN}╰{top_border}╯{NC}")
        print()


# Global singleton instance for easy import across modules
ui = TerminalUI()
