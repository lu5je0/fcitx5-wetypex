"""Verify native candidate forgetting in a disposable word store, including restart.

Run with python3 tests/backend_forget_smoke.py --package ./result.
"""

import argparse
import json
import os
from pathlib import Path
import select
import subprocess
import tempfile


class Backend:
    def __init__(self, package, root):
        env = {k: v for k, v in os.environ.items() if not k.startswith("WETYPE_")}
        env.update(HOME=str(root), XDG_CONFIG_HOME=str(root / "config"),
                   XDG_DATA_HOME=str(root / "data"), WETYPE_STATE_DIR=str(root / "state"))
        self.log = tempfile.TemporaryFile(mode="w+")
        self.process = subprocess.Popen(
            [str(package / "bin/fcitx5-wetypex-backend")], env=env, text=True,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log,
        )
        self.seq = 0

    def read(self):
        assert select.select([self.process.stdout], [], [], 15)[0], "backend timeout"
        line = self.process.stdout.readline()
        if not line:
            self.log.seek(0)
            raise AssertionError("backend exited: " + self.log.read()[-4000:])
        return json.loads(line)

    def request(self, operation, **fields):
        self.seq += 1
        self.process.stdin.write(json.dumps(dict(
            session=1, seq=self.seq, epoch=1, op=operation, **fields)) + "\n")
        self.process.stdin.flush()
        return self.read()

    def type(self, spelling):
        result = self.request("reset")
        for char in spelling:
            result = self.request("key", key=char)
        assert result["candidates"], result
        return result

    def __enter__(self):
        assert self.read()["event"] == "ready"
        self.request("open")
        return self

    def __exit__(self, *args):
        try:
            if self.process.poll() is None:
                # quit has no response; finalization flushes the user store.
                self.process.stdin.write(json.dumps(dict(
                    session=1, seq=self.seq + 1, epoch=1, op="quit")) + "\n")
                self.process.stdin.flush()
                self.process.wait(timeout=15)
        finally:
            if self.process.poll() is None:
                self.process.kill()
                self.process.wait()
            self.process.stdin.close()
            self.process.stdout.close()
            self.log.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    args = parser.parse_args()
    package = args.package.resolve()
    with tempfile.TemporaryDirectory(prefix="wetypex-forget-check-") as directory:
        root = Path(directory)
        config = root / "config/fcitx5"
        config.mkdir(parents=True)
        (config / "wetypex.json").write_text('{"standalone":true}')
        with Backend(package, root) as backend:
            candidates = backend.type("nihao")
            target = candidates["candidates"][0]
            assert target == "你好", candidates
            # An emoji replacement of the same word may disappear with it.
            remaining = candidates["candidates"][2]
            for fields in ({"revision": -1, "index": 0},
                           {"revision": candidates["revision"] + 100, "index": 0},
                           {"revision": candidates["revision"], "index": -1}):
                rejected = backend.request("forget", **fields)
                assert rejected.get("error"), rejected
                assert target in rejected["candidates"], rejected
                assert not rejected["commits"], rejected
            backend.request("key", key="x")
            rejected = backend.request("forget", index=0, revision=candidates["revision"])
            assert rejected.get("error") and not rejected["commits"], rejected
            candidates = backend.type("nihao")
            assert candidates["candidates"][0] == target, candidates
            result = backend.request("forget", index=0, revision=candidates["revision"])
            assert not result.get("error"), result
            assert target not in result["candidates"], result
            assert remaining in result["candidates"], result
            assert result["preedit"] == "nihao" and not result["commits"], result
            assert target not in backend.type("nihao")["candidates"]
            learned = backend.type("tuzihuanggua")
            learned_word = learned["candidates"][0]
            assert learned_word == "兔子黄瓜", learned
            committed = backend.request("select", index=0, revision=learned["revision"])
            assert committed["commits"] == [learned_word], committed
            learned = backend.type("tuzihuanggua")
            result = backend.request("forget", index=0, revision=learned["revision"])
            assert not result.get("error") and learned_word not in result["candidates"], result
            assert not result["commits"], result
        # A fresh process must use the core's persisted block list, rather
        # than a temporary filter in the plugin or in the current session.
        with Backend(package, root) as backend:
            result = backend.type("nihao")
            assert target not in result["candidates"], result
            assert remaining in result["candidates"], result
            assert learned_word not in backend.type("tuzihuanggua")["candidates"]
    print("PASS: native forgetting, learned words, stale snapshot rejection, no commit, restart persistence")


if __name__ == "__main__":
    main()
