"""Test corpus of numpydoc docstrings for a conformance test suite.

CORPUS is a list of (name, docstring_text) pairs. Every entry in CORPUS
must parse without raising when fed to numpydoc.docscrape.NumpyDocString.

RAISING_CORPUS is a list of (name, docstring_text, exception_type_name)
triples for inputs that are expected to make NumpyDocString raise.

Targets numpydoc 1.10.

Sources, in priority order:
  1. Docstring literals from numpydoc/numpydoc/tests/test_docscrape.py
     (copied verbatim).
  2. Docstrings from
     numpydoc/numpydoc/tests/tinybuild/numpydoc_test_module.py.
  3. Hand-written edge cases (see the "Hand-written edge cases" section
     below).
  4. Hand-written edge cases targeting behaviour that is new or changed
     in numpydoc 1.10 (see the corresponding section below).
"""

CORPUS: list[tuple[str, str]] = []
RAISING_CORPUS: list[tuple[str, str, str]] = []


# ---------------------------------------------------------------------------
# 1. Verbatim docstrings from numpydoc/numpydoc/tests/test_docscrape.py
# ---------------------------------------------------------------------------

# doc_txt
CORPUS.append(("test_docscrape.doc_txt", '  numpy.multivariate_normal(mean, cov, shape=None, spam=None)\n\n  Draw values from a multivariate normal distribution with specified\n  mean and covariance.\n\n  The multivariate normal or Gaussian distribution is a generalisation\n  of the one-dimensional normal distribution to higher dimensions.\n\n  Parameters\n  ----------\n  mean : (N,) ndarray\n      Mean of the N-dimensional distribution.\n\n      .. math::\n\n         (1+2+3)/3\n\n  cov : (N, N) ndarray\n      Covariance matrix of the distribution.\n  shape : tuple of ints\n      Given a shape of, for example, (m,n,k), m*n*k samples are\n      generated, and packed in an m-by-n-by-k arrangement.  Because\n      each sample is N-dimensional, the output shape is (m,n,k,N).\n  dtype : data type object, optional (default : float)\n      The type and size of the data to be returned.\n\n  Returns\n  -------\n  out : ndarray\n      The drawn samples, arranged according to `shape`.  If the\n      shape given is (m,n,...), then the shape of `out` is\n      (m,n,...,N).\n\n      In other words, each entry ``out[i,j,...,:]`` is an N-dimensional\n      value drawn from the distribution.\n  list of str\n      This is not a real return value.  It exists to test\n      anonymous return values.\n  no_description\n\n  Other Parameters\n  ----------------\n  spam : parrot\n      A parrot off its mortal coil.\n\n  Raises\n  ------\n  RuntimeError\n      Some error\n\n  Warns\n  -----\n  RuntimeWarning\n      Some warning\n\n  Warnings\n  --------\n  Certain warnings apply.\n\n  Notes\n  -----\n  Instead of specifying the full covariance matrix, popular\n  approximations include:\n\n    - Spherical covariance (`cov` is a multiple of the identity matrix)\n    - Diagonal covariance (`cov` has non-negative elements only on the diagonal)\n\n  This geometrical property can be seen in two dimensions by plotting\n  generated data-points:\n\n  >>> mean = [0,0]\n  >>> cov = [[1,0],[0,100]] # diagonal covariance, points lie on x or y-axis\n\n  >>> x,y = multivariate_normal(mean,cov,5000).T\n  >>> plt.plot(x,y,\'x\'); plt.axis(\'equal\'); plt.show()\n\n  Note that the covariance matrix must be symmetric and non-negative\n  definite.\n\n  References\n  ----------\n  .. [1] A. Papoulis, "Probability, Random Variables, and Stochastic\n         Processes," 3rd ed., McGraw-Hill Companies, 1991\n  .. [2] R.O. Duda, P.E. Hart, and D.G. Stork, "Pattern Classification,"\n         2nd ed., Wiley, 2001.\n\n  See Also\n  --------\n  some, other, funcs\n  otherfunc : relationship\n  :py:meth:`spyder.widgets.mixins.GetHelpMixin.show_object_info`\n\n  Examples\n  --------\n  >>> mean = (1,2)\n  >>> cov = [[1,0],[1,0]]\n  >>> x = multivariate_normal(mean,cov,(3,3))\n  >>> print(x.shape)\n  (3, 3, 2)\n\n  The following is probably true, given that 0.6 is roughly twice the\n  standard deviation:\n\n  >>> print(list((x[0, 0, :] - mean) < 0.6))\n  [True, True]\n\n  .. index:: random\n     :refguide: random;distributions, random;gauss\n\n  '))

