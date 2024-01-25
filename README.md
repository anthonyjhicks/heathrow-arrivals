# Heathrow Arrivals
[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

![Project Maintenance][maintenance-shield]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

Home Assistant sensor indicating the current active Arrival runway at London Heathrow Airport according to the EGLL ATIS. Ideal for use if you live in the Heathrow flight path and want to be to able to track if aircraft are likely to be flying over your location for display on your Dashboard or perhaps linked to an automation.

I recommend combining this with my [Heathrow Landings](http://github.com/anthonyjhicks/heathrow-landings) integration to also obtain three additional sensors showing scheduled runway usage, giving you a full view of arrival flight paths for the morning, afternoon and night.

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
  - platform: heathrow_arrival_rwy
```

## Usage

This will create a sensor you can use in your Dashboards, Automations etc.

| Entity | Name | State | Attributes |
| -- | -- | -- | -- |
| sensor.heathrow_arrival_rwy | Heathrow Arrival Rwy | 27L | friendly_name: Heathrow Arrival Rwy |

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
