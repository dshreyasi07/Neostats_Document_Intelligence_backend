import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(ROOT / "backend" / "data" / "documents.db")))
UPLOAD_DIR = ROOT / "backend" / "uploads"
FRONTEND_DIST = ROOT / "frontend" / "dist"
MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH_MB", "15")) * 1024 * 1024
SUPPORTED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}
SUPPORTED_TYPES = {"invoice", "balance_sheet", "profit_and_loss", "cash_flow_statement"}
