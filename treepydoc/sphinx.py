"""Swap treepydoc in for numpydoc's parser inside a Sphinx build.

Add this instead of `numpydoc` to `extensions` in `conf.py`:

    extensions = ["treepydoc.sphinx"]

Everything else -- every `numpydoc_*` config value, the templates, the emitted
reStructuredText -- stays exactly as it was. Only the parse changes.

How it works: `numpydoc.numpydoc.setup` takes a `get_doc_object_` argument and
installs it as the module global that `mangle_docstrings` and
`mangle_signature` call. That is a documented extension point, so this module
does not patch anything; it builds its own `get_doc_object` and hands it over.

numpydoc's Sphinx layer is *rendering* -- `SphinxDocString` subclasses
`NumpyDocString` and overrides the `_str_*` methods with ones that emit Sphinx
directives. That rendering is reused here rather than copied, by rebuilding
each class on treepydoc's parser with the same method bodies. Copying it would
mean maintaining a second copy of 400 lines of template glue that has to stay
byte-identical to whatever numpydoc version is installed.
"""

from __future__ import annotations

import inspect
import os
import pydoc
from collections.abc import Callable

from jinja2 import FileSystemLoader
from jinja2.sandbox import SandboxedEnvironment
from numpydoc import docscrape_sphinx as _numpydoc_sphinx
from numpydoc import numpydoc as _numpydoc_ext
from sphinx.jinja2glue import BuiltinTemplateLoader

from . import ClassDoc, FunctionDoc, NumpyDocString

__all__ = [
    "SphinxDocString",
    "SphinxFunctionDoc",
    "SphinxClassDoc",
    "SphinxObjDoc",
    "get_doc_object",
    "setup",
]

_TEMPLATE_DIRS = [os.path.join(os.path.dirname(_numpydoc_sphinx.__file__), "templates")]


def _rendering_methods(cls):
    """The parts of a numpydoc Sphinx class that are pure rendering.

    `__init__` is dropped because every one of them calls its base class by
    name rather than through `super()`, which would route straight back into
    numpydoc's parser.
    """
    return {
        name: value
        for name, value in vars(cls).items()
        if name not in ("__init__", "__dict__", "__weakref__")
    }


def _load_config(self, config):
    """`SphinxDocString.load_config`, with numpydoc's template directory.

    Reused verbatim except for the template path, which has to resolve against
    numpydoc's package rather than this one.
    """
    _numpydoc_sphinx.SphinxDocString.load_config(self, config)


class SphinxDocString(NumpyDocString):
    pass


for _name, _value in _rendering_methods(_numpydoc_sphinx.SphinxDocString).items():
    setattr(SphinxDocString, _name, _value)


def _sphinx_doc_string_init(self, docstring, config=None):
    config = {} if config is None else config
    NumpyDocString.__init__(self, docstring, config=config)
    self.load_config(config)


SphinxDocString.__init__ = _sphinx_doc_string_init


def _str_see_also(self, func_role):
    """`SphinxDocString._str_see_also`, without the `super()` call.

    The original reads `super(SphinxDocString, self)`, resolved against
    numpydoc's module globals, so on an instance of *this* class it would raise
    TypeError. The body is otherwise unchanged.
    """
    out = []
    if self["See Also"]:
        see_also = NumpyDocString._str_see_also(self, func_role)
        out = [".. seealso::", ""]
        out += self._str_indent(see_also[2:])
    return out


SphinxDocString._str_see_also = _str_see_also


class SphinxFunctionDoc(SphinxDocString, FunctionDoc):
    def __init__(self, obj, doc=None, config=None):
        config = {} if config is None else config
        self.load_config(config)
        FunctionDoc.__init__(self, obj, doc=doc, config=config)


class SphinxClassDoc(SphinxDocString, ClassDoc):
    def __init__(self, obj, doc=None, func_doc=None, config=None):
        config = {} if config is None else config
        self.load_config(config)
        ClassDoc.__init__(self, obj, doc=doc, func_doc=None, config=config)


class SphinxObjDoc(SphinxDocString):
    def __init__(self, obj, doc=None, config=None):
        config = {} if config is None else config
        self._f = obj
        self.load_config(config)
        NumpyDocString.__init__(self, doc or "", config=config)


def get_doc_object(obj, what=None, doc=None, config=None, builder=None):
    """Dispatch to the right documenter. Mirrors numpydoc's, on our parser."""
    config = {} if config is None else config

    if what is None:
        if inspect.isclass(obj):
            what = "class"
        elif inspect.ismodule(obj):
            what = "module"
        elif isinstance(obj, Callable):
            what = "function"
        else:
            what = "object"

    if builder is not None:
        template_loader = BuiltinTemplateLoader()
        template_loader.init(builder, dirs=_TEMPLATE_DIRS)
    else:
        template_loader = FileSystemLoader(_TEMPLATE_DIRS)
    template_env = SandboxedEnvironment(loader=template_loader)
    config["template"] = template_env.get_template("numpydoc_docstring.rst")

    if what == "class":
        return SphinxClassDoc(obj, func_doc=SphinxFunctionDoc, doc=doc, config=config)
    elif what in ("function", "method"):
        return SphinxFunctionDoc(obj, doc=doc, config=config)
    else:
        if doc is None:
            doc = pydoc.getdoc(obj)
        return SphinxObjDoc(obj, doc, config=config)


def setup(app, get_doc_object_=get_doc_object):
    """Sphinx entry point: numpydoc's extension, with treepydoc's parser."""
    return _numpydoc_ext.setup(app, get_doc_object_=get_doc_object_)
