import os
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain.chains.question_answering import load_qa_chain
from langchain.chat_models import ChatOpenAI
from langchain.document_loaders import PyPDFium2Loader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import docx2txt

class PDFQuery:
    def __init__(self, openai_api_key=None):
        self.embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)
        os.environ["OPENAI_API_KEY"] = openai_api_key
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        self.llm = ChatOpenAI(temperature=0, openai_api_key=openai_api_key)
        self.chain = None
        self.db = None

    def ask(self, question):
        if self.chain is None:
            return "Please, add a document."

        if self.db is None:
            return "Please, add a document."

        response = self.chain.run(input_documents=self.db.get_relevant_documents(question), question=question)
        return response

    def ingest(self, file_path):
        # Check if the file is a PDF
        if file_path.lower().endswith('.pdf'):
            # Process PDF file
            self.ingest_pdf(file_path)
        # Check if the file is a DOCX
        elif file_path.lower().endswith('.docx'):
            # Process DOCX file
            self.ingest_docx(file_path)
        else:
            print("Unsupported file format:", file_path)

    def ingest_pdf(self, file_path):
        # Process PDF file
        loader = PyPDFium2Loader(file_path)
        documents = loader.load()
        splitted_documents = self.text_splitter.split_documents(documents)
        self.db = Chroma.from_documents(splitted_documents, self.embeddings).as_retriever()
        self.chain = load_qa_chain(ChatOpenAI(temperature=0), chain_type="stuff")

    def ingest_docx(self, file_path):
        # Process DOCX file
        text = docx2txt.process(file_path)
        self.ingest_text(text)

    def ingest_text(self, text):
        self._ingest_documents([text])

    def _ingest_documents(self, documents):
        self.db = Chroma.from_texts(documents, self.embeddings).as_retriever()
        self.chain = load_qa_chain(ChatOpenAI(temperature=0), chain_type="stuff")

    def forget(self):
        self.db = None
        self.chain = None
