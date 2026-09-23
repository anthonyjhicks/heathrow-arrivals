# Heathrow Arrivals

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

![Project Maintenance][maintenance-shield]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

A Home Assistant integration that reports which runway aircraft are landing on at London Heathrow — both what is **actually** in use and what the airport **planned**.

If you live under the flight path, the runway in use decides whether aircraft pass over your house. Westerly arrivals route in over London from the east; easterly arrivals come in from the west. Which of the two parallel runways is landing then shifts the path by about a mile, and it swaps at 15:00.

## Sensors

| Entity | Example | What it tells you |
| -- | -- | -- |
| `sensor.heathrow_arrival_rwy` | `27R` | **Actual** — from the ATIS, or computed when no recent one is available |
| `sensor.heathrow_planned_arrival_rwy` | `27R` | **Planned** — the programme for right now, given the wind |
| `sensor.heathrow_planned_rwy_0600_1500` | `27R` | This week's morning runway |
| `sensor.heathrow_planned_rwy_1500` | `27L` | This week's afternoon runway |
| `sensor.heathrow_planned_rwy_night` | `09R` | This week's night runway |

States are runway designators: `09L`, `09R`, `27L` or `27R`. The first two read `27L/27R` between 06:00 and 07:00, when Heathrow lands on both.

The three `Planned Rwy` sensors do no network I/O and stay available even when both feeds are down. The two live sensors go `unavailable` only if neither the ATIS nor the METAR can be read.

## How it works

Three published sources, in priority order:

