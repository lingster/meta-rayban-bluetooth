#!/usr/bin/env python3
"""
Audio Recorder for Meta Ray-Ban Glasses

Records audio from the glasses' microphone (paired via macOS System Settings
as a Classic Bluetooth audio device) and saves as WAV or MP3.

The glasses expose their microphone as a standard HFP/A2DP audio input once
paired over Classic Bluetooth. This recorder captures from that system input
using sounddevice (PortAudio) — the same approach used by VisionClaw and
other production apps.

Recommended settings (validated by VisionClaw / Gemini Live):
  - Sample rate: 16000 Hz (speech-optimised)
  - Channels:    1 (mono — glasses output mono)
  - Bit depth:   16-bit PCM Int16
  - Chunk size:  100ms (3200 bytes)

Requires: ffmpeg (`brew install ffmpeg`) only for MP3 encoding.
"""

import math
import struct
import sys
import signal
import threading
import time
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

import typer

try:
    import sounddevice as sd
except ImportError:
    print("Error: sounddevice is required. Install with: uv sync")
    sys.exit(1)

try:
    import soundfile as sf
except ImportError:
    print("Error: soundfile is required. Install with: uv sync")
    sys.exit(1)

# Name patterns used to auto-detect the glasses as a system audio input
GLASSES_NAME_PATTERNS = ("RB Meta", "Ray-Ban", "Meta Ray")

# Audio defaults matching VisionClaw's proven configuration
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_CHANNELS = 1
CHUNK_DURATION_MS = 100  # 100ms chunks, same as VisionClaw
LEVEL_METER_WIDTH = 30


class OutputFormat(str, Enum):
    mp3 = "mp3"
    wav = "wav"


app = typer.Typer(help="Record audio from Meta Ray-Ban glasses microphone.")


def _format_duration(seconds: float) -> str:
    """Format seconds as MM:SS or HH:MM:SS."""
    total = int(seconds)
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _rms_db(samples: bytes, num_samples: int) -> float:
    """Calculate RMS level in dB from raw PCM16 bytes."""
    if num_samples == 0:
        return -100.0
    int16_samples = struct.unpack(f"<{num_samples}h", samples[:num_samples * 2])
    sum_sq = sum(s * s for s in int16_samples)
    rms = math.sqrt(sum_sq / num_samples)
    if rms < 1:
        return -100.0
    return 20 * math.log10(rms / 32768.0)


def _render_level_bar(db: float, width: int = LEVEL_METER_WIDTH) -> str:
    """Render a text-based VU meter. Range: -60dB to 0dB."""
    clamped = max(-60.0, min(0.0, db))
    filled = int((clamped + 60.0) / 60.0 * width)
    bar = "#" * filled + "-" * (width - filled)
    return f"[{bar}] {db:+5.1f} dB"


