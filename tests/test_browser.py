import unittest
from unittest.mock import AsyncMock, MagicMock
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from myvoice.actions.browser import BrowserActions
from myvoice.actions.streaming import get_streaming_service


class StreamingServiceTests(unittest.TestCase):
    def test_service_aliases(self):
        self.assertIs(get_streaming_service("HBO Max"), get_streaming_service("max"))
        self.assertEqual(get_streaming_service("amazon prime").key, "prime_video")
        self.assertEqual(get_streaming_service("Sky Showtime").key, "skyshowtime")

    def test_unknown_service_lists_supported_services(self):
        with self.assertRaisesRegex(ValueError, "Supported services"):
            get_streaming_service("unknown")


class BrowserStreamingTests(unittest.IsolatedAsyncioTestCase):
    async def test_skyshowtime_tiles_without_href_are_collected_and_clicked(self):
        browser = BrowserActions()
        page = MagicMock()
        page.url = "https://www.skyshowtime.com/watch/search"
        page.wait_for_timeout = AsyncMock()
        page.goto = AsyncMock()
        tiles = [AsyncMock(), AsyncMock()]
        for index, (tile, title) in enumerate(zip(tiles, ("Mr. Robot", "Dexter"))):
            tile.is_visible.return_value = True
            tile.evaluate.return_value = {
                "href": None, "domId": f"tile-{index}", "names": [title],
            }
            tile.element_handle.return_value.evaluate.return_value = True
        page.locator.return_value.count = AsyncMock(return_value=2)
        page.locator.return_value.first.wait_for = AsyncMock()
        page.locator.return_value.nth.side_effect = tiles
        browser._page = page
        browser._streaming_service = get_streaming_service("skyshowtime")

        results = await browser.get_streaming_results()

        self.assertEqual([result["title"] for result in results], ["Mr. Robot", "Dexter"])
        page.locator.assert_called_once_with(
            ':is([data-testid="collection-tile"] [role="link"]):visible'
        )
        page.locator.return_value.first.wait_for.assert_awaited_once_with(
            state="visible", timeout=15_000
        )
        await browser.open_streaming_title("Mr. Robot")
        tiles[0].element_handle.return_value.click.assert_awaited_once()
        tiles[1].element_handle.return_value.click.assert_not_awaited()
        page.goto.assert_not_awaited()

        tiles[0].element_handle.return_value.evaluate.return_value = False
        with self.assertRaisesRegex(RuntimeError, "stale"):
            await browser.open_streaming_title("Mr. Robot")
        self.assertEqual(tiles[0].element_handle.return_value.click.await_count, 1)

    async def test_result_with_href_still_navigates(self):
        browser = BrowserActions()
        browser._page = MagicMock()
        browser._page.goto = AsyncMock()
        browser._streaming_results = [{"href": "https://example.test/title"}]
        await browser.open_streaming_result(0)
        browser._page.goto.assert_awaited_once_with("https://example.test/title")

    async def test_results_timeout_reports_read_failure_and_clears_old_results(self):
        browser = BrowserActions()
        page = MagicMock()
        page.url = "https://www.skyshowtime.com/watch/search"
        page.locator.return_value.first.wait_for = AsyncMock(
            side_effect=PlaywrightTimeoutError("Timeout")
        )
        page.locator.return_value.count = AsyncMock(return_value=0)
        browser._page = page
        browser._streaming_service = get_streaming_service("skyshowtime")
        browser._streaming_results = [{"title": "old"}]

        with self.assertRaisesRegex(RuntimeError, "does not confirm"):
            await browser.get_streaming_results()

        self.assertEqual(browser._streaming_results, [])

    async def test_search_uses_profile_url_and_resets_results(self):
        browser = BrowserActions()
        browser._page = MagicMock()
        browser._page.title = AsyncMock(return_value="Search")
        browser.open_url = AsyncMock()
        browser.get_streaming_results = AsyncMock(return_value=[])
        browser._streaming_results = [{"title": "old"}]

        service = get_streaming_service("netflix")
        await browser.search_streaming(service, "Breaking Bad")

        browser.open_url.assert_awaited_once_with(
            "https://www.netflix.com/search?q=Breaking+Bad"
        )
        self.assertEqual(browser._streaming_results, [])

    async def test_open_title_matches_alias(self):
        browser = BrowserActions()
        browser._streaming_results = [
            {
                "id": 0,
                "title": "The Last of Us",
                "names": ["The Last of Us", "Last of Us"],
                "href": "https://example.test/title",
            }
        ]
        browser.open_streaming_result = AsyncMock()

        await browser.open_streaming_title("Last of Us")

        browser.open_streaming_result.assert_awaited_once_with(0)

    async def test_service_without_query_url_fills_search_input(self):
        browser = BrowserActions()
        page = MagicMock()
        search_input = AsyncMock()
        page.title = AsyncMock(return_value="Search")
        page.locator.return_value.first = search_input
        browser._page = page
        browser.open_url = AsyncMock()
        browser.get_streaming_results = AsyncMock(return_value=[])

        await browser.search_streaming(get_streaming_service("max"), "Dune")

        browser.open_url.assert_awaited_once_with(get_streaming_service("max").search_url)
        page.locator.assert_called_once_with(
            ':is(input[data-testid="searchBar_field"]):visible'
        )
        search_input.wait_for.assert_awaited_once_with(state="visible", timeout=15_000)
        search_input.fill.assert_awaited_once_with("Dune")
        search_input.press.assert_awaited_once_with("Enter")

    async def test_missing_search_input_times_out_without_filling(self):
        browser = BrowserActions()
        page = MagicMock()
        page.url = "https://example.test/search"
        page.title = AsyncMock(return_value="Search")
        search_input = AsyncMock()
        search_input.wait_for.side_effect = PlaywrightTimeoutError("Timeout")
        page.locator.return_value.first = search_input
        browser._page = page
        browser.open_url = AsyncMock()
        browser.get_streaming_results = AsyncMock()

        with self.assertRaisesRegex(RuntimeError, "within 15 seconds"):
            await browser.search_streaming(get_streaming_service("max"), "Dune")

        search_input.fill.assert_not_awaited()
        search_input.press.assert_not_awaited()
        browser.get_streaming_results.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
