import pdfplumber
import fitz
import pathlib
import json

# Folder where faculty uploads PDFs
UPLOAD_FOLDER = pathlib.Path("uploads")

# Output folders
BASE_OUTPUT = pathlib.Path("output_folder")
TEXT_OUTPUT = BASE_OUTPUT / "text"
IMAGES_OUTPUT = BASE_OUTPUT / "images"

TEXT_OUTPUT.mkdir(parents=True, exist_ok=True)
IMAGES_OUTPUT.mkdir(parents=True, exist_ok=True)


def extract_module(pdf_path: pathlib.Path, module_id: int):

    print(f"\n🔍 Extracting text for module {module_id} from {pdf_path.name}")

    text_file_path = TEXT_OUTPUT / f"{pdf_path.stem}.txt"
    extracted_text_parts = []

    # -------- TEXT EXTRACTION --------
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):

            text = page.extract_text(layout=True)

            if text:
                cleaned = "\n".join(
                    line.rstrip()
                    for line in text.splitlines()
                    if line.strip()
                )

                extracted_text_parts.append(
                    f"\n\n--- Page {i+1} ---\n{cleaned}"
                )

    full_text = "".join(extracted_text_parts)
    text_file_path.write_text(full_text, encoding="utf-8")

    print(f"✅ Text saved to: {text_file_path}")


    # -------- IMAGE EXTRACTION --------
    print(f"🖼 Extracting images from {pdf_path.name}")

    doc = fitz.open(pdf_path)

    seen_xrefs = set()
    image_meta = []
    image_count = 0

    for page_index in range(len(doc)):

        page = doc[page_index]
        page_number = page_index + 1

        for img_index, img in enumerate(page.get_images(full=True)):

            try:

                xref, smask, w, h, *_ = img

                if xref in seen_xrefs:
                    continue

                seen_xrefs.add(xref)

                # skip huge background images
                if w > 2500 and h > 2500:
                    continue

                base_image = doc.extract_image(xref)

                image_bytes = base_image["image"]
                image_ext = base_image.get("ext", "png")

                image_filename = (
                    f"{pdf_path.stem}_mod{module_id}_page{page_number}_xref{xref}.{image_ext}"
                )

                image_path = IMAGES_OUTPUT / image_filename

                with open(image_path, "wb") as f:
                    f.write(image_bytes)

                image_meta.append({
                    "file": image_filename,
                    "module": module_id,
                    "page": page_number,
                })

                image_count += 1

            except Exception as e:
                print(f"⚠ Skipped image on page {page_number}: {e}")


    meta_path = IMAGES_OUTPUT / f"{pdf_path.stem}_mod{module_id}_images_meta.json"

    meta_path.write_text(
        json.dumps(image_meta, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"📊 Total images extracted: {image_count}")
    print(f"📄 Image metadata saved to: {meta_path}")


def process_uploaded_pdfs():

    if not UPLOAD_FOLDER.exists():
        print("❌ uploads folder not found")
        return

    pdf_files = list(UPLOAD_FOLDER.glob("*.pdf"))

    if not pdf_files:
        print("❌ No PDFs found in uploads folder")
        return

    print(f"\n📚 Found {len(pdf_files)} uploaded PDFs")

    for i, pdf_path in enumerate(pdf_files, start=1):
        extract_module(pdf_path, i)


if __name__ == "__main__":

    print("\n🚀 Processing uploaded PDFs for Smart AI Tutor...\n")

    process_uploaded_pdfs()

    print("\n✅ Extraction complete.")