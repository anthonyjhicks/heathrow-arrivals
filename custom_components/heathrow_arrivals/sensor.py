from __future__ import annotations

import aiohttp
import asyncio
from bs4 import BeautifulSoup
from cachetools import TTLCache

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

# Cache for 10 minutes so as not to hammer the atis report website - I do wish I could find a good free API for this instead
cache = TTLCache(maxsize=10, ttl=600)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    add_entities([HeathrowArrivalRwySensor()], update_before_add=True)


async def fetch_arrival_rwy(session, url):
    if url in cache:
        return cache[url]

    async with session.get(url) as response:
        response.raise_for_status()
        text = await response.text()
        soup = BeautifulSoup(text, "html.parser")
        atis_text = soup.find(class_="atis-text").get_text()
        arrival_rwy_index = atis_text.find("ARRIVAL RWY")

        # Check if "ARRIVAL RWY" is found in the ATIS text
        if arrival_rwy_index != -1:
            arrival_rwy_value = atis_text[arrival_rwy_index:].split()[2]
            cache[url] = arrival_rwy_value
            return arrival_rwy_value
        else:
            # Return "Unknown" if "ARRIVAL RWY" is not found
            cache[url] = "Unknown"
            return "Unknown"

class HeathrowArrivalRwySensor(SensorEntity):
    _attr_name = "Heathrow Arrival Rwy"

    async def async_update(self):
        url = "https://atis.report/a/EGLL"
        async with aiohttp.ClientSession() as session:
            self._attr_native_value = await fetch_arrival_rwy(session, url)