# doc_yields_txt
CORPUS.append(("test_docscrape.doc_yields_txt", '\nTest generator\n\nYields\n------\na : int\n    The number of apples.\nb : int\n    The number of bananas.\nint\n    The number of unknowns.\n'))

# doc_sent_txt
CORPUS.append(("test_docscrape.doc_sent_txt", '\nTest generator\n\nYields\n------\na : int\n    The number of apples.\n\nReceives\n--------\nb : int\n    The number of bananas.\nc : int\n    The number of oranges.\n\n'))

# test_returnyield: doc_text (Returns + Yields together; does not raise in 1.10)
CORPUS.append(("test_docscrape.test_returnyield.doc_text", '\nTest having returns and yields.\n\nReturns\n-------\nint\n    The number of apples.\n\nYields\n------\na : int\n    The number of apples.\nb : int\n    The number of bananas.\n\n'))

# test_section_twice: doc_text (Notes section appears twice -> raises ValueError)
RAISING_CORPUS.append(("test_docscrape.test_section_twice.doc_text", '\nTest having a section Notes twice\n\nNotes\n-----\nSee the next note for more information\n\nNotes\n-----\nThat should break...\n', "ValueError"))

# test_section_twice: Dummy class docstring (Notes section twice)
RAISING_CORPUS.append(("test_docscrape.test_section_twice.Dummy_class_doc", '\n        Dummy class.\n\n        Notes\n        -----\n        First note.\n\n        Notes\n        -----\n        Second note.\n\n        ', "ValueError"))

# test_section_twice: Dummy.spam / Dummy.ham method docstrings (fine on their own)
CORPUS.append(("test_docscrape.test_section_twice.Dummy.spam", 'Spam\n\nSpam spam.'))
CORPUS.append(("test_docscrape.test_section_twice.Dummy.ham", 'Cheese\n\nNo cheese.'))

# test_section_twice: dummy_func docstring (Notes section twice)
RAISING_CORPUS.append(("test_docscrape.test_section_twice.dummy_func_doc", '\n        Dummy function.\n\n        Notes\n        -----\n        First note.\n\n        Notes\n        -----\n        Second note.\n        ', "ValueError"))


# doc2
CORPUS.append(("test_docscrape.doc2", '\n    Returns array of indices of the maximum values of along the given axis.\n\n    Parameters\n    ----------\n    a : {array_like}\n        Array to look in.\n    axis : {None, integer}\n        If None, the index is into the flattened array, otherwise along\n        the specified axis'))

# doc3
CORPUS.append(("test_docscrape.doc3", '\n    my_signature(*params, **kwds)\n\n    Return this and that.\n    '))

# doc4
CORPUS.append(("test_docscrape.doc4", 'a.conj()\n\n    Return an array with all complex-valued elements conjugated.'))

# doc5
CORPUS.append(("test_docscrape.doc5", '\n    a.something()\n\n    Raises\n    ------\n    LinAlgException\n        If array is singular.\n\n    Warns\n    -----\n    SomeWarning\n        If needed\n    '))

