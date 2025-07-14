# Create new file: front-end/document_processor.py

import docx
import PyPDF2
import io
from pathlib import Path

def extract_text_from_upload(uploaded_file):
    """Extract text from uploaded document"""
    
    file_extension = Path(uploaded_file.name).suffix.lower()
    
    try:
        if file_extension == '.docx':
            return extract_from_docx(uploaded_file)
        elif file_extension == '.pdf':
            return extract_from_pdf(uploaded_file)
        elif file_extension == '.txt':
            return uploaded_file.read().decode('utf-8')
        else:
            return f"Unsupported file type: {file_extension}"
    except Exception as e:
        return f"Error processing file: {str(e)}"

def extract_from_docx(uploaded_file):
    """Extract text from Word document"""
    doc = docx.Document(uploaded_file)
    text = []
    for paragraph in doc.paragraphs:
        if paragraph.text.strip():
            text.append(paragraph.text)
    return '\n'.join(text)

def extract_from_pdf(uploaded_file):
    """Extract text from PDF"""
    pdf_reader = PyPDF2.PdfReader(uploaded_file)
    text = []
    for page in pdf_reader.pages:
        text.append(page.extract_text())
    return '\n'.join(text)

def summarize_document_if_needed(text, max_length=20000): # I should probably include AI summarization here
    """Summarize document if it exceeds context limits"""
    if len(text) <= max_length:
        return text, False
    
    # Simple truncation with note - could be enhanced with AI summarization
    truncated = text[:max_length]
    summary_note = f"\n\n[NOTE: Document truncated to {max_length} characters for processing]"
    return truncated + summary_note, True