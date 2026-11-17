"""One explicitly bounded real-service synthetic smoke, never benchmark scoring."""
from copy import deepcopy
import hashlib
import importlib.machinery
import json
import marshal
from pathlib import Path
import sys
import threading
import time
import traceback
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
OUTPUT = Path(__file__).resolve().parent
if (OUTPUT / "smoke_report.json").exists():
    raise SystemExit("This one-shot smoke already has a report; do not retry implicitly.")

# Record the code object actually returned by the import loader, independently
# of source files that another development process may edit during this run.
loaded_code = {}
original_get_code = importlib.machinery.SourceFileLoader.get_code
def audited_get_code(loader, fullname):
    code = original_get_code(loader, fullname)
    path = Path(loader.path).resolve()
    if code is not None and path.is_relative_to(ROOT):
        loaded_code[fullname] = {
            "path": str(path.relative_to(ROOT)),
            "runtime_code_sha256": hashlib.sha256(marshal.dumps(code)).hexdigest(),
            "source_sha256_observed_at_load": hashlib.sha256(path.read_bytes()).hexdigest(),
            "loaded_unix": time.time(),
        }
    return code
importlib.machinery.SourceFileLoader.get_code = audited_get_code

from dagbt import runner
from dagbt.engine import run_question, legacy_modules
from dagbt.bridge import BridgeSession
from dagbt import final_selection
from dagbt.budget import Ledger
from dagbt.config import resolve
from dagbt.model_runtime import load_tokenizer
from dagbt.resources import ProvenanceDocument, _embedding_batch, SERIALIZATION
from dagbt.transport import Transport

config = deepcopy(runner.load(ROOT / "configs/paired.example.json"))
config.update(request_timeout_seconds=20, max_identical_attempts=1)
config["reranker"]["timeout_seconds"] = 20
config["fusion"].update(ann_calls=8, set_score_calls=32, llm_calls=24, max_feedback_rounds=0)
settings = resolve(config, "fusion")
runner.validate_config(config)
e, _, _ = legacy_modules()
runner.configure_personamem_reader()
tokenizer = load_tokenizer(config)

records = [
    ("synthetic_user_preferences", "user", "I like nonfiction about psychology and human relationships."),
    ("synthetic_user_dislikes", "user", "I dislike horror books and violent stories."),
    ("synthetic_user_weekend", "user", "For a quiet weekend, I want light reading in short chapters."),
    ("synthetic_assistant_suggestion", "assistant", "You could try a horror novel."),
]
docs = {}
for index, (doc_id, role, text) in enumerate(records):
    metadata = {"shared_context_id": "synthetic_smoke_only", "source_message_indices": [index],
        "roles": [role], "time": {"kind": "observation_order_only"},
        "source_segments": [{"role": role, "start": 0, "end": len(text),
                             "source_message_indices": [index], "provenance": "authoritative"}]}
    docs[doc_id] = ProvenanceDocument(doc_id, "", text, metadata)
ids = list(docs)
query = "I have a quiet weekend ahead. What kind of book would suit me?"
options = ("(a) Short, gentle nonfiction pieces about psychology and relationships.\n"
           "(b) A suspenseful horror novel.\n"
           "(c) A graphic, violent crime saga.\n"
           "(d) An intense, demanding textbook to study all weekend.")
reader_question = query + "\nOptions:\n" + options
question = {"id": "synthetic_personal_weekend_v3", "question": query}
corpus_trace, task_trace = OUTPUT / "corpus_embedding", OUTPUT / "task"
source_start = runner.frozen_sources()
started = time.monotonic()
report = {
    "status": "running", "kind": "real_services_one_synthetic_full_engine_smoke",
    "scope": "four artificial memories; no public dataset or gold loaded; no benchmark accuracy claim",
    "attempts_allowed": 1, "transport_max_identical_attempts": 1,
    "config_source": "configs/paired.example.json", "config_sha256": runner.digest(config),
    "config_file_sha256_at_start": runner.file_hash(ROOT / "configs/paired.example.json"),
    "models": {"llm": config["llm_model"], "embedding": config["embedding_model"],
               "reranker": config["reranker"]["deployment_identity"]["model_id"]},
    "limits": {name: settings[name] for name in ("llm_calls", "reader_calls", "ann_calls", "set_score_calls",
        "max_feedback_rounds", "context_tokens", "reasoning_output_tokens", "reader_output_tokens")},
    "source_hashes_at_start": source_start, "source_hash_at_start": runner.digest(source_start),
    "script_sha256": runner.file_hash(Path(__file__)),
    "corpus_serialization": SERIALIZATION, "corpus_documents": len(ids),
    "reader_options_visible_only_to_reader": None,
}
runner.save(OUTPUT / "smoke_report.json", report)
runner.save(OUTPUT / "effective_config.json", config)
runner.save(OUTPUT / "synthetic_input.json", {"question": question, "reader_question": reader_question,
    "documents": [{"doc_id": d.doc_id, "title": d.title, "text": d.text, "metadata": d.metadata} for d in docs.values()]})
