from sentence_transformers import SentenceTransformer
from supabase import create_client, Client
import numpy as np

SUPABASE_URL= "https://hkyfmotuulvpycjibbvg.supabase.co"
SUPABASE_KEY= "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhreWZtb3R1dWx2cHljamliYnZnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njg4Mzg5NDYsImV4cCI6MjA4NDQxNDk0Nn0.1nW5UN5H2-Jt3LMR2oPGVfYBBR8Rt_ciSH9f9GyoNpk"
supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)



model = SentenceTransformer("all-MiniLM-L6-v2")

query = "What's the weather like?"

query_embedding = model.encode([query])  
query_embedding_list = query_embedding[0].tolist() 

sentences = [
    "The weather is lovely today.",
    "It's so sunny outside!",
    "He drove to the stadium.",
]

embeddings = model.encode(sentences)
print(embeddings.shape)

similarities = model.similarity(embeddings, embeddings)
print(similarities)

embedding_data_to_insert = [
    {
        "conversation_chunk": sentences[0],
        "embedding": embeddings[0].tolist()
    },
    {
        "conversation_chunk": sentences[1],
        "embedding": embeddings[1].tolist()
    },
    {
        "conversation_chunk": sentences[2],
        "embedding": embeddings[2].tolist()
    }
]
print(embedding_data_to_insert)

send_data = supabase_client.table("memory_embeddings").insert(embedding_data_to_insert).execute()

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