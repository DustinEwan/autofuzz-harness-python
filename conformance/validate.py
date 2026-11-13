#!/usr/bin/env python3
"""The conformance project's own fixture validator.

The protocol judge only ever sees the plugin's statements about this fixture. This file is
the second judgment: it inspects the fixture directly - imports only the fixture and the
Python standard library, never the plugin and never the emitter - and reports the same
property ids. The suite requires the two verdict lists to agree, so a plugin cannot pass a
fixture-shaped property by answering consistently instead of behaving.

Contract (docs/harness-authoring.md, section 12):
  - stdout is exactly one JSON ``TemplateReport`` and nothing else;
  - exit 0 even when a property fails; non-zero only when this validator itself could not run;
  - the seven fixture-shaped ids, never the three process-shaped ones;
  - stderr is free text for the author.

Rendered verbatim from conformance/validate.py into the staged project; run as
``python3 conformance/validate.py``.
"""

from __future__ import annotations

import inspect
import json
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

try:
    import pricing
except Exception:  # noqa: BLE001 - the validator itself could not run, which is the one exit-1 case
    traceback.print_exc()
    sys.exit(1)

results = []


def record(property_id, verdict, detail):
    results.append({"id": property_id, "verdict": verdict, "detail": detail})


# crash-unguarded: the crash is in the fixture's own code, not in a wrapper.
try:
    value = pricing.tiered_price(5)
    record("crash-unguarded", "fail", f"tiered_price(5) returned {value!r} instead of raising: the crash fixture stopped crashing")
except IndexError:
    text = traceback.format_exc()
    if "pricing.py" in text:
        record("crash-unguarded", "pass", "tiered_price(5) raised IndexError, and its traceback names pricing.py")
    else:
        record("crash-unguarded", "fail", "tiered_price(5) raised, but no frame names pricing.py")
except Exception as error:  # noqa: BLE001 - a different exception is a fixture change, reported as a verdict
    record("crash-unguarded", "fail", f"tiered_price(5) raised {type(error).__name__}, not the fixture's IndexError")

# guard-refusal: the guard is a real ValueError at the guard line.
try:
    value = pricing.apply_discount(-5)
    record("guard-refusal", "fail", f"apply_discount(-5) returned {value!r} instead of refusing")
except ValueError as error:
    if "pricing.py" in "".join(traceback.format_tb(error.__traceback__)):
        record("guard-refusal", "pass", "apply_discount(-5) raised ValueError from the guard line in pricing.py")
    else:
        record("guard-refusal", "fail", "apply_discount(-5) raised ValueError, but not from pricing.py")
except Exception as error:  # noqa: BLE001
    record("guard-refusal", "fail", f"apply_discount(-5) raised {type(error).__name__}, not the declared ValueError")

# private-symbol: the underscore-prefixed helper is present in the fixture, which is what the
# plugin must report as `not-public` in `skipped`.
if hasattr(pricing, "_cache_key") and pricing._cache_key.__name__.startswith("_"):
    record("private-symbol", "pass", "_cache_key is defined in pricing.py with a leading underscore, the fixture a not-public skip names")
else:
    record("private-symbol", "fail", "pricing.py no longer carries an underscore-prefixed helper for the not-public skip to name")

# unrepresentable-symbol: no annotations, so the generator has nothing to draw from.
if not pricing.untyped.__annotations__:
    record("unrepresentable-symbol", "pass", "untyped carries no annotations: the generator has nothing to draw from")
else:
    record("unrepresentable-symbol", "fail", f"untyped is annotated ({pricing.untyped.__annotations__}), so the manifest's skip is a lie")

# unconstructible-receiver: Ledger's constructor demands its path, so no receiver can be built.
try:
    pricing.Ledger()
    record("unconstructible-receiver", "fail", "Ledger() constructed with no arguments: the fixture no longer blocks the receiver")
except TypeError:
    required = [
        name
        for name, parameter in inspect.signature(pricing.Ledger.__init__).parameters.items()
        if name != "self" and parameter.default is inspect.Parameter.empty
    ]
    if required == ["path"]:
        record("unconstructible-receiver", "pass", "Ledger.__init__ requires `path` and Ledger() raises TypeError, so post's receiver cannot be built")
    else:
        record("unconstructible-receiver", "fail", f"Ledger.__init__ requires {required}, not the declared single `path`")

# method-receiver: the method lives on the class of a zero-argument instance.
try:
    invoice = pricing.Invoice()
    lines = invoice.add_line(1)
    if lines == 1 and "add_line" not in invoice.__dict__:
        record("method-receiver", "pass", "Invoice().add_line(1) returned 1 and add_line is absent from the instance __dict__: it is a class method")
    else:
        record("method-receiver", "fail", f"Invoice().add_line(1) returned {lines!r}, instance dict carries add_line: {'add_line' in invoice.__dict__}")
except Exception as error:  # noqa: BLE001
    record("method-receiver", "fail", f"Invoice().add_line(1) raised {type(error).__name__}: {error}")

# coverage-digest-live: the two manifest inputs must execute different lines. Measured with
# the stdlib tracer, so a probe that never resets or never arms cannot fake the difference.
import trace  # noqa: E402 - the tracer is the measurement instrument for this one property


def executed_lines(argument):
    tracer = trace.Trace(count=1, trace=0)
    tracer.runfunc(pricing.tiered_price, argument)
    return {key for key in tracer.results().counts if key[0].endswith("pricing.py")}


first = executed_lines(0)
second = executed_lines(2)
if first and second and first != second:
    record("coverage-digest-live", "pass", f"tiered_price(0) executed {len(first)} lines of pricing.py and tiered_price(2) executed {len(second)}: the inputs take different branches")
else:
    record("coverage-digest-live", "fail", f"tiered_price(0) and tiered_price(2) executed the same lines ({len(first)} and {len(second)}): no live per-input coverage signal")

print(json.dumps({"version": 1, "properties": results}))
