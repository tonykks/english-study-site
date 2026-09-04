"""Comparison run helper with Vertex call timing metrics."""

from __future__ import annotations

import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from automation.listening.config import ASR_CACHE_ROOT, COMPARISON_ROOT, load_config
from automation.listening.pipeline import run_pipeline
from automation.listening.script.canonical import consolidate_caption_segments
from automation.listening.script.golden_reference import compare_video_golden_reference
from automation.listening.utils import word_divergence
from automation.listening.youtube.duration import fetch_youtube_duration
from automation.listening.youtube.transcript import fetch_caption_segments

METRICS: dict[str, Any] = {
    "vertex_calls": 0,
    "vertex_errors": 0,
    "vertex_retries_observed": 0,
    "usage_totals": {"prompt_token_count": 0, "candidates_token_count": 0, "total_token_count": 0},
    "calls": [],
}


def _usage_from_response(response: Any) -> dict | None:
    usage = getattr(response, "usage_metadata", None)
    if not usage:
        return None
    data = {
        "prompt_token_count": getattr(usage, "prompt_token_count", None),
        "candidates_token_count": getattr(usage, "candidates_token_count", None),
        "total_token_count": getattr(usage, "total_token_count", None),
    }
    for key, val in data.items():
        if isinstance(val, int):
            METRICS["usage_totals"][key] += val
    return data


def _call_kind(prompt: str) -> str:
    if "Return valid JSON only" in prompt:
        return "generate_json"
    if "batch KR" in prompt or ('"id"' in prompt and "Input JSON:" in prompt):
        return "translate_literal_kr_batch"
    if "literal translation" in prompt.lower() or "직역" in prompt:
        return "translate_literal_kr"
    return "generate_text"


def _install_metrics_hooks() -> None:
    import automation.listening.script.vertex_transcribe as vt
    import automation.listening.vertex_client as vc

    original_transcribe = vc.transcribe_audio_bytes

    def wrapped_generate_text(prompt: str, *, timeout_sec: int = 120) -> str:
        _ = timeout_sec
        started = time.perf_counter()
        kind = _call_kind(prompt)
        client = vc._client()
        try:
            response = client.models.generate_content(model=vc.vertex_model(), contents=prompt)
            text = (response.text or "").strip()
            if not text:
                raise RuntimeError("BLOCKED: Vertex AI returned empty response")
            elapsed = time.perf_counter() - started
            METRICS["vertex_calls"] += 1
            METRICS["calls"].append(
                {
                    "kind": kind,
                    "elapsed_sec": round(elapsed, 2),
                    "prompt_chars": len(prompt),
                    "response_chars": len(text),
                    "usage": _usage_from_response(response),
                    "ok": True,
                }
            )
            return text
        except Exception as exc:
            elapsed = time.perf_counter() - started
            METRICS["vertex_errors"] += 1
            METRICS["calls"].append(
                {
                    "kind": kind,
                    "elapsed_sec": round(elapsed, 2),
                    "prompt_chars": len(prompt),
                    "error": str(exc),
                    "ok": False,
                }
            )
            raise

    def wrapped_transcribe(audio_bytes: bytes, mime_type: str = "audio/mp4") -> str:
        started = time.perf_counter()
        try:
            result = original_transcribe(audio_bytes, mime_type=mime_type)
            elapsed = time.perf_counter() - started
            METRICS["vertex_calls"] += 1
            METRICS["calls"].append(
                {
                    "kind": "transcribe_audio",
                    "elapsed_sec": round(elapsed, 2),
                    "audio_bytes": len(audio_bytes),
                    "response_chars": len(result),
                    "usage": None,
                    "ok": True,
                }
            )
            return result
        except Exception as exc:
            elapsed = time.perf_counter() - started
            METRICS["vertex_errors"] += 1
            METRICS["calls"].append(
                {
                    "kind": "transcribe_audio",
                    "elapsed_sec": round(elapsed, 2),
                    "audio_bytes": len(audio_bytes),
                    "error": str(exc),
                    "ok": False,
                }
            )
            raise

    def retry_with_metrics(audio_path: str, offset: float = 0.0):
        last_error = None
        for attempt in range(3):
            try:
                segs = vt._transcribe_audio_vertex(audio_path)
                if offset:
                    for seg in segs:
                        seg.start += offset
                        seg.end += offset
                return segs
            except Exception as exc:
                last_error = exc
                if attempt < 2:
                    METRICS["vertex_retries_observed"] += 1
        raise RuntimeError(f"BLOCKED: ASR failed after retries: {last_error}")

    vc.generate_text = wrapped_generate_text  # type: ignore[method-assign]
    vc.transcribe_audio_bytes = wrapped_transcribe  # type: ignore[method-assign]
    vt.transcribe_audio_bytes = wrapped_transcribe  # type: ignore[attr-defined]
    vt._transcribe_chunk_with_retry = retry_with_metrics  # type: ignore[attr-defined]


