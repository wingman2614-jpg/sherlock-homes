"""Dr. John: retrieval, providers and verification, with the network mocked."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sherlock import drjohn  # noqa: E402

PROC = Path(__file__).resolve().parent.parent / "data" / "processed"


def offline(url, body=None, timeout=10):
    raise OSError("offline")


def wiki(url, body=None, timeout=10):
    if "w/api.php" in url:
        return {"query": {"search": [{"title": "Housing in Pittsburgh"}]}}
    if "page/summary" in url:
        return {"extract": "Pittsburgh has many historic homes built before 1940.", "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/X"}}}
    raise OSError("offline")


class TestVerify(unittest.TestCase):
    EV = [{"type": "data", "title": "t", "text": "Rents rose from $1,103 to $1,333 (+21%) in 2023–2026."}]

    def test_grounded_numbers_pass(self):
        v = drjohn.verify("Rents rose 21% to $1,333 [D1] since 2023.", self.EV)
        self.assertTrue(v["ok"], v)

    def test_invented_number_flagged(self):
        v = drjohn.verify("Rents rose 35% [D1].", self.EV)
        self.assertIn("35%", v["unmatched_numbers"])

    def test_causal_language_flagged(self):
        v = drjohn.verify("New permits led to higher rents.", self.EV)
        self.assertIn("led to", v["causal_language"])


@unittest.skipUnless((PROC / "cases.json").exists(), "run python -m sherlock.build first")
class TestChat(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from sherlock.service import Store
        cls.store = Store()

    def test_offline_no_model_still_answers_with_citations(self):
        r = drjohn.chat("What's going on in Allentown?", self.store, fetch=offline)
        self.assertEqual(r["provider"], "No AI model (search results only)")
        self.assertIn("[D1]", r["answer"])
        self.assertTrue(any(s["title"].startswith("Case file") for s in r["sources"]))

    def test_web_sources_are_tagged_with_urls(self):
        r = drjohn.chat("Tell me about housing in Pittsburgh", self.store, fetch=wiki)
        web = [s for s in r["sources"] if s["type"] == "web"]
        self.assertTrue(web and web[0]["tag"].startswith("W") and web[0]["url"])

    def test_zip_lookup(self):
        r = drjohn.chat("How are rents in 15210?", self.store, fetch=offline)
        self.assertTrue(any("15210" in s["title"] for s in r["sources"]))

    def test_case_context_used(self):
        r = drjohn.chat("Why was this flagged?", self.store, case_id="case-003", fetch=offline)
        self.assertTrue(r["sources"][0]["title"].startswith("Case file open on screen"))

    def test_ollama_used_when_available_and_checked(self):
        def fake(url, body=None, timeout=10):
            if url.endswith("/api/tags"):
                return {"models": [{"name": "llama3.2:latest"}]}
            if url.endswith("/api/chat"):
                return {"message": {"content": "Permits jumped by 999% [D1], which caused rents to rise."}}
            raise OSError("offline")
        r = drjohn.chat("Allentown?", self.store, fetch=fake)
        self.assertTrue(r["provider"].startswith("Local AI via Ollama"))
        self.assertFalse(r["verification"]["ok"])
        self.assertIn("999%", r["verification"]["unmatched_numbers"])

    def test_unknown_concepts_reported(self):
        r = drjohn.chat("Where is income growing?", self.store, fetch=offline)
        self.assertTrue(any(s["title"] == "What Sherlock cannot measure" for s in r["sources"]))

    def test_empty_question(self):
        r = drjohn.chat("   ", self.store, fetch=offline)
        self.assertEqual(r["sources"], [])


if __name__ == "__main__":
    unittest.main()
