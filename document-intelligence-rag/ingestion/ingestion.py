from pathlib import Path
from typing import Iterator, List, Dict, Any, Optional
import csv
import hashlib
import re

import pymupdf
import pytesseract
from PIL import Image

from docx import Document as DocxDocument
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


# ============================================================
# CONFIGURATION
# ============================================================

DATA_DIR = Path("data")

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".xlsx",
    ".csv",
    ".txt",
}

# Tesseract installation path
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


# ============================================================
# TEXT SPLITTER
# ============================================================

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=[
        "\n\n",
        "\n",
        ". ",
        "? ",
        "! ",
        "; ",
        ", ",
        " ",
        "",
    ],
)


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def clean_text(text: str) -> str:
    """
    Clean unnecessary whitespace while preserving
    meaningful line breaks.
    """

    if not text:
        return ""

    # Normalize different newline formats
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Remove excessive spaces
    text = re.sub(r"[ \t]+", " ", text)

    # Remove excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def create_document_id(file_path: Path) -> str:
    """
    Create a deterministic document ID from the file path.
    """

    normalized_path = str(file_path.resolve()).lower()

    return hashlib.sha256(
        normalized_path.encode("utf-8")
    ).hexdigest()[:16]


def create_chunk_id(
    document_id: str,
    chunk_index: int,
) -> str:
    """
    Create a deterministic chunk ID.
    """

    return f"{document_id}_chunk_{chunk_index}"


def get_file_type(file_path: Path) -> str:
    """
    Return the file type without the leading dot.
    """

    return file_path.suffix.lower().replace(".", "")


def split_text(
    text: str,
    base_metadata: Dict[str, Any],
) -> List[Document]:
    """
    Split text into chunks and create globally unique
    chunk IDs using the source location metadata.
    """

    text = clean_text(text)

    if not text:
        return []

    chunks = text_splitter.split_text(text)

    documents = []

    for chunk_index, chunk in enumerate(chunks):

        metadata = base_metadata.copy()

        # ----------------------------------------------------
        # Create a unique location string
        # ----------------------------------------------------

        location_parts = []

        if "page" in metadata:
            location_parts.append(
                f"page_{metadata['page']}"
            )

        if "paragraph_index" in metadata:
            location_parts.append(
                f"paragraph_{metadata['paragraph_index']}"
            )

        if "table_index" in metadata:
            location_parts.append(
                f"table_{metadata['table_index']}"
            )

        if "row_number" in metadata:
            location_parts.append(
                f"row_{metadata['row_number']}"
            )

        if "sheet_name" in metadata:
            location_parts.append(
                f"sheet_{metadata['sheet_name']}"
            )

        if "section_index" in metadata:
            location_parts.append(
                f"section_{metadata['section_index']}"
            )

        # If no specific location exists,
        # use a generic source-level identifier.
        if location_parts:

            location = "_".join(
                location_parts
            )

        else:

            location = "source"

        # ----------------------------------------------------
        # Create globally unique chunk ID
        # ----------------------------------------------------

        chunk_id = (
            f"{metadata['document_id']}_"
            f"{location}_"
            f"chunk_{chunk_index}"
        )

        metadata["chunk_index"] = chunk_index
        metadata["chunk_id"] = chunk_id

        # ----------------------------------------------------
        # Create LangChain document
        # ----------------------------------------------------

        documents.append(
            Document(
                page_content=chunk,
                metadata=metadata,
            )
        )

    return documents


# ============================================================
# PDF LOADER
# ============================================================

