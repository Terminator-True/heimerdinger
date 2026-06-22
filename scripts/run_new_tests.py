"""Simple test runner for the newly added tests.
Runs test_ functions from tests/test_question_classification.py and tests/test_retrieval_recipes.py
and prints a concise pass/fail summary.
"""
import importlib
import inspect
import traceback

import sys
sys.path.append(r"E:/heimerdinger")

modules = [
    "tests.test_question_classification",
    "tests.test_retrieval_recipes",
]

results = []

for mod_name in modules:
    mod = importlib.import_module(mod_name)
    for name, fn in inspect.getmembers(mod, inspect.isfunction):
        if name.startswith("test_"):
            try:
                fn()
                results.append((mod_name + "." + name, True, ""))
            except Exception as e:
                tb = traceback.format_exc()
                results.append((mod_name + "." + name, False, tb))

for name, ok, info in results:
    print(f"{name}: {'PASS' if ok else 'FAIL'}")
    if not ok:
        print(info)

# summary
passed = sum(1 for r in results if r[1])
total = len(results)
print(f"\nSummary: {passed}/{total} tests passed")
