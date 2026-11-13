"""The `python` harness test package; see `contract_test.py`.

`unittest discover` matches `test*.py` by default; these files are named
`*_test.py` to mirror `test/contract.test.mjs` in `autofuzz-harness-js-ts`, so
`load_tests` is what makes the plain discovery command find them:

    python3 -m unittest discover -s test -t .
"""

import os
import unittest


def load_tests(loader, tests, pattern):
    here = os.path.dirname(os.path.abspath(__file__))
    return loader.discover(start_dir=here, top_level_dir=here, pattern="*_test.py")
