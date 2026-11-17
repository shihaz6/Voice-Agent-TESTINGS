# Voice Agent

LiveKit voice-call agent using Groq for speech-to-text (Whisper), the LLM (`openai/gpt-oss-120b`) and text-to-speech (Orpheus).

Groq's Orpheus TTS model requires accepting its terms once at
https://console.groq.com/playground?model=canopylabs%2Forpheus-v1-english

## Setup (Windows)

Requires Python 3.10–3.13 (3.15 is not yet supported by `livekit-blingfire`).

```powershell
python -m pip install --user uv
python -m uv python install 3.12
python -m uv venv --python 3.12 .venv
python -m uv pip install --python .venv\Scripts\python.exe -r requirements.txt
.\.venv\Scripts\python.exe agent.py download-files
```

Copy `.env.example` to `.env.local` and fill in:
- `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`: LiveKit Cloud dashboard → Settings → API Keys
- `GROQ_API_KEY`: console.groq.com → API Keys

## Run

```powershell
.\.venv\Scripts\python.exe agent.py console   # talk to it in the terminal with your mic
.\.venv\Scripts\python.exe agent.py start     # register with LiveKit Cloud
```

Test from the browser via the LiveKit Cloud dashboard **Sandbox → Agents Playground**.
