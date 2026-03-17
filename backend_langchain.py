# ==================== IMPORTS ====================
from fastapi import FastAPI, WebSocket, HTTPException, UploadFile, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from backend.config import ai_model, client_tts, client_stt, supabase_client
from backend.rag import retrieve_context, embed_messages, is_rag_needed
from pipecat_backend.storage import store_messages, get_latest_messages
from backend.file_processing import upload_file, extract_text_from_file
from io import BytesIO
import json
import asyncio

# ==================== APP SETUP ====================
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/v2", StaticFiles(directory="static_v2", html=True), name="static_v2")


# ==================== SYSTEM PROMPT ====================
SYSTEM_PROMPT = """
You are an intelligent, personalized AI assistant with exceptional 
memory capabilities. You maintain context across conversations and use 
past interactions to provide thoughtful, relevant responses.

--- MEMORY & CONTEXT USAGE ---
You have access to information from previous conversations with this 
user AND from any files they've uploaded. This information appears 
below in the "WHAT YOU REMEMBER" section.

**CRITICAL RULES:**
1. **USE the provided context** - If information is in "WHAT YOU 
   REMEMBER", you KNOW it. Don't claim ignorance.
2. **Be specific** - Reference memories directly: "You mentioned you 
   love basketball" NOT "Based on the context..."
3. **Be natural** - Incorporate memories seamlessly
4. **Don't over-explain** - Avoid meta-commentary like "I see in my 
   records that..."
5. **Prioritize recent context** - More recent information is likely 
   more relevant

--- HANDLING FILES & DOCUMENTS ---
When you retrieve content from uploaded files:
- USE IT directly in your response
- NEVER say "I don't have access to files" if content appears below
- Reference the content naturally: "According to the document..." or 
  "The file shows..."
- If asked about a file, summarize or answer based on the retrieved 
  content

--- WHEN USER ASKS ABOUT THEMSELVES ---
If the user asks "what do you know about me?", "tell me about 
myself", or similar:
- Share relevant details from "WHAT YOU REMEMBER" section
- Be organized and clear
- Group related information
- If no context exists, say: "We haven't chatted much yet, so I 
  don't know much about you. Tell me about yourself!"

--- HANDLING VAGUE QUERIES ---
For vague queries like "tell me more" or "what else":
- Use conversation context to infer what they're asking about
- Reference specific details from memory when relevant
- Ask clarifying questions if truly ambiguous

--- PERSONAL DETAILS TO REMEMBER ---
Pay special attention to:
- **Name** - Use it naturally when appropriate
- **Interests & hobbies** - Sports, activities, pastimes
- **Work/Study** - Job, major, university, projects
- **Preferences** - Favorite things
- **Goals & plans** - What they're working toward
- **Relationships** - People they mention
- **Locations** - Where they live, study, work

--- RESPONSE STYLE ---
- Be conversational and warm
- Keep responses concise unless detail is requested
- Use the user's name occasionally (not every message)
- Match the user's tone (formal vs casual)
- Never be condescending or overly explanatory

--- HANDLING CONTRADICTIONS ---
If new information contradicts old memories:
- Prioritize the NEW information (people change!)
- Don't point out the contradiction unless asked
- Update your understanding naturally

--- WHAT YOU REMEMBER ABOUT THIS USER ---
{memory_text}

--- RESPONSE INSTRUCTIONS ---
Now respond to the user's message naturally, incorporating relevant 
memories or file content when appropriate. Be helpful, personalized, 
and conversational.
"""


# ==================== WEBSOCKET HANDLER ====================


