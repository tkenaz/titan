#!/usr/bin/env python3
"""File watcher plugin - extracts text from files and creates summaries."""

import os
import json
import sys
import logging
from pathlib import Path
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("file_watcher")


def extract_text_from_pdf(file_path: Path) -> str:
    """Extract text from PDF file."""
    try:
        import pdfplumber
        
        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
        
        return "\n".join(text_parts)
    
    except Exception as e:
        logger.error(f"Failed to extract from PDF: {e}")
        # Fallback to PyPDF2
        try:
            from PyPDF2 import PdfReader
            
            reader = PdfReader(file_path)
            text_parts = []
            
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            
            return "\n".join(text_parts)
        
        except Exception as e2:
            logger.error(f"PyPDF2 also failed: {e2}")
            return ""


def extract_text_from_markdown(file_path: Path) -> str:
    """Extract text from Markdown file."""
    try:
        return file_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to read markdown: {e}")
        return ""


def create_summary(text: str, max_length: int = 300) -> str:
    """Create a simple summary of the text."""
    if not text:
        return "Empty document"
    
    # Clean up text
    lines = text.strip().split("\n")
    lines = [line.strip() for line in lines if line.strip()]
    
    # Simple summary: first few sentences
    summary_parts = []
    char_count = 0
    
    for line in lines:
        # Skip very short lines (likely headers or noise)
        if len(line) < 20:
            continue
        
        summary_parts.append(line)
        char_count += len(line)
        
        if char_count >= max_length:
            break
    
    if not summary_parts:
        # If no good lines, just take the beginning
        summary = text[:max_length]
    else:
        summary = " ".join(summary_parts)[:max_length]
    
    # Add ellipsis if truncated
    if len(text) > max_length:
        summary += "..."
    
    return summary


def main():
    """Main plugin entry point."""
    # Get event data from environment
    event_data = os.environ.get("EVENT_DATA")
    if not event_data:
        logger.error("No EVENT_DATA provided")
        sys.exit(1)
    
    try:
        event = json.loads(event_data)
        payload = event.get("payload", {})
        
        # Extract file path
        file_path = payload.get("path")
        if not file_path:
            logger.error("No file path in event")
            sys.exit(1)
        
        file_path = Path(file_path)
        
        # Check if file exists and is readable
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            sys.exit(1)
        
        logger.info(f"Processing file: {file_path}")
        
        # Extract text based on file type
        mime_type = payload.get("mime_type", "")
        
        if "pdf" in mime_type or file_path.suffix.lower() == ".pdf":
            text = extract_text_from_pdf(file_path)
        elif "markdown" in mime_type or file_path.suffix.lower() in [".md", ".markdown"]:
            text = extract_text_from_markdown(file_path)
        elif "text" in mime_type or file_path.suffix.lower() == ".txt":
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        else:
            logger.error(f"Unsupported file type: {mime_type}")
            sys.exit(1)
        
        # Create summary
        summary = create_summary(text)
        
        # Output result (this would normally be published to Event Bus)
        result = {
            "event_type": "file_summary",
            "topic": "system.v1",
            "payload": {
                "path": str(file_path),
                "file_name": file_path.name,
                "mime_type": mime_type,
                "summary": summary,
                "text_length": len(text),
                "success": True
            }
        }
        
        # Print as JSON for the sandbox to capture
        print(json.dumps(result, indent=2))
        
        logger.info(f"Successfully processed {file_path.name}")
        
    except Exception as e:
        logger.error(f"Plugin error: {e}", exc_info=True)
        
        # Output error result
        error_result = {
            "event_type": "file_summary",
            "topic": "system.v1",
            "payload": {
                "path": str(file_path) if 'file_path' in locals() else "unknown",
                "success": False,
                "error": str(e)
            }
        }
        
        print(json.dumps(error_result, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
