"""The two process-shaped properties, driven over the wire against the rendered project.

`opaque-return` and `unbuildable-symbol` say nothing about the fixture's source and
everything about what the plugin answers, so `conformance/validate.py` cannot speak for
them and only a protocol drive can. This renders the emitter's own project into a temp
directory and talks to `src/server.py` the way the suite does - one process, discover
then prepare then invoke - because both properties turn on state that only the running
plugin has: the module it failed to load, and the return value it refused to encode.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

package_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(package_root / "conformance"))

import emit as emitter  # noqa: E402  (the emitter is a standalone program; this imports it)


class Plugin:
    """One plugin process, spoken to over stdio, exactly as the suite speaks to it."""

    def __init__(self):
        self.child = subprocess.Popen(
            ["python3", "src/server.py"],
            cwd=str(package_root),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.next_id = 0

    def call(self, method, params=None):
        self.next_id += 1
        request = {"jsonrpc": "2.0", "id": self.next_id, "method": method, "params": params or {}}
        self.child.stdin.write(json.dumps(request) + "\n")
        self.child.stdin.flush()
        line = self.child.stdout.readline()
        if not line:
            raise AssertionError(f"the plugin answered nothing to {method}")
        return json.loads(line)["result"]

    def close(self):
        for stream in (self.child.stdin, self.child.stdout, self.child.stderr):
            try:
                stream.close()
            except OSError:
                pass  # already closed, which is the case the closed-drain test creates
        self.child.wait(timeout=15)


class ProcessProperties(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.project = Path(cls.directory.name)
        emitter.emit(cls.project)
        cls.manifest = json.loads((cls.project / "afz-conformance-manifest.json").read_text(encoding="utf8"))
        cls.plugin = Plugin()
        cls.plugin.call("handshake")
        discovery = cls.plugin.call(
            "discover", {"root": str(cls.project), "include": ["**/*.py"], "exclude": ["**/__pycache__/**"]}
        )
        cls.targets = {target["name"]: target["id"] for target in discovery["targets"]}

    @classmethod
    def tearDownClass(cls):
        cls.plugin.close()
        cls.directory.cleanup()

    def entry(self, property_id):
        return self.manifest["properties"][property_id]

    def test_the_manifest_accounts_for_every_template_property(self):
        # Twelve is the published v1 set; a property that stops being realized shows up
        # here as a missing id long before `afz install-harness` reports the fail.
        self.assertEqual(self.manifest["templateVersion"], 1)
        self.assertEqual(len(self.manifest["properties"]), 12)
        for property_id in ("opaque-return", "unbuildable-symbol"):
            self.assertIn("symbol", self.entry(property_id))
            self.assertIn("input", self.entry(property_id))

    def test_discovery_lists_both_new_symbols(self):
        self.assertIn("rate_for", self.targets)
        # An unbuildable symbol is a target, never a `skipped` entry: discovery reads the
        # declared signature and has no way to know the module will not load.
        self.assertIn("unbuildable", self.targets)

    def test_opaque_return_answers_ok_with_no_value(self):
        entry = self.entry("opaque-return")
        outcome = self.plugin.call(
            "invoke",
            {"targetId": self.targets[entry["symbol"]], "values": entry["input"], "deadlineMs": 1500, "collectCoverage": False},
        )
        self.assertEqual(outcome["kind"], "ok", outcome)
        self.assertNotIn("value", outcome, f"the plugin invented a wire form for a closure: {outcome}")

    def test_unbuildable_symbol_is_skipped_alone(self):
        entry = self.entry("unbuildable-symbol")
        answer = self.plugin.call("prepare", {"targetId": self.targets[entry["symbol"]], "values": entry["input"]})
        self.assertFalse(answer["ok"], answer)
        self.assertEqual(answer["reason"], "discovery-error")
        sibling = self.manifest["properties"]["method-receiver"]
        prepared = self.plugin.call(
            "prepare", {"targetId": self.targets[sibling["symbol"]], "values": sibling["input"]}
        )
        self.assertTrue(prepared["ok"], f"the unbuildable module took its sibling down: {prepared}")

    def test_a_diagnostic_that_cannot_be_written_never_breaks_the_answer(self):
        """The skip is the answer and the stderr line is only a note about it, so a
        diagnostic channel the reader has abandoned must not reach the wire. This is the
        shape `afz install-harness` drives: the engine's drain is not guaranteed to be
        reading, and a `BrokenPipeError` escaping `prepare` arrives as a plugin error."""
        entry = self.entry("unbuildable-symbol")
        plugin = Plugin()
        plugin.child.stderr.close()
        try:
            plugin.call("handshake")
            plugin.call("discover", {"root": str(self.project), "include": ["**/*.py"]})
            answer = plugin.call("prepare", {"targetId": self.targets[entry["symbol"]], "values": entry["input"]})
            self.assertEqual(answer, {"ok": False, "reason": "discovery-error"})
        finally:
            plugin.close()


if __name__ == "__main__":
    unittest.main()
