#FastAPI imports 
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI,WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

#AI imports 
from openai import OpenAI, AsyncOpenAI
from cartesia import Cartesia

from io import BytesIO
import json 

#database import 
from supabase import create_client, Client

#phone import 
from twilio.rest import Client

#for finding news 
import requests
from datetime import datetime, timedelta

#prayer times 
import aladhan


from dotenv import load_dotenv
import os

import asyncio


#initialize app and set up cors 
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



load_dotenv()
openrouter_key = os.getenv("OPENROUTER_API_KEY")
stt_key = os.getenv("STT_API_KEY")
stt_base_url = os.getenv("STT_BASE_URL")
cartesia_key = os.getenv("CARTESIA_API_KEY")
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_from = os.getenv("TWILIO_FROM_NUMBER")
news_api_key = os.getenv("NEWS_API_KEY")

#calling client credentials and initialization
ACCOUNT_SID = twilio_sid
AUTH_TOKEN = twilio_token
call_client = Client(ACCOUNT_SID, AUTH_TOKEN)


#Supabase client credentials and initialization for storing messages + contacts + rag (soon)
SUPABASE_URL= supabase_url
SUPABASE_KEY= supabase_key
supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)





#AI clients  

#orchestrates and figures out what tool to delegate to + returns a nice message at the end if we do a tool call 
agent_delegator = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key= openrouter_key
)


#text to speech AI  
client_tts = Cartesia(api_key=cartesia_key)

#speech to text AI 
client_stt = OpenAI(
    api_key=cartesia_key, 
    base_url=stt_base_url
)




app.mount("/audio", StaticFiles(directory="audio_files"), name="audio") #for playing  audio 
app.mount("/static", StaticFiles(directory="static"), name="static") #so that things in static can acess this API 





abdullah_variations = [
    "Abdullah", "Abdulla", "Abdulah", "Abdullahh", "Abdu", "Abd", "Abu",
    "Abdullah Ismail", "Abdullah Ismal", "Abdullah Ismael", "Abdulla Ismail",
    "Abdulah Ismail", "Abdu Ismail"
]

jauhar_variations = [
    "Jauhar", "Johar", "Jowhar", "Jawar", "Joharr", "Jau", "Jar",
    "Jauhar Ismail", "Johar Ismail", "Jowhar Ismail", "Jawar Ismail",
    "Jauhar Ismal", "Jauhar Ismael", "Jawhar Ismail", "Jouhar Ismail"
]

fehmeeda_variations = [
    "Fehmeeda", "Femi", "Femeeda", "Fehmida", 
    "Fhamida", "Fhamidah", "Femi the Meta", 
    "Fahmida", "Femida", "Fahmida.Femida", "Femida Mehta", "Femi the better",
    "Famy", "Fampa",
    "Fehmeeda Mehta", "Fehmida Mehta", "Fhamida Mehta", "Fahmida Mehta",
    "Fehmeeda Meta", "Fehmeeda Metta", "Femi Mehta", "Femeeda Mehta"
]
#string -> string
#match variations to contact
def find_contact_simple(user_input):
    input_lower = user_input.lower()


    for name in abdullah_variations:
        if input_lower == name.lower():
            return "Abdullah Ismail"
    

    for name in jauhar_variations:
        if input_lower == name.lower():
            return "Jauhar Ismail"
    

    for name in fehmeeda_variations:
        if input_lower == name.lower():
            return "Fehmeeda Mehta"

    return f"{user_input} number was not found."


    
# string -> string 
#finds a number based on the name  
def find_contact(person):
    canonical_name = find_contact_simple(person)
    if  "not found" in canonical_name:
        return f"{person} number was not found."

    try:
        response = supabase_client.table("contacts").select("number").ilike("name", f"%{canonical_name}%").single().execute()
        return response.data["number"]  
    except:
        return f"{canonical_name} number was not found."
   

#string -> string
#given a name, calls the person
def call_person(person):
    person_number = find_contact(person)
    try: 
        call = call_client.calls.create(
        url="http://demo.twilio.com/docs/voice.xml",
        to=person_number,
        from_=twilio_from,
        )
        return f"succesfully called {person_number}"
    except:
        return f"unable to call {person_number}"
    


