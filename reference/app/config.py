from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[1]

class Settings(BaseModel):
    metadata_db_path: Path = PROJECT_ROOT / os.getenv("METADATA_DB_PATH", "db/metadata.sqlite")
    duckdb_path: Path = PROJECT_ROOT / os.getenv("DUCKDB_PATH", "db/infrarail.duckdb")
    source_registry_path: Path = PROJECT_ROOT / os.getenv("SOURCE_REGISTRY_PATH", "registry/sources.yaml")
    data_dir: Path = PROJECT_ROOT / "data"
    reports_dir: Path = PROJECT_ROOT / "data" / "reports"

settings = Settings()
