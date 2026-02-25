from setuptools import setup
import os

base_dir = os.path.abspath(os.path.dirname(__file__))
readme_path = os.path.join(base_dir, "README.md")

long_description = ""
if os.path.exists(readme_path):
    with open(readme_path, encoding="utf-8") as f:
        long_description = f.read()

setup(
    name="chiton-lang",
    version="1.0.0",
    description="A high-performance systems programming language...",
    long_description=long_description,
    long_description_content_type="text/markdown",
    py_modules=["main", "lexer", "parser", "llvm"],
    package_dir={"": "src"},
    install_requires=[
        "llvmlite",
    ],
    entry_points={
        "console_scripts": [
            "chiton=main:main", 
        ],
    },
    include_package_data=True, 
)