# () -> string
#returns the latest news in Pakistan 
def find_pakistan_news():
    url = (f'https://newsapi.org/v2/everything?'
       f'q=Pakistan News&'
       f'language=en&'
       f'from={datetime.now() - timedelta(days=7)}&'
       f'sortBy=popularity&'
       f'apiKey={news_api_key}')
    response = requests.get(url)
    articles = response.json()["articles"]
    news_list = []
    for article in articles[0:5]:  
       news_list.append(f"{article['title']}: {article['description']}")
    if (len(news_list) == 0):
        return "unable to fetch news."
    else:
        return "\n".join(news_list)
    




#get the last ai message 
def get_last_ai_message():
    try:
        response = (
            supabase_client
            .table("notes")
            .select("*")
            .eq("username", "AI")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if response.data and len(response.data) > 0:
            return response.data[0]["message"]
        else:
            return "I don't have anything to repeat yet."
    except:
        return "I'm sorry, I couldn't retrieve the last message."
    



def get_last_user_message():
    try:
        response = (
            supabase_client
            .table("notes")
            .select("*")
            .neq("username", "AI")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if response.data and len(response.data) > 0:
            return response.data[0]["message"]
        else:
            return "I don't have anything to repeat yet."
    except:
        return "I'm sorry, I couldn't retrieve the last message."





#prayer mishearings 
fajr_mishearings = [
    "fajer",
    "fajhr",
    "fadjr",
    "fajir",
    "fajhar",
    "fudge",
    "fig",
    "fr"
]

dhuhr_mishearings = [
    "duhr",
    "dohr",
    "dhuh",
    "dhoor",
    "door",
    "do her",
    "due her",
    "zoor",
    "zuhur",
    "zhoor",
    "dhur"
]

asr_mishearings = [
    "asir",
    "asar",
    "azr",
    "usher",
    "azur",
    "assure"
]

maghrib_mishearings = [
    "magrib",
    "maghreb",
    "mag grip",
    "mag rib",
    "mag reb",
    "mag grab"
]

isha_mishearings = [
    "ishaa",
    "esha",
    "i she",
    "ish",
    "eye-sha"
]
      
#load in the prayer times 
# () -> list of dictionaries 
def load_prayers():
    location = aladhan.Coordinates(42.2913, -71.71)
    client = aladhan.Client(location)
    adhans = client.get_today_times()
    prayer_entry = []
    for adhan in adhans:
        prayer_entry.append(f"Prayer: {adhan.get_en_name()}, Time: {adhan.readable_timing()}")
    return prayer_entry


#string -> string
def get_prayer_time(prayer_name):
    prayers_list = load_prayers()
    for entry in prayers_list:
        if prayer_name.lower() in entry.lower(): 
            return entry
    for entry in fajr_mishearings:
        if prayer_name.lower() in entry.lower():
            return(prayers_list[0])
    for entry in dhuhr_mishearings:
        if prayer_name.lower() in entry.lower():
            return(prayers_list[1])
    for entry in asr_mishearings:
        if prayer_name.lower() in entry.lower():
            return (prayers_list[2])
    for entry in maghrib_mishearings:
        if prayer_name.lower() in entry.lower():
            return (prayers_list[3])
    for entry in isha_mishearings:
        if prayer_name.lower() in entry.lower():
            return (prayers_list[4])
    else:
        return ("unable to find prayer")









#represents all the various functions that agent_delegator can call out to 
tools = [
    {
        "type": "function",
        "function": {
            "name": "find_contact",
            "description": "Search the contact database for a family member's phone number by name. Returns the phone number if found, or an error message if the contact doesn't exist. "
                           "Handles partial names - 'Abdullah' matches 'Abdullah Ismail', 'Jauhar' matches 'Jauhar Ismail', 'Fehmeeda' matches 'Fehmeeda Mehta'. "
                           "Use this when the user asks for someone's number or wants to know contact information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "person": {
                        "type": "string",
                        "description": "Name of the family member to look up (can be first name or full name)"
                    }
                },
                "required": ["person"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "call_person",
            "description": "Initiate a phone call to a family member using Twilio. "
                           "This function will look up the contact's number and place the call. Use this when the user wants to call someone by name. "
                           "The call will be made from the Twilio number to the contact's verified number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "person": {
                        "type": "string",
                        "description": "Name of the person to call (first name or full name)"
                    }
                },
                "required": ["person"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_pakistan_news",
            "description": "Find the latest news in Pakistan. "
                           "Use this when the user wants to hear about the news going on in Pakistan. The function retrieves the latest Pakistan news using a news API.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
     {
        "type": "function",
        "function": {
            "name": "get_prayer_time",
            "description": "Given a prayer name, find out what time that prayer is. "
                           "Use this when the user asks for what time a prayer is. The function will use a library to find the corresponding prayer time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prayer_name": {
                        "type": "string",
                        "description": "Name of the prayer whose time we are looking for."
                    }
                },
                "required": ["prayer_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_last_ai_message",
            "description": "Returns the last message that the AI sent. "
                           "Use this when the user says 'repeat that' or 'say that again'.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_last_user_message",
            "description": "Returns the last message that the user sent. "
                           "Use this when the user says 'what did I just say?' or 'repeat what I said'.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]


#prompting the LLM to meet the specifications of being a voice assistant to my grandma. 
system_prompt = """
You are an intelligent, helpful, and highly reliable voice assistant for an elderly Urdu-speaking grandmother. She frequently mixes Urdu and English in a single sentence (code-switching). 
Your job is to understand her **intent**, handle mispronunciations and mishearings, and respond appropriately using available tools when necessary.  

--- URDU PHRASES & THEIR INTENT ---
- "ko" = to (e.g., "Abdullah ko call karo" → "call Abdullah")
- "karo" = do it / make it happen
- "sunao" = tell me / let me hear
- "batao" = tell me / inform me
- "ka" / "ki" = of / 's (possessive, e.g., "Abdullah ka number" → "Abdullah's number")
- "kya hai" = what is
- "dikhao" = show me
- "waqt" = time (e.g., "Fajr ka waqt" → "Fajr prayer time")
- "namaz" = prayer  

Always interpret **intent**, not literal words, ignoring filler words, mispronunciations, or code-switching artifacts.  

--- COMMON COMMANDS ---
- "Abdullah ko call karo" → Call Abdullah
- "Pakistan ki khabar sunao" → Give latest Pakistan news
- "Fehmeeda ka number kya hai" → What is Fehmeeda's number
- "Call karo" → Make a call
- "Number batao" → Give a number
- "Namaz ka waqt kya hai" → Give prayer time
- "Fajr ka waqt batao" → Give Fajr prayer time  

--- NAME HANDLING ---
- Map first names to full contacts:
    - "Abdullah" → "Abdullah Ismail"
    - "Jauhar" → "Jauhar Ismail"
    - "Fehmeeda" → "Fehmeeda Mehta"
- Relationship references:
    - "Bete ko" / "my son" → Abdullah or Jauhar (determine from context)
    - "Beti ko" / "my daughter" → Fehmeeda
- If multiple possible matches exist, **ask politely for clarification**  

--- AMBIGUOUS COMMANDS ---
- Use **recent conversation context** to infer ambiguous pronouns: "call him", "usko call karo", "he/she"  
- If intent cannot be determined confidently, respond politely with a clarification question:  
  Example: "Which son would you like me to call, Abdullah or Jauhar?"  

--- TONE & STYLE ---
- Be warm, patient, and respectful
- Keep sentences **short, simple, and easy to read**
- Avoid long explanations; be concise
- Speak naturally, like a **helpful grandchild**
- If a tool fails, politely apologize and suggest alternatives  

--- TOOL USAGE ---
1. **Find Contact**
   - Purpose: Look up a family member's phone number
   - Input: `person` (string)
   - Notes: Handles partial names and first names. Return a clear English sentence with the number.
   - Example: "Abdullah" → "Abdullah's number is +1-555-123-4567"
2. **Call Person**
   - Purpose: Place a call using Twilio
   - Input: `person` (string)
   - Notes: Look up contact first, then call. Only use if user explicitly asks to call.
3. **Find Pakistan News**
   - Purpose: Return latest Pakistan news headlines
   - Input: none
   - Notes: Only use when user asks for news. Return top 5 headlines as concise English sentences.
4. **Get Prayer Time**
   - Purpose: Return prayer time
   - Input: `prayer_name` (string)
   - Notes:
     - Match **common mishearings and mispronunciations**:
       - Fajr: fajer, fajhr, fadjr, fajir, fajhar, fudge, fig, fr
       - Dhuhr: duhr, dohr, dhuh, dhoor, door, do her, due her, zoor, zuhur, zhoor, dhur
       - Asr: asir, asar, azr, usher, azur, assure
       - Maghrib: magrib, maghreb, mag grip, mag rib, mag reb, mag grab
       - Isha: isha, ishah, esha, i she, ish, eye-sha
     - Always return a **clear English sentence**: "The Fajr prayer is at 5:10 AM"
     - If multiple prayers are mentioned or misheard, **return each prayer time in order**
     - If unsure which prayer, ask politely for clarification

--- MULTI-INTENT HANDLING ---
- Detect multiple requests in a single sentence
- Handle each intent sequentially
- Return **clear, separate responses** for each intent
- Examples:
  - User: "Abdullah ko call karo aur Fajr ka waqt batao"
  - Assistant: "I'm calling Abdullah now. The Fajr prayer is at 5:10 AM."

--- ERROR HANDLING ---
- If a tool fails (API, database, or Twilio), respond politely with alternatives:
  Example: "I'm sorry, I couldn't retrieve that information right now. Would you like me to try again later?"  
- If input is not understood, ask politely:  
  Example: "I'm not sure what you mean. Could you say that again?"

--- LANGUAGE INSTRUCTIONS ---
- **Always reply in English**
- Understand Urdu input, including Roman Urdu or code-switched sentences
- Never reply in Urdu script or Roman Urdu  

--- EXAMPLES ---
User: "Abdullah ko call karo"  
You: "I'm calling Abdullah now"  

User: "Fajr ka waqt batao"  
You: "The Fajr prayer is at 5:10 AM"  

User: "Mag grip ka waqt kya hai?"  
You: "The Maghrib prayer is at 6:45 PM"  

User: "Call my son"  
You: "Which son would you like me to call, Abdullah or Jauhar?"  

User: "Pak news sunao"  
You: "Here are the latest headlines from Pakistan: ..."  

User: "Abdullah ko call karo aur Dhuhr ka waqt batao"  
You: "I'm calling Abdullah now. The Dhuhr prayer is at 12:30 PM"
"""


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    state = {"is_responding": False}
    current_task = None 
    
    await websocket.accept() #accept connection 
    try:
        while True: #receive the bytes and store into a "file-like object"
            data = await websocket.receive_bytes()
            state["is_responding"] = False 
            if current_task:
                current_task.cancel()
            audio_file = BytesIO(data)
            transcript_text = await asyncio.to_thread(transcribe_audio, audio_file) #transcribe "file-like object", needed to make into thread since transcrible_audio is syncrhonous (blocking)
            await websocket.send_text(json.dumps({ #send what  the user had said 
                "type": "transcription",
                "text": transcript_text}))
            state["is_responding"] = True
            current_task = asyncio.create_task(handle_tool_call(transcript_text, websocket, state)) #we made this create_task because handle_tool_call is async + Run this coroutine concurrently in the background, don’t block the current loop
            
            
    except WebSocketDisconnect:
        print("disconnected.")
    except Exception as e:
        print(f"Error: {e}")
            
        
        





# audio_file -> string 
# converts the speech into the text via the stt llm, returns transcript 
def transcribe_audio(audio_file):
    transcript = client_stt.audio.transcriptions.create(
        file=audio_file,
        model="ink-whisper",
    )
    return transcript.text

async def handle_tool_call(transcript_text, websocket: WebSocket, state):
    messages=[{"role": "system", "content": system_prompt},{"role": "user", "content": transcript_text}]
    
    response = await agent_delegator.chat.completions.create(
        model="nvidia/nemotron-3-nano-30b-a3b:free",
        messages=messages,tools=tools,stream=False)
    tool_called = None 
    
    if response.choices[0].message.tool_calls:
        function_name = response.choices[0].message.tool_calls[0].function.name
        function_args = json.loads(response.choices[0].message.tool_calls[0].function.arguments)
        tool_called = function_name
        await stream_ack_text_and_audio(function_name, function_args, websocket, state)
        tool_result = execute_tool(function_name, function_args)
        messages.append(response.choices[0].message)
        messages.append({"tool_call_id": response.choices[0].message.tool_calls[0].id,
                         "role": "tool",
                         "name": function_name,
                         "content": str(tool_result)})
        ai_response = await stream_response_text_and_audio(messages, websocket, state)
    else:
        ai_response = await stream_response_text_and_audio(messages, websocket, state)
    await websocket.send_text(json.dumps({"type": "done"}))
    save_messages("user", transcript_text, ai_response, None, tool_called) 
    return ai_response, tool_called

         
        
        
        
        
        
        
        
        
        
        
        
async def stream_ack_text_and_audio(function_name, function_args, websocket, state):
    ack_prompt = '''You are a brief voice assistant. Generate ONE short sentence acknowledging you are about to perform the requested action. 
        Be warm and natural. Nothing more than one sentence.'''
    ack_messages = [
    {"role": "system", "content": ack_prompt},
    {"role": "user", "content": f"Tool being called: {function_name}, Args: {function_args}"}]
    ack_response = await agent_delegator.chat.completions.create(
        model="nvidia/nemotron-3-nano-30b-a3b:free",
        messages=ack_messages,
        stream=True)
    
    await stream_text_and_audio(ack_response, websocket, state)
    
    
    
           
        
    
def execute_tool(function_name, function_args):
    if function_name == "find_contact":
        result = find_contact(function_args.get("person", ""))
    elif function_name == "call_person":
        result = call_person(function_args.get("person", ""))
    elif function_name == "find_pakistan_news":
        result = find_pakistan_news()
    elif function_name == "get_last_ai_message":
        result = get_last_ai_message()
    elif function_name == "get_prayer_time":
        result = get_prayer_time(function_args.get("prayer_name", ""))
    elif function_name == "get_last_user_message":
        result = get_last_user_message()
    else:
        result = "Tool not found"
    return result 
        
        
async def stream_response_text_and_audio(messages, websocket,state):
    final_response = await agent_delegator.chat.completions.create(
        model="nvidia/nemotron-3-nano-30b-a3b:free",
        messages=messages,
        stream=True
    )
    return await stream_text_and_audio(final_response, websocket, state)





async def stream_text_and_audio(llm_response, websocket, state):
    build_response = ""
    buffer = "" 
    async for chunk in llm_response:
        if not state["is_responding"]:
            break
        token = chunk.choices[0].delta.content
        if token:
            build_response += token
            buffer += token 
            await websocket.send_text(json.dumps({"type": "token", "text": token})) #building up the text token by token 
            
            '''bottom part down here is for the voice '''
            sentence, after = extract_sentence(buffer)
            if sentence: #if we see that we have a full sentence
                ai_response_audio = await asyncio.to_thread(generate_audio_bytes, sentence) #generate audio for it 
                await websocket.send_bytes(ai_response_audio)
                buffer = after #now make the next sentence the next buffer 
    if buffer: #if we have any remaining audio that needs to be flushed after the loop, flush it out 
        ai_response_audio = await asyncio.to_thread(generate_audio_bytes, buffer)
        await websocket.send_bytes(ai_response_audio)
    return build_response
    
    
    
      
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
def generate_audio_bytes(response):
    if not response or not response.strip():
        response = "I didn't catch that. Could you try again?"
    chunks_of_audio = client_tts.tts.bytes(
        model_id="sonic-3-latest",
        transcript=str(response),
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





#saves the username, user message, ai message, and audio file name to the data base
def save_messages(username, user_message, ai_message, audio_file, tool_called=None):
    user_data_to_insert = {"username": username,"message" :user_message}
    ai_data_to_insert = {"username": "AI", "message": ai_message, "audio_file": audio_file, "tool_called": tool_called}      
    data_to_insert = []
    data_to_insert.append(user_data_to_insert)
    data_to_insert.append(ai_data_to_insert)
    try:
        #insert user message to database 
        message_response = (
            supabase_client.table("notes")
            .insert(data_to_insert)
            .execute()
            
        )

        print("message inserted successfully:", message_response.data)
    except Exception as e:
        print("An error occurred:", e)






#get the full message log 
@app.get("/getmessagelog/")
def get_messages():
    response = supabase_client.table("notes").select("*").execute()
    all_data = response.data
    return all_data














'''

def chunk_conversation(chunk_size):
    accumulated_string = ""
    accumulated_chunks = []
    recent_messages = supabase_client.table("notes").select("*").order("created_at", desc=True).limit(20).execute()
    messages_list = recent_messages.data 
    
    for i in range(0, len(messages_list), chunk_size):
        chunk = messages_list[i:i+chunk_size] #get a list of dictionaries
        for msg_dict in chunk: 
           accumulated_string += msg_dict['message'] + " " 
        accumulated_chunks.append(accumulated_string)
        accumulated_string = ""
    return accumulated_chunks


def process_chunks(list_of_chunks):
    embedding_data_to_insert = []

    for i in range(len(list_of_chunks)):
        embedding = model.encode(list_of_chunks[i])
        new_dict = {
        'conversation_chunk': list_of_chunks[i],
        'embedding':  embedding.tolist()
    }
        embedding_data_to_insert.append(new_dict)
    supabase_client.table("memory_embeddings").insert(embedding_data_to_insert).execute()


print("Building memories from past conversations...")
chunks = chunk_conversation(5)
process_chunks(chunks)
print(f"Loaded {len(chunks)} memory chunks into database!")

'''