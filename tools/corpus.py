"""Test corpus of numpydoc docstrings for a conformance test suite.

CORPUS is a list of (name, docstring_text) pairs. Every entry in CORPUS
must parse without raising when fed to numpydoc.docscrape.NumpyDocString.

RAISING_CORPUS is a list of (name, docstring_text, exception_type_name)
triples for inputs that are expected to make NumpyDocString raise.

Sources, in priority order:
  1. Docstring literals from numpydoc/numpydoc/tests/test_docscrape.py
     (copied verbatim).
  2. Docstrings from
     numpydoc/numpydoc/tests/tinybuild/numpydoc_test_module.py.
  3. Hand-written edge cases (see the "Hand-written edge cases" section
     below).
"""

CORPUS: list[tuple[str, str]] = []
RAISING_CORPUS: list[tuple[str, str, str]] = []


# ---------------------------------------------------------------------------
# 1. Verbatim docstrings from numpydoc/numpydoc/tests/test_docscrape.py
# ---------------------------------------------------------------------------

# doc_txt
doc_txt = '''\
  numpy.multivariate_normal(mean, cov, shape=None, spam=None)

  Draw values from a multivariate normal distribution with specified
  mean and covariance.

  The multivariate normal or Gaussian distribution is a generalisation
  of the one-dimensional normal distribution to higher dimensions.

  Parameters
  ----------
  mean : (N,) ndarray
      Mean of the N-dimensional distribution.

      .. math::

         (1+2+3)/3

  cov : (N, N) ndarray
      Covariance matrix of the distribution.
  shape : tuple of ints
      Given a shape of, for example, (m,n,k), m*n*k samples are
      generated, and packed in an m-by-n-by-k arrangement.  Because
      each sample is N-dimensional, the output shape is (m,n,k,N).

  Returns
  -------
  out : ndarray
      The drawn samples, arranged according to `shape`.  If the
      shape given is (m,n,...), then the shape of `out` is
      (m,n,...,N).

      In other words, each entry ``out[i,j,...,:]`` is an N-dimensional
      value drawn from the distribution.
  list of str
      This is not a real return value.  It exists to test
      anonymous return values.
  no_description

  Other Parameters
  ----------------
  spam : parrot
      A parrot off its mortal coil.

  Raises
  ------
  RuntimeError
      Some error

  Warns
  -----
  RuntimeWarning
      Some warning

  Warnings
  --------
  Certain warnings apply.

  Notes
  -----
  Instead of specifying the full covariance matrix, popular
  approximations include:

    - Spherical covariance (`cov` is a multiple of the identity matrix)
    - Diagonal covariance (`cov` has non-negative elements only on the diagonal)

  This geometrical property can be seen in two dimensions by plotting
  generated data-points:

  >>> mean = [0,0]
  >>> cov = [[1,0],[0,100]] # diagonal covariance, points lie on x or y-axis

  >>> x,y = multivariate_normal(mean,cov,5000).T
  >>> plt.plot(x,y,'x'); plt.axis('equal'); plt.show()

  Note that the covariance matrix must be symmetric and non-negative
  definite.

  References
  ----------
  .. [1] A. Papoulis, "Probability, Random Variables, and Stochastic
         Processes," 3rd ed., McGraw-Hill Companies, 1991
  .. [2] R.O. Duda, P.E. Hart, and D.G. Stork, "Pattern Classification,"
         2nd ed., Wiley, 2001.

  See Also
  --------
  some, other, funcs
  otherfunc : relationship

  Examples
  --------
  >>> mean = (1,2)
  >>> cov = [[1,0],[1,0]]
  >>> x = multivariate_normal(mean,cov,(3,3))
  >>> print(x.shape)
  (3, 3, 2)

  The following is probably true, given that 0.6 is roughly twice the
  standard deviation:

  >>> print(list((x[0, 0, :] - mean) < 0.6))
  [True, True]

  .. index:: random
     :refguide: random;distributions, random;gauss

  '''
