"""
HILTRON FalakHub — CLI Tool to Add or Update Knowledge Base Entries.
Allows continuous learning and knowledge expansion for HILMI AI Assistant.

Usage:
  python add_knowledge.py --interactive
  python add_knowledge.py --file falak_dasar.json --id my_id --topik "Judul" --kata_kunci "k1, k2" ...
"""

import argparse
import json
import sys
from pathlib import Path

# Add backend directory to path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

KNOWLEDGE_DIR = BACKEND_DIR / "knowledge"


def list_available_categories():
    files = list(KNOWLEDGE_DIR.glob("*.json"))
    return [f.name for f in files]


def add_entry(
    filename: str,
    entry_id: str,
    topik: str,
    kata_kunci: list,
    ringkasan_singkat: str,
    penjelasan_lengkap: str,
    sumber: str,
    tingkat_keyakinan: str = "tinggi"
):
    filepath = KNOWLEDGE_DIR / filename
    if not filepath.exists():
        entries = []
    else:
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                entries = json.load(f)
                if not isinstance(entries, list):
                    entries = [entries]
            except Exception:
                entries = []

    # Check if ID already exists (update) or append
    updated = False
    new_entry = {
        "id": entry_id,
        "topik": topik,
        "kata_kunci": kata_kunci,
        "ringkasan_singkat": ringkasan_singkat,
        "penjelasan_lengkap": penjelasan_lengkap,
        "sumber": sumber,
        "tingkat_keyakinan": tingkat_keyakinan
    }

    for idx, e in enumerate(entries):
        if e.get("id") == entry_id:
            entries[idx] = new_entry
            updated = True
            break

    if not updated:
        entries.append(new_entry)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)

    action = "Updated" if updated else "Added"
    print(f"\n[OK] {action} entry '{entry_id}' in {filename} successfully!")
    print(f"Total entries in {filename}: {len(entries)}")

    # Verify reload in retriever
    try:
        from ai.knowledge_retriever import FalakKnowledgeRetriever
        r = FalakKnowledgeRetriever(KNOWLEDGE_DIR)
        print(f"[OK] KnowledgeRetriever refreshed! Total index: {len(r.documents)} documents.")
    except Exception as e:
        print(f"[Warning] Could not refresh retriever: {e}")


def interactive_mode():
    print("=" * 60)
    print("   HILTRON HILMI — TAMBAH / UPDATE KNOWLEDGE BASE FALAK")
    print("=" * 60)

    categories = list_available_categories()
    print("\nFile kategori yang tersedia:")
    for idx, cat in enumerate(categories, 1):
        print(f"  {idx}. {cat}")
    print(f"  {len(categories) + 1}. [Buat file kategori baru]")

    choice = input("\nPilih nomor file kategori: ").strip()
    try:
        num = int(choice)
        if 1 <= num <= len(categories):
            filename = categories[num - 1]
        else:
            filename = input("Masukkan nama file baru (contoh: fiqh_falak.json): ").strip()
            if not filename.endswith(".json"):
                filename += ".json"
    except Exception:
        filename = "falak_dasar.json"

    print(f"\nTarget File: {filename}")
    entry_id = input("ID entri (contoh: falak_09_contoh): ").strip()
    topik = input("Topik / Judul entri: ").strip()
    kw_raw = input("Kata kunci (pisahkan dengan koma): ").strip()
    kata_kunci = [k.strip() for k in kw_raw.split(",") if k.strip()]
    ringkasan = input("Ringkasan singkat (1-3 kalimat untuk suara): ").strip()
    penjelasan = input("Penjelasan lengkap (ilmiah/fikih): ").strip()
    sumber = input("Sumber rujukan: ").strip() or "Kemenag RI"
    keyakinan = input("Tingkat keyakinan (tinggi/sedang/perlu_verifikasi) [default: tinggi]: ").strip() or "tinggi"

    add_entry(
        filename=filename,
        entry_id=entry_id,
        topik=topik,
        kata_kunci=kata_kunci,
        ringkasan_singkat=ringkasan,
        penjelasan_lengkap=penjelasan,
        sumber=sumber,
        tingkat_keyakinan=keyakinan
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tambah entri pengetahuan ke HILMI")
    parser.add_argument("--interactive", action="store_true", help="Jalankan wizard interaktif")
    parser.add_argument("--file", type=str, help="Nama file JSON di backend/knowledge")
    parser.add_argument("--id", type=str, help="ID unik entri")
    parser.add_argument("--topik", type=str, help="Judul atau topik")
    parser.add_argument("--kata_kunci", type=str, help="Kata kunci dipisahkan koma")
    parser.add_argument("--ringkasan", type=str, help="Ringkasan singkat untuk suara")
    parser.add_argument("--penjelasan", type=str, help="Penjelasan lengkap")
    parser.add_argument("--sumber", type=str, default="Kemenag RI", help="Sumber referensi")
    parser.add_argument("--keyakinan", type=str, default="tinggi", help="Tingkat keyakinan")

    args = parser.parse_args()

    if args.interactive or len(sys.argv) == 1:
        interactive_mode()
    elif args.file and args.id and args.topik and args.ringkasan:
        kws = [k.strip() for k in (args.kata_kunci or "").split(",") if k.strip()]
        add_entry(
            filename=args.file,
            entry_id=args.id,
            topik=args.topik,
            kata_kunci=kws,
            ringkasan_singkat=args.ringkasan,
            penjelasan_lengkap=args.penjelasan or args.ringkasan,
            sumber=args.sumber,
            tingkat_keyakinan=args.keyakinan
        )
    else:
        parser.print_help()

