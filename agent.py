"""Minimal LiveKit voice agent: Groq STT -> Groq LLM -> Groq TTS, Silero VAD."""

from dotenv import load_dotenv

from livekit import agents
from livekit.agents import Agent, AgentSession, inference, room_io
from livekit.plugins import groq, noise_cancellation, silero

load_dotenv(".env.local")


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are a helpful voice assistant on a phone call. "
                "Keep replies short and conversational, with no emojis or markdown."
            )
        )


async def entrypoint(ctx: agents.JobContext):
    session = AgentSession(
        stt=groq.STT(model="whisper-large-v3-turbo"),
        # Low reasoning effort keeps the time to first word short on a call.
        llm=groq.LLM(model="openai/gpt-oss-120b", reasoning_effort="low"),
        tts=groq.TTS(),
        vad=silero.VAD.load(),
        # Pinned to the local model. Left on auto, it uses LiveKit Inference's
        # hosted "v1" model in console/dev mode or when deployed to LiveKit Cloud.
        turn_detection=inference.TurnDetector(version="v1-mini"),
    )

    await session.start(
        room=ctx.room,
        agent=Assistant(),
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                # BVCTelephony is tuned for phone-call (SIP) audio.
                noise_cancellation=noise_cancellation.BVCTelephony(),
            ),
        ),
    )

    await session.generate_reply(instructions="Greet the caller and offer your help.")


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