1. **[atis.guru](https://atis.guru/atis/EGLL)** republishes the real EGLL D-ATIS, collected off ACARS. When it carries a report less than 90 minutes old naming a landing runway, that is used directly — it is the airport itself saying what is landing.
2. **The EGLL METAR** from [aviationweather.gov](https://aviationweather.gov/), whose reported wind decides whether Heathrow is running westerly or easterly.
3. **Heathrow's annual runway alternation programme**, which says which of the parallel pair is planned to take arrivals in each period of each week.

The ATIS is ground truth but arrives opportunistically, so 2 and 3 are the fallback: the integration degrades rather than going dark. The `source` attribute says which produced the current state. Both feeds are polled every five minutes.

This replaces the ATIS screen-scrape the integration used before, whose source no longer exists.

## Installation

### HACS (recommended)

1. In HACS, open the three-dot menu and choose **Custom repositories**.
2. Add `https://github.com/anthonyjhicks/heathrow-arrivals` with category **Integration**.
3. Search for **Heathrow Arrivals**, then download it.
4. Restart Home Assistant.

### Manual

1. Copy `custom_components/heathrow_arrivals` into the `custom_components` directory of your Home Assistant configuration. Create that directory if it does not exist.
2. Restart Home Assistant.

## Configuration

There is no configuration UI. Add this to `configuration.yaml` and restart:

```yaml
sensor:
  - platform: heathrow_arrivals
```

The integration has no Python dependencies and needs no API key.

## Attributes

`sensor.heathrow_arrival_rwy` carries the full picture:

| Attribute | Example | Notes |
| -- | -- | -- |
| `source` | `atis.guru` | Or `metar+schedule` when no recent ATIS was available |
| `runways` | `["27R"]` | The state as a list |
| `planned_runways` | `["27R"]` | What the programme expected |
| `matches_plan` | `true` | Whether actual and planned agree |
| `marginal` | `false` | The state is a toss-up — see [Marginal winds](#marginal-winds) |
| `wind_marginal` | `false` | The wind alone is a toss-up, whatever the source |
| `westerly_tailwind_kt` | `-1` | Tailwind landing westerly; negative is a headwind |
| `mode` | `Westerly` | `Westerly` or `Easterly` |
| `period` | `morning` | `early morning`, `morning`, `afternoon` or `night` |
| `atis_letter` | `B` | The ATIS information letter |
| `atis_issued` | `2026-09-23T06:24:00Z` | When the ATIS was collected |
| `atis_age_minutes` | `17` | Ignored as stale beyond 90 minutes |
| `atis_runways` | `["27R"]` | The ATIS runway even when it was too old to use |
| `atis` | `EGLL ARR ATIS B ...` | The full ATIS text |
| `alternation_week` | `2026-09-21` | Monday of the alternation week in use |
| `alternation_scheduled` | `true` | `false` if the date is not in the published programme |
| `wind_direction` | `170` | Degrees true; `null` when calm or variable |
| `wind_speed_kt` / `wind_gust_kt` | `4` | Knots |
| `wind_variable` | `false` | True when the wind is reported `VRB` |
| `wind_variable_from` / `wind_variable_to` | `130` / `230` | From a `130V230` group |
| `headwind_kt` | `-1` | On the runway in use; negative is a tailwind |
| `crosswind_kt` / `crosswind_from` | `4` / `L` | Side as seen landing |
| `observation_time` | `2026-09-23T06:20:00Z` | When the METAR was issued |
| `metar` | `METAR EGLL 230620Z ...` | The raw observation |

`sensor.heathrow_planned_arrival_rwy` carries `mode`, `period`, `marginal`, `westerly_tailwind_kt` and the alternation fields. The three week sensors carry `alternation_week` plus the runways for their period (`day_morning_runway`, `day_afternoon_runway`, `night_primary_runway`, `night_alternative_runway`).

## How the runway is chosen

**From the ATIS.** If atis.guru has an EGLL arrival ATIS under 90 minutes old naming a landing runway, it is used and nothing below applies. A stale ATIS is ignored rather than trusted, but is still reported in `atis_runways` so you can see it.

**Direction.** Heathrow runs westerly whenever it reasonably can — arrivals over London, departures out west — and only turns round once the tailwind component on runway 27 exceeds about 5 knots. Calm and variable winds stay westerly. Westerly operations account for roughly 70% of the year.

**Which runway.** On westerlies the alternation programme applies: one runway lands from 06:00 to 15:00, the other from 15:00 until the last departure, swapping week by week. Both runways take arrivals between 06:00 and 07:00, the busiest arrivals hour. At night a four-weekly cycle picks a single strip and the wind decides which end of it is used; flights before 06:00 on a Monday still follow the previous week's pattern.

**On easterlies** there is no day-time alternation: the Cranford Agreement keeps departures off the northern runway, so `09L` lands and `09R` departs all day.

### Marginal winds

`marginal` is `true` when the state should be treated as soft: the direction was computed from a wind sitting within 2 knots of the 5-knot switch threshold, where Heathrow's own decision also weighs forecast trend and runway wetness.

`marginal` is always `false` when the ATIS supplied the runway, because that is an observation rather than an inference. `wind_marginal` reports the wind on its own regardless of source, so it still flags a possible switch while the ATIS is being used.

When `marginal` is `true`, the useful response is usually to wait rather than act: the next METAR is at most half an hour away and will normally settle it.

A worked example — tell me when the runway actually changes, but not on a wind that may flip straight back:

```yaml
automation:
  - alias: Heathrow arrival runway changed
    triggers:
      - trigger: state
        entity_id: sensor.heathrow_arrival_rwy
    conditions:
      # A restart or a failed fetch is not a runway change.
      - condition: template
        value_template: >
          {{ trigger.from_state.state not in ['unknown', 'unavailable']
             and trigger.to_state.state not in ['unknown', 'unavailable']
             and trigger.from_state.state != trigger.to_state.state }}
      # Hold off while the wind is sitting on the switch threshold.
      - condition: template
        value_template: "{{ not state_attr('sensor.heathrow_arrival_rwy', 'marginal') }}"
    actions:
      - action: notify.mobile_app_your_phone
        data:
          message: >
            Heathrow now landing {{ trigger.to_state.state }}
            ({{ state_attr('sensor.heathrow_arrival_rwy', 'mode') }},
            from {{ state_attr('sensor.heathrow_arrival_rwy', 'source') }})
```

Drop the second condition if you would rather hear about every change and judge for yourself.

### Spotting the airport running off plan

Compare actual against planned, or read the `matches_plan` attribute, which says the same thing:

```yaml
{{ states('sensor.heathrow_arrival_rwy') != states('sensor.heathrow_planned_arrival_rwy') }}
```

Heathrow notes that it cannot always adhere to the programme — delays put arrivals out of the alternation pattern, and bad weather or runway works can suspend it altogether.

## Accuracy

With a fresh ATIS the runway is observed, not inferred, and should be right.

On the fallback it is an inference, and usually a good one, but it cannot see tactical changes — most notably arrivals being taken on the departure runway when arrivals are running late. Other soft spots:

- the 5-knot switch threshold approximates a judgement call that also weighs forecast trend and runway wetness, which is what `marginal` flags;
- the day/night boundary is fixed at 23:00, while the programme's is "the last departure", which delays can push later;
- Heathrow's published runway works can deviate from the programme, particularly at night.

## Maintenance

### Updating the alternation programme

Heathrow publishes a new programme each year. The current table ships as `custom_components/heathrow_arrivals/runway_alternation_2026.json`. To add a year, run the converter against the published PDF:

```bash
python3 scripts/build_alternation_table.py ~/Downloads/Heathrow_Runway_Alternation_Programme_2027.pdf
```

It validates the parse before writing — 52 contiguous Monday weeks per page, a day-time pair that swaps every week, and a night alternative that is the primary runway's other end — then writes `runway_alternation_<year>.json` beside the existing one. Every year present is loaded, so nothing else needs changing. Requires `pdftotext` (poppler).

Outside any year it has data for, the integration falls back to reporting both runways for the current direction and sets `alternation_scheduled` to `false`.

### Brand icon

Since Home Assistant 2026.3 a custom integration ships its own brand images, so the icon lives at `custom_components/heathrow_arrivals/brand/icon.png` (plus an `@2x` version) rather than in the [home-assistant/brands](https://github.com/home-assistant/brands) repository. Regenerate with `python3 scripts/build_brand_icon.py` (requires Pillow).

## Related

- [Home Assistant Flightradar24](https://github.com/AlexandrErohin/home-assistant-flightradar24) — count aircraft over your location; pair it with a Utility Meter helper for incremental counts.
- [Heathrow Landings](https://github.com/anthonyjhicks/heathrow-landings) — an earlier integration of mine carrying the 2024 schedule only. The `Planned Rwy` sensors here supersede it.

## Credits

- D-ATIS republished by [atis.guru](https://atis.guru/)
- METAR from [aviationweather.gov](https://aviationweather.gov/) (NOAA/NWS)
- Runway alternation programme published by [Heathrow](https://www.heathrow.com/)

## Issues

Please report any [issues](https://github.com/anthonyjhicks/heathrow-arrivals/issues).

***

[buymecoffee]: https://www.buymeacoffee.com/anthonyjhicks
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
[commits-shield]: https://img.shields.io/github/commit-activity/y/anthonyjhicks/heathrow-arrivals.svg?style=for-the-badge
[commits]: https://github.com/anthonyjhicks/heathrow-arrivals/commits/main
[license-shield]: https://img.shields.io/github/license/anthonyjhicks/heathrow-arrivals.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-Anthony%20Hicks%20%40anthonyjhicks-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/anthonyjhicks/heathrow-arrivals.svg?style=for-the-badge
[releases]: https://github.com/anthonyjhicks/heathrow-arrivals/releases
