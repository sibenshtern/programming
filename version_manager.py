import subprocess
import shutil
import json
from pathlib import Path
from typing import List, Dict, Any


class CircuitModel:
    """
    TODO: заменить на реальную объектную модель схемы.
    Должна поддерживать сериализацию в нетлист и графическое представление.
    """
    def __init__(self, components: List[Dict] = None, connections: List[Dict] = None):
        self.components = components or []
        self.connections = connections or []

    def to_netlist(self) -> str:
        """Сериализует модель в нетлист (текст/JSON)."""
        return json.dumps({"components": self.components, "connections": self.connections}, ensure_ascii=False, indent=2)

    def to_graphical_repr(self) -> str:
        """Сериализует модель в формат графического представления (например, JSON с координатами)."""
        return json.dumps({
            "nodes": [{"id": c["id"], "type": c["type"], "x": c.get("x", 0), "y": c.get("y", 0)} for c in self.components],
            "edges": self.connections
        }, ensure_ascii=False, indent=2)

    def to_state(self) -> Dict[str, Any]:
        """Преобразует модель в словарь для сохранения в историю."""
        return {"components": self.components, "connections": self.connections}

    @classmethod
    def from_state(cls, state: Dict[str, Any]) -> "CircuitModel":
        """Создаёт модель из словаря состояния."""
        return cls(components=state.get("components", []), connections=state.get("connections", []))


