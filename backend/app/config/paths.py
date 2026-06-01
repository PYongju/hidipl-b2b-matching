from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = APP_ROOT / "data"
SAMPLE_FILES_DIR = DATA_DIR / "sample_files"
OUTPUT_DIR = DATA_DIR / "demo_outputs"
UPLOAD_DIR = DATA_DIR / "api_demo_uploads"
PARTNER_EMBEDDINGS_PATH = DATA_DIR / "partner_embeddings.json"


def ensure_runtime_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
