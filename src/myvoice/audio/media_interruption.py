from enum import Enum

from myvoice.integrations.windows_audio import WindowsAudioController


class InterruptionMode(str, Enum):
    MUTE = "mute"
    VOLUME_DOWN = "volume_down"
    PAUSE = "pause"


class MediaInterruptionController:
    def __init__(
        self,
        audio_controller: WindowsAudioController,
        mode: InterruptionMode,
        listening_volume: int = 6,
    ):
        self.audio_controller = audio_controller
        self.mode = mode
        self.listening_volume = listening_volume

    def interrupt(self) -> None:
        if self.mode == InterruptionMode.MUTE:
            self.audio_controller.mute()

        elif self.mode == InterruptionMode.VOLUME_DOWN:
            self.audio_controller.set_volume(
                self.listening_volume
            )

        elif self.mode == InterruptionMode.PAUSE:
            self.audio_controller.play_pause()

    def restore(self) -> None:
        if self.mode == InterruptionMode.MUTE:
            self.audio_controller.mute()

        elif self.mode == InterruptionMode.PAUSE:
            self.audio_controller.play_pause()