import os
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma

# 1. Load Environment Variables
load_dotenv()

# Check for API Key
if not os.getenv("GOOGLE_API_KEY"):
    raise ValueError("GOOGLE_API_KEY not found. Check your .env file.")

def setup_rag_pipeline():
    print("--- 📚 Setting up Knowledge Base (RAG) ---")

    # 2. LOAD (Document Loaders - Page 77 of PDF)
    # We load the PDF we just created.
    print("Loading PDF...")
    loader = PyPDFLoader("paris_guide.pdf")
    docs = loader.load()
    print(f"Loaded {len(docs)} page(s).")

    # 3. SPLIT (Text Splitters - Page 86 of PDF)
    # We break the text into smaller chunks so the AI can handle them easily.
    print("Splitting text...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,  # Characters per chunk
        chunk_overlap=200 # Overlap to keep context between chunks
    )
    splits = text_splitter.split_documents(docs)
    print(f"Created {len(splits)} text chunks.")

    # 4. EMBED & STORE (Vector Stores - Page 94 of PDF)
    # We turn text into numbers (vectors) using Google's model and store them in ChromaDB.
    print("Creating Vector Database...")
    embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
    
    # This creates a folder 'chroma_db' to save your database
    vectorstore = Chroma.from_documents(
        documents=splits, 
        embedding=embeddings,
        persist_directory="./chroma_db" 
    )
    print("✅ Database created and saved to './chroma_db'")
    
    return vectorstore

def test_retrieval(vectorstore):
    print("\n--- 🕵️ Testing Retrieval ---")
    
    # 5. RETRIEVE (Retrievers - Page 100 of PDF)
    # We create a retriever that looks for the top 2 most relevant chunks.
    retriever = vectorstore.as_retriever(search_kwargs={"k": 2})
    
    query = "Where can I eat cheaply in Paris?"
    print(f"Query: {query}")
    
    # Ask the database
    relevant_docs = retriever.invoke(query)
    
    print(f"\nFound {len(relevant_docs)} relevant result(s):")
    for i, doc in enumerate(relevant_docs):
        print(f"\n[Result {i+1}]:")
        print(doc.page_content)

if __name__ == "__main__":
    # If the DB already exists, we can load it directly (comment out setup_rag_pipeline if running again)
    if os.path.exists("./chroma_db"):
        print("Loading existing database...")
        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
        vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
    else:
        vectorstore = setup_rag_pipeline()
        
    test_retrieval(vectorstore)