import gzip
import json
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.update_news import (
    load_archive,
    fetch_ai_valley,
    fetch_therundown_ai,
    make_item_id,
    normalize_url,
    parse_date_any,
    parse_opml_subscriptions,
    parse_relative_time_zh,
    split_archive_for_storage,
    resolve_aibase_news_url,
)


class DummyResponse:
    def __init__(self, text: str):
        self.text = text
        self.content = text.encode("utf-8")

    def raise_for_status(self):
        return None


class DummySession:
    def __init__(self, payloads: dict[str, str]):
        self.payloads = payloads
        self.requested: list[str] = []

    def get(self, url, timeout=30, headers=None):
        self.requested.append(url)
        if url not in self.payloads:
            raise AssertionError(f"unexpected url: {url}")
        return DummyResponse(self.payloads[url])


class UtilsTests(unittest.TestCase):
    def test_normalize_url_removes_tracking(self):
        raw = "https://example.com/path?a=1&utm_source=x&fbclid=abc"
        self.assertEqual(normalize_url(raw), "https://example.com/path?a=1")

    def test_resolve_aibase_news_url_prefers_zh_path(self):
        self.assertEqual(
            resolve_aibase_news_url("/news/26362", "https://www.aibase.com/zh/news"),
            "https://www.aibase.com/zh/news/26362",
        )
        self.assertEqual(
            resolve_aibase_news_url("/news/26362", "https://www.aibase.com/news"),
            "https://www.aibase.com/news/26362",
        )

    def test_make_item_id_stable(self):
        a = make_item_id("site", "src", "Title", "https://a.com?p=1&utm_source=x")
        b = make_item_id("site", "src", "Title", "https://a.com?p=1")
        self.assertEqual(a, b)

    def test_parse_relative_time_zh_minutes(self):
        now = datetime(2026, 2, 19, 12, 0, tzinfo=timezone.utc)
        dt = parse_relative_time_zh("8分钟前", now)
        self.assertEqual(dt, datetime(2026, 2, 19, 11, 52, tzinfo=timezone.utc))

    def test_parse_date_any_english_rfc_not_misparsed_as_today(self):
        now = datetime(2026, 2, 21, 4, 30, tzinfo=timezone.utc)
        dt = parse_date_any("Tue, 07 Oct 2025 03:00:00 GMT", now)
        self.assertEqual(dt, datetime(2025, 10, 7, 3, 0, tzinfo=timezone.utc))

    def test_parse_opml_subscriptions(self):
        opml = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0"><body>
