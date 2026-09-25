"""Budgeted, traced, cached offline account-evidence assessment."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid

from dotenv import load_dotenv
from openai import OpenAI


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / "ai"
MODEL_RATES = {
    "gpt-4.1-mini-2025-04-14": (0.40, 1.60),
    "gpt-4.1-2025-04-14": (2.00, 8.00),
}
DEFAULT_MODEL = "gpt-4.1-mini-2025-04-14"
MAX_TOTAL_USD = 10.0
MAX_OUTPUT_TOKENS = 300
SCHEMA_VERSION = "1"
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["supported", "needs_review", "insufficient_evidence"]},
        "evidence_ids": {"type": "array", "items": {"type": "string"}},
        "reason": {"type": "string"},
        "next_action": {"type": "string"},
    },
    "required": ["decision", "evidence_ids", "reason", "next_action"],
    "additionalProperties": False,
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    input_rate, output_rate = MODEL_RATES[model]
    return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000


def validate_result(result: dict, allowed_ids: set[str]) -> None:
    if set(result) != set(OUTPUT_SCHEMA["required"]):
        raise ValueError("Output keys differ from schema")
    if result["decision"] not in ("supported", "needs_review", "insufficient_evidence"):
        raise ValueError("Unknown decision")
    if not isinstance(result["evidence_ids"], list) or not all(
        isinstance(x, str) and x in allowed_ids for x in result["evidence_ids"]
    ):
        raise ValueError("Output cites missing evidence IDs")
    if not all(isinstance(result[key], str) and result[key].strip() for key in ("reason", "next_action")):
        raise ValueError("Reason and next action must be nonempty")
    if result["decision"] == "supported" and not result["evidence_ids"]:
        raise ValueError("Supported result must cite evidence")


class BudgetedAssessor:
    def __init__(self, artifact_dir: Path = ARTIFACTS, model: str = DEFAULT_MODEL):
        if model not in MODEL_RATES:
            raise ValueError("Model has no reviewed rate card")
        load_dotenv(ROOT / ".env")
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "replace_with_your_api_key":
            raise RuntimeError("OPENAI_API_KEY is not configured; keep the real key in the ignored .env file")
        self.client = OpenAI(max_retries=0, timeout=30)
        self.model = model
        self.artifact_dir = artifact_dir
        artifact_dir.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(artifact_dir / "ledger.sqlite3")
        self.db.execute("""CREATE TABLE IF NOT EXISTS calls (
            call_id TEXT PRIMARY KEY, cache_key TEXT, status TEXT,
            reserved_usd REAL, actual_usd REAL, model TEXT, prompt_version TEXT,
            created_at TEXT, finished_at TEXT
        )""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS cache (
            cache_key TEXT PRIMARY KEY, response_json TEXT, call_id TEXT
        )""")
        self.db.commit()

    def assess(self, bundle: dict, prompt_version: str) -> dict:
        prompt_path = ROOT / "prompts" / "account-research" / f"{prompt_version}.md"
        prompt = prompt_path.read_text()
        evidence = bundle.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise ValueError("A nonempty evidence list is required")
        allowed_ids = {item["evidence_id"] for item in evidence}
        if len(allowed_ids) != len(evidence):
            raise ValueError("Evidence IDs must be unique")
        request_json = json.dumps({"candidate_domain": bundle["candidate_domain"],
                                   "evidence": evidence}, sort_keys=True, ensure_ascii=False)
        cache_key = hashlib.sha256(json.dumps([self.model, prompt_version,
            hashlib.sha256(prompt.encode()).hexdigest(), SCHEMA_VERSION, request_json],
            ensure_ascii=False).encode()).hexdigest()
        cached = self.db.execute("SELECT response_json FROM cache WHERE cache_key = ?", (cache_key,)).fetchone()
        if cached:
            return {"result": json.loads(cached[0]), "status": "cache_hit", "cache_key": cache_key}
        input_bytes = len(prompt.encode()) + len(request_json.encode())
        if input_bytes > 10_000:
            raise ValueError("Evidence bundle exceeds 10 KB input guard")
        reservation = cost_usd(self.model, input_bytes + 300, MAX_OUTPUT_TOKENS)
        call_id = uuid.uuid4().hex
        self.db.execute("BEGIN IMMEDIATE")
        spent = self.db.execute("SELECT coalesce(sum(case when status = 'reserved' then reserved_usd else actual_usd end), 0) FROM calls").fetchone()[0]
        if spent + reservation > MAX_TOTAL_USD:
            self.db.rollback()
            raise RuntimeError("US$10 API cost ceiling reached")
        self.db.execute("INSERT INTO calls VALUES (?, ?, 'reserved', ?, 0, ?, ?, ?, NULL)",
                        (call_id, cache_key, reservation, self.model, prompt_version, now_utc()))
        self.db.commit()
        started = time.monotonic()
        trace = {"call_id": call_id, "cache_key": cache_key, "at_utc": now_utc(),
                 "request": {"instructions": prompt, "input": json.loads(request_json)},
                 "model": self.model, "prompt_version": prompt_version,
                 "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                 "schema_version": SCHEMA_VERSION, "reserved_usd": reservation,
                 "response": None, "decision": None, "error": None}
        try:
            response = self.client.responses.create(
                model=self.model, instructions=prompt, input=request_json,
                text={"format": {"type": "json_schema", "name": "account_assessment",
                                 "strict": True, "schema": OUTPUT_SCHEMA}},
                max_output_tokens=MAX_OUTPUT_TOKENS, store=False,
            )
            trace["response_id"] = response.id
            trace["response_status"] = response.status
            trace["response"] = response.output_text
            trace["input_tokens"] = response.usage.input_tokens if response.usage else None
            trace["output_tokens"] = response.usage.output_tokens if response.usage else None
            if response.usage:
                trace["actual_usd"] = cost_usd(self.model, response.usage.input_tokens,
                                               response.usage.output_tokens)
            if response.status != "completed":
                raise ValueError(f"Model response status: {response.status}")
            result = json.loads(response.output_text)
            validate_result(result, allowed_ids)
            trace["decision"] = result["decision"]
            trace["validation"] = "passed"
            self.db.execute("UPDATE calls SET status='completed', actual_usd=?, finished_at=? WHERE call_id=?",
                            (trace.get("actual_usd", reservation), now_utc(), call_id))
            self.db.execute("INSERT INTO cache VALUES (?, ?, ?)",
                            (cache_key, json.dumps(result, ensure_ascii=False), call_id))
            self.db.commit()
            return {"result": result, "status": "completed", "cache_key": cache_key,
                    "call_id": call_id}
        except Exception as exc:
            trace["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
            trace["validation"] = "failed"
            # A timeout can have incurred charges. Retain its reservation when usage is unknown.
            self.db.execute("UPDATE calls SET status='failed', actual_usd=?, finished_at=? WHERE call_id=?",
                            (trace.get("actual_usd", reservation), now_utc(), call_id))
            self.db.commit()
            raise
        finally:
            trace["latency_ms"] = round((time.monotonic() - started) * 1000)
            with (self.artifact_dir / "traces.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(trace, ensure_ascii=False) + "\n")
