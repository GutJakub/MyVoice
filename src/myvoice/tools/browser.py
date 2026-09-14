import asyncio

from agents import function_tool

from myvoice.actions.browser import BrowserActions

async def print_visible_actions(self) -> None:
    if self._page is None:
        return

    elements = self._page.locator(
        """
        button,
        [role="button"],
        a
        """
    )

    print("\nVISIBLE ACTIONS:")
    print("URL:", self._page.url)

    for i in range(await elements.count()):
        element = elements.nth(i)

        if not await element.is_visible():
            continue

        info = await element.evaluate(
            """
            (el) => ({
                tag: el.tagName.toLowerCase(),
                text: (el.innerText || "").trim(),
                ariaLabel: el.getAttribute("aria-label"),
                role: el.getAttribute("role"),
                dataUia: el.getAttribute("data-uia")
            })
            """
        )

        print(i, info)
# One shared browser instance.
# This is important because we want to keep the same Chrome session
# between consecutive agent tool calls.
browser = BrowserActions()


@function_tool
async def browser_open_url(url: str) -> str:
    """Open a URL in the controlled browser."""
    await browser.open_url(url)

    return f"Opened {url}"


@function_tool
async def browser_get_page_info() -> dict:
    """Read the title, URL and visible text of the current page."""
    return await browser.get_page_info()


@function_tool
async def browser_click(name: str) -> str:
    """Click a visible interactive element by its human-readable name."""
    await browser.click_by_name(name)

    return f'Clicked "{name}"'


@function_tool
async def browser_fill(
    name: str,
    text: str,
) -> str:
    """Fill an input field identified by its human-readable name."""
    await browser.fill_by_name(
        name,
        text,
    )

    return f'Filled "{name}" with "{text}"'


@function_tool
async def google_search(query: str) -> list[dict]:
    """Search Google and return the search results."""
    await browser.search_google(query)

    return await browser.get_search_results()


@function_tool
async def google_open_result(result_id: int) -> str:
    """Open a Google search result using its result ID."""
    await browser.open_search_result(result_id)

    return f"Opened Google result {result_id}"


@function_tool
async def netflix_search(query: str) -> list[dict]:
    """Search Netflix for a movie or TV series and return matching titles."""

    await browser.open_url(
        "https://www.netflix.com/browse"
    )

    await browser.click_by_name("Szukaj")

    await browser.fill_by_name(
        "Tytuły",
        query,
    )

    await asyncio.sleep(1)

    return await browser.get_netflix_results()


@function_tool
async def netflix_open_title(title: str) -> str:
    """Open a Netflix title from the current Netflix search results."""
    await browser.open_netflix_title(title)

    return f'Opened Netflix title "{title}"'


@function_tool
async def netflix_play() -> str:
    """Play or resume the currently opened Netflix title."""

    try:
        button_name = await browser.play_current_netflix_title()

        return f'Clicked Netflix "{button_name}" button.'

    except Exception:
        await browser.print_visible_actions()
        raise