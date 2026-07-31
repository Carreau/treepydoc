cmake_minimum_required(VERSION 3.15...3.31)
project(tree_sitter_numpydoc LANGUAGES C)

# The generated parser plus the hand-written external scanner, wrapped in the
# standard tree-sitter CPython binding.
# Built against the stable ABI, so one wheel per platform covers every
# supported Python rather than one wheel per interpreter version.
find_package(Python REQUIRED COMPONENTS Interpreter Development.SABIModule)

python_add_library(_binding MODULE USE_SABI 3.9
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
