import ast
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _code(nb_path: Path) -> str:
    nb = json.loads(nb_path.read_text(encoding="utf-8"))
    cells = []
    for cell in nb["cells"]:
        if cell["cell_type"] == "code":
            src = "".join(cell["source"])
            cells.append(re.sub(r"^([ \t]*)[!%].*$", r"\1pass", src, flags=re.M))  # Colab magics
    return "\n".join(cells)


def test_fr_f1_colab_notebooks_are_valid_python():
    subprocess.run([sys.executable, str(REPO / "scripts" / "make_colab_notebooks.py")], check=True)
    for name in ("unet_train", "unet_infer"):
        path = REPO / "notebooks" / "colab" / f"{name}.ipynb"
        ast.parse(_code(path))  # raises SyntaxError if a cell is broken
        assert "DAIFF-Flood-Risk-Prediction" in path.read_text(encoding="utf-8")
