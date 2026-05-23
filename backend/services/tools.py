"""BSC Forge — Ajan araçları (dosya sistemi, sandbox'lı)."""
from pathlib import Path

from config import settings

# Gürültülü klasörleri listelemede atla
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".cursor"}

MAX_READ_BYTES = 80_000


def _workspace() -> Path:
    return Path(settings.WORKSPACE_ROOT).resolve()


def resolve_path(relative: str) -> Path:
    """Proje kökü altında güvenli yol çöz."""
    rel = (relative or ".").strip().replace("\\", "/").lstrip("/")
    if ".." in rel.split("/"):
        raise ValueError("Üst dizine çıkılamaz.")
    target = (_workspace() / rel).resolve()
    if not str(target).startswith(str(_workspace())):
        raise ValueError("İzin verilmeyen yol.")
    return target


def list_directory(path: str = ".") -> str:
    """Dizin içeriğini listele (dosya + klasör)."""
    target = resolve_path(path)
    if not target.exists():
        return f"[HATA] Yol bulunamadı: {path}"
    if not target.is_dir():
        return f"[HATA] Bu bir klasör değil: {path}"

    lines = [f"📂 {path or '.'}/"]
    try:
        entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except PermissionError:
        return f"[HATA] Klasör okunamadı: {path}"

    for entry in entries[:80]:
        if entry.name in SKIP_DIRS and entry.is_dir():
            continue
        prefix = "📁" if entry.is_dir() else "📄"
        rel = entry.relative_to(_workspace())
        lines.append(f"  {prefix} {rel}")
    if len(entries) > 80:
        lines.append(f"  … ({len(entries) - 80} öğe daha)")
    return "\n".join(lines)


def read_file(path: str) -> str:
    """Metin dosyası oku (boyut sınırı var)."""
    if not path or not path.strip():
        return "[HATA] Dosya yolu gerekli."
    target = resolve_path(path)
    if not target.exists():
        return f"[HATA] Dosya bulunamadı: {path}"
    if not target.is_file():
        return f"[HATA] Bu bir dosya değil: {path}"

    size = target.stat().st_size
    if size > MAX_READ_BYTES:
        return f"[HATA] Dosya çok büyük ({size} bayt). Üst sınır: {MAX_READ_BYTES} bayt."

    try:
        text = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"[HATA] Metin dosyası değil (ikili dosya): {path}"

    rel = target.relative_to(_workspace())
    return f"📄 {rel} ({len(text)} karakter)\n\n```\n{text}\n```"


TOOL_SCHEMAS = [
    {
        "name": "list_directory",
        "description": "Proje kökünde bir klasörün içeriğini listeler. Göreli yol kullan (örn. backend, frontend/src).",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Göreli klasör yolu. Boş veya '.' proje kökü.",
                },
            },
        },
    },
    {
        "name": "read_file",
        "description": "Proje kökündeki bir metin dosyasını okur.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Göreli dosya yolu (örn. backend/main.py).",
                },
            },
            "required": ["path"],
        },
    },
]


def execute_tool(name: str, args: dict) -> str:
    """Araç adına göre çalıştır."""
    args = args or {}
    if name == "list_directory":
        return list_directory(args.get("path", "."))
    if name == "read_file":
        return read_file(args.get("path", ""))
    return f"[HATA] Bilinmeyen araç: {name}"
