import json
from pathlib import Path

from neo4j import GraphDatabase


def load_knowledge(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def create_driver(settings):
    driver = GraphDatabase.driver(
        settings["uri"], auth=(settings["user"], settings["password"])
    )
    driver.verify_connectivity()
    return driver


def ingest(driver, database, knowledge):
    with driver.session(database=database) as session:
        session.run(
            "CREATE CONSTRAINT portfolio_concept_id IF NOT EXISTS "
            "FOR (n:PortfolioDemoConcept) REQUIRE n.id IS UNIQUE"
        ).consume()
        session.run(
            "CREATE CONSTRAINT portfolio_evidence_id IF NOT EXISTS "
            "FOR (n:PortfolioDemoEvidence) REQUIRE n.id IS UNIQUE"
        ).consume()
        session.run(
            "MATCH (n:PortfolioDemoConcept) DETACH DELETE n"
        ).consume()
        session.run(
            "MATCH (n:PortfolioDemoEvidence) DETACH DELETE n"
        ).consume()
        session.run(
            "UNWIND $items AS item "
            "MERGE (c:PortfolioDemoConcept {id: item.id}) "
            "SET c.name = item.name, c.aliases = item.aliases, "
            "c.description = item.description",
            items=knowledge["concepts"],
        ).consume()
        session.run(
            "UNWIND $items AS item "
            "MATCH (source:PortfolioDemoConcept {id: item.source}) "
            "MATCH (target:PortfolioDemoConcept {id: item.target}) "
            "MERGE (source)-[r:PORTFOLIO_RELATION {kind: item.type}]->(target)",
            items=knowledge["relations"],
        ).consume()
        session.run(
            "UNWIND $items AS item "
            "MERGE (e:PortfolioDemoEvidence {id: item.id}) "
            "SET e.title = item.title, e.text = item.text, "
            "e.page = item.page, e.source = $source_name, e.source_url = $source_url "
            "WITH e, item "
            "UNWIND item.concept_ids AS concept_id "
            "MATCH (c:PortfolioDemoConcept {id: concept_id}) "
            "MERGE (e)-[:SUPPORTED_BY]->(c)",
            items=knowledge["passages"],
            source_name=knowledge["source"]["name"],
            source_url=knowledge["source"]["url"],
        ).consume()


def find_seed_concepts(driver, database, question):
    with driver.session(database=database) as session:
        result = session.run(
            "MATCH (c:PortfolioDemoConcept) "
            "WHERE any(alias IN c.aliases "
            "WHERE toLower($question) CONTAINS toLower(alias)) "
            "RETURN c.id AS id, c.name AS name ORDER BY c.name",
            question=question,
        )
        return [record.data() for record in result]


def find_neighbors(driver, database, seed_ids):
    if not seed_ids:
        return []
    with driver.session(database=database) as session:
        result = session.run(
            "MATCH (seed:PortfolioDemoConcept) WHERE seed.id IN $seed_ids "
            "OPTIONAL MATCH (seed)-[r:PORTFOLIO_RELATION]-(neighbor:PortfolioDemoConcept) "
            "RETURN DISTINCT neighbor.id AS id, neighbor.name AS name, "
            "r.kind AS relation ORDER BY name",
            seed_ids=seed_ids,
        )
        return [record.data() for record in result if record["id"] is not None]


def fetch_evidence(driver, database, concept_ids=None):
    with driver.session(database=database) as session:
        if concept_ids:
            result = session.run(
                "MATCH (e:PortfolioDemoEvidence)-[:SUPPORTED_BY]->(c:PortfolioDemoConcept) "
                "WHERE c.id IN $concept_ids "
                "WITH e, collect(DISTINCT c.id) AS concept_ids "
                "RETURN e.id AS id, e.title AS title, e.text AS text, "
                "e.page AS page, e.source AS source, e.source_url AS source_url, "
                "concept_ids ORDER BY e.page",
                concept_ids=concept_ids,
            )
        else:
            result = session.run(
                "MATCH (e:PortfolioDemoEvidence)-[:SUPPORTED_BY]->(c:PortfolioDemoConcept) "
                "WITH e, collect(DISTINCT c.id) AS concept_ids "
                "RETURN e.id AS id, e.title AS title, e.text AS text, "
                "e.page AS page, e.source AS source, e.source_url AS source_url, "
                "concept_ids ORDER BY e.page"
            )
        return [record.data() for record in result]
