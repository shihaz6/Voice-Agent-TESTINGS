"""Alex, the AlchemyX Global AI receptionist (LiveKit voice agent).

Groq STT -> Groq LLM -> Groq TTS, with local Silero VAD and local turn detection.
The company facts in knowledge/ are inserted into the prompt in prompts/ at startup.
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from livekit import agents
from livekit.agents import (
    Agent,
    AgentSession,
    RunContext,
    ToolError,
    function_tool,
    inference,
    room_io,
)
from livekit.plugins import groq, noise_cancellation, silero

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env.local")

KNOWLEDGE_FILE = ROOT / "knowledge" / "alchemyx_facts.md"
PROMPT_FILE = ROOT / "prompts" / "alex_instructions.md"
CALLBACKS_FILE = ROOT / "data" / "callbacks.jsonl"

AGENT_NAME = "alchemyx-alex"

GREETING ="Hi, thanks for calling AlchemyX Global, this is Alex. How can I help you today?"

logger = logging.getLogger("alex")


def build_instructions(caller_number: str | None = None) -> str:
    facts = KNOWLEDGE_FILE.read_text(encoding="utf-8")
    prompt = PROMPT_FILE.read_text(encoding="utf-8")
    # str.replace, not str.format, so braces in the facts can't break the prompt.
    text = prompt.replace("{knowledge}", facts)
    if caller_number:
        text += (
            "\n\nCALLER\n"
            f"- The caller is phoning from {caller_number}. When taking a callback, read this "
            "number back in words and ask if it is the best number to reach them."
        )
    else:
        text += (
            "\n\nCALLER\n"
            "- The caller's number is not available. When taking a callback, ask for the best "
            "number to reach them and read it back in words to confirm."
        )
    return text


def build_llm(**overrides) -> groq.LLM:
    # Low reasoning effort keeps the time to first word short on a call.
    return groq.LLM(model="openai/gpt-oss-120b", reasoning_effort="low", **overrides)


def normalize_phone(phone_number: str) -> str | None:
    """Digits of a plausible phone number, or None for empty or placeholder values."""
    digits = re.sub(r"\D", "", phone_number or "")
    if not 9 <= len(digits) <= 15 or len(set(digits)) < 3:
        return None
    return digits


def save_callback(record: dict) -> None:
    CALLBACKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with CALLBACKS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


class Alex(Agent):
    def __init__(self, caller_number: str | None = None) -> None:
        super().__init__(instructions=build_instructions(caller_number))
        self._caller_number = caller_number

    @function_tool
    async def record_callback(
        self,
        context: RunContext,
        name: str,
        business_type: str,
        need: str,
        phone_number: str,
    ) -> str:
        """Save a callback request for the AlchemyX team. Call this only once you have the
        caller's name, business type and need, and the caller has confirmed the phone number.
        Never make up or use a placeholder number.

        Args:
            name: The caller's name.
            business_type: The caller's type of business, for example tuition class or pharmacy.
            need: What the caller needs, in a few words.
            phone_number: The number the caller confirmed, as digits only.
        """
        phone = normalize_phone(phone_number) or (
            normalize_phone(self._caller_number) if not phone_number else None
        )
        if not phone:
            raise ToolError(
                "Not saved: no valid phone number. Ask the caller for the best number to "
                "reach them, read it back in words, and save again once they confirm."
            )
        if not name.strip():
            raise ToolError("Not saved: ask the caller for their name first.")

        record = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "name": name.strip(),
            "business_type": business_type.strip(),
            "need": need.strip(),
            "phone_number": phone,
            "caller_id": self._caller_number,
        }
        try:
            save_callback(record)
        except OSError as e:
            logger.exception("failed to save callback request")
            raise ToolError(
                "Not saved because of a system error. Tell the caller plainly that you "
                "couldn't save their callback request just now, do not say the team will "
                "call them, and suggest they message AlchemyX Global on Facebook, Instagram, "
                "TikTok or LinkedIn instead."
            ) from e
        logger.info("callback saved: %s", record)
        return (
            "Saved. Tell the caller the team will contact them. When the caller says goodbye, "
            "repeat the request back in one natural sentence, thank them and say goodbye, "
            f'for example: "So the team will call {record["name"]} about {record["need"]} '
            f'for your {record["business_type"]}. Thanks for calling AlchemyX Global, goodbye!"'
        )


def find_caller_number(room) -> str | None:
    # Set for phone (SIP) callers; absent for browser callers such as the Agents Playground.
    try:
        for p in room.remote_participants.values():
            if number := p.attributes.get("sip.phoneNumber"):
                return number
    except Exception:  # console mode has no real room
        pass
    return None


async def entrypoint(ctx: agents.JobContext):
    alex = Alex()
    session = AgentSession(
        stt=groq.STT(model="whisper-large-v3-turbo"),
        llm=build_llm(),
        tts=groq.TTS(),
        vad=silero.VAD.load(),
        # Pinned to the local model. Left on auto, it uses LiveKit Inference's
        # hosted "v1" model in console/dev mode or when deployed to LiveKit Cloud.
        turn_detection=inference.TurnDetector(version="v1-mini"),
    )

    await session.start(
        room=ctx.room,
        agent=alex,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                # BVCTelephony is tuned for phone-call (SIP) audio.
                noise_cancellation=noise_cancellation.BVCTelephony(),
            ),
        ),
    )

    if caller_number := find_caller_number(ctx.room):
        alex._caller_number = caller_number
        await alex.update_instructions(build_instructions(caller_number))

    # Fixed greeting: no LLM round trip, and always names AlchemyX Global.
    session.say(GREETING)


if __name__ == "__main__":
    # A named agent is only sent to rooms that explicitly request it (a dispatch rule,
    # a token, or the API), not to every new room.
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint, agent_name=AGENT_NAME))