# test_see_also: doc6
CORPUS.append(("test_docscrape.test_see_also.doc6", 'z(x,theta)\n\n    See Also\n    --------\n    func_a, func_b, func_c\n    func_d : some equivalent func\n    foo.func_e : some other func over\n             multiple lines\n    func_f, func_g, :meth:`func_h`, func_j,\n    func_k\n    func_f1, func_g1, :meth:`func_h1`, func_j1\n    func_f2, func_g2, :meth:`func_h2`, func_j2 : description of multiple\n    :obj:`baz.obj_q`\n    :obj:`~baz.obj_r`\n    :class:`class_j`: fubar\n        foobar\n    '))

# test_see_also_parse_error: text (See Also parse error -> ValueError in 1.10)
RAISING_CORPUS.append(("test_docscrape.test_see_also_parse_error.text", '\n    z(x,theta)\n\n    See Also\n    --------\n    :func:`~foo`\n    ', "ValueError"))

# test_see_also_print: Dummy class docstring
CORPUS.append(("test_docscrape.test_see_also_print.Dummy", '\n        See Also\n        --------\n        func_a, func_b\n        func_c : some relationship\n                 goes here\n        func_d\n        '))

# test_see_also_trailing_comma_warning: (warns, does not raise)
CORPUS.append(("test_docscrape.test_see_also_trailing_comma_warning", '\n            z(x,theta)\n\n            See Also\n            --------\n            func_f2, func_g2, :meth:`func_h2`, func_j2, : description of multiple\n            :class:`class_j`: fubar\n                foobar\n            '))

# test_unknown_section: doc_text (warns about unknown section, does not raise)
CORPUS.append(("test_docscrape.test_unknown_section.doc_text", '\nTest having an unknown section\n\nMope\n----\nThis should be ignored and warned about\n'))

# test_unknown_section: BadSection class docstring
CORPUS.append(("test_docscrape.test_unknown_section.BadSection", 'Class with bad section.\n\n        Nope\n        ----\n        This class has a nope section.\n        '))

# doc7
CORPUS.append(("test_docscrape.doc7", '\n\n        Doc starts on second line.\n\n        '))

# doc8: parameter with a colon and no type (header.removesuffix(' :'))
CORPUS.append(("test_docscrape.doc8", '\n\n        Parameters with colon and no types:\n\n        Parameters\n        ----------\n\n        data :\n            some stuff, technically invalid\n        '))

# test_returns_with_roles_no_names: a Returns entry using a sphinx role as the type
CORPUS.append(("test_docscrape.test_returns_with_roles_no_names", '\n        Returns\n        -------\n        str or :class:`NumpyDocString`\n        '))

# test_no_summary
CORPUS.append(("test_docscrape.test_no_summary", '\n        Parameters\n        ----------'))

# test_unicode
CORPUS.append(("test_docscrape.test_unicode", '\n    öäöäöäöäöåååå\n\n    öäöäöäööäååå\n\n    Parameters\n    ----------\n    ååå : äää\n        ööö\n\n    Returns\n    -------\n    ååå : ööö\n        äää\n\n    '))

# test_plot_examples (three variants)
CORPUS.append(("test_docscrape.test_plot_examples.1", '\n    Examples\n    --------\n    >>> import matplotlib.pyplot as plt\n    >>> plt.plot([1,2,3],[4,5,6])\n    >>> plt.show()\n    '))
CORPUS.append(("test_docscrape.test_plot_examples.2", '\n    Examples\n    --------\n    >>> from matplotlib import pyplot as plt\n    >>> plt.plot([1,2,3],[4,5,6])\n    >>> plt.show()\n    '))
CORPUS.append(("test_docscrape.test_plot_examples.3", '\n    Examples\n    --------\n    .. plot::\n\n       import matplotlib.pyplot as plt\n       plt.plot([1,2,3],[4,5,6])\n       plt.show()\n    '))

# test_class_members: Dummy class and its methods
CORPUS.append(("test_docscrape.test_class_members.Dummy", '\n        Dummy class.\n\n        '))
CORPUS.append(("test_docscrape.test_class_members.Dummy.spam", 'Spam\n\nSpam spam.'))
CORPUS.append(("test_docscrape.test_class_members.Dummy.ham", 'Cheese\n\nNo cheese.'))
CORPUS.append(("test_docscrape.test_class_members.Dummy.spammity", 'Spammity index'))
CORPUS.append(("test_docscrape.test_class_members.Dummy.Ignorable", 'local class, to be ignored'))

