"""Heathrow arrival runways: what is actually landing, and what was planned.

The integration used to scrape an ATIS mirror for the "ARRIVAL RWY" line, but
that source is no longer available. Three published sources replace it:

* atis.guru republishes the real EGLL D-ATIS collected off ACARS. When it has
  a recent report this is ground truth - it is the airport saying what is
  landing right now.
* the half-hourly EGLL METAR (aviationweather.gov) gives the reported wind,
  which decides whether Heathrow is landing westerly or easterly - westerly by
  preference, turning round only once the tailwind on 27 passes the operating
  tolerance.
* Heathrow's annual runway alternation programme says which of the parallel
  pair is planned to take the arrivals in each period of each week.

The "Arrival Rwy" sensor reports the ATIS runway, falling back to the wind and
the programme when no recent ATIS is available, so it degrades rather than
going dark. The "Planned" sensors report the published programme on its own,
so you can see when the airport is running off plan - delays, bad weather and
runway works all push arrivals out of the alternation pattern.
"""

from __future__ import annotations

import asyncio
import html
import json
import logging
import math
import re
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import aiohttp

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

_LOGGER = logging.getLogger(__name__)

STATION = "EGLL"
METAR_URL = "https://aviationweather.gov/api/data/metar"
ATIS_URL = f"https://atis.guru/atis/{STATION}"
USER_AGENT = "heathrow-arrivals (+https://github.com/anthonyjhicks/heathrow-arrivals)"

# EGLL issues a METAR every half hour (plus SPECIs when things change), and the
# ATIS is reissued alongside it, so five minutes picks up a change promptly
# without hammering either source.
SCAN_INTERVAL = timedelta(minutes=5)
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)

# atis.guru collects D-ATIS opportunistically, when an aircraft requests it.
# Heathrow is busy enough that arrival reports normally arrive every half hour,
# but there are gaps; anything older than this is ignored in favour of the
# wind and the programme, because a stale runway is worse than a computed one.
MAX_ATIS_AGE = timedelta(minutes=90)

WESTERLY = ("27L", "27R")
EASTERLY = ("09L", "09R")
WESTERLY_HEADING = 270
EASTERLY_HEADING = 90

# Heathrow runs westerly whenever it reasonably can (arrivals over London,
# departures out west) and only swaps to easterly once the tailwind on 27
# exceeds roughly five knots.
TAILWIND_TOLERANCE_KT = 5

# How close to that threshold the wind has to sit before the direction is a
# coin toss. Heathrow weighs forecast trend and runway wetness too, so within
# a couple of knots either way the computed direction should be treated as
# soft rather than as an answer.
MARGINAL_BAND_KT = 2

# The alternation programme is published in London local time, whatever the
# Home Assistant instance is set to.
LONDON = ZoneInfo("Europe/London")

# Day-time alternation runs 06:00 to the last departure, switching runways at
# 15:00; the night pattern holds from after the last departure until 06:00.
# The last departure is not a fixed time - scheduled departures end around
# 23:00, so that is where this splits day from night.
DAY_START = time(6, 0)
DUAL_ARRIVALS_END = time(7, 0)  # both runways take arrivals in the busy first hour
RUNWAY_SWITCH = time(15, 0)
NIGHT_START = time(23, 0)

# Day-time alternation only happens on westerlies. On easterlies the Cranford
# Agreement keeps departures off the northern runway, so 09L lands and 09R
# departs all day, with no switch at 15:00.
EASTERLY_DAY_ARRIVALS = "09L"

SCHEDULE_GLOB = "runway_alternation_*.json"

SOURCE_ATIS = "atis.guru"
SOURCE_COMPUTED = "metar+schedule"

_WIND_VAR_RE = re.compile(r"\b(\d{3})V(\d{3})\b")


# --- wind -> operating direction ---------------------------------------------


def _wind_direction(raw_dir) -> int | None:
    """The reported wind direction in degrees true, or None if variable/calm."""
    if isinstance(raw_dir, bool) or not isinstance(raw_dir, (int, float)):
        # "VRB", null, or anything unexpected.
        return None
    direction = int(raw_dir)
    return direction if 1 <= direction <= 360 else None


def wind_components(wdir: int | None, wspd, heading: int) -> tuple:
    """Head/crosswind (kt) landing on ``heading``.

    ``headwind`` is negative for a tailwind; ``crosswind`` is unsigned, with the
    side it blows from given separately as seen from the flight deck.
    """
    if wspd is None or wspd == 0:
        return 0, 0, None
    if wdir is None:
        return None, None, None
    rel = math.radians(wdir - heading)
    head = wspd * math.cos(rel)
    cross = wspd * math.sin(rel)
    side = "R" if cross > 0.5 else ("L" if cross < -0.5 else None)
    return round(head), round(abs(cross)), side


