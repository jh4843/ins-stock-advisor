import shutil
import sys
from pathlib import Path


APP_DATA_DIR_NAME = ".inz_stock_advisor"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_root() -> Path:
    """Return the project root in dev, or PyInstaller's unpacked resource dir."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parents[2]


def executable_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return app_root()


def resource_path(*parts: str) -> Path:
    return app_root().joinpath(*parts)


def user_data_dir() -> Path:
    path = Path.home() / APP_DATA_DIR_NAME / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def user_data_path(*parts: str) -> Path:
    return user_data_dir().joinpath(*parts)


def ensure_user_data_file(file_name: str, bundled_relative_path: str) -> Path:
    destination = user_data_path(file_name)
    if destination.exists():
        return destination

    source = resource_path(*Path(bundled_relative_path).parts)
    if source.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return destination


def log_dir() -> Path:
    path = executable_dir() / "log"
    path.mkdir(parents=True, exist_ok=True)
    return path