def _code_sha() -> str:
    try:
        import subprocess

        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def _asr_cache_path(video_id: str) -> Path:
    return ASR_CACHE_ROOT / f"{video_id}.json"


def _legacy_asr_cache_path(video_id: str) -> Path:
    return COMPARISON_ROOT / video_id / "asr_cache.json"


def _load_asr_cache(video_id: str):
    from automation.listening.script.canonical import segments_from_raw

    for path in (_asr_cache_path(video_id), _legacy_asr_cache_path(video_id)):
        if not path.exists():
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        segments = segments_from_raw(raw, source="asr")
        if path == _legacy_asr_cache_path(video_id):
            _save_asr_cache(video_id, segments)
        return segments
    return None


def _save_asr_cache(video_id: str, segments) -> None:
    path = _asr_cache_path(video_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [{"start": s.start, "end": s.end, "text": s.text_en} for s in segments]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _fetch_asr_with_quality_check(
    video_id: str,
    duration: float,
    *,
    max_attempts: int = 3,
    hard_threshold: float = 0.15,
    soft_threshold: float = 0.20,
):
    """Fetch ASR for comparison runs.

    Prefer divergence <= hard_threshold. If all attempts exceed that but the best
    result is still <= soft_threshold, accept it (caption remains canonical).
    """
    from automation.listening.script.vertex_transcribe import transcribe_with_vertex

    caps, _, _ = fetch_caption_segments(video_id)
    cap_text = " ".join(s.text_en for s in consolidate_caption_segments(caps))
    last_error = None
    best_segments = None
    best_div = None
    for attempt in range(1, max_attempts + 1):
        try:
            segments = transcribe_with_vertex(video_id, duration)
            asr_text = " ".join(s.text_en for s in segments)
            doc_div = word_divergence(cap_text, asr_text)
            within_hard = doc_div <= hard_threshold
            within_soft = doc_div <= soft_threshold
            METRICS["calls"].append(
                {
                    "kind": "asr_quality_check",
                    "attempt": attempt,
                    "document_divergence": round(doc_div, 4),
                    "ok": within_hard,
                    "accepted_soft": within_soft and not within_hard,
                }
            )
            if best_div is None or doc_div < best_div:
                best_div = doc_div
                best_segments = segments
            if within_hard:
                _save_asr_cache(video_id, segments)
                return segments
            last_error = RuntimeError(f"ASR document divergence {doc_div:.1%} too high on attempt {attempt}")
        except Exception as exc:
            last_error = exc
            METRICS["vertex_errors"] += 1
    if best_segments is not None and best_div is not None and best_div <= soft_threshold:
        METRICS["calls"].append(
            {
                "kind": "asr_quality_check",
                "attempt": "best_of",
                "document_divergence": round(best_div, 4),
                "ok": False,
                "accepted_soft": True,
            }
        )
        _save_asr_cache(video_id, best_segments)
        return best_segments
    raise RuntimeError(f"BLOCKED: ASR quality check failed after {max_attempts} attempts: {last_error}")


def main(argv: list[str] | None = None) -> int:
    import argparse
    from automation.listening.config import extract_video_id

    parser = argparse.ArgumentParser(description="Run comparison mode with metrics.")
    parser.add_argument("--url", required=True)
    parser.add_argument("--level", type=int, choices=[1, 2, 3], required=True)
    args = parser.parse_args(argv)

    load_config()
    _install_metrics_hooks()

    video_id = extract_video_id(args.url)
    duration = fetch_youtube_duration(video_id)

    started = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    error_text = None
    result = None
    try:
        asr_segments = _load_asr_cache(video_id)
        if asr_segments is None:
            asr_segments = _fetch_asr_with_quality_check(video_id, duration)
        result = run_pipeline(
            args.url,
            args.level,
            comparison=True,
            asr_override=asr_segments,
        )
    except Exception:
        error_text = traceback.format_exc()

    elapsed = time.perf_counter() - started
    video_id = result.video_id if result else video_id

    golden_report = None
    if result and result.status == "COMPARISON" and video_id:
        content_04_path = COMPARISON_ROOT / video_id / "04_full_script.txt"
        if content_04_path.exists():
            golden = compare_video_golden_reference(video_id, content_04_path.read_text(encoding="utf-8"))
            if golden is not None:
                golden_report = golden.to_report()
                if not golden.ok:
                    result = type(result)(
                        "NEEDS_FIX",
                        f"Golden reference compare failed: {golden.reason}",
                        folder=result.folder,
                        video_id=result.video_id,
                        staging_dir=result.staging_dir,
                    )

    report = {
        "started_at_utc": started_at,
        "elapsed_sec": round(elapsed, 2),
        "url": args.url,
        "level": args.level,
        "video_duration_sec": duration,
        "status": result.status if result else "ERROR",
        "message": result.message if result else error_text,
        "video_id": video_id,
        "output_dir": str(COMPARISON_ROOT / video_id) if video_id else None,
        "vertex_calls": METRICS["vertex_calls"],
        "vertex_errors": METRICS["vertex_errors"],
        "vertex_retries_observed": METRICS["vertex_retries_observed"],
        "usage_totals": METRICS["usage_totals"],
        "calls": METRICS["calls"],
        "billing_note": "Exact USD cost requires Google Cloud Billing export; usage_totals are from Vertex usage_metadata when available.",
        "code_sha": _code_sha(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if golden_report is not None:
        report["golden_compare"] = golden_report

    if video_id:
        content_04_path = COMPARISON_ROOT / video_id / "04_full_script.txt"
        if content_04_path.exists():
            from automation.listening.generate.data_files import (
                count_04_kr_sentence_alignment_mismatches,
                count_en_punctuation,
                validate_04_kr_sentence_alignment,
            )

            content_04 = content_04_path.read_text(encoding="utf-8")
            report["en_punctuation_counts"] = count_en_punctuation(content_04)
            mismatch_n, mismatch_sample = count_04_kr_sentence_alignment_mismatches(content_04)
            report["kr_sentence_alignment_mismatch_count"] = mismatch_n
            if mismatch_sample:
                report["kr_sentence_alignment_sample"] = mismatch_sample
            kr_ok, kr_reason = validate_04_kr_sentence_alignment(content_04)
            report["kr_sentence_alignment_ok"] = kr_ok
            report["kr_sentence_alignment_reason"] = kr_reason
            if result and result.status == "COMPARISON" and not kr_ok:
                result = type(result)(
                    "NEEDS_FIX",
                    kr_reason,
                    folder=result.folder,
                    video_id=result.video_id,
                    staging_dir=result.staging_dir,
                )
                report["status"] = result.status
                report["message"] = result.message

    out_dir = COMPARISON_ROOT / video_id if video_id else COMPARISON_ROOT / "unknown"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "run_metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2, ensure_ascii=False))
    if result:
        print(f"Status: {result.status}")
        print(f"Message: {result.message}")
    if error_text:
        print(error_text, file=sys.stderr)
        return 2
    return 0 if result and result.status == "COMPARISON" else 2


if __name__ == "__main__":
    sys.exit(main())