CORPUS.append(("test_docscrape.test_class_members.SubDummy", '\n        Subclass of Dummy class.\n\n        '))
CORPUS.append(("test_docscrape.test_class_members.SubDummy.ham", 'Cheese\n\nNo cheese.\nOverloaded Dummy.ham'))
CORPUS.append(("test_docscrape.test_class_members.SubDummy.bar", 'Bar\n\nNo bar'))


# test_duplicate_signature
CORPUS.append(("test_docscrape.test_duplicate_signature", '\n    z(x1, x2)\n\n    z(a, theta)\n    '))


# class_doc_txt
CORPUS.append(("test_docscrape.class_doc_txt", '\n    Foo\n\n    Parameters\n    ----------\n    f : callable ``f(t, y, *f_args)``\n        Aaa.\n    jac : callable ``jac(t, y, *jac_args)``\n\n        Bbb.\n\n    Attributes\n    ----------\n    t : float\n        Current time.\n    y : ndarray\n        Current variable values.\n\n        * hello\n        * world\n    an_attribute : float\n        The docstring is printed instead\n    no_docstring : str\n        But a description\n    no_docstring2 : str\n    multiline_sentence\n    midword_period\n    no_period\n\n    Methods\n    -------\n    a\n    b\n    c\n\n    Other Parameters\n    ----------------\n\n    another parameter : str\n        This parameter is less important.\n\n    Notes\n    -----\n\n    Some notes about the class.\n\n    Examples\n    --------\n    For usage examples, see `ode`.\n'))


# test_class_members_doc_sphinx: property docstrings
CORPUS.append(("test_docscrape.test_class_members_doc_sphinx.an_attribute", 'Test attribute'))
CORPUS.append(("test_docscrape.test_class_members_doc_sphinx.multiline_sentence", 'This is a\n            sentence. It spans multiple lines.'))
CORPUS.append(("test_docscrape.test_class_members_doc_sphinx.midword_period", 'The sentence for numpy.org.'))
CORPUS.append(("test_docscrape.test_class_members_doc_sphinx.no_period", 'This does not have a period\n            so we truncate its summary to the first linebreak\n\n            Apparently.\n            '))


# test_class_attributes_as_member_list: Foo class docstring
CORPUS.append(("test_docscrape.test_class_attributes_as_member_list.Foo", '\n        Class docstring.\n\n        Attributes\n        ----------\n        an_attribute\n            Another description that is not used.\n\n        '))
CORPUS.append(("test_docscrape.test_class_attributes_as_member_list.Foo.an_attribute", 'Test attribute'))


# test_nonstandard_property
CORPUS.append(("test_docscrape.test_nonstandard_property.attr", 'test attribute'))


# test_args_and_kwargs
CORPUS.append(("test_docscrape.test_args_and_kwargs", '\n    Parameters\n    ----------\n    param1 : int\n        First parameter\n    *args : tuple\n        Arguments\n    **kwargs : dict\n        Keyword arguments\n    '))


# test_autoclass
CORPUS.append(("test_docscrape.test_autoclass", '\nA top section before\n\n.. autoclass:: str\n    '))


# xref_doc_txt
CORPUS.append(("test_docscrape.xref_doc_txt", '\nTest xref in Parameters, Other Parameters and Returns\n\nParameters\n----------\np1 : int\n    Integer value\n\np2 : float, optional\n    Integer value\n\nOther Parameters\n----------------\np3 : list[int]\n    List of integers\np4 : :class:`pandas.DataFrame`\n    A dataframe\np5 : sequence of `int`\n    A sequence\n\nReturns\n-------\nout : array\n    Numerical return value\n'))