def load_pdf(file_path: Path) -> Iterator[Document]:

    print(f"[PDF] Loading: {file_path.name}")

    pdf = pymupdf.open(file_path)

    document_id = create_document_id(file_path)

    total_pages = len(pdf)

    print(f"[PDF] Pages: {total_pages}")

    for page_number, page in enumerate(pdf, start=1):

        # ----------------------------------------------------
        # Extract normal PDF text
        # ----------------------------------------------------

        text = clean_text(
            page.get_text("text")
        )

        # ----------------------------------------------------
        # Detect images
        # ----------------------------------------------------

        images = page.get_images(full=True)

        has_image = len(images) > 0

        # ----------------------------------------------------
        # OCR extracted images
        # ----------------------------------------------------

        ocr_texts = []

        for image_index, image_info in enumerate(images):

            try:

                xref = image_info[0]

                image_data = pdf.extract_image(xref)

                image_bytes = image_data["image"]

                image = Image.open(
                    __import__("io").BytesIO(image_bytes)
                )

                ocr_text = pytesseract.image_to_string(
                    image
                )

                ocr_text = clean_text(ocr_text)

                if ocr_text:

                    ocr_texts.append(
                        ocr_text
                    )

                    print(
                        f"[PDF] Page {page_number}: "
                        f"OCR image {image_index + 1}"
                    )

            except Exception as error:

                print(
                    f"[PDF] OCR failed on "
                    f"page {page_number}: {error}"
                )

        # ----------------------------------------------------
        # Scanned-page OCR fallback
        # ----------------------------------------------------

        # If almost no normal text exists, render the
        # complete page and OCR it.
        if len(text) < 30:

            try:

                pixmap = page.get_pixmap(
                    dpi=200
                )

                image = Image.frombytes(
                    "RGB",
                    [
                        pixmap.width,
                        pixmap.height,
                    ],
                    pixmap.samples,
                )

                scanned_ocr = pytesseract.image_to_string(
                    image
                )

                scanned_ocr = clean_text(
                    scanned_ocr
                )

                if scanned_ocr:

                    if text:

                        text += "\n\n" + scanned_ocr

                    else:

                        text = scanned_ocr

                    print(
                        f"[PDF] Page {page_number}: "
                        f"Scanned-page OCR"
                    )

            except Exception as error:

                print(
                    f"[PDF] Scanned OCR failed "
                    f"on page {page_number}: {error}"
                )

        # ----------------------------------------------------
        # Combine normal text + image OCR
        # ----------------------------------------------------

        if ocr_texts:

            ocr_section = "\n\n".join(
                ocr_texts
            )

            if text:

                text += (
                    "\n\n"
                    "[OCR CONTENT]\n"
                    + ocr_section
                )

            else:

                text = (
                    "[OCR CONTENT]\n"
                    + ocr_section
                )

        text = clean_text(text)

        if not text:
            continue

        # ----------------------------------------------------
        # Metadata
        # ----------------------------------------------------

        metadata = {
            "document_id": document_id,
            "source": file_path.name,
            "file_type": "pdf",
            "content_type": (
                "mixed"
                if ocr_texts
                else "text"
            ),
            "page": page_number,
            "total_pages": total_pages,
            "has_image": has_image,
            "ocr_used": bool(ocr_texts),
        }

        # ----------------------------------------------------
        # Chunk page text
        # ----------------------------------------------------

        chunks = split_text(
            text,
            metadata,
        )

        # Make chunk IDs unique across pages
        for local_index, chunk in enumerate(chunks):

            chunk.metadata["page_chunk_index"] = (
                local_index
            )

            yield chunk

    pdf.close()


# ============================================================
# DOCX LOADER
# ============================================================

def load_docx(file_path: Path) -> Iterator[Document]:

    print(f"[DOCX] Loading: {file_path.name}")

    document = DocxDocument(file_path)

    document_id = create_document_id(file_path)

    section_index = 0

    # --------------------------------------------------------
    # Paragraphs
    # --------------------------------------------------------

    for paragraph_index, paragraph in enumerate(
        document.paragraphs
    ):

        text = clean_text(
            paragraph.text
        )

        if not text:
            continue

        metadata = {
            "document_id": document_id,
            "source": file_path.name,
            "file_type": "docx",
            "content_type": "paragraph",
            "section_index": section_index,
            "paragraph_index": paragraph_index,
        }

        chunks = split_text(
            text,
            metadata,
        )

        for chunk in chunks:
            yield chunk

        section_index += 1

    # --------------------------------------------------------
    # Tables
    # --------------------------------------------------------

    for table_index, table in enumerate(
        document.tables
    ):

        rows = []

        for row_index, row in enumerate(
            table.rows
        ):

            cells = []

            for cell in row.cells:

                cell_text = clean_text(
                    cell.text
                )

                cells.append(cell_text)

            row_text = " | ".join(cells)

            if row_text.strip():

                rows.append(
                    f"Row {row_index + 1}: "
                    f"{row_text}"
                )

        if not rows:
            continue

        table_text = "\n".join(rows)

        metadata = {
            "document_id": document_id,
            "source": file_path.name,
            "file_type": "docx",
            "content_type": "table",
            "table_index": table_index,
        }

        chunks = split_text(
            table_text,
            metadata,
        )

        for chunk in chunks:
            yield chunk


# ============================================================
# XLSX LOADER
# ============================================================

def load_xlsx(file_path: Path) -> Iterator[Document]:

    print(f"[XLSX] Loading: {file_path.name}")

    from openpyxl import load_workbook

    document_id = create_document_id(file_path)

    workbook = load_workbook(
        filename=file_path,
        read_only=True,
        data_only=True,
    )

    for sheet in workbook.worksheets:

        sheet_name = sheet.title

        print(
            f"[XLSX] Sheet: {sheet_name}"
        )

        for row_number, row in enumerate(
            sheet.iter_rows(values_only=True),
            start=1,
        ):

            values = []

            for value in row:

                if value is None:
                    values.append("")
                else:
                    values.append(
                        str(value).strip()
                    )

            # Skip completely empty rows
            if not any(values):
                continue

            row_text = " | ".join(
                values
            )

            metadata = {
                "document_id": document_id,
                "source": file_path.name,
                "file_type": "xlsx",
                "content_type": "spreadsheet_row",
                "sheet_name": sheet_name,
                "row_number": row_number,
            }

            chunks = split_text(
                row_text,
                metadata,
            )

            for chunk in chunks:
                yield chunk

    workbook.close()


