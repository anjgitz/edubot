import os
import tempfile
import streamlit as st
from streamlit_chat import message
from pdfquery import PDFQuery
import docx2txt
import sqlite3
import speech_recognition as sr
from gtts import gTTS
from playsound import playsound
from dotenv import load_dotenv  # import statement

# Load environment variables from .env file
load_dotenv()

# Get the OpenAI API key from environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if OPENAI_API_KEY is None:
    raise ValueError("OpenAI API Key not found. Please set the API key in your environment or .env file.")

# Create or connect to the database
conn = sqlite3.connect('login_credentials.db')
c = conn.cursor()

# Create table if it does not exist
c.execute('''CREATE TABLE IF NOT EXISTS login (
                 prn TEXT PRIMARY KEY,
                 name TEXT
                 )''')
conn.commit()


st.set_page_config(page_title="EduBot")

def is_user_authenticated(prn):
    c.execute("SELECT * FROM login WHERE prn = ?", (prn,))
    result = c.fetchone()
    return result is not None

def save_credentials(prn, name):
    try:
        c.execute("INSERT INTO login (prn, name) VALUES (?, ?)", (prn, name))
        conn.commit()
        st.success(f"Logged in as {name} with PRN: {prn}")
        st.session_state["is_logged_in"] = True  # Set authentication state to True
    except sqlite3.IntegrityError:
        conn.rollback()
        st.error("PRN already exists. Please choose a different PRN.")
    except Exception as e:
        conn.rollback()
        st.error(f"Error occurred while saving credentials: {e}")

def login_user(prn, name):
    if is_user_authenticated(prn):
        st.session_state["is_logged_in"] = True
        st.success(f"Logged in as {name} with PRN: {prn}")
    else:
        st.error("Invalid PRN. Please check your PRN or sign up.")

def display_messages():
    st.subheader("Chat")
    for i, (msg, is_user) in enumerate(st.session_state["messages"]):
        message(msg, is_user=is_user, key=str(i))
    st.session_state["thinking_spinner"] = st.empty()

def process_input():
    if st.session_state["user_input"] and len(st.session_state["user_input"].strip()) > 0:
        user_text = st.session_state["user_input"].strip()
        with st.session_state["thinking_spinner"], st.spinner(f"Thinking"):
            query_text = st.session_state["pdfquery"].ask(user_text)

        st.session_state["messages"].append((user_text, True))
        st.session_state["messages"].append((query_text, False))
        
        # Assign the chatbot response to query_text
        st.session_state["query_text"] = query_text

def read_and_save_file():
    st.session_state["pdfquery"].forget()  # to reset the knowledge base
    st.session_state["messages"] = []
    st.session_state["user_input"] = ""

    for file in st.session_state["file_uploader"]:
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(file.getbuffer())
            file_path = tf.name

        with st.session_state["ingestion_spinner"], st.spinner(f"Ingesting {file.name}"):
            if file.name.endswith(".pdf"):
                st.session_state["pdfquery"].ingest_pdf(file_path)
            elif file.name.endswith(".docx"):
                text = docx2txt.process(file_path)
                st.session_state["pdfquery"].ingest_text(text)
            else:
                st.warning(f"Unsupported file format: {file.name}")

        os.remove(file_path)

def is_openai_api_key_set() -> bool:
    return len(st.session_state.get("OPENAI_API_KEY", "")) > 0

def speech_to_text():
    recognizer = sr.Recognizer()

    with sr.Microphone() as source:
        st.info("Listening...")
        recognizer.adjust_for_ambient_noise(source, duration=1)
        audio_data = recognizer.listen(source)

    try:
        user_text = recognizer.recognize_google(audio_data)
        st.session_state["user_input"] = user_text
        st.success(f"Recognized: {user_text}")
    except sr.UnknownValueError:
        st.error("Sorry, I could not understand what you said. Please try again.")
    except sr.RequestError as e:
        st.error(f"Error occurred: {e}")

def text_to_speech(text):
    # Create a temporary directory to save the audio file
    with tempfile.TemporaryDirectory() as temp_dir:
        output_file = os.path.join(temp_dir, "output.mp3")
        
        tts = gTTS(text=text, lang="en")
        tts.save(output_file)
        
        # Play the audio file
        playsound(output_file)

def init_feedback_db():
    conn = sqlite3.connect('feedback.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS feedback
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, rating INTEGER, comment TEXT)''')
    conn.commit()
    conn.close()

init_feedback_db()

def insert_feedback(rating, comment):
    conn = sqlite3.connect('feedback.db')
    c = conn.cursor()
    c.execute("INSERT INTO feedback (rating, comment) VALUES (?, ?)", (rating, comment))
    conn.commit()
    conn.close()

def feedback_form():
    st.header('Feedback')
    rating = st.slider('Rating:', min_value=1, max_value=5, step=1)
    comment = st.text_area('Additional Comments:')
    if st.button('Send'):
        insert_feedback(rating, comment)
        st.success('Feedback sent successfully!')
                

def main():
    if len(st.session_state) == 0:
        st.session_state["messages"] = []
        st.session_state["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY", "")
        if is_openai_api_key_set():
            st.session_state["pdfquery"] = PDFQuery(st.session_state["OPENAI_API_KEY"])
        else:
            st.session_state["pdfquery"] = None

    st.sidebar.header("Navigation")
    if st.sidebar.button("Home"):
        st.session_state["page"] = "home"
    if st.session_state.get("is_logged_in", False):    
       if st.sidebar.button("Upload"):
            st.session_state["page"] = "upload"
       if st.sidebar.button("Chat"):
            st.session_state["page"] = "chat"
       if st.sidebar.button("Feedback"):  
            st.session_state["page"] = "feedback"
    

    if "page" not in st.session_state:
        st.session_state["page"] = "home"

    if st.session_state["page"] == "chat":
        display_messages()
        if st.button("Start Voice Input"):
            speech_to_text()
        st.text_input("Message", key="user_input", disabled=not is_openai_api_key_set(), on_change=process_input)
        query_text = st.session_state.get("query_text", "")
        if st.button("Convert to Speech"):
            if not query_text.strip():  # Check if the text is empty
                st.error("Cannot convert empty text to speech.")
            else:
                text_to_speech(query_text)
    elif st.session_state["page"] == "upload":
        st.header("EduBot - Upload a Document")
        st.subheader("Upload a document")
        st.file_uploader(
            "Upload document",
            type=["pdf", "docx"],
            key="file_uploader",
            on_change=read_and_save_file,
            label_visibility="collapsed",
            accept_multiple_files=True,
            disabled=not is_openai_api_key_set(),
        )
        st.session_state["ingestion_spinner"] = st.empty()
    elif st.session_state["page"] == "home":
        st.title("EduBot - Home")
        prn = st.text_input("PRN (Personal Registration Number)")
        name = st.text_input("Name")
        if st.button("Login"):
            if prn and name:
                login_user(prn, name)
            else:
                st.error("Please enter both PRN and Name to login.")
        if st.button("Sign Up"):
            if prn and name:
                save_credentials(prn, name)
            else:
                st.error("Please enter both PRN and Name to sign up.")
                

    elif st.session_state["page"] == "feedback":
       feedback_form()    



   

if __name__ == "__main__":
    main()