def operating_mode(wdir: int | None, wspd) -> str:
    """"Westerly" or "Easterly" for the reported wind."""
    if wdir is None or not wspd:
        # Calm or variable: the airport sits on its westerly preference.
        return "Westerly"
    headwind_on_27, _, _ = wind_components(wdir, wspd, WESTERLY_HEADING)
    if headwind_on_27 is not None and -headwind_on_27 > TAILWIND_TOLERANCE_KT:
        return "Easterly"
    return "Westerly"


def westerly_tailwind(wdir: int | None, wspd) -> int | None:
    """Tailwind (kt) landing westerly - the component the direction turns on.

    Negative is a headwind on 27. None when the wind direction is unknown.
    """
    headwind, _, _ = wind_components(wdir, wspd, WESTERLY_HEADING)
    return None if headwind is None else -headwind


def is_marginal(wdir: int | None, wspd) -> bool:
    """Whether the wind sits close enough to the switch threshold to be a toss-up."""
    tailwind = westerly_tailwind(wdir, wspd)
    if tailwind is None:
        return False
    return abs(tailwind - TAILWIND_TOLERANCE_KT) <= MARGINAL_BAND_KT


def parse_wind_variation(raw: str | None) -> tuple[int | None, int | None]:
    """The variable-wind range from a raw METAR ("210V270")."""
    match = _WIND_VAR_RE.search(raw or "")
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


# --- alternation programme ---------------------------------------------------


def load_schedule(directory: Path | None = None) -> dict:
    """Every published alternation year found beside this module, merged.

    Dropping next year's ``runway_alternation_<year>.json`` in is all it takes
    to extend the table.
    """
    directory = directory or Path(__file__).parent
    schedule: dict[str, dict] = {"day": {}, "night": {}, "sources": {}}
    for path in sorted(directory.glob(SCHEDULE_GLOB)):
        try:
            data = json.loads(path.read_text())
            schedule["day"].update(data["day"])
            schedule["night"].update(data["night"])
            schedule["sources"][str(data.get("year", path.stem))] = data.get("source", path.name)
        except (OSError, ValueError, KeyError) as err:
            _LOGGER.warning("Ignoring unreadable alternation table %s: %s", path.name, err)
    return schedule


def week_commencing(day: date) -> str:
    """The Monday of ``day``'s week, as the schedule keys it."""
    return str(day - timedelta(days=day.weekday()))


def night_week_commencing(now: datetime) -> str:
    """The night pattern's week - flights before 06:00 on a Monday keep the last."""
    reference = now.date()
    if now.time() < DAY_START and now.weekday() == 0:
        reference -= timedelta(days=7)
    return week_commencing(reference)


def current_period(now: datetime) -> str:
    """Which of the programme's periods ``now`` falls in."""
    clock = now.time()
    if clock >= NIGHT_START or clock < DAY_START:
        return "night"
    if clock < DUAL_ARRIVALS_END:
        return "early morning"
    return "morning" if clock < RUNWAY_SWITCH else "afternoon"


def arrival_runways(schedule: dict, now: datetime, mode: str) -> dict:
    """The planned arrival runway(s) for a moment in time and a direction.

    Normally a single runway; both, when the programme cannot narrow it down or
    during the 06:00-07:00 hour in which Heathrow lands on either.
    """
    pair = WESTERLY if mode == "Westerly" else EASTERLY
    period = current_period(now)

    if period == "night":
        week = night_week_commencing(now)
        entry = schedule["night"].get(week)
        if not entry:
            return _unscheduled(pair, period, week)
        # The primary and its alternative are the same strip from either end;
        # the wind picks which end.
        runways = [rwy for rwy in entry if rwy in pair]
        return {
            "runways": runways or list(pair),
            "period": period,
            "week_commencing": week,
            "scheduled": bool(runways),
            "night_primary": entry[0],
            "night_alternative": entry[1],
        }

    week = week_commencing(now.date())
    entry = schedule["day"].get(week)

    if mode == "Easterly":
        # No day-time alternation on easterlies.
        return {
            "runways": [EASTERLY_DAY_ARRIVALS],
            "period": period,
            "week_commencing": week,
            "scheduled": True,
            "day_morning": None,
            "day_afternoon": None,
        }

    if not entry:
        return _unscheduled(pair, period, week)
    morning, afternoon = entry
    if period == "early morning":
        runways = sorted({morning, afternoon})  # both runways land in the busy hour
    elif period == "morning":
        runways = [morning]
    else:
        runways = [afternoon]
    return {
        "runways": runways,
        "period": period,
        "week_commencing": week,
        "scheduled": True,
        "day_morning": morning,
        "day_afternoon": afternoon,
    }


