from agents import function_tool

from myvoice.actions.browser import BrowserActions
from myvoice.actions.streaming import get_streaming_service

import logging

logger = logging.getLogger(__name__)

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
async def streaming_search(service: str, query: str) -> list[dict]:
    """Search a supported streaming service for a movie or TV series."""

    logger.warning("Streaming search: service=%r query=%r", service, query)

    try:
        profile = get_streaming_service(service)
        results = await browser.search_streaming(profile, query)
        logger.warning("Streaming results: %d", len(results))
        return results
    except Exception:
        logger.exception("Streaming search failed")
        raise
    
    # profile = get_streaming_service(service)
    # return await browser.search_streaming(profile, query)


@function_tool
async def streaming_open_title(title: str) -> str:
    """Open a title from the latest streaming search results."""
    await browser.open_streaming_title(title)

    return f'Opened streaming title "{title}"'


@function_tool
async def streaming_play() -> str:
    """Play or resume the currently opened streaming title."""

    try:
        button_name = await browser.play_current_streaming_title()

        return f'Clicked streaming "{button_name}" button.'

    except Exception:
        await browser.print_visible_actions()
        raise