class AudioRecorder:
    """Captures audio from a system audio input device."""

    def __init__(
        self,
        device_name: str,
        output_file: str,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        channels: int = DEFAULT_CHANNELS,
        show_level: bool = True,
    ):
        self.device_name = device_name
        self.output_file = output_file
        self.sample_rate = sample_rate
        self.channels = channels
        self.show_level = show_level
        self._stop_event = threading.Event()
        self._frames_written = 0

    @staticmethod
    def list_audio_devices() -> list[dict]:
        """Return all system audio input devices with details."""
        devices = sd.query_devices()
        inputs: list[dict] = []
        for idx, dev in enumerate(devices):
            if dev["max_input_channels"] > 0:
                inputs.append({
                    "index": idx,
                    "name": dev["name"],
                    "channels": dev["max_input_channels"],
                    "default_samplerate": dev["default_samplerate"],
                })
        return inputs

    def find_glasses_device(self) -> Optional[int]:
        """Find the glasses in the system audio device list by name pattern match."""
        for dev in self.list_audio_devices():
            if any(pattern.lower() in dev["name"].lower() for pattern in GLASSES_NAME_PATTERNS):
                return dev["index"]
        return None

    def _resolve_device_index(self) -> int:
        """Resolve the configured device name to a device index."""
        for dev in self.list_audio_devices():
            if self.device_name.lower() in dev["name"].lower():
                return dev["index"]
        raise RuntimeError(f"Audio device matching '{self.device_name}' not found.")

    def _get_device_index(self) -> int:
        """Resolve the target device index, auto-detecting glasses if needed."""
        if self.device_name:
            return self._resolve_device_index()

        device_index = self.find_glasses_device()
        if device_index is None:
            self._print_pairing_help()
            raise RuntimeError("Glasses not found as audio input device.")
        return device_index

    def record(self, duration: Optional[float] = None) -> Path:
        """Record audio and save as WAV. Returns the WAV file path."""
        device_index = self._get_device_index()
        device_info = sd.query_devices(device_index)
        wav_path = Path(self.output_file).with_suffix(".wav")

        chunk_samples = int(self.sample_rate * CHUNK_DURATION_MS / 1000)

        print(f"  Device:      {device_info['name']}")
        print(f"  Sample rate: {self.sample_rate} Hz")
        print(f"  Channels:    {self.channels}")
        print(f"  Bit depth:   16-bit PCM")
        print(f"  Chunk size:  {CHUNK_DURATION_MS}ms ({chunk_samples * 2} bytes)")
        if duration:
            print(f"  Duration:    {duration}s")
        else:
            print(f"  Duration:    unlimited (Ctrl+C to stop)")
        print()

        self._stop_event.clear()
        self._frames_written = 0
        start_time = time.monotonic()
        last_display_time = 0.0

        try:
            with sf.SoundFile(
                str(wav_path),
                mode="w",
                samplerate=self.sample_rate,
                channels=self.channels,
                format="WAV",
                subtype="PCM_16",
            ) as wav_file:

                def _callback(indata, frames, _time_info, status):
                    nonlocal last_display_time
                    if status:
                        print(f"  Warning: {status}", file=sys.stderr)
                    wav_file.write(indata)
                    self._frames_written += frames

                    if self.show_level:
                        now = time.monotonic()
                        if now - last_display_time >= 0.15:
                            last_display_time = now
                            raw = indata[:, 0] if indata.ndim > 1 else indata
                            pcm_bytes = (raw * 32767).astype("int16").tobytes()
                            db = _rms_db(pcm_bytes, len(raw))
                            elapsed = now - start_time
                            bar = _render_level_bar(db)
                            print(
                                f"\r  {_format_duration(elapsed)}  {bar}",
                                end="",
                                flush=True,
                            )

                with sd.InputStream(
                    device=device_index,
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    blocksize=chunk_samples,
                    callback=_callback,
                ):
                    if duration:
                        self._stop_event.wait(timeout=duration)
                    else:
                        self._stop_event.wait()

        except sd.PortAudioError as exc:
            raise RuntimeError(
                f"Audio device error: {exc}\n"
                "Ensure the device is not in use by another app and that "
                "microphone permissions are granted in System Settings > "
                "Privacy & Security > Microphone."
            ) from exc

        elapsed = time.monotonic() - start_time
        print(f"\n\n  Recorded {_format_duration(elapsed)} -> {wav_path}")
        return wav_path

    def stream_raw(self, duration: Optional[float] = None) -> None:
        """Stream raw PCM16 audio to stdout for piping to other tools.

        Usage examples:
          uv run src/recorder.py stream | ffmpeg -f s16le -ar 16000 -ac 1 -i - out.mp3
          uv run src/recorder.py stream | sox -t raw -r 16000 -e signed -b 16 -c 1 - out.wav
        """
        device_index = self._get_device_index()
        device_info = sd.query_devices(device_index)
        chunk_samples = int(self.sample_rate * CHUNK_DURATION_MS / 1000)

        print(f"Streaming PCM16 from: {device_info['name']}", file=sys.stderr)
        print(
            f"Format: s16le, {self.sample_rate}Hz, {self.channels}ch, "
            f"{CHUNK_DURATION_MS}ms chunks",
            file=sys.stderr,
        )
        print("Pipe stdout to ffmpeg/sox/etc. Ctrl+C to stop.\n", file=sys.stderr)

        self._stop_event.clear()
        stdout_bin = sys.stdout.buffer

        try:
            def _callback(indata, _frames, _time_info, status):
                if status:
                    print(f"Warning: {status}", file=sys.stderr)
                raw = indata[:, 0] if indata.ndim > 1 else indata
                pcm_bytes = (raw * 32767).astype("int16").tobytes()
                stdout_bin.write(pcm_bytes)
                stdout_bin.flush()

            with sd.InputStream(
                device=device_index,
                samplerate=self.sample_rate,
                channels=self.channels,
                blocksize=chunk_samples,
                callback=_callback,
            ):
                if duration:
                    self._stop_event.wait(timeout=duration)
                else:
                    self._stop_event.wait()

        except sd.PortAudioError as exc:
            raise RuntimeError(f"Audio device error: {exc}") from exc

    @staticmethod
    def convert_to_mp3(wav_path: Path, mp3_path: Path) -> Path:
        """Convert a WAV file to MP3 using pydub (requires ffmpeg)."""
        try:
            from pydub import AudioSegment
        except ImportError:
            raise RuntimeError(
                "pydub is required for MP3 conversion. Install with: uv sync"
            )

        try:
            audio = AudioSegment.from_wav(str(wav_path))
            audio.export(str(mp3_path), format="mp3")
        except Exception as exc:
            error_msg = str(exc).lower()
            if "ffmpeg" in error_msg or "ffprobe" in error_msg or "couldnt find" in error_msg:
                raise RuntimeError(
                    "ffmpeg is required for MP3 encoding.\n"
                    "Install with: brew install ffmpeg"
                ) from exc
            raise

        print(f"  Encoded MP3: {mp3_path}")
        return mp3_path

    @staticmethod
    def cleanup(wav_path: Path) -> None:
        """Remove intermediate WAV file."""
        try:
            wav_path.unlink()
        except OSError:
            pass

    def stop(self) -> None:
        """Signal the recording loop to stop."""
        self._stop_event.set()

    @staticmethod
    def _print_pairing_help() -> None:
        print("No Meta Ray-Ban glasses detected as an audio input device.\n")
        print("To pair the glasses with macOS:")
        print("  1. Open System Settings > Bluetooth")
        print("  2. Put the glasses in pairing mode:")
        print("     - Place glasses in charging case")
        print("     - Hold the button on the back of the case for 5 seconds")
        print("     - Wait until the LED turns blue")
        print("  3. Select the glasses when they appear and click Connect")
        print("  4. The glasses mic should appear as a system audio input")
        print()
        print("Troubleshooting:")
        print("  - Ensure glasses are not connected to another device")
        print("  - Check System Settings > Sound > Input for the glasses")
        print("  - Grant microphone access in Privacy & Security settings")
        print("\nUse --list-devices to see available audio inputs.")


