from backend.config import (
    ai_model, embeddings, supabase_client,
    CONV_RETRIEVAL_COUNT, GLOBAL_RETRIEVAL_COUNT, 
    CHUNK_FREQUENCY
)
from langchain_community.vectorstores import Chroma
import uuid
import asyncio

# ==================== COLLECTION CACHE ====================
global_collection = None
conversation_collections = {}
# return full conversation given an id for chroma side (not supabase), uses caching 
def get_conversation_collection(conversation_id):
    if conversation_id not in conversation_collections:
        conversation_collections[conversation_id] = Chroma(
            persist_directory="./chroma_db",
            embedding_function=embeddings,
            collection_name=f"conv_{conversation_id}",)
    return conversation_collections[conversation_id]


# get full collection of all conversations, uses caching 
def get_global_collection():
    global global_collection
    if not global_collection:
        global_collection = Chroma(
            persist_directory="./chroma_db",
            embedding_function=embeddings,
            collection_name="user_123_global",)
    return global_collection



# ==================== RETRIEVAL ====================


def retrieve_context(conversation_id, query):
    """
    Retrieves relevant context from conversation and global collections using filtered metadata queries.
    """
    conv = get_conversation_collection(conversation_id)
    glob = get_global_collection()
    exclude_current = {"conversation_id": {"$ne": conversation_id}}

    same_conversation_msgs = ""
    for res in safe_search(conv, query, k=CONV_RETRIEVAL_COUNT, filter={"type": "message"}):
        
        same_conversation_msgs += res.page_content + "\n"
    print(f"[1] same_conversation_msgs:\n{same_conversation_msgs}")

    same_conversation_files = ""
    for res in safe_search(conv, query, k=CONV_RETRIEVAL_COUNT, filter={"type": "file"}):
        
        same_conversation_files += res.page_content + "\n"
    print(f"[2] same_conversation_files:\n{same_conversation_files}")

    messages_in_other_conversations = ""
    for res in safe_search(glob,query,k=GLOBAL_RETRIEVAL_COUNT,filter={"$and": [{"type": "message"}, exclude_current]},):
        
        messages_in_other_conversations += res.page_content + "\n"
    print(f"[3] messages_in_other_conversations:\n{messages_in_other_conversations}")

    global_chunks = ""
    for res in safe_search(glob,query,k=GLOBAL_RETRIEVAL_COUNT,filter={"$and": [{"type": "chunk"}, exclude_current]},):
        global_chunks += res.page_content + "\n"
    print(f"[4] global_chunks:\n{global_chunks}")

    files_in_other_conversations = ""
    for res in safe_search(glob,query,k=GLOBAL_RETRIEVAL_COUNT,filter={"$and": [{"type": "file"}, exclude_current]},):
        files_in_other_conversations += res.page_content + "\n"
    print(f"[5] files_in_other_conversations:\n{files_in_other_conversations}")

    print((f"""=== CONTEXT ===\n{build_context_string(same_conversation_msgs, messages_in_other_conversations, global_chunks, 
         same_conversation_files, files_in_other_conversations)}\n=== END ==="""))

    return build_context_string(
        same_conversation_msgs,
        messages_in_other_conversations,
        global_chunks,
        same_conversation_files,
        files_in_other_conversations,)


def safe_search(collection, query, k, filter=None):
    """
    finds K number of similar results with respect to query.

    :param collection: the collection to search from
    :param query: the message that the user sent
    :param k: the number of similar results that we are looking for
    :param filter: to filter by metadata to find the type of data we want (message, file, chunk)
    """
    try:
        results = collection.similarity_search(query=query, k=k, filter=filter)
    except Exception as e:
        results = []
    return results





def build_context_string(same_msgs, other_msgs, other_chunks, same_files, other_files):
    """
    The purpose of this function is to take all the 5 rag components and merge into one.

    :param same_msgs: messaages retrieved from the same conversation.
    :param other_msgs: messages retrieved from other conversations.
    :param other_chunks: chunks of messages retrieved globally.
    :param same_files: files retrieved from the same conversation.
    :param other_files: files retrieved from other conversations.
    """
    memory_text = ""

    if same_msgs:
        memory_text += "--- This Conversation Messages ---\n" + same_msgs + "\n"

    if other_msgs:
        memory_text += "--- Past Conversations Messages ---\n" + other_msgs + "\n"

    if other_chunks:
        memory_text += "--- Past Conversation Summaries ---\n" + other_chunks + "\n"

    if same_files:
        memory_text += "--- Uploaded Documents From This Conversation ---\n" + same_files + "\n"
        

    if other_files:
        memory_text += "--- Uploaded Documents From Other Conversations ---\n" + other_files + "\n"
        

    if not memory_text:
        memory_text = "No previous conversations yet. This is a fresh start!"

    return memory_text


# ==================== RAG - STORAGE ====================