class GitBasedUndoRedo:
    """
    Менеджер истории изменений на основе Git в изолированном кэше.
    Не изменяет исходные файлы проекта — работает только с копией в .circuit_cache/repo/.
    """
    def __init__(self, project_dir: str, tracked_files: List[str]):
        self.project_dir = Path(project_dir).resolve()
        self.tracked_files = tracked_files
        self.cache_dir = self.project_dir / ".circuit_cache"
        self.repo_dir = self.cache_dir / "repo"
        self.repo_dir.mkdir(parents=True, exist_ok=True)

        # Инициализация Git-репозитория в кэше
        if not (self.repo_dir / ".git").exists():
            self._run_git(["init"])
            self._run_git(["config", "user.name", "CircuitApp"])
            self._run_git(["config", "user.email", "circuit@local"])
            # .gitignore: отслеживаем ТОЛЬКО указанные файлы
            (self.repo_dir / ".gitignore").write_text("*\n!.gitignore\n!" + "\n!".join(tracked_files))

        # При первом запуске — копируем исходные файлы в кэш
        for f in self.tracked_files:
            src = self.project_dir / f
            dst = self.repo_dir / f
            if src.exists() and not dst.exists():
                shutil.copy(src, dst)
            elif not dst.exists():
                dst.write_text("{}")

        # Создаём начальный коммит, если история пуста
        if not self._has_commits():
            self.save_snapshot("Initial state")

    def _run_git(self, args: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """Выполняет команду git в директории кэша."""
        return subprocess.run(["git"] + args, cwd=self.repo_dir, capture_output=True, text=True, check=check)

    def _has_commits(self) -> bool:
        try:
            self._run_git(["rev-parse", "HEAD"])
            return True
        except subprocess.CalledProcessError:
            return False

    def save_snapshot(self, message: str = "Auto-save"):
        """Сохраняет текущее состояние файлов в кэше как коммит."""
        try:
            for f in self.tracked_files:
                self._run_git(["add", f])
            self._run_git(["commit", "-m", message])
        except subprocess.CalledProcessError as e:
            if "nothing to commit" not in e.stderr:
                raise RuntimeError(f"Git commit failed: {e.stderr}")

    def can_undo(self) -> bool:
        """Проверяет, есть ли коммиты для отката."""
        return self._has_commits()

    def undo(self) -> bool:
        """Откатывает кэш на предыдущий коммит."""
        if not self.can_undo():
            return False
        try:
            self._run_git(["reset", "--hard", "HEAD~1"])
            return True
        except subprocess.CalledProcessError:
            return False

    def redo(self) -> bool:
        """Восстанавливает состояние после отката через reflog."""
        try:
            result = self._run_git(["reflog", "--oneline", "-n", "2"], check=False)
            lines = [line for line in result.stdout.strip().split("\n") if line]
            if len(lines) < 2:
                return False
            target_commit = lines[1].split()[0]
            self._run_git(["reset", "--hard", target_commit])
            return True
        except Exception:
            return False

    def read_file_from_cache(self, filename: str) -> str:
        """Читает файл из кэша (после undo/redo он уже обновлён)."""
        return (self.repo_dir / filename).read_text(encoding='utf-8')

    def write_file_to_cache(self, filename: str, content: str):
        """Записывает новое содержимое в кэш (перед коммитом)."""
        (self.repo_dir / filename).write_text(content, encoding='utf-8')

    def export_file_to_project(self, filename: str):
        """Копирует файл из кэша в исходную директорию проекта."""
        shutil.copy(self.repo_dir / filename, self.project_dir / filename)

    def get_current_state_from_cache(self) -> CircuitModel:
        """Загружает модель из кэша (из первого отслеживаемого файла)."""
        netlist_path = self.repo_dir / self.tracked_files[0]
        if netlist_path.exists():
            try:
                data = json.loads(netlist_path.read_text(encoding='utf-8'))
                return CircuitModel.from_state(data)
            except Exception:
                pass
        return CircuitModel()


class ProjectSession:
    """
    Сессия проекта: связывает GUI, модель и изолированную Git-историю.
    Исходные файлы обновляются ТОЛЬКО при явном сохранении.
    """
    def __init__(self, project_dir: str, graphical_file: str = "schematic.json", netlist_file: str = "netlist.json"):
        self.project_dir = Path(project_dir).resolve()
        self.graphical_file = graphical_file
        self.netlist_file = netlist_file

        self.git_manager = GitBasedUndoRedo(
            project_dir=str(self.project_dir),
            tracked_files=[self.graphical_file, self.netlist_file]
        )
        self.model = self.git_manager.get_current_state_from_cache()

    def apply_change(self, new_state: Dict[str, Any]):
        """Применяет новое состояние: обновляет кэш и делает коммит."""
        self.model = CircuitModel.from_state(new_state)
        self.git_manager.write_file_to_cache(self.graphical_file, self.model.to_graphical_repr())
        self.git_manager.write_file_to_cache(self.netlist_file, self.model.to_netlist())
        self.git_manager.save_snapshot()

    def undo(self) -> bool:
        """Выполняет откат в кэше и обновляет модель."""
        if self.git_manager.undo():
            self.model = self.git_manager.get_current_state_from_cache()
            return True
        return False

    def redo(self) -> bool:
        """Выполняет возврат в кэше и обновляет модель."""
        if self.git_manager.redo():
            self.model = self.git_manager.get_current_state_from_cache()
            return True
        return False

    def save_to_disk(self):
        """Сохраняет текущее состояние из кэша в исходные файлы проекта."""
        self.git_manager.export_file_to_project(self.graphical_file)
        self.git_manager.export_file_to_project(self.netlist_file)

    def get_current_model(self) -> CircuitModel:
        """Возвращает текущую модель."""
        return self.model


# ==============================================================================
# Пример использования
# ==============================================================================
if __name__ == "__main__":
    session = ProjectSession("./my_circuit")

    session.apply_change({
        "components": [{"id": "R1", "type": "resistor", "x": 100, "y": 50}],
        "connections": []
    })

    session.apply_change({
        "components": [
            {"id": "R1", "type": "resistor", "x": 100, "y": 50},
            {"id": "C1", "type": "capacitor", "x": 200, "y": 60}
        ],
        "connections": [{"from": "R1", "to": "C1"}]
    })

    session.undo()
    session.apply_change({
        "components": [{"id": "L1", "type": "inductor", "x": 150, "y": 70}],
        "connections": []
    })

    session.undo()  # → R1
    session.redo()  # → L1

    # Явное сохранение в проектную директорию
    session.save_to_disk()

    # При следующем запуске:
    session2 = ProjectSession("./my_circuit")  # — загрузит историю из кэша