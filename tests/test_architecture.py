"""Comprueba que las capas no importen hacia arriba.

El dominio no puede depender de nada, la aplicacion solo del dominio, la
infraestructura de ambas, y las interfaces de todo lo anterior. Si alguien
mueve un import al reves, este test lo detecta.
"""

import ast
import unittest
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent.parent / "src" / "taximeter"
ORDER = ("domain", "application", "infrastructure", "interfaces")
RANK = {name: position for position, name in enumerate(ORDER)}


def layer_of(path: Path) -> str | None:
    relative = path.relative_to(PACKAGE)
    if len(relative.parts) < 2:
        return None
    layer = relative.parts[0]
    return layer if layer in RANK else None


def imported_layers(path: Path) -> set[str]:
    layers: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        modules: list[str] = []
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
        elif isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        for module in modules:
            parts = module.split(".")
            if len(parts) > 1 and parts[1] in RANK:
                layers.add(parts[1])
    return layers


class LayerDependencyTest(unittest.TestCase):
    def test_layers_do_not_import_upwards(self) -> None:
        violations: list[str] = []

        for path in sorted(PACKAGE.rglob("*.py")):
            layer = layer_of(path)
            if layer is None:
                continue
            for target in imported_layers(path):
                if RANK[target] > RANK[layer]:
                    violations.append(
                        f"{path.relative_to(PACKAGE)} ({layer}) importa de {target}"
                    )

        self.assertEqual(violations, [], "dependencias entre capas invertidas")

    def test_the_domain_only_depends_on_itself(self) -> None:
        for path in sorted((PACKAGE / "domain").rglob("*.py")):
            self.assertLessEqual(
                imported_layers(path),
                {"domain"},
                f"{path.relative_to(PACKAGE)} no debe depender de otra capa",
            )

    def test_every_layer_is_present(self) -> None:
        for layer in ORDER:
            self.assertTrue(
                (PACKAGE / layer).is_dir(), f"falta la capa {layer}"
            )


if __name__ == "__main__":
    unittest.main()