def _default_output_name(fmt: OutputFormat) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"recording_{timestamp}.{fmt.value}"


def _install_signal_handler(recorder: AudioRecorder) -> None:
    """Install Ctrl+C handler to stop recording gracefully."""
    def _handle(_sig, _frame):
        print("\n\nStopping recording...")
        recorder.stop()
    signal.signal(signal.SIGINT, _handle)


@app.command()
def record(
    duration: Optional[float] = typer.Option(
        None, "--duration", "-d",
        help="Recording duration in seconds (default: unlimited, Ctrl+C to stop)",
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o",
        help="Output file path (default: recording_<timestamp>.<format>)",
    ),
    fmt: OutputFormat = typer.Option(
        OutputFormat.mp3, "--format", "-f",
        help="Output format: mp3 (requires ffmpeg) or wav",
    ),
    device: Optional[str] = typer.Option(
        None, "--device", "-D",
        help="Audio device name override (default: auto-detect glasses)",
    ),
    sample_rate: int = typer.Option(
        DEFAULT_SAMPLE_RATE, "--sample-rate", "-s",
        help="Sample rate in Hz (16000 recommended for speech)",
    ),
    channels: int = typer.Option(
        DEFAULT_CHANNELS, "--channels", "-c",
        help="Number of audio channels (1=mono, glasses output mono)",
    ),
    no_level: bool = typer.Option(
        False, "--no-level",
        help="Disable the live audio level meter",
    ),
) -> None:
    """Record audio from Meta Ray-Ban glasses microphone and save as MP3 or WAV."""
    output_path = output or _default_output_name(fmt)

    recorder = AudioRecorder(
        device_name=device or "",
        output_file=output_path,
        sample_rate=sample_rate,
        channels=channels,
        show_level=not no_level,
    )

    _install_signal_handler(recorder)

    print("Recording from Meta Ray-Ban glasses\n")

    try:
        wav_path = recorder.record(duration=duration)
    except RuntimeError as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        raise typer.Exit(code=1)

    if fmt == OutputFormat.mp3:
        mp3_path = Path(output_path)
        if mp3_path.suffix.lower() != ".mp3":
            mp3_path = mp3_path.with_suffix(".mp3")
        try:
            recorder.convert_to_mp3(wav_path, mp3_path)
        except RuntimeError as exc:
            print(f"\nError: {exc}", file=sys.stderr)
            print(f"  WAV file preserved at: {wav_path}")
            raise typer.Exit(code=1)
        recorder.cleanup(wav_path)
        final_path = mp3_path
    else:
        final_path = wav_path

    # Summary
    try:
        info = sf.info(str(final_path))
        print(f"\n  Done! {info.duration:.1f}s saved to {final_path}")
    except Exception:
        print(f"\n  Done! Audio saved to {final_path}")


