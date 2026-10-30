import argparse
import json

from app.config import DATA_DIR, load_environment, neo4j_settings
from app.generation import answer
from app.graph_store import create_driver, ingest, load_knowledge
from app.retrieval import retrieve


def run_ingest(driver, settings, knowledge):
    ingest(driver, settings["database"], knowledge)
    print(f"Loaded {len(knowledge['concepts'])} concepts and "
          f"{len(knowledge['passages'])} evidence passages into Neo4j.")


def run_ask(driver, settings, question):
    context = retrieve(driver, settings["database"], question)
    if not context["passages"]:
        print("No supporting passages were found.")
        return

    print("Answer\n")
    print(answer(question, context["passages"]))
    print("\nGraph context")
    print("Seeds: " + (", ".join(seed["name"] for seed in context["seeds"]) or "none"))
    expanded = sorted({neighbor["name"] for neighbor in context["neighbors"]})
    print("Expanded concepts: " + (", ".join(expanded) or "none"))
    print("\nRetrieved evidence")
    for passage in context["passages"]:
        print(f"- [NASA, p. {passage['page']}] {passage['title']} "
              f"(score {passage['score']:.2f})")


def run_evaluate(driver, settings):
    questions = json.loads(
        (DATA_DIR / "questions.json").read_text(encoding="utf-8")
    )
    recalls = []
    reciprocal_ranks = []
    for item in questions:
        results = retrieve(driver, settings["database"], item["question"], top_k=3)
        ranked_ids = [passage["id"] for passage in results["passages"]]
        expected = set(item["expected_passage_ids"])
        recalls.append(len(expected & set(ranked_ids)) / len(expected))
        first_relevant = next(
            (rank for rank, passage_id in enumerate(ranked_ids, 1)
             if passage_id in expected),
            None,
        )
        reciprocal_ranks.append(1 / first_relevant if first_relevant else 0.0)

    recall_at_3 = sum(recalls) / len(recalls)
    mean_reciprocal_rank = sum(reciprocal_ranks) / len(reciprocal_ranks)
    print(f"Questions: {len(questions)}")
    print(f"Recall@3: {recall_at_3:.3f}")
    print(f"MRR: {mean_reciprocal_rank:.3f}")
    print("These metrics cover only the small hand-labelled retrieval set.")


def main():
    load_environment()
    parser = argparse.ArgumentParser(description="GraphRAG demo over NASA handbook excerpts")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("ingest", help="load the curated sample graph into Neo4j")
    ask_parser = subparsers.add_parser("ask", help="retrieve evidence and answer a question")
    ask_parser.add_argument("question")
    subparsers.add_parser("evaluate", help="measure retrieval on the sample questions")
    args = parser.parse_args()

    settings = neo4j_settings()
    knowledge = load_knowledge(DATA_DIR / "knowledge.json")
    with create_driver(settings) as driver:
        if args.command == "ingest":
            run_ingest(driver, settings, knowledge)
        elif args.command == "ask":
            run_ask(driver, settings, args.question)
        else:
            run_evaluate(driver, settings)


if __name__ == "__main__":
    main()
