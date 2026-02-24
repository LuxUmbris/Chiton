# Chiton LLVM Compiler

**License:** [Apache License 2.0](LICENSE)

---

## Overview

Chiton is a high-performance compiler built on top of LLVM. It combines a clean, Python-inspired syntax with the performance of native machine code.

Built using `llvmlite` and a custom TOML-based build system, Chiton is designed for rapid development, seamless cross-compilation, and efficient native binary generation.

---

## Features

- **LLVM Backend**  
  Generates highly optimized machine code for multiple architectures.

- **Python-Like Syntax**  
  Clean, indentation-based syntax with intuitive control flow, including a `repeat` loop construct.

- **Cross-Compilation**  
  Target platforms such as Linux from a Windows host using LLVM target triples.

- **Integrated Build System**  
  Project configuration and dependency management via `build.toml`.

- **C Interoperability**  
  Directly call external C functions using the `extern` keyword.

---

## Project Structure

```
Chiton/
│-- build.toml        # Project configuration
│-- pyproject.toml    # Python build system (PEP 517)
│-- setup.py          # Installation script
│
└── src/
    │-- __init__.py   # Package initialization
    │-- chiton.py     # CLI logic and build system
    │-- lexer.py      # Lexical analysis
    │-- parser.py     # Syntactic analysis (AST)
    └-- llvm.py       # LLVM IR code generation
```

---

## Installation

### From Source (Recommended)

```bash
git clone https://github.com/youruser/chiton.git
cd chiton
pip install -e .
```

### Via pip

```bash
pip install chiton
```

This installs the `chiton` CLI globally.

---

## Usage

### 1. Project Configuration

Create a `build.toml` file in your project root:

```toml
[project]
name = "my_app"
version = "0.1.0"
src = "src"
target = "x86_64-pc-linux-gnu"  # Optional (for cross-compilation)

[dependencies]
c_deps = ["m"]  # Example: link against the math library
```

---

### 2. Example Source Code

Create `src/main.ctn`:

```chiton
extern def printf(fmt: str, ...) -> int

def main() -> int:
    int x = 5
    repeat x:
        printf("Hello Chiton!\n")
    return 0
```

---

### 3. Build Commands

**Full build (compile and link):**

```bash
chiton build
```

**Compile only (generate object files):**

```bash
chiton build -c
```

---

## CLI Commands

| Command            | Description                                             |
|--------------------|---------------------------------------------------------|
| `chiton build`     | Compile all `.ctn` files and link the final binary     |
| `chiton build -c`  | Generate object files (`.o`) without linking           |
| `chiton help`      | Display CLI help information                           |

---

## Requirements

- Python 3.11+
- `llvmlite`
- `clang` or `gcc` (must be available in your system `PATH` as linker)

---

## License
[Apache 2.0](LICENSE)
