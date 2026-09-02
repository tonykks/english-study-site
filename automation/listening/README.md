# English Listening Content Automation V1

Automates adding new Listening content from a YouTube URL + Level (1/2/3).

## Prerequisites

- Python 3.10+
- `yt-dlp` and `ffmpeg` on PATH
- Google Cloud project with Vertex AI enabled
- Application Default Credentials (ADC): `gcloud auth application-default login`

## Setup

```bash
pip install -r automation/listening/requirements.txt
cp .env.example .env
# Set GOOGLE_CLOUD_PROJECT and optional GOOGLE_CLOUD_LOCATION
```

## Usage

```bash
# Real run (captions + Vertex ASR cross-validation + ADC)
python -m automation.listening.add --url "https://youtu.be/VIDEO_ID" --level 2

# Dry-run
python -m automation.listening.add --url "https://youtu.be/VIDEO_ID" --level 2 --dry-run

# Fixture test (no Vertex / network)
python -m automation.listening.add --fixture sample_segments.json --level 2
```

## Content standards

| File | Standard |
|------|----------|
| `02_core.txt` | **12** `[Sentence N]` blocks |
| `03_summary.txt` | **5** `[Part N]` blocks |
| `05_wordcard.txt` | **10** `[Card N]` blocks (8 fields each) |
| KR translation | Literal (직역), preserving English structure |

## Pipeline

1. YouTube captions (required; ASR-only without captions → **BLOCKED** in V1)
2. Vertex AI ASR cross-validation (google-genai + ADC, Google Cloud Credit)
3. Coverage / gap / duplicate / order validation
4. Deterministic `04_full_script.txt` EN + literal KR per paragraph
5. Generate `00~03`, `05` via Vertex AI (Data Maker quality)
6. Stage → validate → publish

## Tests

```bash
python -m pytest automation/listening/tests/ -q
```

## Safety

- Staging before publish; duplicate rejection; rollback on failure
- OpenAI fallback **disabled** unless `ALLOW_OPENAI_FALLBACK=1` (Owner opt-in)
- Without captions or Vertex ADC → `BLOCKED`
