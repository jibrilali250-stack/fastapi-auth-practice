
from contextlib import asynccontextmanager
import string

from fastapi import FastAPI, Request
from pydantic import BaseModel, Field

# 1. Define the request data
class TextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    batch_size: int = Field(default=3, ge=1, le=10)

# 2. Generator: produce words one at a time
def iter_words(text):
    for raw_word in text.lower().split():
        word = raw_word.strip(string.punctuation)
        if word:
            yield word

# 3. Generator: produce batches one at a time
def iter_batches(words, batch_size):
    current_batch = []

    for word in words:
        current_batch.append(word)

        if len(current_batch) == batch_size:
            yield current_batch
            current_batch = []

    if current_batch:
        yield current_batch

# 4. Application lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.request_count = 0
    app.state.cache_hits = 0
    app.state.cache_misses = 0
    app.state.batches_generated = 0
    app.state.cache = {}

    print("Day 12 application starting")

    yield

    print("Application shutting down")
    print("Total requests:", app.state.request_count)

app = FastAPI(lifespan=lifespan)

# 5. Analyze text
@app.post("/analyze")
def analyze(data: TextRequest, request: Request):
    state = request.app.state
    state.request_count += 1

    words = list(iter_words(data.text))

    if not words:
        return {"message": "Please enter some words."}

    cache_key = (tuple(words), data.batch_size)

    if cache_key in state.cache:
        result = state.cache[cache_key]
        state.cache_hits += 1
        cache_hit = True

    else:
        batches = []

        for batch in iter_batches(words, data.batch_size):
            batches.append(batch)
            state.batches_generated += 1

        result = {
            "batches": batches,
            "total_words": len(words),
            "total_batches": len(batches)
        }

        state.cache[cache_key] = result
        state.cache_misses += 1
        cache_hit = False

    return {
        "normalized_words": words,
        **result,
        "cache_hit": cache_hit,
        "request_count": state.request_count
    }

# 6. Tracking endpoint
@app.get("/stats")
def stats(request: Request):
    state = request.app.state
    state.request_count += 1

    return {
        "total_requests": state.request_count,
        "cache_hits": state.cache_hits,
        "cache_misses": state.cache_misses,
        "batches_generated": state.batches_generated,
        "cached_configurations": len(state.cache)
    }