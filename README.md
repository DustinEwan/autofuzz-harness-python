# autofuzz harness: Python

The harness plugin the autofuzz engine loads for Python targets. It discovers module-level callables and methods, builds arguments from generated values, invokes each entry point, and answers with coverage digests, fault outcomes, and reproducer scripts over the plugin protocol (`afz/1`).

Host runtime: Python 3.12 or newer, standard library only. The plugin installs no dependencies and has none.

## Install

```sh
afz install-harness https://github.com/DustinEwan/autofuzz-harness-python.git
```

Install drives the conformance suite against `src/server.py` before it records anything; a plugin that violates any rule is not recorded. `afz harnesses` lists what the registry holds.

A scan project names the harness and no command:

```json
{ "harness": { "name": "python" } }
```

The engine resolves the plugin argv from the registry record. To try the plugin on the fixture that ships here:

```sh
afz probe-plugin --path test-targets/pricing
```

## Author

Edit, then validate — there are no dependencies to fetch:

```sh
afz validate-harness
```

`afz validate-harness` with no argument validates the repository it is run in: it renders the conformance project with this repository's own emitter, drives the suite, and reports rule by rule. It never touches an install or a registry.

Run the unit tests and the wire-vocabulary contract tests:

```sh
AFZ_DOCS=/path/to/autofuzz/docs python3 -m unittest discover -s test -t .
```

`AFZ_DOCS` points at an engine checkout; `test/contract_test.py` reads `docs/schema/`, `docs/architecture.md`, and `docs/harness-authoring.md` from it. The default is the sibling checkout `../autofuzz/docs`; CI sets the variable explicitly.

## afz-harness.json

| key | meaning |
|---|---|
| `install` | argv that fetch dependencies; run only by `afz install-harness`, never by `afz validate-harness`. This harness has none: the standard library is the dependency set |
| `build` | argv that compile the plugin; run by both commands, after `install`, in order, in this root. This harness has none: Python source runs as written |
| `command` | the plugin argv; an element that names an existing file is resolved against this root |
| `conformance.emitter` | a program run as `<argv…> --out <dir>` that renders the whole conformance scan project — source tree, `autofuzz.json`, and `afz-conformance-manifest.json` — into the directory it is given; that rendered project is the only project validation ever drives |
| `conformance.deadlineMs` | the per-invocation deadline the suite passes, default 1000 |

The emitter is a standalone program: `conformance/emit.py` imports `argparse`, `json`, and `pathlib` only. A harness with no `conformance` block installs only with `--no-validate`, and `afz validate-harness` refuses it by name, because there is nothing to validate against.

## The conformance project

`conformance/emit.py` renders a small pricing package and the manifest that names the symbol behind each template property. `conformance/validate.py` is the project's own fixture validator: it imports the rendered fixture and the standard library only — never the plugin, never the emitter — and the suite requires its verdicts to agree with the plugin's.

## The contract

`docs/harness-authoring.md` in the engine repository, <https://github.com/DustinEwan/autofuzz>, states the plugin contract this harness implements.
