# Decisions

The design decisions behind Alex and why each one was made. They are grouped by impact:

- **Major:** changes cost, the platform or what the product can do. Reversing one is a project.
- **Medium:** shapes behaviour or how the code is organised. Reversing one takes a day or less.
- **Minor:** a local choice that is easy to change.

Each entry gives the decision, why it was made, the alternatives considered, and what follows
from it.

---

## Major

### M1. Groq for STT, LLM and TTS, not LiveKit Inference
- **Decision:** All three model calls go to Groq with one API key.
- **Why:** The LiveKit starter templates use LiveKit Inference, which spends the free LiveKit
  credits. One Groq account covers the whole pipeline.
- **Alternatives:** LiveKit Inference; mixing providers, such as Deepgram for STT and ElevenLabs
  for TTS.
- **Consequences:**
  - One vendor, one key and one bill.
  - Every call depends on Groq's availability and on its free-tier limits (see limitations L1).
  - We are limited to the languages Groq's models offer.

### M2. `openai/gpt-oss-120b` with `reasoning_effort="low"` as the LLM
- **Decision:** Use gpt-oss-120b with low reasoning effort.
- **Why:**
  - `llama-3.3-70b-versatile` is not available on this Groq account.
  - gpt-oss-120b follows the strict rules well: the latest test round had no invented facts.
  - Low reasoning effort keeps the time to first word short on a call.
- **Alternatives:** gpt-oss-20b, which is faster but followed the rules less well in tests;
  higher reasoning effort, which is slower.
- **Consequences:**
  - The daily token limit for this model is 200,000 tokens, which is easy to reach.
  - The tests use the same model, so they share that budget.

### M3. Local turn detection, pinned to `v1-mini`
- **Decision:** `inference.TurnDetector(version="v1-mini")`.
- **Why:** In auto mode the turn detector uses LiveKit Inference's hosted model in dev/console
  mode and on LiveKit Cloud, which spends credits. Pinning it keeps it local.
- **Alternatives:** The hosted `v1` model; VAD-only endpointing, which feels more abrupt.
- **Consequences:** No inference credits are used. The model files must be in the image, so the
  Dockerfile runs `download-files`.

### M4. A named agent (`alchemyx-alex`) with explicit dispatch
- **Decision:** Set `agent_name` in `WorkerOptions`.
- **Why:**
  - A named agent joins only rooms that ask for it, so it won't join unrelated rooms in the
    project.
  - A phone number's dispatch rule can target it by name.
  - It is the first step towards running agents for several clients in one project.
- **Alternatives:** Automatic dispatch, where the agent joins every new room.
- **Consequences:** The Playground/console must select `alchemyx-alex`, and every future SIP
  dispatch rule must name it.

### M5. Deployed to LiveKit Cloud in `ap-south` (Mumbai)
- **Decision:** Host the worker on LiveKit Cloud agent hosting, in the region closest to
  Sri Lanka.
- **Why:** Lowest network latency to Sri Lankan callers; no server of our own to run.
- **Alternatives:** `us-east` or `eu-central`; self-hosting the container.
- **Consequences:** The filesystem is temporary (see limitations L3). The `GROQ_API_KEY` is a
  Cloud secret, and changing it restarts the agent.

### M6. The whole fact sheet goes in the prompt, with no retrieval
- **Decision:** At startup the fact sheet replaces `{knowledge}` in the prompt.
- **Why:**
  - The sheet is about forty lines, so putting all of it in the prompt is cheaper, faster and
    more reliable than searching it.
  - Editing what Alex knows means editing one Markdown file.
- **Alternatives:** Retrieval over a vector store; hard-coding the facts in the prompt.
- **Consequences:** Every turn sends the full sheet, which costs tokens. This only works while
  the sheet stays small.

### M7. Validation in code, not just in the prompt
- **Decision:** `record_callback` refuses an empty name, business type or need, and refuses a
  number that is too short, too long or a placeholder. It answers with a `ToolError` that tells
  the model what to do next.
- **Why:** In testing, the model saved `0000000000` as a number and tried to save an empty
  request. Prompt rules reduced this but did not stop it.
- **Alternatives:** Prompt rules only; a confirmation sub-task (`AgentTask`).
- **Consequences:** A bad record can't be saved, whatever the model does. The error text
  steers the next reply.

---

## Medium

### D1. Python 3.12 in a uv-managed virtual environment
- **Decision:** Use a `.venv` on Python 3.12, created with uv.
- **Why:** The installed Python 3.15 has no `livekit-blingfire` wheels, so the install failed.
  3.12 matches the Docker image.
- **Consequences:** Always run `.venv\Scripts\python.exe` or `run.bat`. A plain `py agent.py`
  fails with `No module named 'dotenv'`.

