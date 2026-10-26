"""Run the whole project from scratch:  python run_all.py"""
import subprocess
import sys

for step in ("src/download.py", "src/build_db.py", "src/analysis.py", "src/model.py", "src/make_notebook.py"):
    print(f"\n=== {step}")
    subprocess.run([sys.executable, step], check=True, cwd=__import__("pathlib").Path(__file__).parent)