# test_namedtuple_class_docstring: MyFoo / MyFooWithParams class docstrings
CORPUS.append(("test_docscrape.test_namedtuple_class_docstring.MyFoo", "MyFoo's class docstring"))
CORPUS.append(("test_docscrape.test_namedtuple_class_docstring.MyFooWithParams", "\n        MyFoo's class docstring\n\n        Parameters\n        ----------\n        bar : str\n           The bar attribute\n        baz : str\n           The baz attribute\n        "))


# ---------------------------------------------------------------------------
# 2. Docstrings from
#    numpydoc/numpydoc/tests/tinybuild/numpydoc_test_module.py
# ---------------------------------------------------------------------------

_tinybuild_module_doc = """Numpydoc test module.

.. currentmodule:: numpydoc_test_module

.. autosummary::
   :toctree: generated/

   MyClass
   my_function

Reference [1]_

References
----------
.. [1] https://numpydoc.readthedocs.io
"""
CORPUS.append(("tinybuild.numpydoc_test_module", _tinybuild_module_doc))

_tinybuild_myclass_doc = """A class.

    Reference [2]_

    Parameters
    ----------
    *args : iterable
        Arguments.
    **kwargs : dict
        Keyword arguments.

    References
    ----------
    .. [2] https://numpydoc.readthedocs.io
    """
CORPUS.append(("tinybuild.MyClass", _tinybuild_myclass_doc))

_tinybuild_myclass_example_doc = """Example method."""
CORPUS.append(("tinybuild.MyClass.example", _tinybuild_myclass_example_doc))

_tinybuild_my_function_doc = """Return None.

    See [3]_.

    Parameters
    ----------
    *args : iterable
        Arguments.
    **kwargs : dict
        Keyword arguments.

    Returns
    -------
    out : None
        The output.

    References
    ----------
    .. [3] https://numpydoc.readthedocs.io
    """
CORPUS.append(("tinybuild.my_function", _tinybuild_my_function_doc))


# ---------------------------------------------------------------------------
# 3. Hand-written edge cases
# ---------------------------------------------------------------------------

# --- empty / whitespace / single line -------------------------------------

CORPUS.append(("edge.empty_string", ""))
CORPUS.append(("edge.whitespace_only", "   \n   \n\t\n   "))
CORPUS.append(("edge.single_line", "This is a single line summary."))

# --- no trailing newline ----------------------------------------------------

CORPUS.append((
    "edge.no_trailing_newline",
    "Summary line with no trailing newline.\n\nParameters\n----------\nx : int\n    An int."
))

# --- underline length variations --------------------------------------------

# Underline LONGER than the title: still a valid section.
CORPUS.append((
    "edge.underline_longer_than_title",
    "Summary.\n\nNotes\n----------------\nSome notes here.\n"
))

# Underline SHORTER than the title: NOT recognized as a section header,
# so it is treated as ordinary summary/extended-summary text.
CORPUS.append((
    "edge.underline_shorter_than_title",
    "Summary.\n\nParameters\n---\nThis is not really a section because the\n"
    "underline is too short to match the title length.\n"
))

# Underline with trailing junk after enough dashes, e.g. '-----abc' under a
# 5-char title ('Notes'). This does not match the strict dashes-only
# underline regex, so it is not treated as a section header either.
CORPUS.append((
    "edge.underline_trailing_junk",
    "Summary.\n\nNotes\n-----abc\nThis is not recognized as a Notes section.\n"
))

# '=' underlines instead of '-': not a recognized numpydoc section underline
# character, so this is not parsed as a section header.
CORPUS.append((
    "edge.equals_underline",
    "Summary.\n\nParameters\n==========\nx : int\n    An int.\n"
))

# --- section header not preceded by a blank line ----------------------------

CORPUS.append((
    "edge.section_header_no_blank_line_before",
    "Summary line immediately before section.\nParameters\n----------\nx : int\n    An int.\n"
))

# --- parameter header with 0, 1, 2, 3 occurrences of ' : ' ------------------

CORPUS.append((
    "edge.param_header_zero_colons",
    "Summary.\n\nParameters\n----------\nx\n    A parameter with no type.\n"
))

