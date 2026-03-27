import asyncio
import base64
import json
from typing import Optional, AsyncIterator
from dataclasses import dataclass


@dataclass
class VoiceConfig:
    """Voice configuration"""
    asr_model: str = "base"  # tiny/base/small/medium/large
    tts_voice: str = "zh-CN-XiaoxiaoNeural"  # Default Chinese voice
    tts_rate: str = "+0%"  # Speech rate adjustment
    tts_pitch: str = "+0Hz"  # Pitch adjustment


class WhisperASR:
    """
    Whisper-based Automatic Speech Recognition.

    Supports local inference with various model sizes.
    """

    def __init__(self, model_size: str = "base"):
        self.model_size = model_size
        self.model = None

    def load_model(self):
        """Load Whisper model"""
        try:
            import whisper
            self.model = whisper.load_model(self.model_size)
            print(f"Whisper model '{self.model_size}' loaded successfully")
        except ImportError:
            print("Whisper not installed. Run: pip install openai-whisper")
            self.model = None

    async def transcribe(
        self,
        audio_data: bytes,
        language: str = "zh"
    ) -> str:
        """
        Transcribe audio to text.

        Args:
            audio_data: Raw audio bytes ( WAV or MP3)
            language: Source language code (zh/en)

        Returns:
            Transcribed text
        """
        if self.model is None:
            self.load_model()

        if self.model is None:
            return ""

        # Save audio to temp file
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_data)
            temp_path = f.name

        try:
            # Run transcription
            result = self.model.transcribe(
                temp_path,
                language=language if language != "zh" else "Chinese",
                fp16=False  # Use CPU
            )
            return result.get("text", "").strip()
        finally:
            os.unlink(temp_path)

    async def transcribe_chunk(
        self,
        audio_data: bytes,
        language: str = "zh"
    ) -> str:
        """Transcribe audio chunk (for streaming)"""
        return await self.transcribe(audio_data, language)


class EdgeTTS:
    """
    Edge TTS (Text-to-Speech) client.

    Uses Microsoft Edge's neural voices for high-quality Chinese TTS.
    """

    def __init__(
        self,
        voice: str = "zh-CN-XiaoxiaoNeural",
        rate: str = "+0%",
        pitch: str = "+0Hz"
    ):
        self.voice = voice
        self.rate = rate
        self.pitch = pitch

    async def synthesize(
        self,
        text: str,
        output_format: str = "audio-24khz-48kbitrate-mono-mp3"
    ) -> bytes:
        """
        Synthesize text to speech.

        Args:
            text: Text to synthesize
            output_format: Audio format

        Returns:
            Audio bytes
        """
        try:
            import edge_tts
        except ImportError:
            print("edge-tts not installed. Run: pip install edge-tts")
            return b""

        communicate = edge_tts.Communicate(
            text,
            voice=self.voice,
            rate=self.rate,
            pitch=self.pitch
        )

        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]

        return audio_data

    async def synthesize_to_file(
        self,
        text: str,
        output_path: str
    ) -> bool:
        """
        Synthesize text to audio file.

        Args:
            text: Text to synthesize
            output_path: Output file path

        Returns:
            True if successful
        """
        try:
            import edge_tts
        except ImportError:
            return False

        communicate = edge_tts.Communicate(
            text,
            voice=self.voice,
            rate=self.rate,
            pitch=self.pitch
        )

        await communicate.save(output_path)
        return True


class VoiceSession:
    """
    Voice session manager for real-time voice dialogue.
    """

    def __init__(
        self,
        session_id: str,
        asr: WhisperASR = None,
        tts: EdgeTTS = None
    ):
        self.session_id = session_id
        self.asr = asr or WhisperASR()
        self.tts = tts or EdgeTTS()
        self.is_active = False

    async def process_audio(
        self,
        audio_chunk: bytes,
        language: str = "zh"
    ) -> str:
        """
        Process incoming audio and return transcription.

        Args:
            audio_chunk: Audio data bytes
            language: Source language

        Returns:
            Transcribed text
        """
        if not audio_chunk:
            return ""

        text = await self.asr.transcribe(audio_chunk, language)
        return text

    async def generate_speech(
        self,
        text: str
    ) -> bytes:
        """
        Generate speech from text.

        Args:
            text: Text to speak

        Returns:
            Audio bytes
        """
        if not text:
            return b""

        audio = await self.tts.synthesize(text)
        return audio

    async def stream_speech(
        self,
        text: str
    ) -> AsyncIterator[bytes]:
        """
        Stream speech audio in chunks.

        Args:
            text: Text to speak

        Yields:
            Audio chunks
        """
        try:
            import edge_tts
        except ImportError:
            return

        communicate = edge_tts.Communicate(
            text,
            voice=self.tts.voice,
            rate=self.tts.rate,
            pitch=self.tts.pitch
        )

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]


class VoiceHandler:
    """
    Main voice handler managing voice sessions.
    """

    def __init__(self):
        self.sessions = {}
        self.asr = WhisperASR()
        self.tts = EdgeTTS()

    def create_session(self, session_id: str) -> VoiceSession:
        """Create a new voice session"""
        session = VoiceSession(
            session_id=session_id,
            asr=self.asr,
            tts=self.tts
        )
        self.sessions[session_id] = session
        session.is_active = True
        return session

    def get_session(self, session_id: str) -> Optional[VoiceSession]:
        """Get existing session"""
        return self.sessions.get(session_id)

    def end_session(self, session_id: str) -> bool:
        """End a voice session"""
        session = self.sessions.get(session_id)
        if session:
            session.is_active = False
            del self.sessions[session_id]
            return True
        return False


# Global voice handler instance
voice_handler = VoiceHandler()
