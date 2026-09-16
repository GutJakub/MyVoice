from dataclasses import dataclass


@dataclass(frozen=True)
class StreamingService:
    key: str
    display_name: str
    aliases: tuple[str, ...]
    search_url: str
    result_selector: str
    search_input_selector: str = (
        'input[type="search"], [role="searchbox"], '
        'input[placeholder*="search" i], input[placeholder*="szuk" i]'
    )
    play_names: tuple[str, ...] = (
        "odtwórz",
        "wznów",
        "kontynuuj oglądanie",
        "następny odcinek",
        "play",
        "resume",
        "continue watching",
        "next episode",
    )


STREAMING_SERVICES = (
    StreamingService(
        key="netflix",
        display_name="Netflix",
        aliases=("netflix",),
        search_url="https://www.netflix.com/search?q={query}",
        result_selector=(
            'a[href*="jbv="], a[href*="/watch/"], '
            'a[href*="/title/"]'
        ),
    ),
    StreamingService(
        key="hbo max",
        display_name="Hbo Max",
        aliases=("max", "hbo", "hbo max", "hbomax"),
        search_url="https://play.hbomax.com/search",
        search_input_selector='input[data-testid="searchBar_field"]',
        result_selector=(
            'a[href*="/video/watch/"], a[href*="/show/"], '
            'a[href*="/movie/"]'
        ),
    ),
    StreamingService(
        key="prime_video",
        display_name="Prime Video",
        aliases=(
            "prime video",
            "prime",
            "amazon prime",
            "amazon prime video",
        ),
        search_url=(
            "https://www.primevideo.com/search/"
            "ref=atv_nb_sr?phrase={query}"
        ),
        result_selector=(
            'a[href*="/detail/"], a[href*="/region/"][href*="detail"]'
        ),
    ),
    StreamingService(
        key="skyshowtime",
        display_name="SkyShowtime",
        aliases=("skyshowtime", "sky showtime", "sky"),
        search_url="https://www.skyshowtime.com/watch/search",
        result_selector=(
            '[data-testid="collection-tile"] [role="link"]'
        ),
    ),
)


def get_streaming_service(name: str) -> StreamingService:
    normalized = " ".join(name.casefold().split())

    for service in STREAMING_SERVICES:
        if normalized == service.key or normalized in service.aliases:
            return service

    supported = ", ".join(service.display_name for service in STREAMING_SERVICES)
    raise ValueError(
        f'Unsupported streaming service "{name}". Supported services: {supported}.'
    )
