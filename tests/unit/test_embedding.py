from app.services.embedding.embedder import embed_batch, embed_one


def test_embedding_is_deterministic():
    v1 = embed_one("remote work policy")
    v2 = embed_one("remote work policy")
    assert v1 == v2


def test_embedding_batch_matches_individual():
    texts = ["alpha document", "beta document", "gamma document"]
    batch_vectors = embed_batch(texts)
    individual_vectors = [embed_one(t) for t in texts]
    assert batch_vectors == individual_vectors


def test_different_text_produces_different_vector():
    v1 = embed_one("expense reimbursement policy")
    v2 = embed_one("parental leave policy")
    assert v1 != v2
