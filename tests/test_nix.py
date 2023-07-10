from typing import (
    Iterator,
    Optional,
    Tuple,
    Dict,
    List,
    Set,
    Any,
)
import subprocess
import pytest
import json


def assert_deepequals(
    a: Any,
    b: Any,
    ignore_paths: Optional[Set[str]] = None,
    _path: Optional[Tuple[str]] = None,
):
    """Compare objects a and b keeping track of object path for error reporting.

    Keyword arguments:
    a -- Object a
    b -- Object b
    ignore_paths -- List of object paths (delimited by .)

    Example:
    assert_deepequals({
        "poetry-version": "1.0.0a3",
        "content-hash": "example",
    }, {
      "metadata": {
        "poetry-version": "1.0.0a4",
        "content-hash": "example",
      }
    }, ignore_paths=set(["metadata.poetry-version"]))
    """

    _path = _path if _path else tuple()
    ignore_paths = ignore_paths if ignore_paths else set()
    path = ".".join(_path)
    err = ValueError("{}: {} != {}".format(path, a, b))

    def make_path(entry):
        return _path + (str(entry),)

    if isinstance(a, list):
        if not isinstance(b, list) or len(a) != len(b):
            raise err

        for vals in zip(a, b):
            p = make_path("[]")
            if ".".join(p) not in ignore_paths:
                assert_deepequals(*vals, _path=p, ignore_paths=ignore_paths)

    elif isinstance(a, dict):
        if not isinstance(b, dict):
            raise err

        for key in set(a.keys()) | set(b.keys()):
            p = make_path(key)
            if ".".join(p) not in ignore_paths:
                assert_deepequals(a[key], b[key], _path=p, ignore_paths=ignore_paths)

    elif a == b:
        return

    else:
        raise err


def nix_eval(attr: str, args: Optional[List[str]] = None) -> Dict:
    cmd: List[str] = ["nix", "eval", "--json"]
    if args:
        cmd.extend(args)
    cmd.append(attr)

    proc = subprocess.run(
        cmd, stdout=subprocess.PIPE, check=True, stderr=subprocess.PIPE
    )
    return json.loads(proc.stdout)


def gen_checks() -> Iterator[str]:
    """Get sub attributes of flake attribute libChecks to generate tests"""
    proc = subprocess.run(
        [
            "nix",
            "eval",
            "--json",
            "--apply",
            "builtins.mapAttrs (_: v: builtins.attrNames v)",
            "--json",
            ".#libChecks",
        ],
        check=True,
        stdout=subprocess.PIPE,
    )
    for suite, cases in json.loads(proc.stdout).items():
        for test_case in cases:
            yield f"{suite}.{test_case}"


@pytest.mark.parametrize("check", gen_checks())
def test_attrs(check) -> None:
    """Automatically generate pytest tests from Nix attribute set"""
    result = nix_eval(f".#libChecks.{check}")
    assert_deepequals(result["output"], result["expected"])