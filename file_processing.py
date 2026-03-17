


from fastapi import HTTPException, UploadFile
from backend.config import (
    ocr_processor, ocr_model,
    caption_processor, caption_model,
    UPLOAD_DIR
)
from backend.rag import get_conversation_collection, get_global_collection
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from PIL import Image
from pathlib import Path
import aiofiles
import uuid
import os



# ==================== FILE PROCESSING ====================
async def upload_file(file: UploadFile):
    random_uuid = uuid.uuid4()
    new_filename = f"{random_uuid}_{file.filename}"
    filename = os.path.basename(new_filename)
    file_location = Path(UPLOAD_DIR) / filename

    try:
        async with aiofiles.open(file_location, "wb") as buffer:
            contents = await file.read()
            await buffer.write(contents)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"There was an error uploading the file: {e}")
    finally:
        await file.close()

    return file_location


# extracting and processing information from file
def extract_text_from_file(file_location: Path, conversation_id):
    """
    The purpose of this function is to extract the text from a file (whether it be an image or a pdf) and then store that information in the chroma collection for RAG.
    The text could also be a caption of an image if the image does not have a lot of text/any text.

    :param file_location: represents the location of the file that was uploaded by the user. This is used to extract the text from the file and also to reference the file in the stored text in chroma for RAG.
    :type file_location: represents the location of the file.
    :param conversation_id: represents the current conversation id.
    """
    ext = file_location.suffix.lower()
    if ext == ".pdf":
        process_pdf(file_location, conversation_id)
    elif ext == ".png" or ext == ".jpg" or ext == ".jpeg":
        generated_text_from_image = process_image_with_text(file_location)

        if (len(generated_text_from_image.split()) > 3):  # simple placeholder, but the idea for now is that if there is no more than 3 words, text is not signifcant.
            store_to_both_collections_file(conversation_id, generated_text_from_image, file_location)
        else:
            generated_caption_of_image = process_image_photo(file_location)
            store_to_both_collections_file(conversation_id, generated_caption_of_image, file_location)


def process_pdf(file_location, conversation_id):
    """
    The purpose of this function is extract the text from a pdf.

    :param file_location: represents file location of file
    :param conversation_id: current conversation id
    """
    loader = PyPDFLoader(file_location)
    documents = loader.load()
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800, chunk_overlap=150, add_start_index=True)
    splits = text_splitter.split_documents(documents)
    for index, content in enumerate(splits):
        get_conversation_collection(conversation_id).add_texts(
            texts=[content.page_content],
            ids=[f"{conversation_id}_file_{index}_{uuid.uuid4()}"],
            metadatas=[
                {
                    "type": "file",
                    "filename": file_location.name,
                    "conversation_id": conversation_id,}],)
        get_global_collection().add_texts(
            texts=[f"[File: {file_location.name}] {content.page_content}"],
            ids=[f"global_file_{conversation_id}_{index}_{uuid.uuid4()}"],
            metadatas=[
                {
                    "type": "file",
                    "filename": file_location.name,
                    "conversation_id": conversation_id,}],)


def process_image_with_text(file_location):
    """
    The purpose of this function is process an image that has text to turn into text.

    :param file_location: represents the file location of file .
    """
    file_path = str(file_location)
    image = Image.open(file_path)
    image = image.convert("RGB")
    pixel_values = ocr_processor(image, return_tensors="pt").pixel_values
    generated_ids = ocr_model.generate(pixel_values)
    generated_text = ocr_processor.batch_decode(
        generated_ids, skip_special_tokens=True)[0]
    return generated_text


def process_image_photo(file_location):
    """
    The purpose of this function is process an image that has does not have a lot of text to caption it
    so that it can be refered to.

    :param file_location: represents location of file.
    """
    file_path = str(file_location)
    image = Image.open(file_path)
    image = image.convert("RGB")
    inputs = caption_processor(image, return_tensors="pt")
    generated_ids = caption_model.generate(**inputs)
    generated_text = caption_processor.batch_decode(
        generated_ids, skip_special_tokens=True)[0]
    return generated_text


def store_to_both_collections_file(conversation_id, generated_text, file_location):
    """
    The purpose of this function is to store the AI generated text and store and embed it  to this current conversation
    and store and embed to the global function.

    :param conversation_id: represents the current conversation id.
    :param generated_text: represents the text that was generated by the AI after processing the file.
    :param file_location: represents the location of the file.
    """
    get_conversation_collection(conversation_id).add_texts(
        texts=[f"[File: {file_location.name}] {generated_text}"],
        ids=[f"{conversation_id}_file_{uuid.uuid4()}"],
        metadatas=[
            {
                "type": "file",
                "filename": file_location.name,
                "conversation_id": conversation_id,}],)
    
    get_global_collection().add_texts(
        texts=[f"[File: {file_location.name}] {generated_text}"],
        ids=[f"global_file_{conversation_id}_file_{uuid.uuid4()}"],
        metadatas=[
            {
                "type": "file",
                "filename": file_location.name,
                "conversation_id": conversation_id,}],)

    