from abc import ABC, abstractmethod
import PyPDF2
import pytesseract
from PIL import Image
import fitz  # PyMuPDF
import io
import logging
import os
from typing import Type, Dict


# Base Parser Interface
class BaseParser(ABC):
    @abstractmethod
    def parse(self, filepath: str) -> str:
        pass


# Concrete Parser for PDF
class PdfParser(BaseParser):
    def parse(self, filepath: str) -> str:
        try:
            content: str = ""
            with open(filepath, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                if reader.is_encrypted:
                    try:
                        reader.decrypt('')
                    except Exception as e:
                        logging.error(f"Failed to decrypt PDF: {e}")
                        return "Unable to decrypt PDF"

                for page_num in range(len(reader.pages)):
                    page = reader.pages[page_num]
                    page_content = page.extract_text()
                    if not page_content:  # If text extraction fails, use OCR
                        page_content = self._ocr_page(filepath, page_num)
                    content += page_content
            return content
        except Exception as e:
            logging.error(f"Error processing PDF: {e}")
            return "Error processing PDF file"

    def _ocr_page(self, filepath: str, page_num: int) -> str:
        try:
            document = fitz.open(filepath)
            page = document.load_page(page_num)
            pix = page.get_pixmap()
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            ocr_text = pytesseract.image_to_string(img)
            document.close()
            return ocr_text
        except Exception as e:
            logging.error(f"OCR processing error: {e}")
            return "Error in OCR processing"


# Concrete Parser for TXT
class TxtParser(BaseParser):
    def parse(self, filepath: str) -> str:
        try:
            with open(filepath, 'r') as file:
                return file.read()
        except Exception as e:
            logging.error(f"Error reading text file: {e}")
            return "Error reading text file"


# Parser Factory with Registration System
class ParserFactory:
    _parsers: Dict[str, Type[BaseParser]] = {}

    @classmethod
    def register_parser(cls, extension: str, parser: Type[BaseParser]) -> None:
        cls._parsers[extension] = parser

    @classmethod
    def get_parser(cls, extension: str) -> BaseParser:
        parser = cls._parsers.get(extension)
        if not parser:
            raise ValueError(f"No parser found for extension: {extension}")
        return parser()


ParserFactory.register_parser('txt', TxtParser)
ParserFactory.register_parser('pdf', PdfParser)


# FileParser Class
class FileParser:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.parser = self._get_parser()

    def _get_parser(self) -> BaseParser:
        extension = self.filepath.split('.')[-1]
        if extension not in ParserFactory._parsers:
            raise ValueError(f"Unsupported file extension: {extension}")
        return ParserFactory.get_parser(extension)

    def parse(self) -> str:
        if not os.path.exists(self.filepath):
            raise FileNotFoundError(f"File not found: {self.filepath}")
        return self.parser.parse(self.filepath)


# # Example Usage
# try:
#     pdf_parser = FileParser('sources/cv-fs.pdf')
#     pdf_content = pdf_parser.parse()
#     print(pdf_content)

#     txt_parser = FileParser('sources/Pitch Rimbaud Inc-3.txt')
#     txt_content = txt_parser.parse()
#     print(txt_content)
# except ValueError as e:
#     print(e)
