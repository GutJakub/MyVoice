from myvoice.actions.system import SystemActions
import re

class CommandRouter:

    GOOGLE_SEARCH_PREFIXES = (
        "search google for ",
        "start google for ",
    )

    KNOWN_APPLICATIONS = {
        "spotify",
        "calculator",
        "notepad",
    }

    def __init__(self, system_actions: SystemActions):
        self.system_actions = system_actions

    def route(self, text: str) -> str | None:
        command = self._normalize(text)

        application = self._extract_argument(
            command=command,
            prefixes=("open ",),
        )

        if application in self.KNOWN_APPLICATIONS:
            return self.system_actions.open_application(
                application
            )
        
        if command in {
            "what time is it",
            "what's the time",
            "tell me the time",
        }:
            return self.system_actions.get_time()

        if command in {
            "open vs code",
            "open vscode",
            "open visual studio code",
        }:
            return self.system_actions.open_vscode()

        if command == "open youtube":
            return self.system_actions.open_website(
                "https://www.youtube.com"
            )

        if command == "open google":
            return self.system_actions.open_website(
                "https://www.google.com"
            )

        if command in {
            "play", "start",
            "pause", "stop",
            "play music",
            "pause music",
        }:
            return self.system_actions.play_pause()

        if command in {
            "next",
            "next song",
            "next track",
        }:
            return self.system_actions.next_track()

        if command in {
            "previous",
            "previous song",
            "previous track",
        }:
            return self.system_actions.previous_track()

        if command in {
            "mute",
            "mute volume",
            "mute audio",
        }:
            return self.system_actions.mute()

        if command in {
            "volume up",
            "turn volume up",
        }:
            return self.system_actions.volume_up()

        if command in {
            "volume down",
            "turn volume down",
        }:
            return self.system_actions.volume_down()
        
        google_query = self._extract_argument(
            command=command,
            prefixes=self.GOOGLE_SEARCH_PREFIXES,
        )
        if google_query:
            return self.system_actions.search_google(
                google_query
            )

        volume = self._extract_volume(command)
        if volume is not None:
            return self.system_actions.set_volume(volume)

        return None

        
    def _extract_volume(self, command: str) -> int | None:
        match = re.search(r"set volume to (\d{1,3})", command)

        if match is None:
            return None

        return int(match.group(1))
    
    @staticmethod
    def _extract_argument(
        command: str,
        prefixes: tuple[str, ...],
    ) -> str | None:
        for prefix in prefixes:
            if command.startswith(prefix):
                return command.removeprefix(prefix).strip()

        return None
    

    @staticmethod
    def _normalize(text: str) -> str:
        return (
            text
            .lower()
            .strip()
            .rstrip(".?!")
            .lstrip("Hey Jarvis,")
        )