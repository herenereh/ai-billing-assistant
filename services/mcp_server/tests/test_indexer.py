import pytest

from billing_docs.indexer import GuideIndex, parse_guide, tokenize


@pytest.fixture(scope="module")
def index():
    return GuideIndex.from_file()


def test_document_id_and_name(index):
    assert index.document_id == "MOB-BILLING-2026-01"
    assert index.document_name == "Mobile_Provider_Billing_Guide.md"


def test_every_numbered_section_is_a_chunk(index):
    sections = [c.section for c in index.chunks]
    assert sections == [
        "1", "2.1", "2.2", "2.3", "3.1", "3.2", "3.3", "4.1", "4.2", "4.3", "4.4",
        "5.1", "5.2", "5.3", "6.1", "6.2", "6.3", "7.1", "7.2", "7.3",
        "8.1", "8.2", "8.3", "8.4", "9",
    ]


def test_chunk_metadata_and_clean_text(index):
    chunk = next(c for c in index.chunks if c.section == "3.2")
    assert chunk.heading == "Additional internet blocks"
    assert chunk.parent_heading == "Internet pricing"
    assert chunk.text.startswith("Each additional 10 GB block costs $10.")
    assert "**" not in chunk.text


def test_preamble_not_indexed(index):
    assert all("Fictitious teaching document" not in c.text for c in index.chunks)


def test_parse_minimal_markdown():
    doc_id, chunks = parse_guide(
        "**Document ID:** TEST-1\n\n## 1. Intro\n\nHello.\n\n## 2. Prices\n\n### 2.1 Basic\n\nTen dollars.\n"
    )
    assert doc_id == "TEST-1"
    assert [(c.section, c.heading, c.parent_heading, c.text) for c in chunks] == [
        ("1", "Intro", "Intro", "Hello."),
        ("2.1", "Basic", "Prices", "Ten dollars."),
    ]


def test_empty_guide_rejected():
    with pytest.raises(ValueError):
        GuideIndex("x.md", "X", [])


def test_tokenize_stems_and_drops_stopwords():
    assert tokenize("How much does the Payments cost?") == ["pay", "cost"]
    assert tokenize("charges charged") == ["charg", "charg"]


# --- The three required retrieval demonstrations (plus extras) ---------------

@pytest.mark.parametrize(
    "query, expected_top, expected_in_top3",
    [
        ("How much does extra internet cost?", "8.1", "3.2"),
        ("Can I pay only part of my bill?", "8.3", "5.1"),
        ("What happens if I pay late?", "6.2", "6.3"),
    ],
)
def test_required_retrieval_queries(index, query, expected_top, expected_in_top3):
    hits = index.search(query, top_k=3)
    sections = [h.chunk.section for h in hits]
    assert sections[0] == expected_top
    assert expected_in_top3 in sections


@pytest.mark.parametrize(
    "query, expected_section",
    [
        ("How do I dispute a charge?", "8.4"),
        ("Why is my bill higher this month?", "8.2"),
        ("When is my bill due?", "6.1"),
        ("Are there taxes on my bill?", "4.2"),
        ("How many free minutes do I get?", "2.1"),
    ],
)
def test_more_policy_queries(index, query, expected_section):
    assert index.search(query, top_k=1)[0].chunk.section == expected_section


def test_scores_are_descending(index):
    scores = [h.score for h in index.search("internet cost per GB", top_k=5)]
    assert scores == sorted(scores, reverse=True)
    assert len(scores) == 5


def test_unrelated_query_returns_nothing(index):
    assert index.search("weather in izmir") == []


def test_stopword_only_query_returns_nothing(index):
    assert index.search("what is the") == []
