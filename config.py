from supabase import create_client
from openai import AsyncOpenAI
from langchain_huggingface import HuggingFaceEmbeddings
from transformers import (
    BlipProcessor,
    BlipForConditionalGeneration,
)
from cartesia import Cartesia
from dotenv import load_dotenv
import os

load_dotenv()

# ==================== ENV VARS ====================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")
STT_TTS_KEY = os.getenv("STT_TTS_KEY")

# ==================== CONSTANTS ====================
CONV_RETRIEVAL_COUNT = 5
GLOBAL_RETRIEVAL_COUNT = 3
CHUNK_FREQUENCY = 8
UPLOAD_DIR = "uploaded_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ==================== CLIENTS ====================
supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
ai_model = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_KEY)
client_tts = Cartesia(api_key=STT_TTS_KEY)
client_stt = AsyncOpenAI(api_key=STT_TTS_KEY, base_url="https://api.cartesia.ai")

# ==================== MODELS ====================
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")


caption_processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-large")
caption_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-large")