CORPUS.append((
    "edge.param_header_one_colon",
    "Summary.\n\nParameters\n----------\nx : int\n    A parameter with a type.\n"
))

CORPUS.append((
    "edge.param_header_two_colons",
    "Summary.\n\nParameters\n----------\nx : dict of {str : int}\n"
    "    A parameter whose type description itself contains ' : '.\n"
))

CORPUS.append((
    "edge.param_header_three_colons",
    "Summary.\n\nParameters\n----------\nx : dict of {str : int} : weird\n"
    "    A parameter whose type description contains ' : ' twice more.\n"
))

# --- parameter header irregular spacing -------------------------------------

CORPUS.append((
    "edge.param_spacing_double_space_before_colon",
    "Summary.\n\nParameters\n----------\nx  : int\n    Extra space before colon.\n"
))

CORPUS.append((
    "edge.param_spacing_double_space_after_colon",
    "Summary.\n\nParameters\n----------\nx :  int\n    Extra space after colon.\n"
))

CORPUS.append((
    "edge.param_spacing_no_space_after_colon",
    "Summary.\n\nParameters\n----------\nx :int\n    No space after colon.\n"
))

CORPUS.append((
    "edge.param_spacing_single_colon_no_space_before",
    "Summary.\n\nParameters\n----------\nx: int\n    No space before colon.\n"
))

# --- case variations of section names ---------------------------------------

CORPUS.append((
    "edge.section_name_lowercase",
    "Summary.\n\nparameters\n----------\nx : int\n    An int.\n"
))

CORPUS.append((
    "edge.section_name_uppercase",
    "Summary.\n\nPARAMETERS\n----------\nx : int\n    An int.\n"
))

CORPUS.append((
    "edge.section_name_mixedcase_other_parameters",
    "Summary.\n\nOther PARAMETERs\n----------------\nx : int\n    An int.\n"
))

# --- blank lines inside a parameter description -----------------------------

CORPUS.append((
    "edge.param_description_with_blank_lines",
    "Summary.\n\nParameters\n----------\nx : int\n"
    "    First paragraph of the description.\n\n"
    "    Second paragraph, after a blank line.\n"
))

# --- parameter with no description ------------------------------------------

CORPUS.append((
    "edge.param_with_no_description",
    "Summary.\n\nParameters\n----------\nx : int\ny : float\n    Has a description.\n"
))

# --- See Also variations -----------------------------------------------------

CORPUS.append((
    "edge.see_also_trailing_comma",
    "Summary.\n\nSee Also\n--------\nfunc_a, func_b,\n"
))

CORPUS.append((
    "edge.see_also_trailing_period",
    "Summary.\n\nSee Also\n--------\nfunc_a, func_b.\n"
))

CORPUS.append((
    "edge.see_also_with_roles",
    "Summary.\n\nSee Also\n--------\n:func:`func_a`, :meth:`func_b`, :obj:`func_c`\n"
))

CORPUS.append((
    "edge.see_also_multiline_description",
    "Summary.\n\nSee Also\n--------\nfunc_a : a short description that\n"
    "    continues on a second line\n    and a third line too.\n"
))

# --- .. index:: vs .. index :: (space before colons) ------------------------

CORPUS.append((
    "edge.index_no_space_before_colons",
    "Summary.\n\n.. index:: random\n   :refguide: random;distributions\n"
))

CORPUS.append((
    "edge.index_space_before_colons",
    "Summary.\n\n.. index :: random\n   :refguide: random;distributions\n"
))

# --- unknown section name ----------------------------------------------------

CORPUS.append((
    "edge.unknown_section_name",
    "Summary.\n\nBogusSection\n------------\nSome text under an unrecognized section.\n"
))

# --- CRLF line endings --------------------------------------------------------

CORPUS.append((
    "edge.crlf_line_endings",
    "Summary line.\r\n\r\nParameters\r\n----------\r\nx : int\r\n    An int parameter.\r\n"
))

# --- non-ASCII text in summary and descriptions ------------------------------

