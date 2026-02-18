#!/usr/bin/env python3
"""
Enhance help document embeddings using Google Gemini embedding model with CHUNKING.

This script replaces the simple embedding generation with a more robust approach:
1. Parses HTML more cleanly.
2. Chunks content into manageable sizes (e.g., 2000 chars) with overlap.
3. Generates embeddings for ALL chunks, ensuring large documents are fully covered.

Usage:
    python enhance_embeddings.py
"""

import os
import re
import numpy as np
import google.generativeai as genai
from dotenv import load_dotenv
from pathlib import Path

# Try to import BeautifulSoup
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
    print("Warning: BeautifulSoup4 not found. Using regex fallback for HTML parsing.")

# Load environment variables
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if api_key is None:
    raise ValueError("GOOGLE_API_KEY not set in your .env file")
genai.configure(api_key=api_key)

# Embedding model
EMBED_MODEL = "models/gemini-embedding-001"

# Chunking configuration
CHUNK_SIZE = 4000  # characters
CHUNK_OVERLAP = 400  # characters

def get_embedding(text: str) -> list:
    """Generate embedding for a text using Gemini."""
    # Add a small delay/retry logic if needed, but usually Gemini is fast enough
    try:
        result = genai.embed_content(
            model=EMBED_MODEL,
            content=text,
            task_type="retrieval_document"
        )
        return result['embedding']
    except Exception as e:
        print(f"    Error getting embedding: {e}")
        return [0.0] * 768  # Return zero vector on failure

def clean_html(html_content: str) -> str:
    """Extract clean text from HTML."""
    if HAS_BS4:
        soup = BeautifulSoup(html_content, "html.parser")
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer"]):
            script.decompose()
        text = soup.get_text(separator=" ")
        # Clean whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        return text
    else:
        # Regex fallback
        text = re.sub(r'<script[^>]*>.*?</script>', ' ', html_content, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', ' ', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = ' '.join(text.split())
        return text

def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    """Split text into chunks with overlap."""
    if len(text) <= size:
        return [text]
    
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        # Try to find a sentence break near the end
        if end < len(text):
            # Look for period, question mark, or exclamation point
            last_period = text.rfind('.', start, end)
            if last_period != -1 and last_period > start + size // 2:
                 end = last_period + 1
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        start += (size - overlap)
    
    return chunks

def load_and_chunk_documents():
    """Load, clean, and chunk help documents."""
    all_chunks = []
    help_path = Path("HelpContent")
    
    if not help_path.exists():
        print(f"Warning: HelpContent folder not found at {help_path.absolute()}")
        return all_chunks
    
    html_files = list(help_path.glob("*.html"))
    print(f"Found {len(html_files)} HTML files to process.")

    for html_file in html_files:
        try:
            with open(html_file, "r", encoding="utf-8") as f:
                content = f.read()
            
            clean_text = clean_html(content)
            
            # Metadata
            base_url = "http://dev.tcube360.com/help"
            source_url = f"{base_url}/{html_file.name}"
            section_title = html_file.stem.replace("-", " ").replace("_", " ").title()
            
            # Create chunks
            chunks = chunk_text(clean_text, CHUNK_SIZE, CHUNK_OVERLAP)
            
            print(f"  Processed {html_file.name}: {len(chunks)} chunks")
            
            for i, chunk in enumerate(chunks):
                doc_chunk = {
                    "source_url": source_url,
                    "section_title": section_title,
                    "content": chunk,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "original_filename": html_file.name
                }
                all_chunks.append(doc_chunk)
                
        except Exception as e:
            print(f"  Error processing {html_file.name}: {e}")
    
    return all_chunks

def regenerate_embeddings():
    """Main function to regenerate embeddings with chunking."""
    print("=" * 50)
    print("Gemini Enhanced Embedding Generator (Chunked)")
    print("=" * 50)
    
    embeddings_file = Path("help_embeddings.npz")
    
    # 1. Load and chunk
    print("\nProcessing documents...")
    chunked_docs = load_and_chunk_documents()
    
    if not chunked_docs:
        print("No documents found. Exiting.")
        return
    
    print(f"\nTotal chunks to embed: {len(chunked_docs)}")
    
    # 2. Generate embeddings
    print("\nGenerating embeddings (this may take a moment)...")
    embeddings = []
    
    # Process in batches to show progress
    for i, doc in enumerate(chunked_docs):
        # Create a rich text representation for the embedding
        # "Title: Section Name. Content: ... chunk text ..."
        text_to_embed = f"Title: {doc['section_title']}. Content: {doc['content']}"
        
        emb = get_embedding(text_to_embed)
        embeddings.append(emb)
        
        if (i + 1) % 10 == 0:
            print(f"  Progress: {i + 1}/{len(chunked_docs)} chunks embedded")
            
    # 3. Save
    print(f"\nSaving {len(embeddings)} embeddings to {embeddings_file}...")
    np.savez(
        embeddings_file,
        embeddings=np.array(embeddings),
        documents=np.array(chunked_docs, dtype=object)
    )
    
    print("\n" + "=" * 50)
    print("✅ Enhanced embeddings generated successfully!")
    print(f"   Total source documents: {len(set(d['original_filename'] for d in chunked_docs))}")
    print(f"   Total searchable chunks: {len(chunked_docs)}")
    print("=" * 50)

if __name__ == "__main__":
    regenerate_embeddings()
