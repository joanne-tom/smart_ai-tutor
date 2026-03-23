import fitz  # PyMuPDF
import os
import pathlib

def extract_images_from_pdf(pdf_path: str, output_base_dir: str = "static/images"):
    """
    Extracts all images from a PDF file and saves them to:
    static/images/<pdf_name>/page_<page_num>_<image_index>.png
    
    Returns the number of images extracted.
    """
    pdf_path_obj = pathlib.Path(pdf_path)
    if not pdf_path_obj.exists():
        print(f"Error: {pdf_path} does not exist.")
        return 0

    pdf_name = pdf_path_obj.stem
    output_dir = pathlib.Path(output_base_dir) / pdf_name
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"Failed to open PDF {pdf_path}: {e}")
        return 0

    total_images_extracted = 0

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        image_list = page.get_images(full=True)
        
        # page_num is 0-indexed in PyMuPDF, but our chunks use 1-indexed (e.g., "Page 4")
        real_page_num = page_num + 1 
        
        for image_index, img in enumerate(image_list, start=1):
            xref = img[0]
            try:
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                
                # Save as PNG or original extension
                filename = f"page_{real_page_num}_{image_index}.{image_ext}"
                filepath = output_dir / filename
                
                filepath.write_bytes(image_bytes)
                total_images_extracted += 1
            except Exception as e:
                print(f"Failed to extract image {xref} on page {real_page_num}: {e}")

    print(f"Extracted {total_images_extracted} images from {pdf_name}")
    return total_images_extracted

if __name__ == "__main__":
    # Retroactively extract images for all PDFs in the uploads directory
    uploads_dir = pathlib.Path("uploads")
    if uploads_dir.exists():
        for pdf_file in uploads_dir.glob("*.pdf"):
            print(f"Processing {pdf_file.name}...")
            extract_images_from_pdf(str(pdf_file))
    else:
        print("No uploads directory found.")
