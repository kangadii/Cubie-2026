#!/usr/bin/env python3
"""
Regenerate help document embeddings using Google Gemini embedding model.

This script replaces the OpenAI embeddings with Gemini embeddings.
Run this once after migrating from OpenAI to Gemini.

Usage:
    python regenerate_embeddings.py
"""

import os
import numpy as np
from google import genai
from google.genai import types
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if api_key is None:
    raise ValueError("GOOGLE_API_KEY not set in your .env file")
client = genai.Client(api_key=api_key)

# Embedding model
EMBED_MODEL = "models/gemini-embedding-001"

def get_embedding(text: str) -> list:
    """Generate embedding for a text using Gemini."""
    result = client.models.embed_content(
        model=EMBED_MODEL,
        contents=text,
        config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
    )
    return result.embeddings[0].values

def load_help_documents():
    """Load help documents from HelpContent folder."""
    documents = []
    help_path = Path("HelpContent")
    
    if not help_path.exists():
        print(f"Warning: HelpContent folder not found at {help_path.absolute()}")
        return documents
    
    for html_file in help_path.glob("*.html"):
        try:
            with open(html_file, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Extract text content (basic extraction)
            # For better results, you might want to use BeautifulSoup
            import re
            # Remove HTML tags
            text = re.sub(r'<[^>]+>', ' ', content)
            # Clean up whitespace
            text = ' '.join(text.split())
            
            doc = {
                "source_url": f"http://dev.tcube360.com/help/{html_file.name}",
                "section_title": html_file.stem.replace("-", " ").replace("_", " ").title(),
                "content": text[:5000]  # Limit content length
            }
            documents.append(doc)
            print(f"  Loaded: {html_file.name}")
        except Exception as e:
            print(f"  Error loading {html_file.name}: {e}")
    
    return documents

def regenerate_embeddings():
    """Main function to regenerate embeddings."""
    print("=" * 50)
    print("Gemini Embedding Regeneration Script")
    print("=" * 50)
    
    # Check if old embeddings exist
    embeddings_file = Path("help_embeddings.npz")
    if embeddings_file.exists():
        print(f"\nFound existing embeddings file: {embeddings_file}")
        backup_file = Path("help_embeddings_openai_backup.npz")
        if not backup_file.exists():
            print(f"Creating backup: {backup_file}")
            import shutil
            shutil.copy(embeddings_file, backup_file)
    
    # Load documents
    print("\nLoading help documents...")
    documents = load_help_documents()
    
    if not documents:
        print("No documents found! Checking for existing documents in embeddings file...")
        if embeddings_file.exists():
            data = np.load(embeddings_file, allow_pickle=True)
            documents = list(data["documents"])
            print(f"Found {len(documents)} documents in existing file")
        else:
            print("No documents found. Exiting.")
            return
    
    print(f"\nTotal documents: {len(documents)}")
    
    # Generate embeddings
    print("\nGenerating Gemini embeddings...")
    embeddings = []
    for i, doc in enumerate(documents):
        try:
            # Combine section title and content for embedding
            text = f"{doc.get('section_title', '')} {doc.get('content', '')}"
            embedding = get_embedding(text)
            embeddings.append(embedding)
            print(f"  [{i+1}/{len(documents)}] Embedded: {doc.get('section_title', 'Unknown')[:50]}...")
        except Exception as e:
            print(f"  Error embedding document {i}: {e}")
            # Use zero embedding as fallback
            embeddings.append([0.0] * 768)  # Gemini embedding dimension
    
    # Save new embeddings
    print(f"\nSaving embeddings to {embeddings_file}...")
    np.savez(
        embeddings_file,
        embeddings=np.array(embeddings),
        documents=np.array(documents, dtype=object)
    )
    
    print("\n" + "=" * 50)
    print("✅ Embeddings regenerated successfully!")
    print(f"   Documents: {len(documents)}")
    print(f"   Embedding dimension: {len(embeddings[0]) if embeddings else 'N/A'}")
    print("=" * 50)

if __name__ == "__main__":
    regenerate_embeddings()
