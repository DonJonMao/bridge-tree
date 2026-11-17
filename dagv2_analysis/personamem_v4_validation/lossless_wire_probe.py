#!/usr/bin/env python3
"""Analysis-only observation interning; never traverses typed values or sources.

Not integrated into the runtime. References are recognized only at explicit
observation positions. The table contains unchanged complete observation JSON.
"""
from collections import Counter
from copy import deepcopy
import json


TABLE = "wire_observation_values"
REF = "observation_ref"
INSTRUCTION = ("\nLOSSLESS OBSERVATION REFERENCES: At observation positions only, an object "
               "{\"observation_ref\":i} denotes the complete unchanged observation object "
               "at user.wire_observation_values[i]. Read all referenced fields, including "
               "value, original citations, scopes, parents, counter stance and retraction "
               "targets. References do not merge observations or waive any validation.\n")


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def observation_paths(data):
    """Known request containers only; do not recursively scan arbitrary JSON."""
    paths = []

    def rows(container, key, base):
        value = container.get(key)
        if isinstance(value, list):
            paths.extend(base + (key, i) for i, item in enumerate(value) if isinstance(item, dict))

    def failures(container, base):
        for i, item in enumerate(container.get("failed", [])):
            if not isinstance(item, dict):
                continue
            prefix = base + ("failed", i)
            if isinstance(item.get("observation"), dict):
                paths.append(prefix + ("observation",))
            for key in ("replacement_observations", "required_counter_observations"):
                rows(item, key, prefix)
            if isinstance(item.get("slot"), dict):
                rows(item["slot"], "observations", prefix + ("slot",))

    def whole(container, base):
        for i, item in enumerate(container.get("whole_value_reviews", [])):
            if isinstance(item, dict):
                for key in ("draft_observations", "known_observations"):
                    rows(item, key, base + ("whole_value_reviews", i))

    rows(data, "known_observations", ())
    repair = data.get("repair_scope")
    if isinstance(repair, dict):
        failures(repair, ("repair_scope",))
        whole(repair, ("repair_scope",))
    for i, record in enumerate(data.get("failed_batch_reviews", [])):
        if isinstance(record, dict):
            base = ("failed_batch_reviews", i)
            failures(record, base)
            whole(record, base)
            rows(record, "validated_observations", base)
    return paths


def get(data, path):
    for part in path:
        data = data[part]
    return data


def put(data, path, value):
    parent = get(data, path[:-1])
    parent[path[-1]] = value


def encode_observations(data):
    paths = observation_paths(data)
    result = deepcopy(data)
    metadata = {"observation_positions": len(paths), "shared_objects": 0, "references": 0,
                "source_fields_untouched": True, "typed_values_traversed": False}
    if TABLE in data or any(set(get(data, path)) == {REF} for path in paths):
        return result, {**metadata, "declined": "reserved_shape_collision"}
    keys = {path: compact(get(data, path)) for path in paths}
    counts = Counter(keys.values())
    selected = {key for key, count in counts.items() if count > 1 and len(key.encode()) >= 100}
    if not selected:
        return result, {**metadata, "declined": "no_repeated_observations"}
    aliases, bank = {}, []
    for path in paths:
        key = keys[path]
        if key not in selected:
            continue
        if key not in aliases:
            aliases[key] = len(bank)
            bank.append(deepcopy(get(data, path)))
        put(result, path, {REF: aliases[key]})
    result[TABLE] = bank
    saving = len(compact(data).encode()) - len(compact(result).encode()) - len(INSTRUCTION.encode())
    if saving <= 0:
        return deepcopy(data), {**metadata, "declined": "not_smaller_in_bytes"}
    assert decode_observations(result) == data
    return result, {**metadata, "shared_objects": len(bank),
                    "references": sum(key in selected for key in keys.values()),
                    "bytes_saved_including_instruction": saving,
                    "roundtrip_equal": True,
                    "shared_object_occurrences": sorted([counts[key] for key in aliases], reverse=True)}


def decode_observations(data):
    result = deepcopy(data)
    if TABLE not in result:
        return result
    bank = result.pop(TABLE)
    for path in observation_paths(result):
        value = get(result, path)
        if set(value) == {REF}:
            index = value[REF]
            if type(index) is not int or not 0 <= index < len(bank):
                raise ValueError("invalid observation reference")
            put(result, path, deepcopy(bank[index]))
    return result
