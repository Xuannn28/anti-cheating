import os 
import shutil
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain_chroma import Chroma

DOCS_DIR = "./context_docs"
DB_DIR = "./database"

# initialize embedding model 
embeddings = OllamaEmbeddings(model="nomic-embed-text")

def index_all_documents(): 
    """Read content in DOCS_DIR, process, save into ChromaDB. """

    # collect markdown from directory
    all_markdown_text = ""
    print(f"Reading markdown files")
    if not os.path.exists(DOCS_DIR):
        os.makedirs(DOCS_DIR)
        print(f"Created context_docs directory.")
        return 
    
    for filename in os.listdir(DOCS_DIR):
        if filename.endswith(".md"):
            with open(os.path.join(DOCS_DIR, filename), "r", encoding="utf-8") as f:
                all_markdown_text += f.read() + "\n\n"
    
    if not all_markdown_text.strip():
        print("No markdown content found.")
        return 

    print("Splitting documents")  # reduce computation, more precise retrieval

    # TXT FILE SPLITTING DOCUMENT METHOD
    # chunk_size: max size of each chunk
    # chunk_overlap: repeat the last n characters of one chunk at the beginning of next chunk 
    # to preserve context across chunk
    # splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=50)
    # chunks = splitter.split_documents(documents)

    headers_to_split = [
        ("#", "Category"), 
        ("##", "Topic"), 
        ("###", "SubTopic")
    ]

    # keep header inside text so LLM can read
    md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split, strip_headers=False)
    chunks = md_splitter.split_text(all_markdown_text)

    print("Convert to token embedding and save to vector database")
    vectore_store = Chroma.from_documents(
        documents=chunks, 
        embedding=embeddings, 
        persist_directory=DB_DIR
    )

    print(f"Success! Indexed {len(chunks)} chunks into '{DB_DIR}'.")
    

if __name__ == "__main__":
    index_all_documents()