from playwright.async_api import (
    Browser,
    BrowserContext,
    ElementHandle,
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeoutError,
    Page,
    Playwright,
    async_playwright,
)
import re
import asyncio
from urllib.parse import quote_plus

from myvoice.actions.streaming import StreamingService

class BrowserActions:
    CDP_URL = "http://127.0.0.1:9222"

    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._search_results: list[dict] = []
        self._streaming_results: list[dict] = []
        self._streaming_targets: dict[int, ElementHandle] = {}
        self._streaming_results_url: str | None = None
        self._streaming_service: StreamingService | None = None

    async def start(self) -> None:
        """Connect to the MyVoice Chrome instance running on Windows."""
        if self._browser is not None and self._browser.is_connected():
            return

        self._playwright = await async_playwright().start()

        try:
            await self._connect()
        except PlaywrightError:
            await self._start_windows_chrome()
            await self._wait_for_chrome()
        
    async def _connect(self) -> None:
        """Connect Playwright to Chrome through Chrome DevTools Protocol."""

        assert self._playwright is not None

        self._browser = await self._playwright.chromium.connect_over_cdp(
            self.CDP_URL,
            timeout=1_500,
        )

        if not self._browser.contexts:
            raise RuntimeError("Chrome has no browser context.")

        self._context = self._browser.contexts[0]

        pages = [
            page
            for page in self._context.pages
            if not page.is_closed()
        ]

        if pages:
            self._page = pages[-1]
        else:
            self._page = await self._context.new_page()

    async def _start_windows_chrome(self) -> None:
        """Start a native Windows Chrome instance with CDP enabled."""

        powershell_script = r"""
$chrome = "$env:ProgramFiles\Google\Chrome\Application\chrome.exe"

if (-not (Test-Path $chrome)) {
    $chrome = "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe"
}

if (-not (Test-Path $chrome)) {
    throw "Google Chrome was not found."
}

$profile = Join-Path $env:LOCALAPPDATA "MyVoice\ChromeProfile"

Start-Process `
    -FilePath $chrome `
    -ArgumentList @(
        "--remote-debugging-port=9222",
        "--user-data-dir=$profile",
        "--no-first-run",
        "--no-default-browser-check"
    )
"""

        process = await asyncio.create_subprocess_exec(
            "powershell.exe",
            "-NoProfile",
            "-Command",
            powershell_script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        _, stderr = await process.communicate()

        if process.returncode != 0:
            raise RuntimeError(
                f"Could not start Windows Chrome: "
                f"{stderr.decode().strip()}"
            )

    async def _wait_for_chrome(self) -> None:
        """Wait until the Windows Chrome CDP endpoint becomes available."""

        for _ in range(20):
            try:
                await self._connect()
                return
            except PlaywrightError:
                await asyncio.sleep(0.5)

        raise RuntimeError(
            "Windows Chrome started, but MyVoice could not connect "
            "to http://127.0.0.1:9222."
        )

    async def open_url(self, url: str) -> None:
        if self._page is None:
            await self.start()

        assert self._page is not None

        await self._page.goto(url)

    async def search_google(self, query: str) -> None:
        if self._page is None:
            await self.start()

        assert self._page is not None

        encoded_query = quote_plus(query)

        await self._page.goto(
            f"https://www.google.com/search?q={encoded_query}"
        )

    async def get_page_info(self) -> dict[str, str]:
        if self._page is None:
            await self.start()

        assert self._page is not None

        title = await self._page.title()
        url = self._page.url

        body = self._page.locator("body")
        text = await body.inner_text()

        return {
            "title": title,
            "url": url,
            "text": text[:5000],
        }

    async def get_search_results(
        self,
        limit: int = 10,
    ) -> list[dict]:
        if self._page is None:
            await self.start()

        assert self._page is not None

        results = self._page.locator("#search a:has(h3)")

        count = await results.count()

        output = []

        for i in range(min(count, limit)):
            result = results.nth(i)

            if not await result.is_visible():
                continue

            heading = result.locator("h3")

            title = (await heading.inner_text()).strip()
            href = await result.get_attribute("href")

            if not title or not href:
                continue

            output.append(
                {
                    "id": len(output),
                    "title": title,
                    "href": href,
                }
            )

            if len(output) >= limit:
                break
        self._search_results = output
        return output

    async def open_search_result(
        self,
        result_id: int,
    ) -> None:

        if self._page is None:
            raise RuntimeError("Browser is not started.")

        if result_id >= len(self._search_results):
            raise ValueError(
                f"Search result {result_id} does not exist."
            )

        result = self._search_results[result_id]

        await self._page.goto(result["href"])

    async def get_interactive_elements(
        self,
        limit: int = 50,
    ) -> list[dict]:
        if self._page is None:
            await self.start()

        assert self._page is not None

        await self._page.locator("[data-myvoice-id]").evaluate_all(
            """
            elements => {
                elements.forEach(
                    element => element.removeAttribute("data-myvoice-id")
                )
            }
            """
        )

        elements = await self._page.locator(
            """
            a[href],
            button,
            input,
            textarea,
            select,
            [role="button"],
            [role="link"],
            [role="textbox"],
            [role="searchbox"],
            [role="combobox"],
            [role="tab"],
            [role="menuitem"]
            """
        ).all()

        output = []
        element_id = 0

        for element in elements:
            if not await element.is_visible():
                continue

            info = await element.evaluate(
                """
                (el) => ({
                    tag: el.tagName.toLowerCase(),
                    role: el.getAttribute("role"),
                    text: (el.innerText || "").trim(),
                    ariaLabel: el.getAttribute("aria-label"),
                    placeholder: el.getAttribute("placeholder"),
                    title: el.getAttribute("title"),
                    href: el.getAttribute("href"),
                    type: el.getAttribute("type")
                })
                """
            )

            name = (
                info["ariaLabel"]
                or info["text"]
                or info["placeholder"]
                or info["title"]
            )

            if not name:
                continue

            await element.evaluate(
                "(el, id) => el.setAttribute('data-myvoice-id', id)",
                str(element_id),
            )

            output.append(
                {
                    "id": element_id,
                    "tag": info["tag"],
                    "role": info["role"],
                    "name": name[:150],
                    "href": info["href"],
                    "type": info["type"],
                }
            )

            element_id += 1

            if element_id >= limit:
                break

        return output

    async def click_element(self, element_id: int) -> None:
        if self._page is None:
            raise RuntimeError("Browser is not started.")

        element = self._page.locator(
            f'[data-myvoice-id="{element_id}"]'
        )

        if await element.count() == 0:
            raise ValueError(
                f"Element {element_id} was not found. "
                "Call get_interactive_elements() again."
            )

        await element.click()

    async def find_element_by_name(
        self,
        name: str,
    ) -> dict | None:
        elements = await self.get_interactive_elements()

        name_lower = name.lower()

        for element in elements:
            if name_lower in element["name"].lower():
                return element

        return None

    async def click_by_name(
        self,
        name: str,
    ) -> None:
        element = await self.find_element_by_name(name)

        if element is None:
            raise ValueError(
                f'Interactive element "{name}" was not found.'
            )

        await self.click_element(element["id"])

    async def fill_element(
        self,
        element_id: int,
        text: str,
    ) -> None:
        if self._page is None:
            raise RuntimeError("Browser is not started.")

        element = self._page.locator(
            f'[data-myvoice-id="{element_id}"]'
        )

        if await element.count() == 0:
            raise ValueError(
                f"Element {element_id} was not found. "
                "Call get_interactive_elements() again."
            )

        await element.fill(text)

    async def fill_by_name(
        self,
        name: str,
        text: str,
    ) -> None:
        element = await self.find_element_by_name(name)

        if element is None:
            raise ValueError(
                f'Interactive element "{name}" was not found.'
            )

        await self.fill_element(
            element["id"],
            text,
        )

    async def search_streaming(
        self,
        service: StreamingService,
        query: str,
    ) -> list[dict]:
        self._streaming_service = service
        self._streaming_results = []
        self._streaming_targets = {}
        search_url = service.search_url.format(query=quote_plus(query))
        await self.open_url(search_url)

        print("Requested URL:", search_url, flush=True)
        print("Actual URL:", self._page.url, flush=True)
        print("Page title:", await self._page.title(), flush=True)

        if "{query}" not in service.search_url:
            assert self._page is not None
            search_input = self._page.locator(
                f":is({service.search_input_selector}):visible"
            ).first
            try:
                await search_input.wait_for(state="visible", timeout=15_000)
            except PlaywrightTimeoutError as error:
                raise RuntimeError(
                    f"{service.display_name} search input was not visible "
                    "within 15 seconds. "
                    f"Current URL: {self._page.url}"
                ) from error

            await search_input.fill(query)
            await search_input.press("Enter")

        return await self.get_streaming_results()

    async def get_streaming_results(
        self,
        limit: int = 30,
    ) -> list[dict]:
        if self._page is None:
            raise RuntimeError("Browser is not started.")

        if self._streaming_service is None:
            raise RuntimeError("No streaming service was selected.")

        self._streaming_results = []
        self._streaming_targets = {}
        selector = self._streaming_service.result_selector
        links = self._page.locator(f":is({selector}):visible")
        try:
            await links.first.wait_for(state="visible", timeout=15_000)
        except PlaywrightTimeoutError as error:
            tile_count = await self._page.locator(
                '[data-testid="collection-tile"]'
            ).count()
            role_link_count = await self._page.locator('[role="link"]').count()
            raise RuntimeError(
                f"{self._streaming_service.display_name}: no visible result "
                f"matched {selector!r} within 15 seconds. "
                f"Collection tiles: {tile_count}; role links: {role_link_count}. "
                f"Current URL: {self._page.url}. "
                "Search results could not be read; this does not confirm "
                "that the requested title is unavailable."
            ) from error

        count = await links.count()

        results = []
        seen_urls = set()
        self._streaming_targets = {}
        self._streaming_results_url = self._page.url

        for i in range(count):
            link = links.nth(i)

            if not await link.is_visible():
                continue

            info = await link.evaluate(
                """
                (el) => {
                    const card =
                        el.closest(
                            '[data-uia*="title-card"], '
                            + '[class*="title-card"], '
                            + 'article, li'
                        ) || el;

                    const values = [
                        el.querySelector('[data-testid="title"]')?.textContent,
                        el.getAttribute("aria-label"),
                        el.getAttribute("title"),

                        ...Array.from(
                            el.querySelectorAll("[aria-label]")
                        ).map(
                            node => node.getAttribute("aria-label")
                        ),

                        ...Array.from(
                            el.querySelectorAll("img[alt]")
                        ).map(
                            node => node.getAttribute("alt")
                        ),

                        ...Array.from(
                            card.querySelectorAll("[aria-label]")
                        ).map(
                            node => node.getAttribute("aria-label")
                        ),

                        ...Array.from(
                            card.querySelectorAll("img[alt]")
                        ).map(
                            node => node.getAttribute("alt")
                        ),

                        ...(card.innerText || "").split("\\n")
                    ];

                    const names = [
                        ...new Set(
                            values
                                .filter(Boolean)
                                .map(value => value.trim())
                                .filter(Boolean)
                        )
                    ];

                    return {
                        href: el.href || null,
                        domId: el.id || null,
                        names: names
                    };
                }
                """
            )

            href = info["href"]

            # Keep query parameters: Netflix identifies preview results with
            # the `jbv` parameter even when the path is the same.
            canonical_url = href or info.get("domId") or f"element:{i}"

            if canonical_url in seen_urls:
                continue

            names = [
                name
                for name in info["names"]
                if 1 < len(name) <= 150
            ]

            if not names:
                continue

            seen_urls.add(canonical_url)

            if not href:
                target = await link.element_handle()
                if target is None:
                    continue
                self._streaming_targets[len(results)] = target

            results.append(
                {
                    "id": len(results),
                    "title": names[0],
                    "names": names,
                    "href": href,
                    "service": self._streaming_service.key,
                }
            )

            if len(results) >= limit:
                break

        self._streaming_results = results

        if not results:
            raise RuntimeError(
                f"Found {count} visible streaming candidates, but could not "
                "extract any titles. Search results could not be read."
            )

        return results

    async def open_streaming_title(
        self,
        title: str,
    ) -> None:
        if not self._streaming_results:
            await self.get_streaming_results()

        normalized_title = title.casefold().strip()

        # First try exact match.
        for result in self._streaming_results:
            if any(
                name.casefold().strip() == normalized_title
                for name in result["names"]
            ):
                await self.open_streaming_result(result["id"])
                return

        # Then allow partial match.
        matches = [
            result
            for result in self._streaming_results
            if any(
                normalized_title in name.casefold()
                for name in result["names"]
            )
        ]

        if len(matches) == 1:
            await self.open_streaming_result(matches[0]["id"])
            return

        if len(matches) > 1:
            names = [result["title"] for result in matches]

            raise ValueError(
                f'Multiple streaming results match "{title}": {names}'
            )

        raise ValueError(
            f'Streaming title "{title}" was not found.'
        )

    async def open_streaming_result(
        self,
        result_id: int,
    ) -> None:
        if self._page is None:
            raise RuntimeError("Browser is not started.")

        if result_id < 0 or result_id >= len(self._streaming_results):
            raise ValueError(
                f"Streaming result {result_id} does not exist."
            )

        result = self._streaming_results[result_id]

        if result["href"]:
            await self._page.goto(result["href"])
            return

        target = self._streaming_targets.get(result_id)
        if (
            target is None
            or self._page.url != self._streaming_results_url
            or not await target.evaluate("el => el.isConnected")
        ):
            raise RuntimeError("Streaming result is stale. Search again.")
        await target.click()

    async def click_first_available(
        self,
        names: list[str],
    ) -> str:
        elements = await self.get_interactive_elements()

        normalized_names = [
            name.casefold().strip()
            for name in names
        ]

        # First try exact matches.
        for target in normalized_names:
            for element in elements:
                if element["name"].casefold().strip() == target:
                    await self.click_element(element["id"])
                    return element["name"]

        # Then allow partial matches.
        for target in normalized_names:
            for element in elements:
                if target in element["name"].casefold():
                    await self.click_element(element["id"])
                    return element["name"]

        raise ValueError(
            f"None of these elements were found: {names}"
        )

    async def play_current_streaming_title(
        self,
        timeout_seconds: float = 10.0,
    ) -> str:
        if self._page is None:
            raise RuntimeError("Browser is not started.")

        if self._streaming_service is None:
            raise RuntimeError("No streaming service was selected.")

        play_names = tuple(
            name.casefold() for name in self._streaming_service.play_names
        )

        attempts = int(timeout_seconds / 0.5)

        for _ in range(attempts):
            # Prefer a preview/details modal if one exists.
            dialogs = self._page.locator('[role="dialog"]')

            scope = self._page

            for i in range(await dialogs.count()):
                dialog = dialogs.nth(i)

                if await dialog.is_visible():
                    scope = dialog
                    break

            candidates = scope.locator(
                """
                button,
                [role="button"],
                a,
                [data-uia*="play"]
                """
            )

            for i in range(await candidates.count()):
                candidate = candidates.nth(i)

                if not await candidate.is_visible():
                    continue

                info = await candidate.evaluate(
                    """
                    (el) => ({
                        text: (el.innerText || "").trim(),
                        ariaLabel: el.getAttribute("aria-label"),
                        title: el.getAttribute("title"),
                        dataUia: el.getAttribute("data-uia")
                    })
                    """
                )

                label = (
                    info["ariaLabel"]
                    or info["text"]
                    or info["title"]
                    or ""
                ).strip()

                normalized = label.casefold()

                if not any(
                    name in normalized
                    for name in play_names
                ):
                    continue

                await candidate.click()

                return label or "Play"

            await asyncio.sleep(0.5)

        raise RuntimeError(
            f"{self._streaming_service.display_name} play/resume action "
            "was not found. "
            f"Current URL: {self._page.url}"
        )

    async def print_visible_actions(self) -> None:
        if self._page is None:
            return

        elements = self._page.locator("button, [role=button], a")
        print("\nVISIBLE ACTIONS:")
        print("URL:", self._page.url)

        for i in range(await elements.count()):
            element = elements.nth(i)
            if not await element.is_visible():
                continue
            print(i, await element.evaluate("""
                (el) => ({
                    tag: el.tagName.toLowerCase(),
                    text: (el.innerText || "").trim(),
                    ariaLabel: el.getAttribute("aria-label"),
                    role: el.getAttribute("role")
                })
            """))

    async def close(self) -> None:
        if self._browser is not None:
            await self._browser.close()

        if self._playwright is not None:
            await self._playwright.stop()

        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