CORPUS.append(("test_docscrape.doc_txt", doc_txt))


# doc_yields_txt
doc_yields_txt = """
Test generator

Yields
------
a : int
    The number of apples.
b : int
    The number of bananas.
int
    The number of unknowns.
"""
CORPUS.append(("test_docscrape.doc_yields_txt", doc_yields_txt))


# doc_sent_txt
doc_sent_txt = """
Test generator

Yields
------
a : int
    The number of apples.

Receives
--------
b : int
    The number of bananas.
c : int
    The number of oranges.

"""
CORPUS.append(("test_docscrape.doc_sent_txt", doc_sent_txt))


# test_returnyield: doc_text (Returns + Yields together -> raises ValueError)
_test_returnyield_doc_text = """
Test having returns and yields.

Returns
-------
int
    The number of apples.

Yields
------
a : int
    The number of apples.
b : int
    The number of bananas.

"""
RAISING_CORPUS.append(
    ("test_docscrape.test_returnyield.doc_text", _test_returnyield_doc_text, "ValueError")
)


# test_section_twice: doc_text (Notes section appears twice -> raises ValueError)
_test_section_twice_doc_text = """
Test having a section Notes twice

Notes
-----
See the next note for more information

Notes
-----
That should break...
"""
RAISING_CORPUS.append(
    ("test_docscrape.test_section_twice.doc_text", _test_section_twice_doc_text, "ValueError")
)

# test_section_twice: Dummy class docstring (Notes section twice)
_test_section_twice_dummy_class_doc = """
        Dummy class.

        Notes
        -----
        First note.

        Notes
        -----
        Second note.

        """
RAISING_CORPUS.append(
    ("test_docscrape.test_section_twice.Dummy_class_doc",
     _test_section_twice_dummy_class_doc, "ValueError")
)

# test_section_twice: Dummy.spam / Dummy.ham method docstrings (fine on their own)
CORPUS.append(("test_docscrape.test_section_twice.Dummy.spam", "Spam\n\nSpam spam."))
CORPUS.append(("test_docscrape.test_section_twice.Dummy.ham", "Cheese\n\nNo cheese."))

# test_section_twice: dummy_func docstring (Notes section twice)
_test_section_twice_dummy_func_doc = """
        Dummy function.

        Notes
        -----
        First note.

        Notes
        -----
        Second note.
        """
RAISING_CORPUS.append(
    ("test_docscrape.test_section_twice.dummy_func_doc",
     _test_section_twice_dummy_func_doc, "ValueError")
)


# doc2
_doc2_txt = """
    Returns array of indices of the maximum values of along the given axis.

    Parameters
    ----------
    a : {array_like}
        Array to look in.
    axis : {None, integer}
        If None, the index is into the flattened array, otherwise along
        the specified axis"""
CORPUS.append(("test_docscrape.doc2", _doc2_txt))


# doc3
_doc3_txt = """
    my_signature(*params, **kwds)

    Return this and that.
    """
CORPUS.append(("test_docscrape.doc3", _doc3_txt))


# doc4
_doc4_txt = """a.conj()

    Return an array with all complex-valued elements conjugated."""
CORPUS.append(("test_docscrape.doc4", _doc4_txt))


# doc5
_doc5_txt = """
    a.something()

    Raises
    ------
    LinAlgException
        If array is singular.

    Warns
    -----
    SomeWarning
        If needed
    """
CORPUS.append(("test_docscrape.doc5", _doc5_txt))


# test_see_also: doc6
_doc6_txt = """
    z(x,theta)

    See Also
    --------
    func_a, func_b, func_c
    func_d : some equivalent func
    foo.func_e : some other func over
             multiple lines
    func_f, func_g, :meth:`func_h`, func_j,
    func_k
    func_f1, func_g1, :meth:`func_h1`, func_j1
    func_f2, func_g2, :meth:`func_h2`, func_j2 : description of multiple
    :obj:`baz.obj_q`
    :obj:`~baz.obj_r`
    :class:`class_j`: fubar
        foobar
    """
