from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import os
from dotenv import load_dotenv

from langchain_community.document_loaders import WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_groq import ChatGroq
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains import create_retrieval_chain
from langchain.chains.history_aware_retriever import create_history_aware_retriever
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel, Field
from typing import Literal


load_dotenv()
os.environ['USER_AGENT'] = "Mozilla/5.0 (compatible; MyApp/1.0; +https://example.com/myapp-info)"
os.environ['OPENAI_API_KEY'] = os.getenv("OPENAI_API_KEY")
os.environ['HF_TOKEN'] = os.getenv("HF_TOKEN")


twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_client = Client(twilio_sid, twilio_token)


app = Flask(__name__)

def get_chatbot_response(message, session_id="123"):
    llm = ChatOpenAI(model="gpt-4-turbo")


    data = WebBaseLoader(["https://www.divtechnosoft.com/artificial-intelligence"]).load()
    data = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200).split_documents(data)
    embedding = HuggingFaceEmbeddings()
    vectorstore = FAISS.from_documents(data, embedding=embedding)
    retriever = vectorstore.as_retriever()

    
    prompt = ChatPromptTemplate.from_template("""
    You are a smart assistant replying on WhatsApp. Use the context below to answer the user's question briefly and clearly.

    ----------------------
    CONTEXT:
    {context}
    ----------------------

    If the context doesn't help, reply with:
    **"Sorry, I couldn’t find that info."**

    Keep responses short, friendly, and to the point.

    ----------------------
    CHAT HISTORY:
    {history}
    ----------------------

    QUESTION:
    {input}

    ANSWER (in WhatsApp style):
    """)

 
    history_prompt = ChatPromptTemplate.from_template("""
    You're a context-aware assistant helping in a WhatsApp chat. Based on the chat so far and the new question, find or infer the info needed.

    ----------------------
    CHAT HISTORY:
    {history}
    ----------------------

    CURRENT QUESTION:
    {input}

    Return keywords or context needed to answer the question.
    """)

  
    history_retriever = create_history_aware_retriever(llm, retriever, history_prompt)
    document_chain = create_stuff_documents_chain(llm, prompt)
    rag_chain = create_retrieval_chain(history_retriever, document_chain)

    
    store = {}
    def session_wise(session_id: str) -> BaseChatMessageHistory:
        if session_id not in store:
            store[session_id] = ChatMessageHistory()
        return store[session_id]

    config = {"configurable": {"session_id": session_id}}
    chain = RunnableWithMessageHistory(
        rag_chain,
        session_wise,
        config=config,
        input_messages_key="input",
        history_messages_key="history",
        output_messages_key="answer"
    )

 
    result = chain.invoke({"input": message}, config=config)
    answer_text = result['answer']

    return answer_text

@app.route("/")
def home():
    return "Flask app is running."

@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    incoming_msg = request.values.get('Body', '').strip()
    from_number = request.values.get('From', '')

    print("Incoming:", incoming_msg, "From:", from_number)

 
    response_text = get_chatbot_response(incoming_msg, session_id=from_number)

  
    resp = MessagingResponse()
    resp.message(response_text)
    print("Response sent:", response_text)
    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