def _unscheduled(pair: tuple[str, ...], period: str, week: str) -> dict:
    """Fall back to the direction's pair when the week is not in the table."""
    _LOGGER.debug("No alternation entry for week commencing %s", week)
    return {
        "runways": list(pair),
        "period": period,
        "week_commencing": week,
        "scheduled": False,
    }


# --- atis.guru ---------------------------------------------------------------

_ATIS_BLOCK_RE = re.compile(r'<div class="atis">(.*?)</div>', re.S)
_ATIS_SUBTITLE_RE = re.compile(r"card-subtitle[^>]*>([^<]+)</h6>")
_ATIS_LETTER_RE = re.compile(r"ARR\s+ATIS\s+([A-Z])\b")
_ATIS_LANDING_RE = re.compile(r"LANDING\s+RWYS?\b")
_ATIS_RUNWAY_RE = re.compile(r"\b(09[LR]|27[LR])\b")


def parse_atis_page(page: str) -> dict | None:
    """The arrival ATIS from an atis.guru station page.

    The site is a Blazor app; the report is in the server-prerendered HTML, so
    it can be read without running any of its JavaScript. Returns None when the
    page carries no arrival report.
    """
    for match in _ATIS_BLOCK_RE.finditer(page):
        text = html.unescape(match.group(1)).replace("\r", "").strip()
        if "ARR ATIS" not in text.upper():
            continue  # the same page also carries the departure ATIS, METAR and TAF
        # The card's timestamp is the last subtitle before the report itself.
        subtitles = _ATIS_SUBTITLE_RE.findall(page[: match.start()])
        letter = _ATIS_LETTER_RE.search(text.upper())
        return {
            "text": text,
            "letter": letter.group(1) if letter else None,
            "issued": _parse_atis_time(subtitles[-1] if subtitles else None),
            "runways": parse_atis_runways(text),
        }
    return None


def _parse_atis_time(value: str | None) -> datetime | None:
    """atis.guru prints its collection time as "2026-09-23 06:24 UTC"."""
    try:
        return datetime.strptime((value or "").strip(), "%Y-%m-%d %H:%M UTC").replace(tzinfo=UTC)
    except ValueError:
        return None


def parse_atis_runways(text: str) -> list[str]:
    """The landing runway(s) named by an ATIS ("LANDING RWY 27R")."""
    for line in text.upper().splitlines():
        if _ATIS_LANDING_RE.search(line):
            found = _ATIS_RUNWAY_RE.findall(line)
            if found:
                return sorted(dict.fromkeys(found))
    return []


async def async_fetch_atis(session: aiohttp.ClientSession) -> dict | None:
    """The current EGLL arrival ATIS republished by atis.guru."""
    async with session.get(
        ATIS_URL, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT
    ) as response:
        response.raise_for_status()
        page = await response.text()
    return parse_atis_page(page)


# --- METAR -------------------------------------------------------------------


def _observation_time(record: dict) -> str | None:
    timestamp = record.get("obsTime")
    if isinstance(timestamp, (int, float)):
        return datetime.fromtimestamp(timestamp, UTC).isoformat().replace("+00:00", "Z")
    report_time = record.get("reportTime")
    return str(report_time) if report_time else None


async def async_fetch_metar(session: aiohttp.ClientSession) -> dict:
    """The latest EGLL observation from aviationweather.gov."""
    async with session.get(
        METAR_URL,
        params={"ids": STATION, "format": "json"},
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT,
    ) as response:
        response.raise_for_status()
        records = await response.json(content_type=None)

    if not isinstance(records, list) or not records:
        raise ValueError(f"no METAR returned for {STATION}")
    return records[0]


# --- combining the sources ---------------------------------------------------