# ============================================================
# CSV LOADER
# ============================================================

def load_csv(file_path: Path) -> Iterator[Document]:

    print(f"[CSV] Loading: {file_path.name}")

    document_id = create_document_id(file_path)

    with open(
        file_path,
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:

        reader = csv.reader(file)

        for row_number, row in enumerate(
            reader,
            start=1,
        ):

            values = [
                str(value).strip()
                for value in row
            ]

            if not any(values):
                continue

            row_text = " | ".join(
                values
            )

            metadata = {
                "document_id": document_id,
                "source": file_path.name,
                "file_type": "csv",
                "content_type": "csv_row",
                "row_number": row_number,
            }

            chunks = split_text(
                row_text,
                metadata,
            )

            for chunk in chunks:
                yield chunk


# ============================================================
# TXT LOADER
# ============================================================

def load_txt(file_path: Path) -> Iterator[Document]:

    print(f"[TXT] Loading: {file_path.name}")

    document_id = create_document_id(file_path)

    text = file_path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    metadata = {
        "document_id": document_id,
        "source": file_path.name,
        "file_type": "txt",
        "content_type": "text",
    }

    chunks = split_text(
        text,
        metadata,
    )

    for chunk in chunks:
        yield chunk


# ============================================================
# FILE ROUTER
# ============================================================

def load_file(file_path: Path) -> Iterator[Document]:

    extension = file_path.suffix.lower()

    if extension == ".pdf":

        yield from load_pdf(
            file_path
        )

    elif extension == ".docx":

        yield from load_docx(
            file_path
        )

    elif extension == ".xlsx":

        yield from load_xlsx(
            file_path
        )

    elif extension == ".csv":

        yield from load_csv(
            file_path
        )

    elif extension == ".txt":

        yield from load_txt(
            file_path
        )

    else:

        print(
            f"[SKIP] Unsupported file: "
            f"{file_path.name}"
        )


def load_file_with_metadata(
    file_path: Path,
    user_id: Optional[str] = None,
    document_id: Optional[str] = None,
) -> Iterator[Document]:
    """
    Loads a file and attaches multi-tenant ownership metadata (user_id, document_id).
    Prepared for future uploaded files and Supabase Storage integration.
    """
    for doc in load_file(file_path):
        if user_id is not None:
            doc.metadata["user_id"] = str(user_id)
        if document_id is not None:
            doc.metadata["document_id"] = str(document_id)
            chunk_index = doc.metadata.get("chunk_index", 0)
            doc.metadata["chunk_id"] = f"{document_id}_chunk_{chunk_index}"
        yield doc


# ============================================================
# LOAD ALL DOCUMENTS
# ============================================================

def load_all_documents(
    data_directory: str = "data",
) -> Iterator[Document]:

    data_path = Path(
        data_directory
    )

    if not data_path.exists():

        print(
            f"[ERROR] Data directory "
            f"does not exist: {data_path}"
        )

        return

    files = sorted(
        [
            file
            for file in data_path.rglob("*")
            if file.is_file()
            and file.suffix.lower()
            in SUPPORTED_EXTENSIONS
        ]
    )

    print()
    print(
        f"[DATA] Found {len(files)} "
        f"supported files."
    )
    print()

    total_chunks = 0

    for file_path in files:

        print(
            f"[FILE] {file_path}"
        )

        file_chunk_count = 0

        for document in load_file(
            file_path
        ):

            file_chunk_count += 1
            total_chunks += 1

            yield document

        print(
            f"[FILE] Generated "
            f"{file_chunk_count} chunks."
        )

        print()

    print(
        "[DATA] Ingestion completed."
    )

    print(
        f"[DATA] Total chunks generated: "
        f"{total_chunks}"
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    documents = list(
        load_all_documents("data")
    )

    print()
    print("=" * 60)
    print("INGESTION TEST")
    print("=" * 60)

    print(
        f"Total chunks: {len(documents)}"
    )

    if documents:

        print()
        print("FIRST CHUNK")
        print("-" * 60)

        print(
            documents[0].page_content[:500]
        )

        print()
        print("METADATA")
        print("-" * 60)

        for key, value in (
            documents[0]
            .metadata
            .items()
        ):

            print(
                f"{key}: {value}"
            )