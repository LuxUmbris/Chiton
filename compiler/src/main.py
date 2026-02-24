import sys
import os
import tomllib
import subprocess
from glob import glob
from src.lexer import Lexer
from src.parser import Parser
from src.llvm import ChitonCompiler

def build_project(compile_only=False):
    if not os.path.exists("build.toml"):
        print("Error: build.toml not found.")
        return

    with open("build.toml", "rb") as f:
        config = tomllib.load(f)

    project = config.get("project", {})
    src_dir = project.get("src", "src")
    target = project.get("target", None)
    binary_name = project.get("name", "out")
    c_deps = config.get("dependencies", {}).get("c_deps", [])

    # Check for Windows to adjust binary extension and default compiler
    is_windows = sys.platform == "win32"
    if is_windows and not binary_name.endswith(".exe"):
        binary_name += ".exe"

    print(f"Building {project.get('name', 'Unknown')} v{project.get('version', '0.0.1')}...")

    # 1. Collect all .ctn files
    files = glob(f"{src_dir}/**/*.ctn", recursive=True)
    if not files:
        print(f"No .ctn files found in {src_dir}")
        return

    object_files = []
    compiler = ChitonCompiler(target_triple=target)

    for file_path in files:
        with open(file_path, "r") as f:
            code = f.read()
        
        lexer_inst = Lexer(code, filename=file_path)
        parser_inst = Parser(lexer_inst)
        ast = parser_inst.parse_program()
        
        compiler.compile(ast)
        
        # Determine object file name
        obj_name = file_path.replace(".ctn", ".o")
        compiler.generate_object_file(obj_name)
        object_files.append(obj_name)
        print(f"Compiled: {file_path} -> {obj_name}")

    if compile_only:
        print("Object files generated. Stopping as requested.")
        return

    # 2. Linking
    # On Windows, we check if gcc (MinGW) is available, otherwise fallback to clang
    linker = "gcc" if is_windows else "clang"
    
    linker_cmd = [linker] + object_files + ["-o", binary_name]
    
    for dep in c_deps:
        linker_cmd.append(f"-l{dep}")

    if target and linker == "clang":
        linker_cmd.extend(["-target", target])

    print(f"Linking with {linker} -> {binary_name}...")
    try:
        result = subprocess.run(linker_cmd, check=True)
        if result.returncode == 0:
            print("Build Success!")
    except FileNotFoundError:
        print(f"Error: {linker} not found in PATH. Please install MinGW (gcc) or Clang.")
    except subprocess.CalledProcessError:
        print("Linking failed.")

def print_help():
    print("""
Chiton Compiler CLI
Usage: chiton <command> [options]

Commands:
  build       Build the project using build.toml
  help        Show this help message

Options:
  -c          Compile only (generate .o files, do not link)
    """)

def main():
    if len(sys.argv) < 2:
        print_help()
        return

    cmd = sys.argv[1]
    
    # Check for -c or -o flag in arguments
    compile_only = "-c" in sys.argv or "-o" in sys.argv

    if cmd == "build":
        build_project(compile_only=compile_only)
    elif cmd == "help":
        print_help()
    else:
        print(f"Unknown command: {cmd}")
        print_help()

if __name__ == "__main__":
    main()