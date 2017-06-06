"""Tests for the namedtuple implementation in collections_overlay.py."""
import textwrap


from pytype import utils
from pytype.tests import test_inference


class NamedtupleTests(test_inference.InferenceTest):
  """Tests for collections.namedtuple."""

  def _repeat_type(self, type_str, n):
    return ", ".join((type_str,) * n) if n else "nothing"

  def _namedtuple_def(self, name, fields, suffix=""):
    num_fields = len(fields)
    field_defs = "\n  ".join(
        "%s = ...  # type: Any" % field for field in fields)
    field_names = "".join(", " + field for field in fields)
    nt = textwrap.dedent("""\
      import collections
      from typing import Any, Callable, Iterable, Tuple, Type, TypeVar
      collections = ...  # type: module
      _T{name} = TypeVar("_T{name}", bound={name})
      class {name}(tuple):
        __dict__ = ...  # type: collections.OrderedDict[str, Any]
        __slots__ = ...  # type: Tuple[nothing]
        _fields = ...  # type: Tuple[{repeat_str}]
        {field_defs}
        def __getnewargs__(self) -> Tuple[{repeat_any}]: ...
        def __getstate__(self) -> None: ...
        def __init__(self, *args, **kwargs) -> None: ...
        def __new__(cls: Type[_T{name}]{field_names}) -> _T{name}: ...
        def _asdict(self) -> collections.OrderedDict[str, Any]: ...
        @classmethod
        def _make(cls, iterable: Iterable, new = ..., len: Callable[[Iterable], int] = ...) -> {name}: ...
        def _replace(self, **kwds) -> {name}: ...
    """).format(name=name,
                repeat_str=self._repeat_type("str", num_fields),
                field_defs=field_defs,
                repeat_any=self._repeat_type("Any", num_fields),
                field_names=field_names)
    return nt + suffix

  def test_basic_namedtuple(self):
    ty = self.Infer("""
      import collections

      X = collections.namedtuple("X", ["y", "z"])
      a = X(y=1, z=2)
      """)
    self.assertTypesMatchPytd(
        ty, self._namedtuple_def("X", ["y", "z"], "a = ...  # type: X"))

  def test_no_fields(self):
    ty = self.Infer("""
        import collections

        F = collections.namedtuple("F", [])
        a = F()
        """)
    self.assertTypesMatchPytd(
        ty, self._namedtuple_def("F", [], "a = ...  # type: F"))

  def test_str_args(self):
    ty = self.Infer("""
        import collections

        S = collections.namedtuple("S", "a b c")
        b = S(1, 2, 3)
    """)
    self.assertTypesMatchPytd(
        ty, self._namedtuple_def("S", ["a", "b", "c"], "b = ...  # type: S"))

  def test_str_args2(self):
    self.assertNoErrors("""
        import collections
        collections.namedtuple("_", "a,b,c")
        """)
    self.assertNoErrors("""
        import collections
        collections.namedtuple("_", "a, b, c")
        """)
    self.assertNoErrors("""
        import collections
        collections.namedtuple("_", "a ,b")
        """)

  def test_bad_fieldnames(self):
    _, errorlog = self.InferAndCheck("""\
        import collections
        collections.namedtuple("_", ["abc", "def", "ghi"])
        collections.namedtuple("_", "_")
        collections.namedtuple("_", "a, 1")
        collections.namedtuple("_", "a, !")
        collections.namedtuple("_", "a, b, c, a")
        collections.namedtuple("1", "")
        """)
    self.assertErrorLogIs(errorlog,
                          [(2, "invalid-namedtuple-arg"),
                           (3, "invalid-namedtuple-arg"),
                           (4, "invalid-namedtuple-arg"),
                           (5, "invalid-namedtuple-arg"),
                           (6, "invalid-namedtuple-arg"),
                           (7, "invalid-namedtuple-arg")])

  def test_rename(self):
    ty = self.Infer("""
        import collections

        S = collections.namedtuple("S", "abc def ghi abc", rename=True)
        """)
    self.assertTypesMatchPytd(
        ty, self._namedtuple_def("S", ["abc", "_1", "ghi", "_3"]))

  def test_bad_initialize(self):
    _, errlog = self.InferAndCheck("""\
        from collections import namedtuple

        X = namedtuple("X", "y z")
        a = X(1)
        b = X(y = 2)
        c = X(w = 3)
        d = X(y = "hello", z = 4j)  # works
        """)
    self.assertErrorLogIs(errlog, [
        (4, "missing-parameter"),
        (5, "missing-parameter"),
        (6, "wrong-keyword-args")])

  def test_class_name(self):
    _, errorlog = self.InferAndCheck(
        """\
        import collections
        F = collections.namedtuple("S", ['a', 'b', 'c'])
        """)
    self.assertErrorLogIs(errorlog, [(2, "invalid-namedtuple-name")])

  def test_calls(self):
    self.assertNoErrors("""
        import collections
        collections.namedtuple("_", "")
        collections.namedtuple(typename="_", field_names="a")
        collections.namedtuple("_", "", True, False)
        """)
    self.assertNoCrash("""
      collections.namedtuple(u"foo", [])
      collections.namedtuple(u"foo", [], replace=True if __random__ else False)
      collections.namedtuple(1.0, [])
      collections.namedtuple("foo", [1j, 2j])
      collections.namedtuple(__any_object__, __any_object__)
      collections.namedtuple(__any_object__, [__any_object__])
      """)

  def test_bad_call(self):
    _, errorlog = self.InferAndCheck("""\
        import collections
        collections.namedtuple()
        collections.namedtuple("_")
        collections.namedtuple("_", "", True, True, True)
        collections.namedtuple("_", "", True, verbose=True)
        """)
    self.assertErrorLogIs(errorlog,
                          [(2, "missing-parameter"),
                           (3, "missing-parameter"),
                           (4, "wrong-arg-count"),
                           (5, "duplicate-keyword-argument")])

  def test_constructors(self):
    self.assertNoErrors("""
        import collections
        X = collections.namedtuple("X", "a b c")
        g = X(1, 2, 3)
        i = X._make((7, 8, 9))
        j = X._make((10, 11, 12), tuple.__new__, len)
        """)

  def test_instance_types(self):
    ty = self.Infer(
        """
        import collections
        X = collections.namedtuple("X", "a b c")
        a = X._make((1, 2, 3))
        """)
    self.assertTypesMatchPytd(
        ty, self._namedtuple_def("X", ["a", "b", "c"], "a = ...  # type: X"))

  def test_namedtuple_match(self):
    self.assertNoErrors("""\
        from __future__ import google_type_annotations
        import collections
        from typing import Any, Dict

        X = collections.namedtuple("X", ["a"])

        def GetRefillSeekerRanks() -> Dict[str, X]:
          return {"hello": X(__any_object__)}
        """)

  def test_instantiate_pyi_namedtuple(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class X(NamedTuple('X', [('y', str), ('z', int)])): ...
      """)
      _, errors = self.InferAndCheck("""\
        import foo
        foo.X()  # wrong arg count
        foo.X(0, "")  # wrong types
        foo.X(z="", y=0)  # wrong types
        foo.X("", 0)
        foo.X(y="", z=0)
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(2, "missing-parameter", r"y"),
                                     (3, "wrong-arg-types", r"str.*int"),
                                     (4, "wrong-arg-types", r"str.*int")])

  def test_use_pyi_namedtuple(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class X(NamedTuple("X", [])): ...
      """)
      _, errors = self.InferAndCheck("""\
        import foo
        foo.X()._replace()
        foo.X().nonsense
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(3, "attribute-error", r"nonsense.*X")])

  def test_subclass_pyi_namedtuple(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class X(NamedTuple("X", [("y", int)])): ...
      """)
      self.assertNoErrors("""
        import foo
        class Y(foo.X):
          def __new__(cls):
            return super(Y, cls).__new__(cls, 0)
        Y()
      """, pythonpath=[d.path])


if __name__ == "__main__":
  test_inference.main()