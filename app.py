from fastapi import (FastAPI, UploadFile,
                     HTTPException, Depends, BackgroundTasks)
import os
import shutil
import io
from db import get_db, File, FileChunk
from sqlalchemy.orm import Session
from file_parser import FileParser
from background_tasks import TextProcessor, client
from sqlalchemy import select
from pydantic import BaseModel


app = FastAPI()


class QuestionModel(BaseModel):
    question: str


@app.get("/")
def root():
    return "Hello RAG fellow!"


@app.post("/uploadfile/")
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile, db: Session = Depends(get_db)): # noqa
    # Define allowed file extensions
    allowed_extensions = ["txt", "pdf"]

    # Check if the file extension is allowed
    file_extension = file.filename.split('.')[-1]
    if file_extension not in allowed_extensions:
        raise HTTPException(status_code=400, detail="File type not allowed")

    folder = "sources"
    try:
        # Ensure the directory exists
        os.makedirs(folder, exist_ok=True)

        # Secure way to save the file
        file_location = os.path.join(folder, file.filename)

        content_parser = FileParser(file_location)
        file_text_content = content_parser.parse()
        file_content = await file.read()  # Read file content as bytes

        with open(file_location, "wb+") as file_object:
            # Convert bytes content to a file-like object
            file_like_object = io.BytesIO(file_content)
            # Use shutil.copyfileobj for secure file writing
            shutil.copyfileobj(file_like_object, file_object)

        # save file details in the database
        new_file = File(file_name=file.filename,
                        file_content=file_text_content)
        db.add(new_file)
        db.commit()
        db.refresh(new_file)

        # Add background job for processing file content
        background_tasks.add_task(TextProcessor(db, new_file.file_id).chunk_and_embed, file_text_content) # noqa

        return {"info": "File saved", "filename": file.filename}

    except Exception as e:
        # Log the exception (add actual logging in production code)
        print(f"Error saving file: {e}")
        raise HTTPException(status_code=500, detail="Error saving file")


@app.post("/find-similar-chunks/{file_id}")
async def find_similar_chunks(file_id: int, question_data: QuestionModel,
                              db: Session = Depends(get_db)):
    try:
        question = question_data.question

        # Create embeddings for the question
        response = client.embeddings.create(input=question,
                                            model="text-embedding-ada-002")
        question_embedding = response.data[0].embedding

        # Find similar chunks in the database
        similar_chunks_query = select(FileChunk).where(FileChunk.file_id == file_id)\
            .order_by(FileChunk.embedding_vector.l2_distance(question_embedding)).limit(10) # noqa
        similar_chunks = db.scalars(similar_chunks_query).all()

        # Format the response
        formatted_response = [
            {"chunk_id": chunk.chunk_id, "chunk_text": chunk.chunk_text}
            for chunk in similar_chunks
        ]

        return formatted_response

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