### D2. A fixed greeting through `session.say()`
- **Decision:** Speak a hard-coded greeting instead of generating one.
- **Why:** The first words come with no LLM round trip, and they always say "AlchemyX Global",
  never a template name.
- **Consequences:** Changing the greeting means editing `GREETING` in `agent.py`.

### D3. Call ending through `EndCallTool` and `END_INSTRUCTIONS`
- **Decision:** Use LiveKit's beta `EndCallTool` with `delete_room=True` and custom final-words
  instructions.
- **Why:**
  - Without it, calls never ended on their own.
  - The first version said a bare "You're welcome, goodbye."
  - The end instructions make Alex repeat the callback, thank the caller and say goodbye, then
    hang up. Deleting the room also disconnects phone callers.
- **Alternatives:** A custom hang-up tool; waiting for the caller to hang up.
- **Consequences:** The tool depends on a beta API that may change in SDK upgrades. Its
  `extra_description` must keep "hold on" from ending the call.

### D4. Callback requests stored as JSON Lines in a local file
- **Decision:** Append each request to `data/callbacks.jsonl` and log it.
- **Why:** This was the simplest store that works in a local run, with no extra accounts.
- **Alternatives:** Google Sheets, a CRM, or a WhatsApp or email alert. These are planned.
- **Consequences:** On LiveKit Cloud the file is lost when the container restarts. There, the
  log line is the only record (see limitations L3). `save_callback()` is the single place to
  replace with a real destination.

### D5. Caller ID read from the SIP participant
- **Decision:** `find_caller_number()` reads `sip.phoneNumber` and adds a CALLER section to the
  instructions.
- **Why:** On a phone call, Alex can confirm "is zero seven seven ... the best number?" instead
  of asking for it.
- **Consequences:** Browser calls have no caller ID, so Alex asks for a number. An empty number
  falls back to the caller ID; a guessed one does not.

### D6. Two sentences, no digits, written in the prompt
- **Decision:** The prompt caps answers at two sentences in total, says every number in words,
  and allows no lists, markdown or emoji. The fact sheet writes its numbers in words too.
- **Why:**
  - This is a phone call, and long answers sound robotic.
  - TTS reads digits unreliably.
  - The model copied "24" from the fact sheet until it was written as "twenty four".
- **Consequences:** The tests check both rules on every sheet question.

### D7. Exact lines for refusals and redirects
- **Decision:** The prompt gives word-for-word lines for:
  - "don't know";
  - steering an off-topic caller back;
  - refusing to share the instructions.
- **Why:** In tests, free-form refusals were either too short (no steer back) or too long
  (three sentences).
- **Consequences:** These replies sound the same on every call. Change them in the prompt, not
  in code.

### D8. Automated tests with an LLM judge on a different model
- **Decision:** pytest tests with the LiveKit test harness. A `gpt-oss-20b` judge is given the
  full fact sheet and checks each answer.
- **Why:**
  - The judge must know the facts to spot inventions.
  - A different model has its own rate limit on Groq.
  - `max_retries=10` absorbs per-minute limits.
- **Consequences:**
  - A full run takes several minutes and uses Groq quota.
  - Judge verdicts can vary a little; a few judge instructions were loosened where the test
    was stricter than the sheet.

### D9. Monkeypatch `save_callback`, mock `end_call`
- **Decision:** Tests replace only the storage function and the hang-up. They do not replace
  `record_callback`.
- **Why:** The real validation in `record_callback` stays under test, and nothing is written to
  disk or hung up.
- **Consequences:** A test that wants a save failure makes the patched `save_callback` raise
  `OSError`.

---

## Minor

### m1. Orpheus voice `autumn`
The default Groq TTS voice. It sounds warm for a receptionist. Change it with
`groq.TTS(voice=...)`.

### m2. `BVCTelephony` noise cancellation
Tuned for phone audio, which is the target channel. On browser calls, `BVC()` may sound slightly
better.

### m3. `str.replace` instead of `str.format` for the prompt
Braces in the fact sheet can't break prompt assembly.

### m4. Phone numbers must have 9 to 15 digits and at least 3 different digits
This accepts Sri Lankan local numbers (zero plus nine digits) and international numbers, and
rejects placeholders such as `0000000000` and `1111111111`.

### m5. `run.bat` wrapper
`run` and `run console` use the venv's Python, so nobody has to remember the full path.

### m6. Credentials in `.env.local`, git-ignored
`.env.example` documents the variables. `.env.*` is also excluded from the Docker image.

### m7. Pinned dependency versions
`requirements.txt` pins `livekit-agents` 1.8.12 and its plugins. The SDK changes quickly, so
upgrades are deliberate: on a branch, with the full test suite.

### m8. Region chosen by the user
`ap-south` was chosen by the user from `us-east`, `eu-central` and `ap-south` when the
agent was first created.