def build_state(schedule: dict, metar: dict | None, atis: dict | None, now: datetime) -> dict:
    """Everything the sensors need, from whichever sources answered."""
    record = metar or {}
    raw = record.get("rawOb")
    wdir = _wind_direction(record.get("wdir"))
    wspd = record.get("wspd")
    mode = operating_mode(wdir, wspd)
    heading = WESTERLY_HEADING if mode == "Westerly" else EASTERLY_HEADING
    headwind, crosswind, crosswind_from = wind_components(wdir, wspd, heading)
    var_from, var_to = parse_wind_variation(raw)
    plan = arrival_runways(schedule, now, mode)

    age = None
    if atis and atis.get("issued"):
        age = now.astimezone(UTC) - atis["issued"]
    fresh = bool(atis and atis.get("runways") and age is not None and age <= MAX_ATIS_AGE)

    # The wind can be a toss-up even when the ATIS has already settled it; the
    # state is only soft when it was computed from that wind in the first place.
    wind_marginal = is_marginal(wdir, wspd) if metar else False

    return {
        "now": now,
        "metar_available": metar is not None,
        "actual": atis["runways"] if fresh else plan["runways"],
        "wind_marginal": wind_marginal,
        "marginal": wind_marginal and not fresh,
        "westerly_tailwind_kt": westerly_tailwind(wdir, wspd) if metar else None,
        "source": SOURCE_ATIS if fresh else SOURCE_COMPUTED,
        "atis_letter": atis.get("letter") if atis else None,
        "atis_issued": atis["issued"].isoformat().replace("+00:00", "Z")
        if atis and atis.get("issued")
        else None,
        "atis_age_minutes": round(age.total_seconds() / 60) if age is not None else None,
        "atis_runways": atis.get("runways") if atis else None,
        "atis_text": atis.get("text") if atis else None,
        "plan": plan,
        "mode": mode,
        "wind": {
            "wind_direction": wdir,
            "wind_speed_kt": wspd,
            "wind_gust_kt": record.get("wgst"),
            "wind_variable": wdir is None and bool(wspd),
            "wind_variable_from": var_from,
            "wind_variable_to": var_to,
            "headwind_kt": headwind,
            "crosswind_kt": crosswind,
            "crosswind_from": crosswind_from,
        },
        "observation_time": _observation_time(record) if metar else None,
        "metar": raw,
    }


class HeathrowCoordinator(DataUpdateCoordinator):
    """Fetches the ATIS and the METAR together, once per cycle."""

    def __init__(self, hass: HomeAssistant, schedule: dict) -> None:
        super().__init__(
            hass, _LOGGER, name="Heathrow arrival runway", update_interval=SCAN_INTERVAL
        )
        self.schedule = schedule

    async def _async_update_data(self) -> dict:
        session = async_get_clientsession(self.hass)
        atis = metar = None

        try:
            atis = await async_fetch_atis(session)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            _LOGGER.debug("Could not fetch the %s ATIS: %s", STATION, err)

        try:
            metar = await async_fetch_metar(session)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            _LOGGER.warning("Could not fetch the %s METAR: %s", STATION, err)

        if metar is None and not (atis and atis.get("runways")):
            raise UpdateFailed(f"neither the {STATION} ATIS nor its METAR could be read")

        return build_state(self.schedule, metar, atis, datetime.now(LONDON))


# --- platform ----------------------------------------------------------------


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    schedule = await hass.async_add_executor_job(load_schedule)
    coordinator = HeathrowCoordinator(hass, schedule)
    await coordinator.async_refresh()
    async_add_entities(
        [
            HeathrowArrivalRwySensor(coordinator),
            HeathrowPlannedArrivalRwySensor(coordinator),
            HeathrowPlannedMorningSensor(schedule),
            HeathrowPlannedAfternoonSensor(schedule),
            HeathrowPlannedNightSensor(schedule),
        ],
        update_before_add=True,
    )


class HeathrowArrivalRwySensor(CoordinatorEntity, SensorEntity):
    """What is actually landing: the ATIS, or the wind and the programme."""

    _attr_name = "Heathrow Arrival Rwy"
    _attr_icon = "mdi:airplane-landing"
    _attr_attribution = (
        "D-ATIS via atis.guru; METAR from aviationweather.gov (NOAA/NWS); "
        "runway alternation programme from heathrow.com"
    )

    @property
    def native_value(self) -> str | None:
        if not self.coordinator.data:
            return None
        return "/".join(self.coordinator.data["actual"])

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data
        if not data:
            return {}
        plan = data["plan"]
        return {
            "station": STATION,
            "source": data["source"],
            "runways": data["actual"],
            "planned_runways": plan["runways"],
            "matches_plan": data["actual"] == plan["runways"],
            "marginal": data["marginal"],
            "wind_marginal": data["wind_marginal"],
            "westerly_tailwind_kt": data["westerly_tailwind_kt"],
            "mode": data["mode"],
            "period": plan["period"],
            "atis_letter": data["atis_letter"],
            "atis_issued": data["atis_issued"],
            "atis_age_minutes": data["atis_age_minutes"],
            "atis_runways": data["atis_runways"],
            "alternation_week": plan["week_commencing"],
            "alternation_scheduled": plan["scheduled"],
            **data["wind"],
            "observation_time": data["observation_time"],
            "metar": data["metar"],
            "atis": data["atis_text"],
        }