<outline text="A" title="A" xmlUrl="https://a.com/feed.xml" />
<outline text="A2" title="A2" xmlUrl="https://a.com/feed.xml" />
<outline text="B" xmlUrl="https://b.com/rss" />
</body></opml>"""
        with TemporaryDirectory() as td:
            p = Path(td) / "x.opml"
            p.write_text(opml, encoding="utf-8")
            feeds = parse_opml_subscriptions(p)
        self.assertEqual(len(feeds), 2)
        self.assertEqual(feeds[0]["title"], "A")
        self.assertEqual(feeds[1]["title"], "B")

    def test_split_archive_for_storage_moves_old_items_to_cold_store(self):
        now = datetime(2026, 3, 19, 0, 0, tzinfo=timezone.utc)
        archive = {
            "recent": {
                "id": "recent",
                "title": "Recent item",
                "last_seen_at": "2026-03-18T00:00:00Z",
            },
            "old": {
                "id": "old",
                "title": "Old item",
                "last_seen_at": "2026-03-10T00:00:00Z",
            },
        }

        hot, cold = split_archive_for_storage(archive, now, hot_days=7)

        self.assertEqual(list(hot.keys()), ["recent"])
        self.assertEqual(list(cold.keys()), ["old"])

    def test_load_archive_reads_hot_and_cold_files(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            hot_payload = {
                "generated_at": "2026-03-19T00:00:00Z",
                "items": [
                    {
                        "id": "recent",
                        "title": "Recent item",
                        "last_seen_at": "2026-03-18T00:00:00Z",
                    }
                ],
            }
            cold_payload = {
                "generated_at": "2026-03-19T00:00:00Z",
                "items": [
                    {
                        "id": "old",
                        "title": "Old item",
                        "last_seen_at": "2026-03-10T00:00:00Z",
                    }
                ],
            }
            manifest = {
                "generated_at": "2026-03-19T00:00:00Z",
                "hot_days": 7,
                "total_items": 2,
                "hot_items": 1,
                "cold_items": 1,
                "hot_archive": "archive-hot.json.gz",
                "cold_archive": "archive-cold.json.gz",
            }
            (root / "archive.json").write_text(json.dumps(manifest), encoding="utf-8")
            with gzip.open(root / "archive-hot.json.gz", "wt", encoding="utf-8") as fh:
                json.dump(hot_payload, fh)
            with gzip.open(root / "archive-cold.json.gz", "wt", encoding="utf-8") as fh:
                json.dump(cold_payload, fh)

            archive = load_archive(root)

        self.assertEqual(set(archive.keys()), {"recent", "old"})
        self.assertEqual(archive["old"]["title"], "Old item")

    def test_fetch_ai_valley_parses_latest_issue_from_archive(self):
        archive_html = """
        <html><body>
          <a href="/p/a-pentagon-lawsuit">Mar 10, 2026A Pentagon lawsuitPLUS: Nvidia is planning to launch an Open-Source AI Agent Platform</a>
          <a href="/p/a-pentagon-lawsuit">Mar 10, 2026A Pentagon lawsuitPLUS: Nvidia is planning to launch an Open-Source AI Agent Platform</a>
        </body></html>
        """
        issue_html = """
        <html><head>
          <meta property="og:title" content="A Pentagon lawsuit"/>
        </head>
        <body>
          <div>
            <h5>1/ OpenAI just triggered a $50B standoff with Microsoft</h5>
            <a href="https://www.ft.com/content/e814f4c3-4fb5-4e2e-90a6-470044436b39?syn-25a6b1a6=1">OpenAI just triggered a $50B standoff with Microsoft</a>
          </div>
          <div>
            <h5>2/ Anthropic launches Cowork Dispatch to rival OpenClaw</h5>
            <a href="https://x.com/felixrieseberg/status/2034005731457044577?s=20">Anthropic launches Cowork Dispatch to rival OpenClaw</a>
          </div>
          <div>
            <h5>3/ Mistral launches Forge so companies can train AI on their own data</h5>
            <a href="https://mistral.ai/news/forge">Mistral launches Forge so companies can train AI on their own data</a>
          </div>
          <script>window.__DATA__={"override_scheduled_at":"2026-03-10T14:34:14.263Z","slug":"a-pentagon-lawsuit"}</script>
        </body></html>
        """
        session = DummySession(
            {
                "https://www.theaivalley.com/": archive_html,
                "https://www.theaivalley.com/p/a-pentagon-lawsuit": issue_html,
            }
        )
        now = datetime(2026, 3, 19, 0, 0, tzinfo=timezone.utc)

        items = fetch_ai_valley(session, now)

        self.assertEqual([item.title for item in items], [
            "OpenAI just triggered a $50B standoff with Microsoft",
            "Anthropic launches Cowork Dispatch to rival OpenClaw",
            "Mistral launches Forge so companies can train AI on their own data",
        ])
        self.assertEqual(items[0].source, "AI Valley")
        self.assertEqual(items[0].published_at, datetime(2026, 3, 10, 14, 34, 14, 263000, tzinfo=timezone.utc))
        self.assertEqual(items[0].url, "https://www.ft.com/content/e814f4c3-4fb5-4e2e-90a6-470044436b39?syn-25a6b1a6=1")

    def test_fetch_therundown_ai_parses_latest_issue_from_archive(self):
        archive_html = """
        <html><body>
          <a href="/p/google-bets-on-vibe-design-with-stitch">Google bets on 'vibe design' with StitchPLUS: Generate an actionable SEO audit using this LLM strategy Zach Mink, +4</a>
          <a href="/p/google-bets-on-vibe-design-with-stitch">Google bets on 'vibe design' with StitchPLUS: Generate an actionable SEO audit using this LLM strategy Zach Mink, +4</a>
        </body></html>
        """
        issue_html = """
        <html><head>
          <meta property="og:title" content="Google bets on 'vibe design' with Stitch"/>
        </head>
        <body>
          <div>
            <h6>GOOGLE</h6>
            <h4>🎨 Google brings 'vibe design' to its AI UI canvas</h4>
            <a href="https://blog.google/innovation-and-ai/models-and-research/google-labs/stitch-ai-ui-design/">Google brings 'vibe design' to its AI UI canvas</a>
          </div>
          <div>
            <h6>MINIMAX</h6>
            <h4>♻️ MiniMax's new M2.7 helped build itself</h4>
            <a href="https://www.minimax.io/news/minimax-m27-en">MiniMax's new M2.7 helped build itself</a>
          </div>
          <div>
            <h6>AI TRAINING</h6>
            <h4>📝 Generate an actionable SEO audit with AI</h4>
            <a href="https://app.therundown.ai/guides/generate-an-actionable-seo-audit-using-this-strategy-works-with-any-llm">Generate an actionable SEO audit with AI</a>
          </div>
          <div>
            <h6>PRESENTED BY GLEAN</h6>
            <h4>🔒 AI moves fast, and security hasn't caught up</h4>
            <a href="https://www.glean.com/resources/guides/aware/?utm_source=3rd-party&utm_medium=email&utm_campaign=Aware-whitepaper&utm_partner=rundown">AI moves fast, and security hasn't caught up</a>
          </div>
          <div>
            <h6>MICROSOFT &amp; OPENAI</h6>
            <h4>⚖️ Microsoft ‘weighing’ legal action over Amazon-OAI deal</h4>
            <a href="https://www.ft.com/content/e814f4c3-4fb5-4e2e-90a6-470044436b39">Microsoft ‘weighing’ legal action over Amazon-OAI deal</a>
          </div>
          <script>window.__DATA__={"scheduled_at":"2026-03-19T09:00:00Z","slug":"google-bets-on-vibe-design-with-stitch"}</script>
        </body></html>
        """
        session = DummySession(
            {
                "https://www.therundown.ai/archive": archive_html,
                "https://www.therundown.ai/p/google-bets-on-vibe-design-with-stitch": issue_html,
            }
        )
        now = datetime(2026, 3, 19, 12, 0, tzinfo=timezone.utc)

        items = fetch_therundown_ai(session, now)

        self.assertEqual([item.title for item in items], [
            "Google brings 'vibe design' to its AI UI canvas",
            "MiniMax's new M2.7 helped build itself",
            "Generate an actionable SEO audit with AI",
            "Microsoft ‘weighing’ legal action over Amazon-OAI deal",
        ])
        self.assertEqual(items[0].source, "The Rundown AI")
        self.assertEqual(items[0].published_at, datetime(2026, 3, 19, 9, 0, tzinfo=timezone.utc))
        self.assertEqual(items[0].url, "https://blog.google/innovation-and-ai/models-and-research/google-labs/stitch-ai-ui-design")


if __name__ == "__main__":
    unittest.main()
