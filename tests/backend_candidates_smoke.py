"""Verify full native candidate lists and late selections in a disposable store.

Run with python3 tests/backend_candidates_smoke.py --package ./result.
"""

import argparse
from pathlib import Path
import tempfile

from backend_forget_smoke import Backend


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="wetypex-candidates-check-") as directory:
        root = Path(directory)
        config = root / "config/fcitx5"
        config.mkdir(parents=True)
        (config / "wetypex.json").write_text('{"standalone":true}')
        with Backend(args.package.resolve(), root) as backend:
            for spelling, target in (("yi", "羿"), ("yixuan", "翊")):
                result = backend.type(spelling)
                words = result["candidates"]
                assert len(words) > 100, (spelling, len(words))
                assert "翼" in words, spelling
                index = words.index(target)
                assert index >= 50, (spelling, target, index)
                selected = backend.request("select", index=index,
                                           revision=result["revision"])
                assert not selected.get("error"), selected
                if spelling == "yi":
                    assert selected["commits"] == [target], selected
                    assert selected["preedit"] == "", selected
                else:
                    assert not selected["commits"], selected
                    assert selected["preedit"] == target + "xuan", selected
                    # A late candidate must retain its native ID and consume
                    # only yi, leaving xuan available for the next selection.
                    index = selected["candidates"].index("轩")
                    committed = backend.request("select", index=index,
                                                revision=selected["revision"])
                    assert committed["commits"] == [target + "轩"], committed
                    assert committed["preedit"] == "", committed
                print(f"PASS: {spelling}: {len(words)} candidates, "
                      f"selected {target} beyond rank 50")
            for spelling, target, late in (
                ("shi", "螫", True), ("ji", "齑", True),
                ("xian", "鱻", True), ("biao", "驫", True),
                ("da", "龘", False), ("nang", "齉", False),
                ("bing", "靐", False), ("cu", "麤", False),
                ("ben", "犇", False),
            ):
                result = backend.type(spelling)
                index = result["candidates"].index(target)
                if late:
                    assert index >= 50, (spelling, target, index)
                committed = backend.request("select", index=index,
                                            revision=result["revision"])
                assert not committed.get("error"), committed
                assert committed["commits"] == [target], committed
                assert committed["preedit"] == "", committed
                print(f"PASS: {spelling}: selected {target} at rank {index + 1}")


if __name__ == "__main__":
    main()
