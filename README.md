# Cheapest Hotel Chatbot (Flask + OpenAI + Geocoding + Hotel API)

This project is a conversational chatbot that helps users find the **cheapest hotel near a ZIP code or city within a given radius and date range**, using **natural language** input.  
It uses:

| Layer | Technology |
|------|-------------|
| UI | Vanilla JS + HTML (simple chat-style box) |
| Backend | Python + Flask |
| LLM | OpenAI (structured hotel query extraction) |
| Location | Nominatim (OpenStreetMap geocoding) |
| Hotel Data | Amadeus Self-Service (or swappable with Expedia/RapidAPI) |

---

##  Features

✅ Natural language queries (no forms needed)  
✅ Understands radius in miles or km  
✅ Handles relative dates (e.g. “next weekend”, “tomorrow”)  
✅ Auto-normalizes ZIP / city / state  
✅ Returns cheapest and top 10 hotel options  
✅ Works locally in VSCode  
✅ API keys stored securely in `.env`  
✅ Easy to swap Amadeus → Expedia/RapidAPI later

---

 ## Architecture Overview

User → Flask (/api/chat)
↓
OpenAI LLM (slot extraction)
↓
Normalization (dates, radius, adults)
↓
Geocode ZIP/city → lat/lon
↓
Hotel API search (Amadeus)
↓
Cheapest + top 10 results
↓
Return JSON → Render in UI

2. create python 3.11 virtual environment

python3.11 -m venv .venv
source .venv/bin/activate       # macOS/Linux
# .venv\Scripts\activate        # Windows

3. install dependencies
pip install -r requirements.txt

4. Configure .env
OPENAI_API_KEY=sk-xxxxx
AMADEUS_CLIENT_ID=xxxxxxxx
AMADEUS_CLIENT_SECRET=xxxxxxxx
AMADEUS_ENV=test   # or "production" if you have live access

5. Run the server
python app.py

6. Then open:
http://127.0.0.1:5000