CORPUS.append(("test_docscrape.test_see_also.doc6", _doc6_txt))


# test_see_also_parse_error: text (See Also parse error -> ParseError)
_see_also_parse_error_text = (
    """
    z(x,theta)

    See Also
    --------
    :func:`~foo`
    """)
RAISING_CORPUS.append(
    ("test_docscrape.test_see_also_parse_error.text",
     _see_also_parse_error_text, "ParseError")
)


# test_see_also_print: Dummy class docstring
_see_also_print_dummy_doc = """
        See Also
        --------
        func_a, func_b
        func_c : some relationship
                 goes here
        func_d
        """
CORPUS.append(("test_docscrape.test_see_also_print.Dummy", _see_also_print_dummy_doc))


# test_see_also_trailing_comma_warning: (warns, does not raise)
_see_also_trailing_comma_doc = """
            z(x,theta)

            See Also
            --------
            func_f2, func_g2, :meth:`func_h2`, func_j2, : description of multiple
            :class:`class_j`: fubar
                foobar
            """
CORPUS.append(
    ("test_docscrape.test_see_also_trailing_comma_warning", _see_also_trailing_comma_doc)
)


# test_unknown_section: doc_text (warns about unknown section, does not raise)
_unknown_section_doc_text = """
Test having an unknown section

Mope
----
This should be ignored and warned about
"""
CORPUS.append(("test_docscrape.test_unknown_section.doc_text", _unknown_section_doc_text))


# test_unknown_section: BadSection class docstring
_unknown_section_badsection_doc = """Class with bad section.

        Nope
        ----
        This class has a nope section.
        """
CORPUS.append(
    ("test_docscrape.test_unknown_section.BadSection", _unknown_section_badsection_doc)
)


# doc7
_doc7_txt = """

        Doc starts on second line.

        """
CORPUS.append(("test_docscrape.doc7", _doc7_txt))


# test_no_summary
_no_summary_txt = """
    Parameters
    ----------"""
CORPUS.append(("test_docscrape.test_no_summary", _no_summary_txt))


# test_unicode
_unicode_txt = """
    öäöäöäöäöåååå

    öäöäöäööäååå

    Parameters
    ----------
    ååå : äää
        ööö

    Returns
    -------
    ååå : ööö
        äää

    """
CORPUS.append(("test_docscrape.test_unicode", _unicode_txt))


# test_plot_examples (three variants)
_plot_examples_1 = """
    Examples
    --------
    >>> import matplotlib.pyplot as plt
    >>> plt.plot([1,2,3],[4,5,6])
    >>> plt.show()
    """
CORPUS.append(("test_docscrape.test_plot_examples.1", _plot_examples_1))

_plot_examples_2 = """
    Examples
    --------
    >>> from matplotlib import pyplot as plt
    >>> plt.plot([1,2,3],[4,5,6])
    >>> plt.show()
    """
CORPUS.append(("test_docscrape.test_plot_examples.2", _plot_examples_2))

_plot_examples_3 = """
    Examples
    --------
    .. plot::

       import matplotlib.pyplot as plt
       plt.plot([1,2,3],[4,5,6])
       plt.show()
    """
CORPUS.append(("test_docscrape.test_plot_examples.3", _plot_examples_3))


# test_use_blockquotes
_use_blockquotes_txt = """
    Parameters
    ----------
    abc : def
        ghi
    jkl
        mno

    Returns
    -------
    ABC : DEF
        GHI
    JKL
        MNO
    """
CORPUS.append(("test_docscrape.test_use_blockquotes", _use_blockquotes_txt))


# test_class_members: Dummy class and its methods
_class_members_dummy_doc = """
        Dummy class.

        """
CORPUS.append(("test_docscrape.test_class_members.Dummy", _class_members_dummy_doc))
CORPUS.append(("test_docscrape.test_class_members.Dummy.spam", "Spam\n\nSpam spam."))
CORPUS.append(("test_docscrape.test_class_members.Dummy.ham", "Cheese\n\nNo cheese."))
CORPUS.append(("test_docscrape.test_class_members.Dummy.spammity", "Spammity index"))
CORPUS.append(
    ("test_docscrape.test_class_members.Dummy.Ignorable", "local class, to be ignored")
)

