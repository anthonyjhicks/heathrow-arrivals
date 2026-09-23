# Heathrow Arrivals
[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

![Project Maintenance][maintenance-shield]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

Home Assistant sensor indicating the current active Arrival runway at London Heathrow Airport. Ideal for use if you live in the Heathrow flight path and want to be to able to track if aircraft are likely to be flying over your location for display on your Dashboard or perhaps linked to an automation.

It provides both the **actual** arrival runway and the **planned** one, so you can see when Heathrow is running off its published schedule - delays, bad weather and runway works all push arrivals out of the alternation pattern.

Three published sources are used:

* **[atis.guru](https://atis.guru/atis/EGLL)** republishes the real EGLL D-ATIS collected off ACARS. When it has a recent report this is ground truth - the airport itself saying what is landing;
* the **EGLL METAR** from [aviationweather.gov](https://aviationweather.gov/), whose reported wind decides whether Heathrow is landing westerly (arrivals over London) or easterly;
* Heathrow's **annual runway alternation programme**, which says which of the parallel pair is planned to take the arrivals in each period of each week.

The ATIS is preferred; when no recent one is available the wind and the programme are used instead, so the sensor degrades rather than going dark. The `source` attribute tells you which was used.

The `Planned Rwy` sensors below supersede my earlier [Heathrow Landings](http://github.com/anthonyjhicks/heathrow-landings) integration, which carried the same schedule for 2024 only. If you run both, this one is the current source.

You could also add this superb [Home Assistant Flightradar24](https://github.com/AlexandrErohin/home-assistant-flightradar24) integration to count the number of aircraft flying over your location (combine it with the Utility Meter Helper to get the incremental counts you need).

## Installation

### HACS (recommended)

Have [HACS](https://hacs.xyz/) installed, this will allow you to update easily.

1. Go to the <b>HACS</b>-><b>Integrations</b>.
2. Add this repository (https://github.com/anthonyjhicks/heathrow-arrivals) as a [custom repository](https://hacs.xyz/docs/faq/custom_repositories/)
3. Click on `+ Explore & Download Repositories`.
4. Search for `Heathrow Arrivals`. 
5. Navigate to `Heathrow Arrivals` integration 
6. Press `DOWNLOAD` and in the next window also press `DOWNLOAD`. 
7. After download, restart Home Assistant.

### Manual

1. Locate the `custom_components` directory in your Home Assistant configuration directory. It may need to be created.
2. Copy the `custom_components/heathrow_arrivals` directory into the `custom_components` directory.
3. Restart Home Assistant.

## Configuration

There is no configuration UI.  You must add the following to the sensor section of your configuration.yaml and restart Home Assistant:

```markdown
sensor:
  - platform: heathrow_arrivals
```

## Usage

This will create five sensors you can use in your Dashboards, Automations etc.

| Entity | Name | State | What it tells you |
| -- | -- | -- | -- |
| sensor.heathrow_arrival_rwy | Heathrow Arrival Rwy | 27R | **Actual** - from the ATIS, or computed if none is recent |
| sensor.heathrow_planned_arrival_rwy | Heathrow Planned Arrival Rwy | 27R | **Planned** - the programme for right now, given the wind |
| sensor.heathrow_planned_rwy_0600_1500 | Heathrow Planned Rwy 0600-1500 | 27R | This week's morning runway |
| sensor.heathrow_planned_rwy_1500 | Heathrow Planned Rwy 1500 | 27L | This week's afternoon runway |
| sensor.heathrow_planned_rwy_night | Heathrow Planned Rwy Night | 09R | This week's night runway |

States are runway designators: `09L`, `09R`, `27L` or `27R`. The first two are `27L/27R` between 06:00 and 07:00, when Heathrow lands on both runways.

Compare the first two to spot the airport running off plan:

```yaml
{{ states('sensor.heathrow_arrival_rwy') != states('sensor.heathrow_planned_arrival_rwy') }}
```

or use the `matches_plan` attribute, which says the same thing.

The three `Planned Rwy` sensors need no network and stay available even when both feeds are down. `Heathrow Arrival Rwy` and `Heathrow Planned Arrival Rwy` go `unavailable` only if neither the ATIS nor the METAR can be read.

### Attributes

`Heathrow Arrival Rwy` carries the full picture:

| Attribute | Example | Notes |
| -- | -- | -- |
| `source` | `atis.guru` | Or `metar+schedule` when no recent ATIS was available |
| `runways` | `["27R"]` | The state as a list |
| `planned_runways` | `["27R"]` | What the programme expected |
| `matches_plan` | `true` | Whether actual and planned agree |
| `marginal` | `false` | The state is a toss-up - see below |
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

`Heathrow Planned Arrival Rwy` carries `mode`, `period`, `marginal`, `westerly_tailwind_kt` and the alternation fields. The three week sensors carry `alternation_week` plus the runways for their period (`day_morning_runway`, `day_afternoon_runway`, `night_primary_runway`, `night_alternative_runway`).

### Marginal winds

`marginal` is `true` when the state should be treated as soft: the direction was computed from a wind sitting within 2 knots of the 5-knot switch threshold, where Heathrow's own decision also weighs forecast trend and runway wetness. Use it to hold off on acting:

```yaml
{{ is_state('sensor.heathrow_arrival_rwy', '27R')
   and not state_attr('sensor.heathrow_arrival_rwy', 'marginal') }}
```

`marginal` is always `false` when the ATIS supplied the runway, because that is an observation rather than an inference. `wind_marginal` reports the wind on its own regardless of source, so it still flags a possible switch while the ATIS is being used.

## How the runway is chosen

**From the ATIS.** If atis.guru has an EGLL arrival ATIS less than 90 minutes old naming a landing runway, that is used directly and nothing below applies. A stale ATIS is ignored rather than trusted - it is still reported in `atis_runways` so you can see it.

**Direction.** Heathrow runs westerly whenever it reasonably can, and only turns round once the tailwind component on runway 27 exceeds about 5 knots. Calm and variable winds stay westerly. Westerly operations account for roughly 70% of the year. Close to that threshold the call is genuinely uncertain, which is what `marginal` flags.

**Which runway.** On westerlies the alternation programme applies: one runway lands from 06:00 to 15:00, the other from 15:00 until the last departure, swapping week by week. Both runways take arrivals between 06:00 and 07:00, the busiest arrivals hour. At night a four-weekly cycle picks a single strip, and the wind decides which end of it is used. Flights before 06:00 on a Monday still follow the previous week's night pattern.

On easterlies there is no day-time alternation: the Cranford Agreement keeps departures off the northern runway, so `09L` lands and `09R` departs all day.

Heathrow notes that it cannot always adhere to the programme - delays can put arrivals out of the alternation pattern, and bad weather or runway works can suspend it altogether. That is exactly what the `Planned` sensors are for: when `Heathrow Arrival Rwy` disagrees with `Heathrow Planned Arrival Rwy`, the airport is off plan.

When no recent ATIS is available the computed answer is an inference, not an observation. It is usually right, but it cannot see tactical changes - most notably arrivals being taken on the departure runway when arrivals are running late.

### Brand icon

Since Home Assistant 2026.3 a custom integration ships its own brand images, so the icon lives at `custom_components/heathrow_arrivals/brand/icon.png` (plus an `@2x` version) rather than in the [home-assistant/brands](https://github.com/home-assistant/brands) repository. Regenerate it with `python3 scripts/build_brand_icon.py`.

### Updating the alternation programme

The schedule ships as `custom_components/heathrow_arrivals/runway_alternation_2026.json`. Heathrow publishes a new programme each year; to add one, drop a `runway_alternation_<year>.json` file alongside it in the same format and restart Home Assistant. Outside any year it has data for, the sensor falls back to reporting both runways for the current direction and sets `alternation_scheduled` to `false`.

## Issues

Please report any [Issues](http://github.com/anthonyjhicks/heathrow-arrival-rwy/issues)

***

[heathrow-landings]: https://github.com/anthonyjhicks/heathrow-arrivals
[buymecoffee]: https://www.buymeacoffee.com/anthonyjhicks
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
[commits-shield]: https://img.shields.io/github/commit-activity/y/anthonyjhicks/heathrow-arrivals.svg?style=for-the-badge
[commits]: https://github.com/anthonyjhicks/heathrow-arrivals/commits/main
[exampleimg]: example.png
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/
[license-shield]: https://img.shields.io/github/license/anthonyjhicks/heathrow-arrivals.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-Anthony%20Hicks%20%40anthonyjhicks-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/anthonyjhicks/heathrow-arrivals.svg?style=for-the-badge
[releases]: https://github.com/anthonyjhicks/heathrow-arrivals/releases
