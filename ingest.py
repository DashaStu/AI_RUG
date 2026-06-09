import os

os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""
os.environ["NO_PROXY"] = "localhost,127.0.0.1"

from langchain_community.document_loaders import TextLoader, PyPDFLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_chroma import Chroma
from langchain.chains import RetrievalQA

embeddings = OllamaEmbeddings(model="mxbai-embed-large")

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
        retriever=retriever
    )

    response = qa_chain.invoke(question)
    return response["result"]