# conversation -> text
# Given a converastion id, allows for users to chat with AI with streaming
@app.websocket("/conversations/{conversation_id}/chat")
async def chat_websocket(websocket: WebSocket, conversation_id):
    await websocket.accept()  # get connection
    try:
        while True:
            user_message = await websocket.receive_text()

            memory_text = await asyncio.to_thread(retrieve_context,conversation_id, user_message)

            system_prompt = SYSTEM_PROMPT.format(memory_text=memory_text)

            ai_response = await generate_streaming_response(
                system_prompt, user_message, websocket, conversation_id)
            
            await asyncio.to_thread(store_messages,conversation_id, user_message, ai_response)

            await embed_messages(conversation_id, user_message, ai_response)
    except Exception as e:
        print(f"Exception {e}")


# voice -> text -> voice
# Given a conversation id and voice, take the user's voice, process it, and then respond appropriately with AI response in voice form
@app.websocket("/conversations/{conversation_id}/voicechat")
async def chat_websocket_voice(websocket: WebSocket, conversation_id):
    current_task = None
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_bytes()
            if current_task:
                current_task.cancel()
                
            audio_file = BytesIO(data)
            user_transcript_text =  await(transcribe_audio(audio_file))
            await websocket.send_text(
                json.dumps({"type": "transcription", "content": user_transcript_text}))
            
            memory_text = await asyncio.to_thread(retrieve_context, conversation_id, user_transcript_text)


            system_prompt = SYSTEM_PROMPT.format(memory_text=memory_text)
            
            current_task = asyncio.create_task(generate_voice_streaming_response(system_prompt, user_transcript_text, websocket, conversation_id))
    except WebSocketDisconnect:
        print("disconnected.")
    except Exception as e:
        print(f"Error: {e}")
        
        


    


# audio_file -> string
# converts the speech into the text via the stt llm, returns transcript
async def transcribe_audio(audio_file):
    transcript = await client_stt.audio.transcriptions.create(
        file=audio_file,
        model="ink-whisper",)
    return transcript.text


async def generate_streaming_response(full_system_prompt, user_message, websocket, conversation_id):
    """
    The purpose of this function is to create the "streaming" response of LLM to the user for text. 

    :param full_system_prompt: represents the system prompt (when this function is used, includes the RAG)
    :param user_message: the message that the user sent
    :param websocket: websocket connection
    """
    most_recent_messages = get_latest_messages(conversation_id)

    messages = [{"role": "system", "content": full_system_prompt}]  # full system prompt
    for msg in most_recent_messages:  # iterate through the most recent messages and append them, note they are already in form "role: "assistant", "content"
        messages.append(msg)
    messages.append({"role": "user", "content": user_message})
    # make AI response
    response = await ai_model.chat.completions.create(
        model="arcee-ai/trinity-large-preview:free",
        messages=messages,
        stream=True,)
    # build AI response
    build_response = ""
    async for chunk in response:
        token = chunk.choices[0].delta.content
        if token:
            build_response += token
            await websocket.send_text(token)
    return build_response




async def generate_voice_streaming_response(full_system_prompt, user_message, websocket, conversation_id):
    """
    The purpose of this function is to create the voice "streaming" response. 

    :param full_system_prompt: represents the system prompt (when this function is used, includes the RAG)
    :param user_message: the message that the user sent
    :param websocket: websocket connection
    :conversation_id: represents what conversation whe are in

    """
    most_recent_messages = get_latest_messages(conversation_id)
    
  
    messages = [{"role": "system", "content": full_system_prompt}]  # full system prompt

    for msg in most_recent_messages:  # iterate through the most recent messages and append them, note they are already in form "role: "assistant", "content"
        messages.append(msg)
    messages.append({"role": "user", "content": user_message})
    # make AI response
    try:
        response =  await ai_model.chat.completions.create(
        model="arcee-ai/trinity-large-preview:free",
        messages=messages,
        stream=True,)
    # build AI response
        build_response = ""
        buffer = "" 
        async for chunk in response:
            token = chunk.choices[0].delta.content
            if token:
                build_response += token
                buffer += token 
                await websocket.send_text(token)
                sentence, after = extract_sentence(buffer)
                if sentence: #if we see that we have a full sentence
                    ai_response_audio = await(asyncio.to_thread(generate_audio_bytes,sentence)) #generate audio for it 
                    await websocket.send_bytes(ai_response_audio) #send it
                    buffer = after #now make the next sentence the next buffer 
        if buffer: #if we have any remaining audio that needs to be flushed after the loop, flush it out 
            ai_response_audio = await(asyncio.to_thread(generate_audio_bytes,buffer))   
            await websocket.send_bytes(ai_response_audio)
        if build_response:
            await asyncio.to_thread(store_messages,conversation_id, user_message, build_response)
            await embed_messages(conversation_id, user_message, build_response)
        return build_response
    except asyncio.CancelledError:
        pass 
    except Exception as e:
        print(f"something went wrong: {e}")
    






