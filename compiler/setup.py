from setuptools import setup, find_packages

setup(
    name="chiton-lang",
    version="0.1.2",
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
