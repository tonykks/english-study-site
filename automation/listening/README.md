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
# Set GOOGLE_CLOUD_PROJECT; default location is global for gemini-3.1-flash-lite
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
| Sections | Full Script divided into natural story/topic sections (YouTube chapters preferred) |
| `02_core.txt` | One **verbatim** core sentence per section (`[Sentence N]` = Hangman source) |
| `03_summary.txt` | One summary part per section (`[Part N]`); count must match `02_core.txt` |
| `05_wordcard.txt` | Quality-first vocabulary (~10 typical; not a fixed count); 8 fields each |
| KR translation | Literal (직역) via `LITERAL_KR_INSTRUCTION`; model KR fields are re-translated |

## Pipeline

1. YouTube captions (required; ASR-only without captions → **BLOCKED** in V1)
2. Vertex AI ASR cross-validation (google-genai + ADC, Google Cloud Credit)
3. Coverage / gap / duplicate / order validation
4. Deterministic `04_full_script.txt` EN + literal KR per paragraph
5. Section inference → Core + Summary per section; Word Cards with level-aware selection
6. Stage → validate → publish

## Vertex AI defaults

- Model: `gemini-3.1-flash-lite`
- Location: `global` (multi-region endpoint per Google lifecycle docs)

## Tests

```bash
python -m pytest automation/listening/tests/ -q
```

## Safety

- Staging before publish; duplicate rejection; rollback on failure
- OpenAI fallback **disabled** unless `ALLOW_OPENAI_FALLBACK=1` (Owner opt-in)
- Without captions or Vertex ADC → `BLOCKED`
