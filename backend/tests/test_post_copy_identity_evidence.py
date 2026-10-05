"""Publishing-role evidence: local responses only, no model requests.

The public interview response below introduced a former-CEO role absent from
the original subtitle cues. The guard is deliberately finite, not a fact checker.
"""

import unittest

import pytest

from backend.services.studio import post_copy

pytestmark = pytest.mark.stdlib_only

PUBLIC_CASE = {
    "post": {
        "title": "我们曾做了太多产品，错了",
        "description": "OpenAI前CEO承认：浏览器、Sora等都是‘支线任务’，真正该死磕的只有一件事——让AI更智能。你觉得什么是AI最该专注的核心能力？",
        "tags": ["Sora"],
    },
    "lines": [
        ">> I I think we were trying to do too much on the product side. Uh and so there was",
        "like you know we and these were all things that were actually very good things to do. They were "
        "just not as good",
        "as the most important thing to do which was sort of push on the general capability of of the "
        "intelligence. Uh so",
        "we were doing things like a browser and Sora and we now have a very relentless focus on being "
        "this intelligent service",
        "to people and I think our models are they have gotten to be the best in the world and they will "
        "get much much better",
        "over the coming months and people are really doing remarkable things but that is what we should "
        "have been focused on",
        "and I should have been holding everybody to this is the one thing we'll not worry about these "
        "sort of side quests more",
    ],
    "title_hint": "我们曾做太多产品，错了应专注智能服务",
}