@app.command()
def stream(
    duration: Optional[float] = typer.Option(
        None, "--duration", "-d",
        help="Stream duration in seconds (default: unlimited)",
    ),
    device: Optional[str] = typer.Option(
        None, "--device", "-D",
        help="Audio device name override (default: auto-detect glasses)",
    ),
    sample_rate: int = typer.Option(
        DEFAULT_SAMPLE_RATE, "--sample-rate", "-s",
        help="Sample rate in Hz",
    ),
    channels: int = typer.Option(
        DEFAULT_CHANNELS, "--channels", "-c",
        help="Number of audio channels",
    ),
) -> None:
    """Stream raw PCM16 audio to stdout for piping to other tools.

    Examples:

      uv run src/recorder.py stream | ffmpeg -f s16le -ar 16000 -ac 1 -i - out.mp3

      uv run src/recorder.py stream | sox -t raw -r 16000 -e signed -b 16 -c 1 - -d
    """
    recorder = AudioRecorder(
        device_name=device or "",
        output_file="",
        sample_rate=sample_rate,
        channels=channels,
        show_level=False,
    )

    _install_signal_handler(recorder)

    try:
        recorder.stream_raw(duration=duration)
    except RuntimeError as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        raise typer.Exit(code=1)


@app.command("list-devices")
def list_devices() -> None:
    """List all audio input devices and highlight detected glasses."""
    devices = AudioRecorder.list_audio_devices()
    if not devices:
        print("No audio input devices found.")
        raise typer.Exit()

    print("Audio input devices:\n")
    for dev in devices:
        is_glasses = any(
            p.lower() in dev["name"].lower() for p in GLASSES_NAME_PATTERNS
        )
        marker = "  <-- glasses" if is_glasses else ""
        print(
            f"  [{dev['index']:2d}] {dev['name']}"
            f"  ({dev['channels']}ch, {int(dev['default_samplerate'])}Hz)"
            f"{marker}"
        )
    print()


if __name__ == "__main__":
    app()
