"""Recompute three diagnostic cases from archives, without service calls."""
import json
import tarfile
from collections import Counter
from pathlib import Path

from bridgetree.personamem import iter_examples, messages_to_memories

BASE = Path(__file__).resolve().parent
PROJECT = BASE.parents[1]
CASES = {
    "3b1003e23012d57db5e0a5bf1cf473689beef60580562ffe71d84c0dc7cd581b": ("绘画", [39]),
    "dd67463ac5377f24adb34606b97ec13df4e20e72130624ae43c9c4d7d299dec2": ("音乐", [5, 27]),
    "55de70ff2877a08d427cfbccbeb317a07625f037c72a98e72e250340f3faccfa": ("读书会", [37]),
}
examples = {x.question_id: x for x in iter_examples(
    PROJECT / "data/raw/personamem-v1/questions_32k.csv",
    PROJECT / "data/raw/personamem-v1/shared_contexts_32k.jsonl")}
result = []
with tarfile.open("/Users/mao/chain-audit-detail.tgz") as archive:
    for member in archive.getmembers():
        tid = Path(member.name).stem
        if tid not in CASES:
            continue
        data = json.load(archive.extractfile(member))
        search, selection = data["search"], data["selection"]
        qid = search["initial_target_ids"][0].split(":")[0]
        name, evidence_indexes = CASES[tid]
        memories = messages_to_memories(examples[qid].messages, qid)
        by_id = {m.memory_id: m for m in memories}
        assert set(selection["selected_ids"]) <= by_id.keys()
        comparisons = [c for r in selection["rounds"] for c in r["comparisons"]]
        for c in comparisons:
            assert c["feasible"]
            assert abs(c["combined_score"] - c["base_score"] - c["marginal"]) < 1e-12
        for a in search["activations"]:
            assert abs(a["PGe"] - a["PG"] - a["Pe"] + a["P"] - a["activation"]) < 1e-12
        states = search["states"]
        facts = []
        for index in evidence_indexes:
            mid = f"{qid}:m{index:05d}"
            adds = [c for c in comparisons if c["bundle_ids"] == [mid]]
            facts.append({"memory_id": mid, "text": by_id[mid].text,
                "initial_pool": mid in data["retrieval"]["initial_candidate_ids"],
                "selected": mid in selection["selected_ids"], "singleton_comparisons": adds})
        last = selection["rounds"][-1]["comparisons"]
        result.append({"case": name, "task_id": tid, "question_id": qid,
            "initial_targets": len(search["initial_target_ids"]),
            "target_visits": dict(Counter(s["state"]["target_id"] for s in states)),
            "state_events": dict(Counter(s["event"] for s in states)),
            "premise_depths": dict(Counter(len(s["state"]["premise_ids"]) for s in states)),
            "state_records": len(states), "activation_records": len(search["activations"]),
            "selection_comparisons": len(comparisons),
            "last_round_comparisons": len(last),
            "last_round_all_negative": all(c["marginal"] < 0 for c in last),
            "last_round_best_marginal": max(c["marginal"] for c in last),
            "selected_ids": selection["selected_ids"], "evidence": facts})
destination = BASE / "case_evidence.json"
destination.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps([{k: v for k, v in row.items() if k != "evidence"} for row in result], ensure_ascii=False, indent=2))
