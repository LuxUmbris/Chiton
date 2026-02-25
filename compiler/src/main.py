import sys
import os
import tomllib
import subprocess
from glob import glob

from src.lexer import Lexer
from src.parser import Parser
from src.llvm import ChitonCompiler

# ------------------------------------------------------------
# Error reporting helper (can be reused by lexer/parser/backend)
# ------------------------------------------------------------

def report_error(filename: str, line: int, col: int, message: str):
    try:
        with open(filename, "r") as f:
            lines = f.readlines()
        src_line = lines[line - 1].rstrip("\n") if 0 <= line - 1 < len(lines) else ""
    except OSError:
        src_line = ""

    print(f"{filename}:{line}:{col}: error: {message}")
    if src_line:
        print(f"  {src_line}")
        print("  " + " " * (col - 1) + "^")


# ------------------------------------------------------------
# Dist directory management
# ------------------------------------------------------------

def ensure_dirs():
    os.makedirs("dist", exist_ok=True)
    os.makedirs("dist/object_files", exist_ok=True)
    os.makedirs("dist/llvm_ir", exist_ok=True)


# ------------------------------------------------------------
# Incremental build helper
# ------------------------------------------------------------

def needs_rebuild(src_path: str, obj_path: str) -> bool:
    if not os.path.exists(obj_path):
        return True
    src_mtime = os.path.getmtime(src_path)
    obj_mtime = os.path.getmtime(obj_path)
    return src_mtime > obj_mtime


# ------------------------------------------------------------
# Build project
# ------------------------------------------------------------

def build_project(compile_only: bool = False):
    if not os.path.exists("build.toml"):
        print("Error: build.toml not found.")
        return

    ensure_dirs()

    with open("build.toml", "rb") as f:
        config = tomllib.load(f)

    project = config.get("project", {})
    src_dir = project.get("src", "src")
    target = project.get("target", None)
    binary_name = project.get("name", "out")
    c_deps = config.get("dependencies", {}).get("c_deps", [])

    stdlib_cfg = config.get("stdlib", {})
    stdlib_path = stdlib_cfg.get("path", None)
    stdlib_objs = stdlib_cfg.get("objects", [])

    is_windows = sys.platform == "win32"
    if is_windows and not binary_name.endswith(".exe"):
        binary_name += ".exe"

    print(f"Building {project.get('name', 'Unknown')} v{project.get('version', '0.0.1')}...")

    files = glob(f"{src_dir}/**/*.ctn", recursive=True)
    if not files:
        print(f"No .ctn files found in {src_dir}")
        return

    object_files: list[str] = []

    # --------------------------------------------------------
    # Compile each .ctn file (incremental)
    # --------------------------------------------------------

    for file_path in files:
        rel_path = os.path.relpath(file_path, src_dir)
        rel_no_ext = rel_path.replace(".ctn", "")

        ir_path = os.path.join("dist/llvm_ir", rel_no_ext + ".ll")
        obj_path = os.path.join("dist/object_files", rel_no_ext + ".o")

        os.makedirs(os.path.dirname(ir_path), exist_ok=True)
        os.makedirs(os.path.dirname(obj_path), exist_ok=True)

        if not needs_rebuild(file_path, obj_path):
            print(f"Up to date: {file_path}")
            object_files.append(obj_path)
            continue

        with open(file_path, "r") as f:
            code = f.read()

        lexer_inst = Lexer(code, filename=file_path)
        parser_inst = Parser(lexer_inst)

        try:
            ast = parser_inst.parse_program()
        except SystemExit:
            # assume parser/lexer used report_error and exited
            return
        except Exception as e:
            # fallback if parser doesn't yet use report_error
            report_error(file_path, 1, 1, f"Unhandled parse error: {e}")
            return

        compiler = ChitonCompiler(target_triple=target)
        try:
            compiler.compile(ast)
        except Exception as e:
            # backend error – no precise location yet
            print(f"{file_path}: backend error: {e}")
            return

        with open(ir_path, "w") as ir_file:
            ir_file.write(str(compiler.module))
        print(f"Generated LLVM IR: {ir_path}")

        compiler.generate_object_file(obj_path)
        object_files.append(obj_path)
        print(f"Compiled: {file_path} -> {obj_path}")

    if compile_only:
        print("Object files generated. Stopping as requested.")
        return

    # --------------------------------------------------------
    # Add standard library object files (if configured)
    # --------------------------------------------------------

    if stdlib_path:
        for obj in stdlib_objs:
            full = os.path.join(stdlib_path, obj)
            if os.path.exists(full):
                object_files.append(full)
            else:
                print(f"Warning: stdlib object not found: {full}")

    # --------------------------------------------------------
    # Linking
    # --------------------------------------------------------

    linker = "gcc" if is_windows else "clang"
    output_binary = os.path.join("dist", binary_name)

    linker_cmd = [linker] + object_files + ["-o", output_binary]

    for dep in c_deps:
        linker_cmd.append(f"-l{dep}")

    if target and linker == "clang":
        linker_cmd.extend(["-target", target])

    print(f"Linking with {linker} -> {output_binary}...")
    try:
        result = subprocess.run(linker_cmd, check=True)
        if result.returncode == 0:
            print("Build Success!")
    except FileNotFoundError:
        print(f"Error: {linker} not found in PATH. Please install MinGW (gcc) or Clang.")
    except subprocess.CalledProcessError:
        print("Linking failed.")


# ------------------------------------------------------------
# CLI helpers
# ------------------------------------------------------------

def clean_dist():
    if os.path.exists("dist"):
        import shutil
        shutil.rmtree("dist")
        print("Cleaned dist/")
    else:
        print("Nothing to clean.")


def run_project():
    if not os.path.exists("build.toml"):
        print("Error: build.toml not found.")
        return

    with open("build.toml", "rb") as f:
        config = tomllib.load(f)

    project = config.get("project", {})
    binary_name = project.get("name", "out")

    is_windows = sys.platform == "win32"
    if is_windows and not binary_name.endswith(".exe"):
        binary_name += ".exe"

    binary_path = os.path.join("dist", binary_name)
    if not os.path.exists(binary_path):
        print("Binary not found, building first...")
        build_project(compile_only=False)

    if not os.path.exists(binary_path):
        print("Run aborted: binary still not found.")
        return

    print(f"Running {binary_path}...")
    subprocess.run([binary_path])


def print_help():
    print("""
Chiton Compiler CLI
Usage: chiton <command> [options]

Commands:
  build       Build the project using build.toml
  clean       Remove dist/ directory
  run         Build (if needed) and run the resulting binary
  help        Show this help message

Options:
  -c          Compile only (generate .o files, do not link)
    """)


# ------------------------------------------------------------
# Entry point
# ------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print_help()
        return

    cmd = sys.argv[1]
    compile_only = "-c" in sys.argv or "-o" in sys.argv

    if cmd == "build":
        build_project(compile_only=compile_only)
    elif cmd == "clean":
        clean_dist()
    elif cmd == "run":
        build_project(compile_only=False)
        run_project()
    elif cmd == "help":
        print_help()
    else:
        print(f"Unknown command: {cmd}")
        print_help()


if __name__ == "__main__":
    main()