class CopyRegression(unittest.TestCase):
    def build(
        self,
        description,
        lines,
        *,
        title_hint="Product focus",
        source="",
        post_title="Product focus",
        platforms=None,
    ):
        platforms = platforms or ["original"]
        calls = []

        def call(prompt, payload):
            calls.append(payload)
            return {
                "posts": {
                    p: {
                        "title": post_title,
                        "description": description,
                        "tags": ["Sora", "invented"],
                    }
                    for p in platforms
                }
            }

        result = post_copy.build_posts(
            title_hint, lines, platforms, source=source, call=call
        )
        self.assertEqual(len(calls), 1, "Role rejection must not call the model again")
        self.assertEqual(result[platforms[0]]["title"], post_title)
        return result[platforms[0]]

    def test_actual_public_native_description_without_role_evidence(self):
        post = self.build(
            PUBLIC_CASE["post"]["description"],
            PUBLIC_CASE["lines"],
            title_hint=PUBLIC_CASE["title_hint"],
            post_title=PUBLIC_CASE["post"]["title"],
        )
        self.assertEqual(post["description"], "")
        self.assertEqual(post["tags"], ["Sora"])

    def test_generic_company_no_specific_person_hardcoded(self):
        self.assertEqual(
            self.build(
                "Acme former CEO says focus on intelligence.",
                ["We should focus on intelligence."],
            )["description"],
            "",
        )

    def test_generated_title_cannot_supply_role_evidence(self):
        self.assertEqual(
            self.build(
                "Former CEO shares product focus.",
                ["Focus on one product."],
                title_hint="Former CEO interview",
            )["description"],
            "",
        )

    def test_known_channel_cannot_supply_role_evidence(self):
        self.assertEqual(
            self.build(
                "前CEO反思产品方向。",
                ["Focus on one product."],
                source="Known Interview Channel",
            )["description"],
            "",
        )

    def test_role_mentioned_without_former_cannot_support_former_claim(self):
        self.assertEqual(
            self.build("前CEO谈产品。", ["I am the CEO."])["description"], ""
        )

    def test_supported_former_translated_role_kept(self):
        description = "前首席执行官谈产品。"
        self.assertEqual(
            self.build(
                description, ["A former chief executive officer talks about products."]
            )["description"],
            description,
        )

    def test_former_only_source_does_not_support_unqualified_role(self):
        self.assertEqual(
            self.build("CEO谈产品。", ["I am a former CEO."])["description"], ""
        )

    def test_supported_current_translated_role_kept(self):
        description = "首席执行官谈产品取舍。"
        self.assertEqual(
            self.build(
                description, ["Our chief executive officer talks about product focus."]
            )["description"],
            description,
        )

    def test_normal_description_and_tags_preserved(self):
        description = "浏览器和 Sora 都很好，但应该先聚焦智能能力。"
        post = self.build(description, PUBLIC_CASE["lines"])
        self.assertEqual(post["description"], description)
        self.assertEqual(post["tags"], ["Sora"])

    def test_nfkc_acronym_normalization(self):
        self.assertEqual(
            self.build("前ＣＥＯ谈产品。", ["Only product focus is discussed."])[
                "description"
            ],
            "",
        )
        self.assertEqual(
            self.build("ＣＥＯ谈产品。", ["Our CEO talks about products."])[
                "description"
            ],
            "ＣＥＯ谈产品。",
        )

    def test_unrelated_word_not_role(self):
        description = "Archaeology and ocean science are fascinating."
        self.assertEqual(
            self.build(description, ["Science is fascinating."])["description"],
            description,
        )

    def test_acronym_cto_cfo_coo_missing_evidence(self):
        for role in ("CTO", "CFO", "COO"):
            with self.subTest(role=role):
                self.assertEqual(
                    self.build(f"Former {role} shares lessons.", ["Product lessons."])[
                        "description"
                    ],
                    "",
                )
                self.assertEqual(
                    self.build(
                        f"{role} shares lessons.", [f"Our {role} shares lessons."]
                    )["description"],
                    f"{role} shares lessons.",
                )

    def test_one_call_multi_platform_preserves_title(self):
        calls = []

        def call(prompt, payload):
            calls.append(payload)
            return {
                "posts": {
                    p: {
                        "title": "Product focus",
                        "description": "Former CEO says focus.",
                        "tags": ["Sora"],
                    }
                    for p in payload["platforms"]
                }
            }

        posts = post_copy.build_posts(
            "Focus",
            ["Focus on intelligence and Sora."],
            list(post_copy.RULES),
            call=call,
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(posts), 8)
        self.assertTrue(
            all(
                p["description"] == "" and p["title"] == "Product focus"
                for p in posts.values()
            )
        )

    def test_existing_english_title_retry_kept(self):
        calls = []

        def call(prompt, payload):
            calls.append(payload)
            return {
                "posts": {
                    "tiktok": {
                        "title": "中文标题" if len(calls) == 1 else "Product focus",
                        "description": "One product at a time.",
                        "tags": [],
                    }
                }
            }

        result = post_copy.build_posts(
            "标题", ["One product at a time."], ["tiktok"], call=call
        )
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["tiktok"]["description"], "One product at a time.")

    def test_existing_model_error_fallback_kept(self):
        calls = []

        def call(prompt, payload):
            calls.append(payload)
            raise ValueError("local fixture")

        result = post_copy.build_posts(
            "Known title", ["source text"], ["original"], call=call
        )
        self.assertEqual(len(calls), 2)
        self.assertEqual(
            result["original"], {"title": "Known title", "description": "", "tags": []}
        )

    def test_documented_non_role_claim_is_outside_guard(self):
        description = "Revenue doubled last year."
        self.assertEqual(
            self.build(description, ["We discuss our products."])["description"],
            description,
        )


ALIASES = {
    "zh": ("首席执行官", "前"),
    "en": ("chief executive officer", "former "),
    "ja": ("最高経営責任者", "元"),
    "ko": ("최고경영자", "전 "),
    "es": ("director ejecutivo", "antiguo "),
    "pt": ("diretor executivo", "antigo "),
    "ru": ("генеральный директор", "бывший "),
    "fr": ("directeur général", "ancien "),
}


def locale_case(role, former, mode):
    def test(self):
        description = (
            former + role + " / products."
            if mode == "former"
            else role + " / products."
        )
        lines = {
            "unsupported": ["Only products are discussed."],
            "supported": ["The CEO discusses products."],
            "former": ["A former CEO discusses products."],
        }[mode]
        expected = "" if mode == "unsupported" else description
        self.assertEqual(self.build(description, lines)["description"], expected)

    return test


for locale, (role, former) in ALIASES.items():
    for mode in ("unsupported", "supported", "former"):
        setattr(
            CopyRegression,
            f"test_locale_{locale}_{mode}",
            locale_case(role, former, mode),
        )


if __name__ == "__main__":
    unittest.main()
