import asyncio 
import base64
import os
import shutil
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, Union, List
import uuid

OUTPUT_DIR = "/tmp/outputs"

class ToolError(Exception):
    pass

class ToolResult:
    def __init__(self, output: Optional[str] = None, error: Optional[str] = None, base64_image: Optional[str] = None):
        self.output = output
        self.error = error
        self.base64_image = base64_image

    def replace(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        return self

class ComputerTool:
    def __init__(self):
        self.width = int(os.getenv("WIDTH", "1024"))
        self.height = int(os.getenv("HEIGHT", "768"))
        self.display_num = int(os.getenv("DISPLAY_NUM", "1"))
        self._display_prefix = f"DISPLAY=:{self.display_num} "
        self._screenshot_delay = 2.0
        self.xdotool = f"{self._display_prefix}xdotool"

    async def __call__(
        self,
        action: str,
        text: Optional[str] = None,
        coordinate: Optional[Tuple[int, int]] = None,
        **kwargs
    ) -> ToolResult:
        if action in ("mouse_move", "left_click_drag"):
            if not coordinate:
                raise ToolError("coordinate is required for mouse actions")
            if not isinstance(coordinate, (list, tuple)) or len(coordinate) != 2:
                raise ToolError("coordinate must be a tuple/list of length 2") 
            x, y = coordinate
            if not all(isinstance(i, int) and i >= 0 for i in (x,y)):
                raise ToolError("coordinates must be non-negative integers")
                
            if action == "mouse_move":
                return await self._run_command(f"{self.xdotool} mousemove --sync {x} {y}")
            else:  # left_click_drag
                return await self._run_command(
                    f"{self.xdotool} mousedown 1 mousemove --sync {x} {y} mouseup 1"
                )

        elif action in ("key", "type"):
            if not text:
                raise ToolError("text is required for keyboard actions")
            if coordinate:
                raise ToolError("coordinate not accepted for keyboard actions")

            if action == "key":
                return await self._run_command(f"{self.xdotool} key -- {text}")
            else:  # type
                return await self._run_command(f"{self.xdotool} type -- {text}")

        elif action in ("left_click", "right_click", "middle_click", "double_click", "screenshot", "cursor_position"):
            if text:
                raise ToolError(f"text not accepted for {action}")
            if coordinate:
                raise ToolError(f"coordinate not accepted for {action}")

            if action == "screenshot":
                return await self.take_screenshot()
            elif action == "cursor_position":
                return await self.get_cursor_position()
            else:
                click_map = {
                    "left_click": "1",
                    "right_click": "3", 
                    "middle_click": "2",
                    "double_click": "--repeat 2 --delay 500 1"
                }
                return await self._run_command(f"{self.xdotool} click {click_map[action]}")

        raise ToolError(f"Invalid action: {action}")

    async def take_screenshot(self) -> ToolResult:
        output_dir = Path(OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = output_dir / f"screenshot_{uuid.uuid4().hex}.png"

        if shutil.which("gnome-screenshot"):
            cmd = f"{self._display_prefix}gnome-screenshot -f {screenshot_path}"
        else:
            cmd = f"{self._display_prefix}scrot {screenshot_path}"

        result = await self._run_command(cmd, take_screenshot=False)
        if screenshot_path.exists():
            return result.replace(
                base64_image=base64.b64encode(screenshot_path.read_bytes()).decode()
            )
        raise ToolError(f"Failed to take screenshot: {result.error}")

    async def get_cursor_position(self) -> ToolResult:
        result = await self._run_command(
            f"{self.xdotool} getmouselocation --shell",
            take_screenshot=False
        )
        output = result.output or ""
        try:
            x = int(output.split("X=")[1].split("\n")[0])
            y = int(output.split("Y=")[1].split("\n")[0])
            return result.replace(output=f"X={x},Y={y}")
        except:
            raise ToolError("Failed to parse cursor position")

    async def _run_command(self, command: str, take_screenshot: bool = True) -> ToolResult:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        result = ToolResult(
            output=stdout.decode() if stdout else None,
            error=stderr.decode() if stderr else None
        )

        if take_screenshot:
            await asyncio.sleep(self._screenshot_delay)
            screenshot = await self.take_screenshot()
            result.base64_image = screenshot.base64_image

        return result