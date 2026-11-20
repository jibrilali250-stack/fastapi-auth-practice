
from contextlib import asynccontextmanager
import string

from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, Field

# 1. VALIDATE USER INPUT
class TextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    batch_size: int = Field(default=3, ge=1, le=10)

# 2. PYTHON GENERATOR
def iter_words(text: str):

    for raw_word in text.lower().split():

        word = raw_word.strip(string.punctuation)

        if word:
            yield word

# 3. APPLICATION LIFECYCLE
@asynccontextmanager
async def lifespan(app: FastAPI):

    app.state.request_count = 0
    app.state.cache_hits = 0
    app.state.cache_misses = 0
    app.state.cache_resets = 0

    app.state.text_cache = {}

    print("Application starting")

    yield

    print("Application shutting down")
    print("Total requests:", app.state.request_count)

app = FastAPI(lifespan=lifespan)

# 4. PROCESS TEXT
@app.post("/analyze")
def analyze_text(data: TextRequest, request: Request):

    state = request.app.state
    state.request_count += 1

    # Collect words from the generator
    words = list(iter_words(data.text))

    if not words:
        raise HTTPException(
            status_code=400,
            detail="Please enter at least one word."
        )

    # Create a unique cache key
    cache_key = (tuple(words), data.batch_size)

    # 5. CHECK CACHE
    if cache_key in state.text_cache:

        result = state.text_cache[cache_key]

        state.cache_hits += 1
        cache_hit = True

    else:

        word_counts = {}
        batches = []
        current_batch = []

        # Iterate through every word
        for word in words:

            # Count word frequency
            word_counts[word] = (
                word_counts.get(word, 0) + 1
            )

            # Add word to current batch
            current_batch.append(word)

            if len(current_batch) == data.batch_size:

                batches.append(current_batch)
                current_batch = []

        # Save any remaining words
        if current_batch:
            batches.append(current_batch)

        result = {
            "word_counts": word_counts,
            "batches": batches,
            "total_words": len(words),
            "unique_words": len(word_counts)
        }

        # Store results
        state.text_cache[cache_key] = result

        state.cache_misses += 1
        cache_hit = False

    return {
        "normalized_words": words,
        **result,
        "cache_hit": cache_hit,
        "request_count": state.request_count
    }

# 6. TRACK STATISTICS
@app.get("/stats")
def get_stats(request: Request):

    state = request.app.state
    state.request_count += 1

    return {
        "total_requests": state.request_count,
        "cache_hits": state.cache_hits,
        "cache_misses": state.cache_misses,
        "cache_resets": state.cache_resets,
        "cached_configurations": len(state.text_cache)
    }

# 7. RESET CACHE
@app.post("/reset-cache")
def reset_cache(request: Request):

    state = request.app.state
    state.request_count += 1

    state.text_cache.clear()
    state.cache_resets += 1

    return {
        "message": "Cache cleared",
        "cache_resets": state.cache_resets
    }