class HeathrowPlannedArrivalRwySensor(CoordinatorEntity, SensorEntity):
    """What the programme says should be landing now, given the wind."""

    _attr_name = "Heathrow Planned Arrival Rwy"
    _attr_icon = "mdi:calendar-clock"
    _attr_unique_id = "heathrow_arrivals_planned_arrival_rwy"
    _attr_attribution = (
        "Runway alternation programme from heathrow.com; "
        "METAR from aviationweather.gov (NOAA/NWS)"
    )

    @property
    def native_value(self) -> str | None:
        if not self.coordinator.data:
            return None
        return "/".join(self.coordinator.data["plan"]["runways"])

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data
        if not data:
            return {}
        plan = data["plan"]
        return {
            "station": STATION,
            "runways": plan["runways"],
            "mode": data["mode"],
            "marginal": data["wind_marginal"],
            "westerly_tailwind_kt": data["westerly_tailwind_kt"],
            "period": plan["period"],
            "alternation_week": plan["week_commencing"],
            "alternation_scheduled": plan["scheduled"],
            "day_morning_runway": plan.get("day_morning"),
            "day_afternoon_runway": plan.get("day_afternoon"),
            "night_primary_runway": plan.get("night_primary"),
            "night_alternative_runway": plan.get("night_alternative"),
        }


class _PlannedWeekSensor(SensorEntity):
    """A published runway for this week, straight from the programme.

    These need no network, so they stay available even when both feeds are
    down; only the calendar decides them.
    """

    _attr_icon = "mdi:calendar-clock"
    _attr_attribution = "Runway alternation programme from heathrow.com"

    def __init__(self, schedule: dict) -> None:
        self._schedule = schedule

    def _week_entry(self, now: datetime) -> tuple[str, list[str] | None]:
        raise NotImplementedError

    async def async_update(self) -> None:
        now = datetime.now(LONDON)
        week, entry = self._week_entry(now)
        self._attr_available = entry is not None
        self._attr_native_value = self._value(entry) if entry else None
        self._attr_extra_state_attributes = {
            "station": STATION,
            "alternation_week": week,
            **self._attributes(entry),
        }

    def _value(self, entry: list[str]) -> str:
        raise NotImplementedError

    def _attributes(self, entry: list[str] | None) -> dict:
        return {}


class _PlannedDaySensor(_PlannedWeekSensor):
    """Day-time alternation is published for westerly operations only."""

    def _week_entry(self, now: datetime) -> tuple[str, list[str] | None]:
        week = week_commencing(now.date())
        return week, self._schedule["day"].get(week)

    def _attributes(self, entry: list[str] | None) -> dict:
        return {
            "applies_to": "Westerly operations",
            "day_morning_runway": entry[0] if entry else None,
            "day_afternoon_runway": entry[1] if entry else None,
        }


class HeathrowPlannedMorningSensor(_PlannedDaySensor):
    _attr_name = "Heathrow Planned Rwy 0600-1500"
    _attr_unique_id = "heathrow_arrivals_planned_rwy_morning"

    def _value(self, entry: list[str]) -> str:
        return entry[0]


class HeathrowPlannedAfternoonSensor(_PlannedDaySensor):
    _attr_name = "Heathrow Planned Rwy 1500"
    _attr_unique_id = "heathrow_arrivals_planned_rwy_afternoon"

    def _value(self, entry: list[str]) -> str:
        return entry[1]


class HeathrowPlannedNightSensor(_PlannedWeekSensor):
    """The night strip, named from whichever end the programme calls primary."""

    _attr_name = "Heathrow Planned Rwy Night"
    _attr_unique_id = "heathrow_arrivals_planned_rwy_night"

    def _week_entry(self, now: datetime) -> tuple[str, list[str] | None]:
        week = night_week_commencing(now)
        return week, self._schedule["night"].get(week)

    def _value(self, entry: list[str]) -> str:
        return entry[0]

    def _attributes(self, entry: list[str] | None) -> dict:
        return {
            "night_primary_runway": entry[0] if entry else None,
            "night_alternative_runway": entry[1] if entry else None,
        }
