from setuptools import setup, find_packages
import os

base_dir = os.path.abspath(os.path.dirname(__file__))
root_dir = os.path.join(base_dir, "..")
readme_path = os.path.join(root_dir, "README.md")

with open(readme_path, encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="chiton-lang",
    version="0.1.3",
    description="A high-performance systems programming language with Pythonic syntax and native C-ABI interoperability.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    install_requires=[
        "llvmlite",
    ],
    entry_points={
        "console_scripts": [
            "chiton=src.main:main",
        ],
    },
)
