<<<<<<< HEAD

# Procurement-Assistant

=======

# 🛒 Procurement AI Assistant

An AI-powered chatbot that answers natural language questions about
California State procurement data using Claude AI and MongoDB.

## Tech Stack

- **Backend**: Python, FastAPI, LangChain, Claude AI
- **Database**: MongoDB
- **Frontend**: HTML, CSS, JavaScript

## Setup Instructions

### 1. Clone the repo

git clone https://github.com/yourusername/procurement-assistant.git
cd procurement-assistant

### 2. Setup Backend

cd backend
pip install -r requirements.txt

### 3. Add your API key

Create a .env file:
ANTHROPIC_API_KEY=your_key_here
MONGO_URI=mongodb://localhost:27017/

### 4. Load the data

python load_data.py

### 5. Start the backend

uvicorn main:app --reload --port 8000

### 6. Open the frontend

Open frontend/index.html in your browser

> > > > > > > 251ecb0 (first commit)
