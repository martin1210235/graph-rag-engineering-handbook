import math
import re
from collections import Counter

from app.graph_store import fetch_evidence, find_neighbors, find_seed_concepts


STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "does", "for",
    "from", "how", "in", "is", "it", "of", "on", "or", "the", "their",
    "this", "to", "what", "when", "where", "which", "who", "why", "with",
}


def tokenize(text):
    return [
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if token not in STOP_WORDS and len(token) > 1
    ]


def bm25_scores(question, passages):
    query_terms = set(tokenize(question))
    documents = [tokenize(passage["title"] + " " + passage["text"]) for passage in passages]
    if not documents or not query_terms:
        return [0.0] * len(documents)

    average_length = sum(map(len, documents)) / len(documents)
    document_frequency = Counter(
        term for document in documents for term in set(document)
    )
    scores = []
    for document in documents:
        frequencies = Counter(document)
        score = 0.0
        for term in query_terms:
            frequency = frequencies[term]
            if not frequency:
                continue
            inverse_frequency = math.log(
                1 + (len(documents) - document_frequency[term] + 0.5)
                / (document_frequency[term] + 0.5)
            )
            denominator = frequency + 1.2 * (
                0.25 + 0.75 * len(document) / max(average_length, 1)
            )
            score += inverse_frequency * frequency * 2.2 / denominator
        scores.append(score)
    return scores


def retrieve(driver, database, question, top_k=4):
    seeds = find_seed_concepts(driver, database, question)
    seed_ids = {seed["id"] for seed in seeds}
    neighbors = find_neighbors(driver, database, list(seed_ids))
    neighbor_ids = {neighbor["id"] for neighbor in neighbors}
    passages = fetch_evidence(driver, database, seed_ids | neighbor_ids)
    if not passages:
        passages = fetch_evidence(driver, database)

    scores = bm25_scores(question, passages)
    for passage, score in zip(passages, scores):
        attached = set(passage["concept_ids"])
        direct_matches = len(attached & seed_ids)
        expanded_matches = len(attached & neighbor_ids)
        passage["score"] = score + 1.5 * direct_matches + 0.4 * expanded_matches
        passage["direct_matches"] = sorted(attached & seed_ids)
        passage["expanded_matches"] = sorted(attached & neighbor_ids)

    passages.sort(key=lambda passage: (-passage["score"], passage["page"], passage["id"]))
    return {
        "seeds": seeds,
        "neighbors": neighbors,
        "passages": passages[:top_k],
    }
