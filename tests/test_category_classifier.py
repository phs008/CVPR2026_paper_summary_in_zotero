import argparse
import tempfile
import unittest
from pathlib import Path

import cvpr2026_summarize as cvpr


class HybridCategoryClassifierTests(unittest.TestCase):
    def make_args(self, threshold=0.7):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        return argparse.Namespace(
            text_dir=Path(temp_dir.name),
            category_classifier="hybrid",
            hybrid_confidence_threshold=threshold,
            model=None,
            codex=None,
        )

    def test_hybrid_uses_existing_category_metadata_without_codex(self):
        paper = {
            "index": 1,
            "title": "Already Classified Paper",
            "authors": [],
            "primary_category": "Vision, language, and reasoning",
            "secondary_categories": ["Multimodal learning"],
        }

        result = cvpr.classify_paper(paper, self.make_args())

        self.assertEqual(result["primary_category"], "Vision, language, and reasoning")
        self.assertEqual(result["secondary_categories"], ["Multimodal learning"])
        self.assertEqual(result["category_source"], "metadata")

    def test_hybrid_accepts_high_confidence_keyword_result(self):
        paper = {
            "index": 2,
            "title": "Diffusion Text-to-Image Generation and Editing",
            "authors": [],
        }

        result = cvpr.classify_paper(paper, self.make_args())

        self.assertEqual(result["primary_category"], "Image and video synthesis and generation")
        self.assertEqual(result["category_source"], "keywords")
        self.assertGreaterEqual(result["confidence"], 0.7)

    def test_hybrid_sends_low_confidence_keyword_result_to_codex(self):
        paper = {
            "index": 3,
            "title": "A Study of Unclear Visual Patterns",
            "authors": [],
        }
        original = cvpr.codex_completion

        def fake_codex_completion(model, prompt, codex_cmd=None):
            return '{"primary_category":"Datasets and evaluation","secondary_categories":[],"confidence":0.82,"reason":"Codex fallback"}'

        cvpr.codex_completion = fake_codex_completion
        self.addCleanup(lambda: setattr(cvpr, "codex_completion", original))

        result = cvpr.classify_paper(paper, self.make_args())

        self.assertEqual(result["primary_category"], "Datasets and evaluation")
        self.assertEqual(result["category_source"], "hybrid_codex")
        self.assertEqual(result["reason"], "Codex fallback")


if __name__ == "__main__":
    unittest.main()
