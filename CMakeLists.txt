cmake_minimum_required(VERSION 3.15...3.31)
project(tree_sitter_numpydoc LANGUAGES C)

# The generated parser plus the hand-written external scanner, wrapped in the
# standard tree-sitter CPython binding.
# Built against the stable ABI, so one wheel per platform covers every
# supported Python rather than one wheel per interpreter version.
# 3.10 is the floor because that is what numpydoc 1.10 requires.
#
# scikit-build-core sets `SKBUILD_SABI_COMPONENT` to `Development.SABIModule`
# when `wheel.py-api` asks for a stable-ABI wheel, and leaves it empty
# otherwise. Asking for the component unconditionally makes the build fail
# outright wherever CMake cannot find a SABI library -- which is what the
# Windows runners do -- so follow it instead, and fall back to a
# version-specific module rather than to no module at all.
find_package(Python REQUIRED
  COMPONENTS Interpreter Development.Module ${SKBUILD_SABI_COMPONENT})

if(SKBUILD_SABI_COMPONENT)
  set(TREEPYDOC_SABI USE_SABI 3.10)
endif()

python_add_library(_binding MODULE ${TREEPYDOC_SABI}
  bindings/python/tree_sitter_numpydoc/binding.c
  src/parser.c
  src/scanner.c
  WITH_SOABI
)

target_include_directories(_binding PRIVATE src)
target_compile_features(_binding PRIVATE c_std_11)

# `src/parser.c` is generated and is not ours to lint; the scanner is built with
# the same warnings CI enforces.
if(NOT MSVC)
  set_source_files_properties(src/scanner.c PROPERTIES COMPILE_OPTIONS "-Wall;-Wextra")
endif()

install(TARGETS _binding DESTINATION tree_sitter_numpydoc)
