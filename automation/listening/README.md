# English Listening Content Automation V1

Automates adding new Listening content from a YouTube URL + Level (1/2/3).

## Prerequisites

- Python 3.10+
- `yt-dlp` on PATH (for ASR audio download)
- `GOOGLE_API_KEY` in `.env` (Gemini ASR cross-validation + translation)

## Setup

```bash
pip install -r automation/listening/requirements.txt
cp .env.example .env
# Edit .env with your GOOGLE_API_KEY
```

## Usage

```bash
# Real run (requires captions + API key + yt-dlp)
python -m automation.listening.add --url "https://youtu.be/VIDEO_ID" --level 2

# Dry-run (stage + validate, no publish)
python -m automation.listening.add --url "https://youtu.be/VIDEO_ID" --level 2 --dry-run

# Fixture test (no network / API)
python -m automation.listening.add --fixture sample_segments.json --level 2
```

## Pipeline

1. Fetch YouTube captions (manual EN preferred, auto fallback)
2. Vertex/Gemini ASR cross-validation
3. Coverage / gap / duplicate / order validation
4. Deterministic `04_full_script.txt` EN assembly + KR translation
5. Generate `00~03`, `05` via LLM
6. Stage → validate → publish to `pages/listening/levelX/<folder>/`
7. Idempotent `listeningCards` append in `pages/listening/index.html`

## Tests

```bash
python -m pytest automation/listening/tests/ -q
```

## Safety

- Writes to `automation/.staging/<video_id>/` before publish
- Duplicate `video_id` / folder / href rejected
- Publish failure triggers index backup restore
- Without `GOOGLE_API_KEY`, real YouTube runs return `BLOCKED`
