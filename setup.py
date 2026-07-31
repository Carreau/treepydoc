from platform import system

from setuptools import Extension, find_packages, setup

setup(
    packages=find_packages("bindings/python") + ["treepydoc"],
    package_dir={"tree_sitter_numpydoc": "bindings/python/tree_sitter_numpydoc"},
    package_data={"tree_sitter_numpydoc": ["*.pyi", "py.typed"]},
    ext_package="tree_sitter_numpydoc",
    ext_modules=[
        Extension(
            name="_binding",
            sources=[
                "bindings/python/tree_sitter_numpydoc/binding.c",
                "src/parser.c",
                "src/scanner.c",
            ],
            extra_compile_args=(
                ["-std=c11"] if system() != "Windows" else ["/std:c11", "/utf-8"]
            ),
            define_macros=[
                ("TREE_SITTER_HIDE_SYMBOLS", None),
            ],
            include_dirs=["src"],
        )
    ],
    zip_safe=False,
)
