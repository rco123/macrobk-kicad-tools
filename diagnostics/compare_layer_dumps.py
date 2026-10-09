"""Compare captured observations; candidate evidence is not a production getter."""
import argparse
import json
from pathlib import Path

TARGETS = ("F.Cu", "B.Cu", "F.Adhesive", "Edge.Cuts")
METRICS = ("width", "height", "has_alpha", "nontransparent_pixel_count", "alpha_gt_16_count",
           "opaque_pixel_count", "rgb_sum", "rgb_checksum", "alpha_sum", "alpha_checksum")


def compare(dumps):
    if not dumps:
        raise ValueError("No captures supplied")
    missing = set(TARGETS) - {d.get("expected_by_human") for d in dumps}
    observations = []
    indexed = []
    for capture in dumps:
        rows = {row["layer_name"]: row for row in capture["rows"]}
        if len(rows) != len(capture["rows"]):
            raise ValueError("Duplicate layer labels; resolve row identity before comparing")
        indexed.append(rows)
        observations.append({"time": capture["time"], "expected_by_human": capture.get("expected_by_human"),
            "tag": capture.get("tag"), "frame": capture.get("frame"),
            "bitmap_rows": {name: [{"path": b["path"], "metrics": b["metrics"]}
                                   for b in row["bitmaps"]] for name, row in rows.items()}})
    changes = []
    for a, b in zip(range(len(dumps)-1), range(1, len(dumps))):
        for name in sorted(set(indexed[a]).intersection(indexed[b])):
            old = {item["path"]: item["metrics"] for item in indexed[a][name]["bitmaps"]}
            new = {item["path"]: item["metrics"] for item in indexed[b][name]["bitmaps"]}
            for path in sorted(set(old).intersection(new)):
                delta = {m: {"before": old[path].get(m), "after": new[path].get(m)}
                         for m in METRICS if old[path].get(m) != new[path].get(m)}
                if delta:
                    changes.append({"before_capture": a, "after_capture": b, "layer": name,
                                    "bitmap_path": path, "changes": delta})
    # All rows must be present in all captures. A disappearing row cannot be
    # used as evidence for an active indicator signature.
    row_sets_equal = all(set(rows) == set(indexed[0]) for rows in indexed)
    candidates = []
    paths = {b["path"] for rows in indexed for row in rows.values() for b in row["bitmaps"]}
    if not missing and row_sets_equal:
        for path in sorted(paths):
            for metric in METRICS:
                on, off = [], []
                valid = True
                for capture, rows in zip(dumps, indexed):
                    expected = capture.get("expected_by_human")
                    if expected not in rows:
                        valid = False
                        break
                    for name, row in rows.items():
                        entries = [b["metrics"] for b in row["bitmaps"] if b["path"] == path]
                        if len(entries) != 1 or metric not in entries[0] or entries[0][metric] is None:
                            valid = False
                            break
                        (on if name == expected else off).append(entries[0][metric])
                if valid and on and off and len(set(on)) == 1 and on[0] not in off:
                    candidates.append({"bitmap_path": path, "metric": metric,
                                       "observed_selected_value": on[0],
                                       "unselected_values": sorted(set(off), key=str),
                                       "status": "CANDIDATE ONLY: needs repeat/focus/Manager/reopen validation"})
    return {"capture_count": len(dumps), "missing_expected_layers": sorted(missing),
            "row_sets_equal": row_sets_equal, "observations": observations,
            "bitmap_changes": changes, "candidate_fields": candidates,
            "production_getter_verified": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("captures", nargs="+")
    parser.add_argument("--out", default=str(Path(__file__).parent / "comparison.json"))
    args = parser.parse_args()
    result = compare([json.loads(Path(p).read_text(encoding="utf-8-sig")) for p in args.captures])
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("captures={} changes={} candidates={} missing={}".format(result["capture_count"],
          len(result["bitmap_changes"]), len(result["candidate_fields"]), result["missing_expected_layers"]))
    print("No production getter is proven by this comparison alone.")


if __name__ == "__main__":
    main()