async def embed_messages(conversation_id, user_msg, ai_msg):
    """
    This function embeds all the messages and stores them into the chromadb for rag.

    :param conversation_id: current conversation id
    :param user_msg: the message the user sent
    :param ai_msg: the ai's response to user's message
    """
    conv = get_conversation_collection(conversation_id)
    glob = get_global_collection()
    
    if not is_worth_saving_message(user_msg) and not is_worth_saving_message(ai_msg):
        print("Skipping embed - trivial exchange")
        return
    
    await asyncio.to_thread(conv.add_texts,
        texts=[user_msg],
        ids=[f"{conversation_id}_user_{uuid.uuid4()}"],
        metadatas=[{"type": "message", "role": "user", "conversation_id": conversation_id}])

    await asyncio.to_thread(conv.add_texts,
        texts=[ai_msg],
        ids=[f"{conversation_id}_ai_{uuid.uuid4()}"],
        metadatas=[{"type": "message", "role": "assistant", "conversation_id": conversation_id}])

    await asyncio.to_thread(glob.add_texts,
        texts=[user_msg],
        ids=[f"global_{conversation_id}_user_{uuid.uuid4()}"],
        metadatas=[{"type": "message", "role": "user", "conversation_id": conversation_id}])

    await asyncio.to_thread(glob.add_texts,
        texts=[ai_msg],
        ids=[f"global_{conversation_id}_ai_{uuid.uuid4()}"],
        metadatas=[{"type": "message", "role": "assistant", "conversation_id": conversation_id}])
    print("Embedding this AI message:", ai_msg[:200])
    await chunk_to_global(conversation_id)
    
def is_worth_saving_message(message):
    #dummy for now, potentially another LLM call?
    cleaned = message.strip().lower().rstrip(".,!?").split()
    if len(cleaned) < 3:
        return False
    else:
        return True 
 
    
async def chunk_to_global(conversation_id):
    """
    The purpose of this function is to store a large number messages (8 or so)
    in a row and then embed all of that to provide the LLM greater context for when it
    uses RAG.

    :param conversation_id: represents the current conversation id
    """
    try:
        print(f"Checking if should chunk for conversation: {conversation_id}")
        response = (
            supabase_client.table("messages")
            .select("*", count="exact")
            .eq("conversation_id", conversation_id)
            .execute())
        print(f"Message count: {response.count}")
        print(f"Count % {CHUNK_FREQUENCY} = {response.count % CHUNK_FREQUENCY}")

        if response.count % CHUNK_FREQUENCY == 0:
            print(f"Chunking to global! Message count: {response.count}")
            get_last_messages = (
                supabase_client.table("messages")
                .select("*")
                .eq("conversation_id", conversation_id)
                .order("created_at", desc=True)
                .limit(CHUNK_FREQUENCY)
                .execute())
            group_messages = ""
            rows = get_last_messages.data
            for row in rows:
                group_messages += row["content"] + "\n"
            clean_summary = await summarize_messages(group_messages)
            get_global_collection().add_texts(
                texts=[clean_summary],
                ids=[f"chunk_{conversation_id}_{uuid.uuid4()}"],
                metadatas=[{"type": "chunk", "conversation_id": conversation_id}],)
            
            print("Successfully chunked to global!")
    except Exception as e:
        print(f"Exception in chunk_to_global: {e}")


async def summarize_messages(group_messages):
    """
    The purpose of this function is summarize the messages from chunk_to_global to produce a cleaner embedding.


    :param group_messages: the group of messages to be summarized.
    """
    response = await ai_model.chat.completions.create(
        model="nvidia/nemotron-3-nano-30b-a3b:free",
        messages=[
            {
                "role": "system",
                "content": "Summarize this conversation in a brief paragraph, focusing on key topics, facts about the user, and decisions made.",
            },
            {"role": "user", "content": group_messages},],)
    
    if response.choices[0].message.content:
        return response.choices[0].message.content
    else:
        return ""
    
    
    
    
            
        
async def is_rag_needed(message):
    print("checking rag needed?")
    try: 
        response = await ai_model.chat.completions.create(
            model="nvidia/nemotron-3-nano-30b-a3b:free",
            messages=[
            {"role": "system",
             "content": """You decide if a message needs memory retrieval to answer well.
             Reply with only "yes" or "no".
             Use "yes" ONLY if the message:
             - Explicitly asks about something from a past conversation (e.g. "what did we discuss", "do you remember")
             - References a specific file or document the user uploaded
             - Uses words like "last time", "before", "previously", "earlier", "remember"
             - Asks about specific personal details like name, job, family, location
             Use "no" for everything else including:
             - Greetings and small talk
             - General knowledge questions
             - Casual check-ins like "how are you"
             - Any question answerable without personal history"""},
            {"role": "user", "content": message}],max_tokens=1,)
        result = response.choices[0].message.content.strip().lower()
        print(result)
        return result == "yes"
    except Exception as e:
        print(f"rag check failed: {e}")
        return False

