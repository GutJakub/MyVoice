import subprocess
from datetime import datetime
from urllib.parse import quote_plus
from myvoice.integrations.windows_audio import (
    WindowsAudioController,
)

class SystemActions:

    WINDOWS_APPLICATIONS = {
        "spotify": "spotify:",
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
    }

    def __init__(
            self,
            audio_controller: WindowsAudioController,
    ):
        self.audio_controller = audio_controller

    def mute(self) -> str:
        self.audio_controller.mute()
        return "Muted."


    def volume_up(self) -> str:
        self.audio_controller.volume_up()
        return "Volume up."


    def volume_down(self) -> str:
        self.audio_controller.volume_down()
        return "Volume down."


    def play_pause(self) -> str:
        self.audio_controller.play_pause()
        return "Play pause."


    def next_track(self) -> str:
        self.audio_controller.next_track()
        return "Next track."

    def previous_track(self) -> str:
        self.audio_controller.previous_track()
        return "Previous track."
    
    def open_application(self, application: str) -> str:
        target = self.WINDOWS_APPLICATIONS.get(
            application
        )

        if target is None:
            return f"I don't know the application {application}."

        subprocess.Popen(
            [
                "powershell.exe",
                "-Command",
                f"Start-Process '{target}'",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        return f"Opening {application}."

    def get_time(self) -> str:
        current_time = datetime.now().strftime("%H:%M")

        return f"It is {current_time}."

    def open_website(self, url: str) -> str:
        subprocess.Popen(
        [
            "powershell.exe",
            "-Command",
            f"Start-Process '{url}'",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

        return f"Opening {url}."

    def search_google(self, query: str) -> str:
        encoded_query = quote_plus(query)

        url = f"https://www.google.com/search?q={encoded_query}"

        subprocess.Popen(
        [
            "powershell.exe",
            "-Command",
            f"Start-Process '{url}'",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

        return f"Searching Google for {query}."

    def set_volume(self, level: int) -> str:
        self.audio_controller.set_volume(level)

        return f"Setting volume to {level} percent."

    
    