# Audio Retrieval from Meta Ray-Ban Glasses

## Overview

This document summarises findings on how audio can be retrieved from Meta Ray-Ban smart glasses, based on analysis of:

1. **Meta Wearables DAT SDK** (Device Access Toolkit for iOS, v0.4.0)
2. **VisionClaw** — a real-time Gemini-powered AI assistant for Meta Ray-Ban glasses

The key finding is that **no public SDK or application captures raw Bluetooth audio packets**. All known implementations rely on the OS Bluetooth audio profile (HFP/A2DP) to route the glasses microphone as a standard system audio input.

---

## Meta Wearables DAT SDK (iOS)

### What the SDK Provides

The DAT SDK (v0.4.0, released 2026-02-03) is Meta's official developer toolkit for accessing Ray-Ban smart glasses from iOS apps. It is distributed as a Swift Package with three modules:

| Module | Purpose |
|--------|---------|
| `MWDATCore` | Device registration, permissions, lifecycle |
| `MWDATCamera` | Video streaming and photo capture |
| `MWDATMockDevice` | Simulated devices for testing (DEBUG only) |

### Audio Status: Not Yet Public

Audio streaming is **not exposed** in the current public API (v0.4.0). However, the infrastructure exists internally:

- `StreamSessionError.audioStreamingError` — a dedicated error case for audio failures
- "Open-Ear Audio" is mentioned in UI text as a glasses feature
- The streaming architecture (publisher/listener pattern) is designed for multiple media channels

Audio will likely appear in a future SDK release (the error handling and architecture are already in place).

### Connection Architecture

The SDK uses **iOS External Accessory Framework**, not raw BLE GATT:

- **Protocol**: `com.meta.ar.wearable` (declared in `Info.plist`)
- **Auth**: OAuth 2.0 flow through the Meta AI companion app
- **Pairing**: Handled by Meta AI app, not by the developer's app
- **Background modes**: `bluetooth-peripheral` and `external-accessory`

### Required Configuration (Info.plist)

```xml
<key>MWDAT</key>
<dict>
    <key>AppLinkURLScheme</key>
    <string>cameraaccess://</string>
    <key>MetaAppID</key>
    <string>$(META_APP_ID)</string>
    <key>ClientToken</key>
    <string>$(CLIENT_TOKEN)</string>
    <key>TeamID</key>
    <string>$(DEVELOPMENT_TEAM)</string>
</dict>

<key>UISupportedExternalAccessoryProtocols</key>
<array>
    <string>com.meta.ar.wearable</string>
</array>
```

### Video Streaming (for reference)

While audio is gated, video streaming is fully available:

```swift
let config = StreamSessionConfig(
    videoCodec: .raw,
    resolution: .medium,  // 504x896
    frameRate: 24
)
let session = StreamSession(streamSessionConfig: config, deviceSelector: AutoDeviceSelector)
session.start()

session.videoFramePublisher.listen { frame in
    let image = frame.makeUIImage()
}
```

---

## VisionClaw — Audio Pipeline

VisionClaw is a production app that streams glasses audio to Google's Gemini Live API for real-time voice conversation. It has both iOS and Android implementations.

### Audio Configuration

| Parameter | Input (Mic) | Output (Speaker) |
|-----------|-------------|-------------------|
| Sample rate | 16 kHz | 24 kHz |
| Channels | Mono | Mono |
| Bit depth | 16-bit Int16 | 16-bit Int16 |
| Codec | Raw PCM (no compression) | Raw PCM |
| Chunk duration | 100ms | Variable |
| Chunk size | 3200 bytes | Variable |

### How Audio Capture Works

VisionClaw does **not** capture audio directly over BLE. The flow is:

1. Glasses mic audio is routed to the phone via Classic Bluetooth (HFP/A2DP), managed by the DAT SDK
2. The app captures from the system audio input using standard platform APIs
3. Audio is accumulated into 100ms chunks and sent to Gemini

### iOS Implementation (`AudioManager.swift`)

```swift
// Configure audio session for glasses mode
let session = AVAudioSession.sharedInstance()
try session.setCategory(.playAndRecord, mode: .videoChat,
                         options: [.defaultToSpeaker, .allowBluetooth])
try session.setPreferredSampleRate(16000)

// Capture from input node
audioEngine.inputNode.installTap(bufferSize: 4096, format: nativeFormat) { buffer, _ in
    // Convert Float32 -> Int16 PCM
    let sample = Int16(clampedFloat * Float(Int16.max))
    // Accumulate into 100ms chunks (3200 bytes)
    // Fire onAudioCaptured callback when chunk ready
}
```

Two audio session modes:
- **iPhone mode** (`.voiceChat`): Aggressive echo cancellation when mic and speaker are co-located on the phone
- **Glasses mode** (`.videoChat`): Mild AEC since mic is on glasses, speaker is on phone

### Android Implementation (`AudioManager.kt`)

