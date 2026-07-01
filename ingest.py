import os

os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""
os.environ["NO_PROXY"] = "localhost,127.0.0.1"

from langchain_community.document_loaders import TextLoader, PyPDFLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_chroma import Chroma
from langchain.chains import RetrievalQA
import redis

embeddings = OllamaEmbeddings(model="mxbai-embed-large")

redis_client = redis.Redis(
    host="localhost",
    port=6379,
    db=0,
    protocol=2,
    decode_responses=True
)

async def start_ingestion(client_id: int, file: str):


    if file.endswith(".txt"):
        loader = TextLoader(file, encoding="utf-8")
    elif file.endswith(".pdf"):
        loader = PyPDFLoader(file)
    elif file.endswith(".docx") or file.endswith(".doc"):
        loader = Docx2txtLoader(file)
    else:
        raise ValueError("invalid file format")
    documents = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    texts = text_splitter.split_documents(documents)
    for text in texts:
        text.metadata["user_id"] = client_id
        text.metadata["file_name"] = os.path.basename(file)

    vector_db = Chroma(
        embedding_function=embeddings,
        persist_directory="./db_data"
    )
    vector_db.add_documents(texts)
    if os.path.exists(file):
        os.remove(file)
    return True


async def ask_question(client_id: int, question: str):
    db = Chroma(persist_directory="./db_data", embedding_function=embeddings)

    llm = ChatOllama(model="llama3", temperature=0)
    retriever = db.as_retriever(
        search_kwargs={'filter': {'user_id': client_id}}
    )

    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=True
    )

    response = qa_chain.invoke(question)

    answer = response.get("result")
    source = response.get("source_documents", [])
    sources = []

    for text in source:
        name = text.metadata.get("file_name", "No source")
        if name not in sources:
            sources.append(name)
    
    return answer, sources

