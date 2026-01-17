"""
PDF Processing Service
Extracts text from PDF files for knowledge base ingestion
"""
import logging
from typing import Optional
from pathlib import Path
import io

try:
    from pypdf import PdfReader
    import fitz  # PyMuPDF
except ImportError:
    PdfReader = None
    fitz = None

logger = logging.getLogger(__name__)


class PDFService:
    """Service for extracting text from PDF files."""
    
    def __init__(self):
        if PdfReader is None:
            logger.warning("PyPDF2 not available - PDF extraction will fail")
    
    def extract_text(self, pdf_path: str) -> Optional[str]:
        """
        Extract text from a PDF file.
        
        Args:
            pdf_path: Path to PDF file or file-like object
            
        Returns:
            Extracted text or None if extraction fails
        """
        if PdfReader is None:
            logger.error("PyPDF2 not installed - cannot extract PDF text")
            return None
        
        try:
            # Handle both file paths and file-like objects
            if isinstance(pdf_path, str):
                with open(pdf_path, 'rb') as file:
                    return self._extract_from_file(file)
            else:
                return self._extract_from_file(pdf_path)
                
        except Exception as e:
            logger.error(f"Failed to extract text from PDF: {e}")
            return None
    
    def _extract_from_file(self, file) -> str:
        """Extract text from an open PDF file."""
        reader = PdfReader(file)
        
        text_parts = []
        for page_num, page in enumerate(reader.pages):
            try:
                page_text = page.extract_text()
                if page_text:
                    # Add page marker
                    text_parts.append(f"\n--- Page {page_num + 1} ---\n")
                    text_parts.append(page_text)
            except Exception as e:
                logger.warning(f"Failed to extract text from page {page_num + 1}: {e}")
                continue
        
        full_text = "\n".join(text_parts)
        return self.clean_text(full_text)
    
    def clean_text(self, text: str) -> str:
        """
        Clean and normalize extracted text.
        
        Args:
            text: Raw extracted text
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Remove excessive whitespace
        lines = [line.strip() for line in text.split('\n')]
        
        # Remove empty lines but preserve paragraph breaks
        cleaned_lines = []
        prev_empty = False
        for line in lines:
            if line:
                cleaned_lines.append(line)
                prev_empty = False
            elif not prev_empty:
                cleaned_lines.append('')
                prev_empty = True
        
        return '\n'.join(cleaned_lines)
    
    def extract_metadata(self, pdf_path: str) -> dict:
        """
        Extract metadata from PDF.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dictionary with metadata
        """
        if PdfReader is None:
            return {}
        
        try:
            if isinstance(pdf_path, str):
                with open(pdf_path, 'rb') as file:
                    reader = PdfReader(file)
                    return self._get_metadata(reader)
            else:
                reader = PdfReader(pdf_path)
                return self._get_metadata(reader)
        except Exception as e:
            logger.error(f"Failed to extract PDF metadata: {e}")
            return {}
    
    def _get_metadata(self, reader: PdfReader) -> dict:
        """Extract metadata from PDF reader."""
        metadata = {
            'page_count': len(reader.pages),
            'title': None,
            'author': None,
            'subject': None,
            'creator': None
        }
        
        if hasattr(reader, 'metadata') and reader.metadata:
            info = reader.metadata
            metadata['title'] = info.get('/Title', None)
            metadata['author'] = info.get('/Author', None)
            metadata['subject'] = info.get('/Subject', None)
            metadata['creator'] = info.get('/Creator', None)
        
        return metadata
    
    def extract_images_from_pdf(self, pdf_path: str, output_dir: Optional[str] = None) -> list:
        """
        Extract all images from a PDF file.
        
        Args:
            pdf_path: Path to the PDF file
            output_dir: Directory to save extracted images (uses temp if not provided)
            
        Returns:
            List of dicts with image info: {'path': str, 'page': int, 'width': int, 'height': int}
        """
        if not fitz:
            logger.warning("PyMuPDF not installed - cannot extract images from PDF")
            return []
        
        try:
            # Set output directory
            if output_dir:
                output_path = Path(output_dir)
            else:
                output_path = Path("./storage/knowledge/temp")
            
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Open PDF
            pdf_document = fitz.open(pdf_path)
            extracted_images = []
            
            # Iterate through pages
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                
                # Get images on this page
                image_list = page.get_images(full=True)
                
                for img_index, img_info in enumerate(image_list):
                    try:
                        xref = img_info[0]
                        base_image = pdf_document.extract_image(xref)
                        image_bytes = base_image["image"]
                        image_ext = base_image["ext"]
                        
                        # Skip very small images (likely icons/decorations)
                        if len(image_bytes) < 5000:  # Less than 5KB
                            continue
                        
                        # Generate filename
                        image_filename = f"pdf_page{page_num + 1}_img{img_index + 1}.{image_ext}"
                        image_path = output_path / image_filename
                        
                        # Save image
                        with open(image_path, "wb") as img_file:
                            img_file.write(image_bytes)
                        
                        extracted_images.append({
                            "path": str(image_path),
                            "page": page_num + 1,
                            "index": img_index + 1,
                            "width": base_image.get("width", 0),
                            "height": base_image.get("height", 0),
                            "size_bytes": len(image_bytes)
                        })
                        
                        logger.info(f"Extracted image from page {page_num + 1}: {image_filename}")
                        
                    except Exception as e:
                        logger.warning(f"Failed to extract image from page {page_num + 1}: {e}")
                        continue
            
            pdf_document.close()
            logger.info(f"Extracted {len(extracted_images)} images from PDF")
            return extracted_images
            
        except Exception as e:
            logger.error(f"Failed to extract images from PDF: {e}")
            return []
