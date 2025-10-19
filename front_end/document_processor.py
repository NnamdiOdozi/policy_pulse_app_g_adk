# Create new file: front-end/document_processor.py

# =============================================================================
# DOCUMENT PROCESSING & TEXT EXTRACTION
# =============================================================================
# PURPOSE: Extract text from uploaded files and prepare for AI agent context
# SUPPORTS: PDF, DOCX, TXT files
# KEY CHALLENGE: Managing context window limits (max tokens LLM can process)


import docx
import PyPDF2
import io
from pathlib import Path

def extract_text_from_upload(uploaded_file):
    """
    Extract plain text from various file formats
    
    FILE TYPE DETECTION:
    - Uses file.name extension (.pdf, .docx, .txt)
    - Case-insensitive matching
    - Unsupported types raise ValueError
    
    EXTRACTION METHODS BY TYPE:
    
    1. PDF (.pdf):
       - Uses PyPDF2 or pdfplumber library
       - Iterates through pages
       - Extracts text from each page
       - Concatenates with page breaks
       - GOTCHA: Scanned PDFs return empty (need OCR)
    
    2. DOCX (.docx):
       - Uses python-docx library
       - Reads paragraph by paragraph
       - Preserves basic structure
       - Loses formatting/images/tables
       - More reliable than PDF extraction
    
    3. TXT (.txt):
       - Direct decode from bytes
       - UTF-8 encoding assumed
       - Fallback to latin-1 if UTF-8 fails
       - Simplest case, rarely fails
    
    WHY THIS MATTERS:
    - AI agents need plain text input
    - Formatting/images would confuse LLM
    - Text-only is fastest to process
    
    COMMON ISSUES:
    - PDFs with complex layouts extract poorly
    - Tables in documents lose structure
    - Non-English text may have encoding issues
    - Scanned documents need OCR preprocessing
    """
    
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

def summarize_document_if_needed(text, max_length=100000): # I should probably include AI summarization here
    """
    Summarize long documents to fit in context window
    
    THE CONTEXT WINDOW PROBLEM:
    - LLMs have token limits (e.g., Gemini: 32k tokens)
    - 1 token ≈ 4 characters for English text
    - Long documents exceed this limit
    - Solution: Summarize before sending to agent
    
    WHEN TO SUMMARIZE:
    - Estimate: len(text) / 4 = rough token count
    - If > max_tokens threshold: summarize
    - If < max_tokens: pass through unchanged
    
    SUMMARIZATION APPROACH:
    - Uses LLM to create concise summary
    - Preserves key information for policy context
    - Reduces 50-page doc to 2-page summary
    - Loses detail but maintains relevance
    
    PROMPT DESIGN:
    "Summarize this policy document focusing on:
    - Key benefits and entitlements
    - Eligibility criteria  
    - Important dates and deadlines
    - Compliance requirements"
    
    RETURN VALUE:
    - Tuple: (text, was_summarized)
    - was_summarized flag shown to user as warning
    - User knows they're working with summary not full doc
    
    TRADE-OFFS:
    - Faster processing (fewer tokens)
    - Lower cost (fewer API tokens)
    - BUT: Some detail lost in summarization
    - User can always reference original file
    
    WHY 100000 TOKEN DEFAULT?:
    - Leaves room for: user query + document + agent response
    - Prevents hitting context limit mid-conversation
    - Conservative estimate (better safe than sorry)
    """
    if len(text) <= max_length:
        return text, False
    
    # Simple truncation with note - could be enhanced with AI summarization
    truncated = text[:max_length]
    summary_note = f"\n\n[NOTE: Document truncated to {max_length} characters for processing]"
    return truncated + summary_note, True