CORPUS.append((
    "edge.non_ascii_summary_and_description",
    "Résumé: café, naïve, 日本語のテスト.\n\n"
    "Parameters\n----------\n"
    "café : str\n    Un paramètre avec des accents éàüö and 中文字符.\n"
))

# --- deeply indented docstring (as from a real Python method) ---------------

CORPUS.append((
    "edge.deeply_indented_method_docstring",
    "        Compute something useful.\n"
    "\n"
    "        Parameters\n"
    "        ----------\n"
    "        x : int\n"
    "            The input value.\n"
    "        y : float, optional\n"
    "            Another input value.\n"
    "\n"
    "        Returns\n"
    "        -------\n"
    "        out : int\n"
    "            The computed result.\n"
    "        "
))


# ---------------------------------------------------------------------------
# 4. Hand-written edge cases targeting numpydoc 1.10 behaviour
# ---------------------------------------------------------------------------

# --- parameter header ending in " :" with nothing after ---------------------
# 1.10 does `header.removesuffix(" :")` when " : " is not found in the
# header, so a bare trailing " :" is stripped and the whole header becomes
# the (typeless) name.

CORPUS.append((
    "edge_110.param_header_trailing_colon_only",
    "Summary.\n\nParameters\n----------\nx :\n"
    "    A parameter header ending in ' :' with no type text after it.\n"
    "y : int\n    A normal parameter for comparison.\n"
))

# --- type containing ' : ' (1.10 uses split(" : ", maxsplit=1)) -------------
# NOTE: the pre-existing edge.param_header_two_colons and
# edge.param_header_three_colons cases above already exercise this; these
# add coverage for the Other Parameters / Returns sections too.

CORPUS.append((
    "edge_110.other_parameters_type_with_colon",
    "Summary.\n\nOther Parameters\n----------------\nx : Mapping[str : int]\n"
    "    A parameter whose type contains a single ' : ' separator beyond\n"
    "    the header's own.\n"
))

CORPUS.append((
    "edge_110.returns_type_with_three_colons",
    "Summary.\n\nReturns\n-------\nout : dict of {str : int} : weird : still\n"
    "    A description.\n"
))

# --- See Also role with a "py:" prefix (1.10's _role allows "(py:)?\\w+") ---

CORPUS.append((
    "edge_110.see_also_py_role",
    "Summary.\n\nSee Also\n--------\n:py:meth:`bytes.decode`\n:meth:`bytes.encode`\n"
))

# --- a section whose body is empty (dedent_lines([]) returns ['']) ----------
# An empty Parameters section (immediately followed by another section)
# yields a spurious single Parameter with an empty name/type/desc, but does
# not raise.

CORPUS.append((
    "edge_110.empty_section_body",
    "Summary.\n\nParameters\n----------\n\nReturns\n-------\nx : int\n    A value.\n"
))

# --- indented docstring with several parameters (1.10 dedents the section --
# --- body first, via dedent_lines(content) in _parse_param_list) -----------

CORPUS.append((
    "edge_110.indented_section_body_several_params",
    "Summary.\n\nParameters\n----------\n"
    "    x : int\n        Extra indented relative to the header underline.\n"
    "    y : float\n        Another extra indented parameter.\n"
    "    z : str\n        A third extra indented parameter.\n"
))

# --- underline length differs from the title, both longer and shorter ------
# (1.10 warns via _error_location(..., error=False) in _is_at_section).
# The pre-existing edge.underline_longer_than_title and
# edge.underline_shorter_than_title cases above already exercise this for a
# Notes/Parameters section; these add coverage for other section names.

CORPUS.append((
    "edge_110.underline_longer_than_title_warns",
    "Summary.\n\nWarns\n--------\nSomeWarning\n"
    "    A warning entry under an overlong underline.\n"
))

CORPUS.append((
    "edge_110.underline_shorter_than_title_notes",
    "Summary.\n\nNotes\n---\n"
    "This underline is shorter than the title and is not treated as a\n"
    "section header.\n"
))
