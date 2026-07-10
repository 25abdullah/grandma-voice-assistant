# Conversational AI Companion
 
A real-time AI voice assistant built for elderly users, enabling natural spoken conversation through a browser-based interface. The assistant understands Urdu-English code-switching, handles mispronunciations, and supports a set of agentic tools to perform real-world tasks on behalf of the user.
 
---
 
## Overview
 
The assistant listens to the user via microphone, transcribes speech to text, passes the transcript to an LLM agent, and streams the response back as audio in real time. All conversation turns are stored in Supabase and relevant past context is retrieved via a vector store to personalize responses.
 
---
 
## Features
 
**Voice pipeline** — WebSocket-based audio streaming with real-time speech-to-text transcription and text-to-speech synthesis. Audio is processed sentence-by-sentence to minimize latency.
 
**Agentic tool system** — The LLM can invoke the following tools based on user intent:
 
- Look up a family member's phone number from a contact database
- Place a phone call via Twilio
- Fetch the latest Pakistan news headlines
- Retrieve prayer times for the current day and location
- Repeat the last AI or user message
**Urdu-English support** — The system prompt is designed to handle code-switched input (e.g., "Abdullah ko call karo"), resolve name variations and mispronunciations, and always respond in English.
 
**Conversation memory** — All messages are stored in Supabase. A ChromaDB vector store with HuggingFace embeddings retrieves semantically relevant past messages to inject as context on each turn.
 
**Interruption handling** — If the user speaks while the assistant is responding, the current audio playback is cancelled and the new input is processed immediately.
 
---
 
## Tech Stack
 
| Layer | Technology |
|---|---|
| Backend | FastAPI, Python |
| Frontend | JavaScript, HTML, CSS |
| Speech-to-Text | OpenAI-compatible STT API |
| Text-to-Speech | Cartesia |
| LLM | OpenRouter (nvidia/nemotron) |
| Database | Supabase |
| Phone calls | Twilio |
| Vector store | ChromaDB, HuggingFace Embeddings |
| News | NewsAPI |
| Prayer times | aladhan-api |
 
---
 
## Environment Variables
 
Create a `.env` file with the following:
 
```
OPENROUTER_API_KEY=
STT_API_KEY=
STT_BASE_URL=
CARTESIA_API_KEY=
SUPABASE_URL=
SUPABASE_KEY=
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM_NUMBER=
NEWS_API_KEY=
```
 