```kotlin
// VOICE_COMMUNICATION source includes built-in AEC
val recorder = AudioRecord(
    MediaRecorder.AudioSource.VOICE_COMMUNICATION,
    16000,
    AudioFormat.CHANNEL_IN_MONO,
    AudioFormat.ENCODING_PCM_16BIT,
    bufferSize
)

// Separate capture thread
Thread("audio-capture") {
    while (capturing) {
        recorder.read(buffer, 0, buffer.size)
        // Accumulate into 100ms chunks
        // Fire onAudioCaptured callback
    }
}
```

### End-to-End Audio Flow

```
Glasses Microphone (5 mics, beamforming)
    │
    ▼  Classic Bluetooth (HFP/A2DP) — managed by DAT SDK
Phone Audio Input (system routes glasses mic as input device)
    │
    ▼  AVAudioEngine (iOS) / AudioRecord (Android)
AudioManager
    │  Capture 16kHz PCM Int16
    │  Accumulate 100ms chunks (3200 bytes)
    │
    ▼  Base64-encode → JSON
GeminiLiveService (WebSocket)
    │  wss://generativelanguage.googleapis.com/ws/...BidiGenerateContent
    │  Model: gemini-2.5-flash-native-audio-preview
    │
    ▼  Gemini processes speech, generates response
    │
    ▼  Base64 PCM in JSON response (24kHz)
AudioManager (playback)
    │  AVAudioPlayerNode (iOS) / AudioTrack (Android)
    │
    ▼
Phone Speaker
```

### WebSocket Audio Protocol

**Sending audio to Gemini:**
```json
{
  "realtimeInput": {
    "audio": {
      "mimeType": "audio/pcm;rate=16000",
      "data": "<base64-encoded-pcm-bytes>"
    }
  }
}
```

**Receiving audio from Gemini:**
```json
{
  "serverContent": {
    "modelTurn": {
      "parts": [{
        "inlineData": {
          "mimeType": "audio/pcm;rate=24000",
          "data": "<base64-encoded-pcm-bytes>"
        }
      }]
    }
  }
}
```

### Voice Activity Detection (Gemini-side)

```json
"automaticActivityDetection": {
  "startOfSpeechSensitivity": "START_SENSITIVITY_HIGH",
  "endOfSpeechSensitivity": "END_SENSITIVITY_LOW",
  "silenceDurationMs": 500,
  "prefixPaddingMs": 40
}
```

---

## Comparison of Approaches

| Aspect | DAT SDK (iOS) | VisionClaw | Our recorder.py |
|--------|--------------|------------|-----------------|
| Platform | iOS 17+ | iOS / Android | macOS |
| Audio API | Not yet exposed | AVAudioEngine / AudioRecord | PyAudio / sounddevice |
| BT pairing | Meta AI app + OAuth | DAT SDK | macOS System Settings |
| BT transport | External Accessory protocol | DAT SDK (opaque) | Classic BT (HFP/A2DP) |
| Audio format | TBD | 16kHz PCM Int16 | Configurable |
| Output | TBD | WebSocket to Gemini | MP3 file |
| Auth required | Yes (OAuth + Meta App ID) | Yes (via DAT SDK) | No |

---

## Recommendations for This Project

### Current Viable Approach: Classic BT Audio Capture

Our `recorder.py` approach is validated by VisionClaw's architecture:

1. **Pair glasses** via macOS Bluetooth System Settings
2. **Capture audio** using system audio APIs (the OS routes the glasses mic as an input device)
3. **Encode to MP3** for storage

This works because the glasses register as a standard Bluetooth audio device (HFP/A2DP profile) once paired.

### Configuration Notes from VisionClaw

- Use **16kHz sample rate** for speech-quality capture (VisionClaw's chosen rate)
- Use **mono channel** (glasses output mono audio)
- **16-bit PCM** is the native format from the glasses mic
- **100ms chunk size** (3200 bytes) works well for real-time streaming
- For echo cancellation, use voice-communication audio source modes

### Future Options

1. **DAT SDK audio release** — Monitor for v0.5.0+ which will likely expose audio streaming via the publisher pattern (the `audioStreamingError` case already exists)
2. **HCI-level sniffing** — Use `audio_sniff.py` to capture raw Bluetooth HCI traffic and reverse-engineer the audio codec between glasses and phone (likely SBC or AAC over A2DP, mSBC/CVSD over HFP)
3. **External Accessory protocol RE** — Sniff the `com.meta.ar.wearable` protocol traffic to understand the command format Meta uses internally

### What Cannot Be Done

- Direct BLE GATT audio capture — the glasses do not expose audio over BLE characteristics
- Bypassing Meta AI app auth for DAT SDK features
- Accessing the DAT SDK's internal audio channel without an iOS/Android app

---

## References

- Meta Wearables DAT SDK v0.4.0 — `thirdparty/meta-wearables-dat-ios/`
- VisionClaw source — `thirdparty/VisionClaw/`
- Gemini Live API — `wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent`
