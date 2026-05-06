from typing import Dict, Iterator

import requests  # pyright: ignore[reportMissingModuleSource]


def search_assets(api_url: str, headers: Dict[str, str], payload: Dict[str, object], page_size: int = 1000) -> Iterator[dict]:
    seen: set[str] = set()
    page = 1

    while True:
        request_payload: Dict[str, object] = dict(payload)
        request_payload["size"] = page_size
        request_payload["page"] = page

        response = requests.post(
            f"{api_url}/search/metadata",
            json=request_payload,
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()
        items = data["assets"]["items"]

        for item in items:
            item_id = item["id"]
            if item_id in seen:
                continue
            seen.add(item_id)
            yield item

        if len(items) < page_size:
            break

        page += 1
