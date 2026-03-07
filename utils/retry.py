import time
from google.genai.errors import ServerError, ClientError


def gemini_call_with_retry(client, model: str, contents, max_retries: int = 4):
    """
    Retry Gemini calls on 503 (overloaded) and 429 (rate limit).
    Exponential backoff: 5s, 10s, 20s, 40s
    """
    for attempt in range(max_retries):
        try:
            return client.models.generate_content(
                model=model,
                contents=contents
            )
        except ServerError as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                wait = 5 * (2 ** attempt)
                print(f"[Gemini] 503 overloaded — retrying in {wait}s "
                      f"(attempt {attempt + 1}/{max_retries})")
                time.sleep(wait)
            else:
                raise
        except ClientError as e:
            if "429" in str(e):
                wait = 10 * (2 ** attempt)
                print(f"[Gemini] 429 rate limit — retrying in {wait}s "
                      f"(attempt {attempt + 1}/{max_retries})")
                time.sleep(wait)
            else:
                raise
        except Exception as e:
            raise

    raise Exception(f"Gemini failed after {max_retries} retries. Try again later.")