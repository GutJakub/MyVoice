import asyncio

from myvoice.actions.browser import BrowserActions


async def main() -> None:
    browser = BrowserActions()

    await browser.open_url(
        "https://www.netflix.com/browse"
    )

    await browser.click_by_name("Szukaj")

    await browser.fill_by_name(
        "Tytuły",
        "Breaking Bad",
    )

    results = await browser.get_netflix_results()

    for result in results:
        print(
            result["id"],
            result["title"],
            result["href"],
        )

    await browser.open_netflix_title(
        "Breaking Bad"
    )

    await asyncio.sleep(1)

    await browser.play_current_netflix_title()

    await browser.close()


if __name__ == "__main__":
    asyncio.run(main())