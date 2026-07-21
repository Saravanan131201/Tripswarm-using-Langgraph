# 🌍 TripSwarm – AI-Powered Multi-Agent Travel Planner

TripSwarm is an AI-powered travel planning platform that combines **Multi-Agent AI**, **Agentic Retrieval-Augmented Generation (RAG)**, and **real-time travel search** to help users plan smarter trips. The application generates personalized itineraries, suggests flights and hotels, answers travel-related questions, and securely manages user conversations.

---

## ✨ Features

### 🤖 AI Multi-Agent Travel Planning
- Flight Research Agent
- Hotel Recommendation Agent
- Itinerary Planning Agent
- Response Formatting Agent

### 🔍 Agentic Retrieval-Augmented Generation (RAG)
- Upload travel-related documents (PDF, DOCX, TXT)
- Route_query   → LLM decides: hybrid vector search OR direct LLM answer
- Hybrid_search → Dense (ChromaDB embeddings) + Sparse (BM25) → RRF re-rank
- Rag_generate  → Answer from retrieved context + conversational memory
- LLM_direct    → Answer directly with conversational memory

### ✈️ Flight Search
- Live flight information
- Airline details
- Flight duration
- Route information

### 🏨 Hotel Recommendations
- Budget hotels
- Mid-range hotels
- Luxury hotels
- Approximate pricing
- Nearby accommodations

### 📅 Intelligent Itinerary Generation
- Day-by-day travel plans
- Tourist attractions
- Local food recommendations
- Budget estimation
- Travel tips

### 💬 Chat History
- Persistent chat threads
- Multiple conversations 
- Message history
- Conversation management (Only for RAG Agent Workflow)

### 👤 Authentication
- Google OAuth Login
- Secure JWT Authentication
- User profile management

### 📄 Document Management
- Upload PDFs
- Upload DOCX files
- Upload TXT files
- Automatic text extraction
- Embedding generation
- Semantic indexing

### 📊 AI Generated Reports
- Downloadable travel reports
- Markdown formatted responses
- Professional travel recommendations

---

# 🏗️ System Architecture

```
                    User
                      │
             Google OAuth Login
                      │
                      ▼
                FastAPI Backend
                      │
      ┌───────────────┼────────────────┐
      │               │                │
      ▼               ▼                ▼
 Travel Agent     RAG Workflow    Chat History
      │               │                │
      ▼               ▼                ▼
 LangGraph       Chroma VectorDB   PostgreSQL
      │
      ▼
 Flight Agent
      │
 Hotel Agent
      │
 Itinerary Agent
      │
 Response Agent
      │
      ▼
 AI Travel Report
```

---

# 🚀 Technology Stack

## Backend

- FastAPI
- Python
- LangGraph
- LangChain
- SQLAlchemy
- PostgreSQL
- JWT Authentication

## AI & LLM

- Groq
- GPT-OSS-120B
- LangChain
- Fast Embeddings

## Vector Database

- Chroma DB

## Search

- Tavily Search API
- AviationStack API

## Frontend

- HTML
- CSS
- JavaScript
- Jinja2 Templates

## Authentication

- Google OAuth
- JWT Tokens

## Database

- PostgreSQL

## Deployment

- Docker
- Jenkins
- Render

---

# 🤖 Multi-Agent Workflow

```
User Query
     │
     ▼
Flight Agent
     │
     ▼
Hotel Agent
     │
     ▼
Itinerary Agent
     │
     ▼
Response Agent
     │
     ▼
Final AI Travel Report
```

Each agent is responsible for a specific task, allowing TripSwarm to generate comprehensive and well-structured travel plans.

---

# 🐳 Docker

Build Image

```bash
docker build -t tripswarm .
```

Run Container

```bash
docker run -p 8000:8000 tripswarm
```

---

# 🔄 Jenkins CI/CD

The project supports automated CI/CD using Jenkins.

Pipeline stages include:

- Checkout Source Code
- Install Dependencies
- Run Tests
- Deploy Application

---

# 📈 Future Enhancements

- Flight Booking Integration
- Changing tools into MCP Servers
- Hotel Booking Integration
- Visa Assistance
- Weather Forecast Agent Integration
- Travel Expense Tracking
- PDF Travel Report Email
- Multi-language Support
- Voice-based Travel Assistant

---

# 🤝 Contributing

Contributions are welcome!

1. Fork the repository
2. Create a feature branch

```bash
git checkout -b feature/my-feature
```

3. Commit your changes

```bash
git commit -m "Add new feature"
```

4. Push the branch

```bash
git push origin feature/my-feature
```

5. Open a Pull Request

---


# 👨‍💻 Author

**Saravanan S**

- GitHub: https://github.com/Saravanan131201
- LinkedIn: www.linkedin.com/in/saravanan-s1312

---

⭐ If you found this project helpful, consider giving it a Star on GitHub!