_class_members_subdummy_doc = """
        Subclass of Dummy class.

        """
CORPUS.append(("test_docscrape.test_class_members.SubDummy", _class_members_subdummy_doc))
CORPUS.append(
    ("test_docscrape.test_class_members.SubDummy.ham",
     "Cheese\n\nNo cheese.\nOverloaded Dummy.ham")
)
CORPUS.append(("test_docscrape.test_class_members.SubDummy.bar", "Bar\n\nNo bar"))


# test_duplicate_signature
_duplicate_signature_txt = """
    z(x1, x2)

    z(a, theta)
    """
CORPUS.append(("test_docscrape.test_duplicate_signature", _duplicate_signature_txt))


# class_doc_txt
class_doc_txt = """
    Foo

    Parameters
    ----------
    f : callable ``f(t, y, *f_args)``
        Aaa.
    jac : callable ``jac(t, y, *jac_args)``

        Bbb.

    Attributes
    ----------
    t : float
        Current time.
    y : ndarray
        Current variable values.

        * hello
        * world
    an_attribute : float
        The docstring is printed instead
    no_docstring : str
        But a description
    no_docstring2 : str
    multiline_sentence
    midword_period
    no_period

    Methods
    -------
    a
    b
    c

    Examples
    --------
    For usage examples, see `ode`.
"""
CORPUS.append(("test_docscrape.class_doc_txt", class_doc_txt))


# test_class_members_doc_sphinx: property docstrings
CORPUS.append(
    ("test_docscrape.test_class_members_doc_sphinx.an_attribute", "Test attribute")
)
CORPUS.append(
    ("test_docscrape.test_class_members_doc_sphinx.multiline_sentence",
     """This is a
            sentence. It spans multiple lines.""")
)
CORPUS.append(
    ("test_docscrape.test_class_members_doc_sphinx.midword_period",
     "The sentence for numpy.org.")
)
CORPUS.append(
    ("test_docscrape.test_class_members_doc_sphinx.no_period",
     """This does not have a period
            so we truncate its summary to the first linebreak

            Apparently.
            """)
)


# test_class_attributes_as_member_list: Foo class docstring
_class_attributes_foo_doc = """
        Class docstring.

        Attributes
        ----------
        an_attribute
            Another description that is not used.

        """
CORPUS.append(
    ("test_docscrape.test_class_attributes_as_member_list.Foo",
     _class_attributes_foo_doc)
)
CORPUS.append(
    ("test_docscrape.test_class_attributes_as_member_list.Foo.an_attribute",
     "Test attribute")
)


# test_nonstandard_property
CORPUS.append(
    ("test_docscrape.test_nonstandard_property.attr", "test attribute")
)


# test_args_and_kwargs
_args_and_kwargs_txt = """
    Parameters
    ----------
    param1 : int
        First parameter
    *args : tuple
        Arguments
    **kwargs : dict
        Keyword arguments
    """
CORPUS.append(("test_docscrape.test_args_and_kwargs", _args_and_kwargs_txt))


# test_autoclass
_autoclass_txt = '''
A top section before

.. autoclass:: str
    '''
CORPUS.append(("test_docscrape.test_autoclass", _autoclass_txt))


# xref_doc_txt
xref_doc_txt = """
Test xref in Parameters, Other Parameters and Returns

Parameters
----------
p1 : int
    Integer value

p2 : float, optional
    Integer value

Other Parameters
----------------
p3 : list[int]
    List of integers
p4 : :class:`pandas.DataFrame`
    A dataframe
p5 : sequence of `int`
    A sequence

Returns
-------
out : array
    Numerical return value
"""
CORPUS.append(("test_docscrape.xref_doc_txt", xref_doc_txt))


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