def extract_sentence(buffer):
    """
    The purpose of this function is to extract the sentence and return the full sentence and what is coming after the sentence.
    """
    sentence_stoppers = ["! ", ". ", "? "]
    found_element = next((stopper for stopper in sentence_stoppers if stopper in buffer), None)
    if found_element:
        position_of_buffer = buffer.index(found_element) 
        prior_to_buffer = buffer[:position_of_buffer +1]
        after_buffer = buffer[position_of_buffer+1:]
        return prior_to_buffer, after_buffer
    else:
        return None, buffer #we have no full sentence since there is no buffer 
    
    
    
    

# text -> audio bytes
# given a full response, turns it into audio bytes
def generate_audio_bytes(full_response):
    if not full_response or not full_response.strip():
        full_response = "I didn't catch that. Could you try again?"
    chunks_of_audio = client_tts.tts.bytes(
        model_id="sonic-3-latest",
        transcript=str(full_response),
        voice={
            "mode": "id",
            "id": "f786b574-daa5-4673-aa0c-cbe3e8534c02",},
        output_format={
            "container": "wav",
            "sample_rate": 44100,
            "encoding": "pcm_s16le",},)

    sentence_audio = b""
    for chunk in chunks_of_audio:
        sentence_audio += chunk
    return sentence_audio


# ==================== CRUD ENDPOINTS ====================


# create a conversation
@app.post("/conversations")
async def create_conversation():
    try:
        response = supabase_client.table("conversations").insert({}).execute()
        created_conversation = response.data[0]
        return created_conversation
    except Exception as e:
        print(f"Exception {e}")


# delete conversation and corresponding data
@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    try:
        supabase_client.from_("messages").delete().eq(
            "conversation_id", conversation_id).execute()
        supabase_client.table("conversations").delete().eq(
            "id", conversation_id).execute()
        return {
            "status": "success",
            "message": f"Deleted conversation {conversation_id}",}
    except Exception as e:
        print(f"Error deleting conversation id: {conversation_id}")
        raise HTTPException(status_code=500, detail="Failed to delete conversation.")


# return all conversations
@app.get("/conversations")
async def get_all_conversations():
    try:
        response = (
            supabase_client.table("conversations")
            .select("*")
            .order("created_at", desc=True)
            .execute())
        return response.data
    except Exception as e:
        print(f"Error getting all conversations: {e}")
        raise HTTPException(status_code=500, detail="Failed to get all conversations.")


# retrieve messages from specific conversation
@app.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(conversation_id: str):
    try:
        response = (
            supabase_client.table("messages")
            .select("*")
            .eq("conversation_id", conversation_id)
            .order("created_at")
            .execute())
        return response.data
    except Exception as e:
        print(f"Error fetching messages: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch messages")


# endpoint for uploading a file
@app.post("/conversations/{conversation_id}/uploadfile")
async def process_file(file: UploadFile, conversation_id):

    file_location = await upload_file(file)
    print(f"Saved to: {file_location}")
    await asyncio.to_thread(extract_text_from_file, file_location, conversation_id)
    print(f"Extraction complete")
    
    return {"status": "success", "filename": file.filename}