row = None
try:
    corpus_ledger = Ledger({}, sink=lambda event: runner.append_jsonl(corpus_trace / "ledger_events.jsonl", event))
    corpus_calls = Transport("synthetic_corpus_v3", corpus_trace, config, corpus_ledger, tokenizer)
    reply = corpus_calls.get(("index_embedding", "0"), config["embedding_base_url"].rstrip("/") + "/embeddings",
                             {"model": config["embedding_model"], "input": [docs[d].passage for d in ids]})
    vectors, dimension = _embedding_batch(reply["response"], len(ids))
    import numpy as np
    np.save(OUTPUT / "corpus_vectors.npy", vectors, allow_pickle=False)
    report["embedding_dimensions"] = dimension
    index = SimpleNamespace(vectors=dict(zip(ids, vectors)), lock=threading.Lock())
    resources = (docs, ids, vectors, index, tokenizer)
    calls = Transport(question["id"], task_trace, config, Ledger({}), tokenizer)
    row = run_question(question, resources, calls, config, method="fusion", reader_question=reader_question)
    runner.save(task_trace / "result.json", row)
    report.update(status="completed", answer_status=row["answer"]["status"],
                  prediction=row["answer"]["prediction"], selected_doc_ids=row["budgets"]["20"]["selected_doc_ids"],
                  reliability=row["diagnostics"]["reliability"],
                  semantic_evidence=row["diagnostics"]["semantic_evidence"],
                  ledger=row["diagnostics"]["ledger"], reader_feasibility=row["diagnostics"]["reader_feasibility"])
except Exception as exc:
    report.update(status="failed", **runner.redacted_error(exc), traceback=traceback.format_exc())
    if (task_trace / "fusion_partial.json").is_file():
        partial = runner.load(task_trace / "fusion_partial.json")
        report["partial_diagnostics"] = partial.get("diagnostics", {})
        report["ledger"] = partial.get("ledger", {})
finally:
    report["elapsed_seconds"] = time.monotonic() - started
    report["corpus_embedding_cost"] = runner.request_cost(corpus_trace)
    report["task_cost"] = runner.request_cost(task_trace)
    reader_records, nonreader_options = [], []
    for path in sorted((task_trace / "requests").glob("*.json")):
        record = runner.load(path)
        stage = record.get("stage")
        stage_text = "/".join(map(str, stage)) if isinstance(stage, (list, tuple)) else str(stage)
        if stage_text.startswith("reader/"):
            messages = record["payload"]["messages"]
            user_message = messages[-1]["content"]
            context = user_message.split("Context passages:\n", 1)[1].split("\n\nCommitted demand-state evidence:", 1)[0]
            selected = report.get("selected_doc_ids", [])
            item = {"request_ref": path.stem, "stage": stage, "messages": messages,
                "actual_context_passages": context, "context_sha256": hashlib.sha256(context.encode()).hexdigest(),
                "selected_complete_source_present": {doc_id: docs[doc_id].passage in context for doc_id in selected},
                "reader_has_public_options": options in user_message,
                "all_corpus_source_presence_in_context": {doc_id: docs[doc_id].passage in context for doc_id in ids}}
            reader_records.append(item)
        elif any(option in json.dumps(record.get("payload", {}), ensure_ascii=False) for option in options.splitlines()):
            nonreader_options.append({"request_ref": path.stem, "stage": stage})
    runner.save(OUTPUT / "actual_reader_inputs.json", reader_records)
    report["reader_requests"] = len(reader_records)
    report["reader_options_visible_only_to_reader"] = bool(reader_records) and not nonreader_options and all(
        item["reader_has_public_options"] for item in reader_records)
    report["nonreader_option_leaks"] = nonreader_options
    report["selected_complete_sources_present_in_reader_context"] = bool(reader_records) and all(
        all(item["selected_complete_source_present"].values()) for item in reader_records)
    events = []
    event_path = task_trace / "fusion_events.jsonl"
    if event_path.is_file():
        events = [json.loads(line) for line in event_path.read_text().splitlines() if line.strip()]
    budgets = [event for event in events if event.get("event") == "model_context_budget"]
    runner.save(OUTPUT / "observed_input_budget_checks.json", budgets)
    report["observed_input_budget_checks"] = len(budgets)
    report["all_observed_inputs_within_estimated_budget"] = bool(budgets) and all(
        event.get("within_estimated_budget") is True for event in budgets)
    source_end = runner.frozen_sources()
    report["source_hashes_at_end"] = source_end
    report["source_hash_at_end"] = runner.digest(source_end)
    report["source_files_changed_during_run"] = sorted(name for name in set(source_start) | set(source_end)
        if source_start.get(name) != source_end.get(name))
    report["loaded_modules"] = loaded_code
    report["loaded_module_sources_changed_after_import"] = sorted(name for name, record in loaded_code.items()
        if runner.file_hash(ROOT / record["path"]) != record["source_sha256_observed_at_load"])
    report["final_package_identity_not_yet_verified"] = True
    importlib.machinery.SourceFileLoader.get_code = original_get_code
    runner.save(OUTPUT / "smoke_report.json", report)
print(json.dumps({key: report.get(key) for key in ("status", "answer_status", "prediction", "elapsed_seconds",
    "reader_requests", "reader_options_visible_only_to_reader", "selected_complete_sources_present_in_reader_context",
    "source_files_changed_during_run", "error_type", "error")}, ensure_ascii=False))
print("Report:", OUTPUT / "smoke_report.json")
