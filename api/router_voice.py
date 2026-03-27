import asyncio
import base64
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional

from core.voice_handler import voice_handler, VoiceSession
from core.llm_client import LLMClient
from core.safeguard import SafeGuard

router = APIRouter(prefix="/api/voice", tags=["voice"])


# ============ Voice Schemas ============

class TTSRequest(BaseModel):
    """TTS synthesis request"""
    text: str
    voice: Optional[str] = "zh-CN-XiaoxiaoNeural"


class ASRRequest(BaseModel):
    """ASR transcription request"""
    language: Optional[str] = "zh"


# ============ Voice Endpoints ============

@router.post("/tts")
async def text_to_speech(request: TTSRequest):
    """
    Convert text to speech.

    Returns:
        Audio file (MP3)
    """
    try:
        import edge_tts
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="edge-tts not installed. Run: pip install edge-tts"
        )

    audio_data = await voice_handler.tts.synthesize(request.text)

    if not audio_data:
        raise HTTPException(status_code=500, detail="TTS synthesis failed")

    return StreamingResponse(
        iter([audio_data]),
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": "attachment; filename=speech.mp3"
        }
    )


@router.post("/asr")
async def speech_to_text(file: UploadFile = File(...), language: str = "zh"):
    """
    Transcribe audio file to text.

    Args:
        file: Audio file (WAV, MP3, etc.)
        language: Source language (zh/en)

    Returns:
        Transcribed text
    """
    try:
        import whisper
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="whisper not installed. Run: pip install openai-whisper"
        )

    audio_data = await file.read()

    text = await voice_handler.asr.transcribe(audio_data, language)

    return {"text": text}


@router.post("/session/create")
async def create_voice_session():
    """
    Create a new voice session.

    Returns:
        session_id for WebSocket connection
    """
    import uuid
    session_id = f"voice_{uuid.uuid4().hex[:12]}"
    session = voice_handler.create_session(session_id)
    return {"session_id": session_id}


@router.delete("/session/{session_id}")
async def delete_voice_session(session_id: str):
    """
    Delete a voice session.
    """
    success = voice_handler.end_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "success"}


# ============ Voice WebSocket ============

@router.websocket("/ws/{session_id}")
async def voice_websocket(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time voice dialogue.

    Protocol:
    - Client sends: {"type": "audio", "data": "<base64>"}
    - Client sends: {"type": "text", "text": "hello"}
    - Server sends: {"type": "transcription", "text": "..."}
    - Server sends: {"type": "audio", "data": "<base64>"}
    - Server sends: {"type": "response", "text": "..."}
    """
    await websocket.accept()

    session = voice_handler.get_session(session_id)
    if not session:
        session = voice_handler.create_session(session_id)

    llm = LLMClient()
    safeguard = SafeGuard()
    dialogue_history = []

    try:
        while session.is_active:
            # Receive message
            data = await websocket.receive_text()
            message = json.loads(data)

            msg_type = message.get("type")

            if msg_type == "audio":
                # Process audio
                audio_b64 = message.get("data", "")
                audio_data = base64.b64decode(audio_b64)

                # Transcribe
                text = await session.process_audio(audio_data)
                if text:
                    await websocket.send_json({
                        "type": "transcription",
                        "text": text
                    })

                    # Safety check
                    safety_result = safeguard.check_user_input(text)
                    if not safety_result.is_safe:
                        # Send safety warning
                        await websocket.send_json({
                            "type": "safety_warning",
                            "risk_level": safety_result.risk_level.value,
                            "message": safety_result.message
                        })
                        continue

                    # Add to dialogue
                    dialogue_history.append({"role": "user", "content": text})

                    # Get LLM response
                    system_prompt = llm.build_system_prompt()
                    user_prompt = f"User said: {text}\n\nPlease respond as Oscar, the philosophical consultant."

                    response = await llm.generate(system_prompt, user_prompt)

                    # Add to dialogue
                    dialogue_history.append({"role": "oscar", "content": response})

                    # Send response text
                    await websocket.send_json({
                        "type": "response",
                        "text": response
                    })

                    # Generate speech
                    audio = await session.generate_speech(response)
                    if audio:
                        audio_b64 = base64.b64encode(audio).decode()
                        await websocket.send_json({
                            "type": "audio",
                            "data": audio_b64
                        })

            elif msg_type == "text":
                # Process text directly
                text = message.get("text", "")

                # Safety check
                safety_result = safeguard.check_user_input(text)
                if not safety_result.is_safe:
                    await websocket.send_json({
                        "type": "safety_warning",
                        "risk_level": safety_result.risk_level.value,
                        "message": safety_result.message
                    })
                    continue

                dialogue_history.append({"role": "user", "content": text})

                # Get LLM response
                system_prompt = llm.build_system_prompt()
                user_prompt = f"User said: {text}\n\nPlease respond as Oscar."

                response = await llm.generate(system_prompt, user_prompt)
                dialogue_history.append({"role": "oscar", "content": response})

                await websocket.send_json({
                    "type": "response",
                    "text": response
                })

                # Generate speech
                audio = await session.generate_speech(response)
                if audio:
                    audio_b64 = base64.b64encode(audio).decode()
                    await websocket.send_json({
                        "type": "audio",
                        "data": audio_b64
                    })

            elif msg_type == "stop":
                session.is_active = False
                break

    except WebSocketDisconnect:
        voice_handler.end_session(session_id)
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })
        voice_handler.end_session(session_id)


# ============ Helper ============

def audio_to_base64(audio_data: bytes) -> str:
    """Convert audio bytes to base64 string"""
    return base64.b64encode(audio_data).decode()


def base64_to_audio(b64_string: str) -> bytes:
    """Convert base64 string to audio bytes"""
    return base64.b64decode(b64_string)
