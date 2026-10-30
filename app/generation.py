import json
import os
from urllib.error import URLError
from urllib.request import Request, urlopen


def answer(question, passages):
    model = os.environ.get("OLLAMA_MODEL", "").strip()
    if not model:
        return "\n".join(
            f"- {passage['text']} [NASA, p. {passage['page']}]"
            for passage in passages
        )

    evidence = "\n\n".join(
        f"[NASA, p. {passage['page']}] {passage['text']}"
        for passage in passages
    )
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Answer using only the supplied evidence. Keep the answer concise. "
                    "Cite each factual statement with its bracketed source and page. "
                    "If the evidence does not answer the question, say so."
                ),
            },
            {
                "role": "user",
                "content": f"Question: {question}\n\nEvidence:\n{evidence}",
            },
        ],
    }
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    request = Request(
        f"{base_url}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
        return result["message"]["content"].strip()
    except (URLError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "Ollama did not return an answer. Check that it is running and the model exists."
        ) from exc
