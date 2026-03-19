import unittest

from scripts.update_news import (
    dedupe_items_by_title_url,
    is_ai_related_record,
    is_hubtoday_generic_anchor_title,
    is_hubtoday_placeholder_title,
    maybe_fix_mojibake,
    normalize_source_for_display,
    parse_feed_entries_via_xml,
)


class TopicFilterTests(unittest.TestCase):
    def test_accepts_ai_keyword(self):
        rec = {
            "site_id": "techurls",
            "site_name": "TechURLs",
            "source": "Hacker News",
            "title": "OpenAI releases new GPT model",
            "url": "https://example.com/ai",
        }
        self.assertTrue(is_ai_related_record(rec))

    def test_accepts_robotics_keyword(self):
        rec = {
            "site_id": "newsnow",
            "site_name": "NewsNow",
            "source": "technology",
            "title": "Embodied robotics gets new funding",
            "url": "https://example.com/robotics",
        }
        self.assertTrue(is_ai_related_record(rec))

    def test_accepts_beehiiv_ai_newsletters(self):
        aivalley = {
            "site_id": "aivalley",
            "site_name": "AI Valley",
            "source": "AI Valley",
            "title": "A Pentagon lawsuit",
            "url": "https://www.theaivalley.com/p/a-pentagon-lawsuit",
        }
        rundown = {
            "site_id": "therundownai",
            "site_name": "The Rundown AI",
            "source": "The Rundown AI",
            "title": "Google bets on 'vibe design' with Stitch",
            "url": "https://www.therundown.ai/p/google-bets-on-vibe-design-with-stitch",
        }
        self.assertTrue(is_ai_related_record(aivalley))
        self.assertTrue(is_ai_related_record(rundown))

    def test_rejects_noise_topic(self):
        rec = {
            "site_id": "tophub",
            "site_name": "TopHub",
            "source": "微博热搜",
            "title": "明星八卦今日热搜",
            "url": "https://example.com/noise",
        }
        self.assertFalse(is_ai_related_record(rec))

    def test_rejects_commerce_noise(self):
        rec = {
            "site_id": "tophub",
            "site_name": "TopHub",
            "source": "淘宝 ‧ 天猫 · 热销总榜",
            "title": "白象拌面任选加码 券后¥29.96",
            "url": "https://example.com/shop",
        }
        self.assertFalse(is_ai_related_record(rec))

    def test_zeli_only_24h_hot(self):
        keep = {
            "site_id": "zeli",
            "site_name": "Zeli",
            "source": "Hacker News · 24h最热",
            "title": "AI Agent for code search",
            "url": "https://example.com/a",
        }
        drop = {
            "site_id": "zeli",
            "site_name": "Zeli",
            "source": "HN New",
            "title": "AI Agent for code search",
            "url": "https://example.com/b",
        }
        self.assertTrue(is_ai_related_record(keep))
        self.assertFalse(is_ai_related_record(drop))

    def test_buzzing_source_fallback_to_host(self):
        source = normalize_source_for_display("buzzing", "Buzzing", "https://news.ycombinator.com/item?id=1")
        self.assertEqual(source, "news.ycombinator.com")

    def test_fix_mojibake(self):
        raw = "è°å¨ç¼åä»£ç "
        self.assertEqual(maybe_fix_mojibake(raw), "谁在编写代码")

    def test_parse_feed_entries_via_xml(self):
        xml = b"""<?xml version='1.0' encoding='UTF-8'?>
<rss><channel>
<item><title>A</title><link>https://x/a</link><pubDate>2026-02-20</pubDate></item>
</channel></rss>"""
        items = parse_feed_entries_via_xml(xml)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "A")

    def test_hubtoday_placeholder_title(self):
        self.assertTrue(is_hubtoday_placeholder_title("详情见官方介绍(AI资讯)"))
        self.assertTrue(is_hubtoday_placeholder_title("查看详情"))
        self.assertFalse(is_hubtoday_placeholder_title("OpenAI 发布 GPT-5o"))
        self.assertTrue(is_hubtoday_generic_anchor_title("论文已公开(AI资讯)"))
        self.assertFalse(is_hubtoday_generic_anchor_title("Anthropic禁止第三方调用订阅。"))

    def test_dedupe_items_by_title_url_latest(self):
        items = [
            {
                "id": "1",
                "title": "Same",
                "title_original": "Same",
                "url": "https://example.com/a",
                "published_at": "2026-02-20T00:00:00Z",
            },
            {
                "id": "2",
                "title": "Same",
                "title_original": "Same",
                "url": "https://example.com/a",
                "published_at": "2026-02-20T01:00:00Z",
            },
        ]
        out = dedupe_items_by_title_url(items, random_pick=False)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["id"], "2")


if __name__ == "__main__":
    unittest.main()
