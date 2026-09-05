"""Z3RO / SOBIA — Real-Time WebSocket UI Bridge.

Provides a bi-directional local WebSocket server on ws://127.0.0.1:8765 connecting
the Electron Dynamic Island desktop overlay to the agent, models, and voice pipeline.
"""

import sys
import os
import json
import asyncio
import time
import threading
from typing import Set, Optional, Any
from pathlib import Path

import numpy as np
import sounddevice as sd
import websockets

from z3ro.config import config
from z3ro.logger import Colors, logger
from z3ro.agent import Z3ROAgent
from z3ro.voice.stt import STT
from z3ro.voice.tts import TTS


class UIBridgeServer:
    """Async WebSocket server bridging Electron front-end and Python AI engine."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
        self.clients: Set[Any] = set()

        # Engine components (lazy loaded)
        self.agent: Optional[Z3ROAgent] = None
        self.stt: Optional[STT] = None
        self.tts: Optional[TTS] = None

        # State management
        self.is_recording = False
        self.current_recording_chunks = []
        self.is_generating = False
        self._abort_flag = False
        self._mic_stream = None

    def initialize_components(self):
        """Initialize AI agent and voice components."""
        if self.agent is None:
            logger.info("Initializing Agent for UI Bridge...")
            self.agent = Z3ROAgent()
        if self.stt is None:
            logger.info("Initializing STT for UI Bridge...")
            self.stt = STT()
        if self.tts is None:
            logger.info("Initializing Neural TTS for UI Bridge...")
            self.tts = TTS()

    async def broadcast(self, message: dict):
        """Broadcast JSON message to all connected Electron frontends."""
        if not self.clients:
            return
        payload = json.dumps(message)
        to_remove = set()
        for client in self.clients:
            try:
                await client.send(payload)
            except Exception:
                to_remove.add(client)
        self.clients.difference_update(to_remove)

    async def handle_client(self, websocket: Any):
        """Handle incoming WebSocket client connections and messages."""
        self.clients.add(websocket)
        logger.info(f"Electron UI connected: {websocket.remote_address}")

        # Send initial status
        await websocket.send(
            json.dumps({
                "type": "init",
                "name": config.ASSISTANT_NAME,
                "brain_model": config.BRAIN_MODEL,
                "vision_model": config.VISION_MODEL,
                "tts_voice": config.TTS_VOICE,
                "status": "idle",
            })
        )

        try:
            async for raw_message in websocket:
                try:
                    data = json.loads(raw_message)
                    msg_type = data.get("type", "")

                    if msg_type == "chat":
                        text = data.get("text", "").strip()
                        if text:
                            asyncio.create_task(self.process_chat(text))

                    elif msg_type == "start_mic":
                        self.start_mic_recording()

                    elif msg_type == "stop_mic":
                        asyncio.create_task(self.stop_mic_recording_and_process())

                    elif msg_type == "stop_generation":
                        self.stop_generation()

                    elif msg_type == "set_name":
                        name = data.get("name", "").strip()
                        if name:
                            config.ASSISTANT_NAME = name
                            await self.broadcast({"type": "status", "state": "idle", "name": name})

                except json.JSONDecodeError:
                    pass
                except Exception as e:
                    logger.error(f"Error handling UI message: {e}")

        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.discard(websocket)
            logger.info("Electron UI disconnected.")

    def start_mic_recording(self):
        """Begin capturing audio chunks from the microphone."""
        if self.is_recording:
            return

        self.is_recording = True
        self.current_recording_chunks = []
        asyncio.create_task(self.broadcast({"type": "status", "state": "listening"}))

        rate = config.AUDIO_SAMPLE_RATE

        def callback(indata, frames, time_info, status):
            if not self.is_recording:
                return
            chunk = indata[:, 0].copy()
            self.current_recording_chunks.append(chunk)

            # Broadcast live volume level (RMS) for the wave visualizer
            rms = float(np.sqrt(np.mean(chunk**2)))
            level = min(rms * 15, 1.0)
            asyncio.run_coroutine_threadsafe(
                self.broadcast({"type": "audio_level", "level": level}),
                self.loop,
            )

        try:
            self._mic_stream = sd.InputStream(
                device=config.MIC_DEVICE_INDEX,
                samplerate=rate,
                channels=1,
                dtype="float32",
                blocksize=1600,
                callback=callback,
            )
            self._mic_stream.start()
        except Exception as e:
            logger.error(f"Failed to open microphone stream: {e}")
            self.is_recording = False
            asyncio.create_task(self.broadcast({"type": "status", "state": "idle", "error": str(e)}))

    async def stop_mic_recording_and_process(self):
        """Stop mic stream, transcribe audio with Whisper, and run agent."""
        if not self.is_recording:
            return

        self.is_recording = False
        if self._mic_stream:
            try:
                self._mic_stream.stop()
                self._mic_stream.close()
            except Exception:
                pass
            self._mic_stream = None

        if not self.current_recording_chunks:
            await self.broadcast({"type": "status", "state": "idle"})
            return

        await self.broadcast({"type": "status", "state": "transcribing"})

        audio_data = np.concatenate(self.current_recording_chunks).flatten()
        duration = len(audio_data) / config.AUDIO_SAMPLE_RATE
        logger.info(f"Transcribing {duration:.1f}s of speech...")

        # Transcribe in background thread to avoid blocking event loop
        def do_stt():
            self.initialize_components()
            return self.stt.transcribe(audio_data, sample_rate=config.AUDIO_SAMPLE_RATE)

        transcript = await asyncio.to_thread(do_stt)
        transcript = transcript.strip()

        if not transcript:
            await self.broadcast({"type": "status", "state": "idle", "message": "No speech heard."})
            return

        await self.broadcast({"type": "transcript", "text": transcript})
        await self.process_chat(transcript)

    async def process_chat(self, user_input: str):
        """Process user instruction through Agent (Qwen chat / Action planner)."""
        if self.is_generating:
            return

        self.is_generating = True
        self._abort_flag = False
        self.initialize_components()

        # Step 1: Thinking state & release Electron keyboard focus
        await self.broadcast({"type": "blur_focus"})
        await self.broadcast({"type": "status", "state": "thinking", "prompt": user_input})

        def run_agent():
            return self.agent.handle(user_input)

        try:
            results = await asyncio.to_thread(run_agent)

            if self._abort_flag:
                await self.broadcast({"type": "status", "state": "idle", "message": "Stopped."})
                return

            response_text = " ".join(results) if results else "Done."
            await self.broadcast({"type": "response", "text": response_text})

            # Step 2: Speaking state
            await self.broadcast({"type": "status", "state": "speaking", "text": response_text})

            def speak_response():
                if not self._abort_flag:
                    self.tts.speak(response_text)

            await asyncio.to_thread(speak_response)

        except Exception as e:
            logger.error(f"Error processing chat in UI bridge: {e}")
            await self.broadcast({"type": "error", "error": str(e)})

        finally:
            self.is_generating = False
            await self.broadcast({"type": "status", "state": "idle"})

    def stop_generation(self):
        """Abort current generation or stop audio playback immediately."""
        logger.info("Stop generation requested from UI.")
        self._abort_flag = True
        self.is_generating = False
        try:
            sd.stop()  # Stop any active audio playback immediately
        except Exception:
            pass
        asyncio.create_task(self.broadcast({"type": "status", "state": "idle", "message": "Generation stopped."}))

    async def run_server(self):
        """Start and run the WebSocket server."""
        self.loop = asyncio.get_running_loop()
        self.initialize_components()

        # Start real-time downloads and apps watcher with overlay notification
        def on_app_detected(app_name: str, app_path: str):
            if hasattr(self, "loop") and self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self.broadcast({
                        "type": "action",
                        "description": f"Indexed {app_name}",
                    }),
                    self.loop,
                )

        try:
            from z3ro.app_watcher import start_app_watcher
            start_app_watcher(on_new_app=on_app_detected)
        except Exception as e:
            logger.debug(f"Could not start app watcher from UI bridge: {e}")

        logger.info(f"Starting UI Bridge server on ws://{self.host}:{self.port}")
        async with websockets.serve(self.handle_client, self.host, self.port):
            await asyncio.Future()  # run forever


def start_ui_bridge():
    """Entrypoint to run the UI bridge server."""
    bridge = UIBridgeServer()
    try:
        asyncio.run(bridge.run_server())
    except KeyboardInterrupt:
        logger.info("UI Bridge shutting down.")


if __name__ == "__main__":
    start_ui_bridge()
