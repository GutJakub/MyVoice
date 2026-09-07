import subprocess
import tempfile
from pathlib import Path


class WindowsAudioController:
    VOLUME_DOWN_KEY = "0xAE"
    VOLUME_UP_KEY = "0xAF"
    VOLUME_MUTE_KEY = "0xAD"

    MEDIA_NEXT_KEY = "0xB0"
    MEDIA_PREVIOUS_KEY = "0xB1"
    MEDIA_PLAY_PAUSE_KEY = "0xB3"

    def set_volume(self, level: int) -> None:
            if not 0 <= level <= 100:
                raise ValueError("Volume level must be between 0 and 100.")
    
            volume_steps = level // 2
    
            script = self._build_volume_script(
                volume_steps=volume_steps,
            )
            self._run_powershell_script(script)

    def mute(self) -> None:
        self.press_media_key(
            self.VOLUME_MUTE_KEY
        )

    def volume_up(self) -> None:
        self.press_media_key(
            self.VOLUME_UP_KEY
        )

    def volume_down(self) -> None:
        self.press_media_key(
            self.VOLUME_DOWN_KEY
        )

    def play_pause(self) -> None:
        self.press_media_key(
            self.MEDIA_PLAY_PAUSE_KEY
        )

    def next_track(self) -> None:
        self.press_media_key(
            self.MEDIA_NEXT_KEY
        )

    def previous_track(self) -> None:
        self.press_media_key(
            self.MEDIA_PREVIOUS_KEY
        )

    def press_media_key(self, key: str) -> None:
        script = f"""
Add-Type @"
using System;
using System.Runtime.InteropServices;

public class AudioKeys
{{
    [DllImport("user32.dll")]
    public static extern void keybd_event(
        byte bVk,
        byte bScan,
        uint dwFlags,
        UIntPtr dwExtraInfo
    );
}}
"@

[AudioKeys]::keybd_event(
    {key},
    0,
    0,
    [UIntPtr]::Zero
)

Start-Sleep -Milliseconds 50

[AudioKeys]::keybd_event(
    {key},
    0,
    2,
    [UIntPtr]::Zero
)
"""
        self._run_powershell_script(script)

    def _build_volume_script(
        self,
        volume_steps: int,
    ) -> str:
        return f"""
Add-Type @"
using System;
using System.Runtime.InteropServices;

public class AudioKeys
{{
    [DllImport("user32.dll")]
    public static extern void keybd_event(
        byte bVk,
        byte bScan,
        uint dwFlags,
        UIntPtr dwExtraInfo
    );
}}
"@

function Press-Key([byte]$key) {{
    [AudioKeys]::keybd_event(
        $key,
        0,
        0,
        [UIntPtr]::Zero
    )

    Start-Sleep -Milliseconds 20

    [AudioKeys]::keybd_event(
        $key,
        0,
        2,
        [UIntPtr]::Zero
    )
}}

1..50 | ForEach-Object {{
    Press-Key {self.VOLUME_DOWN_KEY}
}}

1..{volume_steps} | ForEach-Object {{
    Press-Key {self.VOLUME_UP_KEY}
}}
"""

    def _run_powershell_script(
        self,
        script: str,
    ) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".ps1",
            delete=False,
        ) as script_file:
            script_file.write(script)
            script_path = Path(script_file.name)

        try:
            windows_path = subprocess.check_output(
                [
                    "wslpath",
                    "-w",
                    str(script_path),
                ],
                text=True,
            ).strip()

            subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    windows_path,
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        finally:
            script_path.unlink(
                missing_ok=True
            )