
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

# initialization
DB_DIR = "./database"
embeddings = OllamaEmbeddings(model="nomic-embed-text")
llm = ChatOllama(model="llama3.2:1b", temperature=0.2)

# load vector database 
vectore_store = Chroma(
    persist_directory=DB_DIR, 
    embedding_function=embeddings
)
retriever = vectore_store.as_retriever(search_kwargs={"k": 2})  # retrieve top 2 similar answers

# Format helper to clean up database outputs for the prompt
def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

# tell LLM how to act using our system guidelines 
# context: the place where LangChain paste the matching paragraph from ChromaDB 
system_instruction = (
    "You are an AI Interview Evaluator. Answer the question using ONLY the provided context below.\n"
    "If the answer isn't explicitly clear in the text, say 'I cannot find that in the rubric database.'\n\n"
    "Context:\n{context}"
)

# structured text into a format model understand
prompt = ChatPromptTemplate.from_messages([
    ("system", system_instruction),   # backend rule
    ("human", "{input}")  # user input
])

# assemble the pipeline 
rag_chain = (
    {"context": retriever | format_docs, "input": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

print("\nLocal LCEL RAG Chatbot Ready! (Type 'exit' to quit)")
while True:
    query = input("\nYou: ")
    if query.lower() in ['exit', 'quit']:
        break
        
    # Simply pass the input. The output is already parsed as a clean text string.
    response = rag_chain.invoke(query)
    print(f"\nAI: {response}")