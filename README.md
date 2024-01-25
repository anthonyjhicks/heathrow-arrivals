# Heathrow Arrival Runway
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/integration)

Home Assistant sensor indicating the current active Arrival runway at London Heathrow Airport according to the EGLL ATIS. Ideal for use if you live in the Heathrow flight path and want to be to able to track if aircraft are likely to be flying over your location for display on your Dashboard or perhaps linked to an automation.

I recommend combining this with my [Heathrow Landings](http://github.com/anthonyjhicks/heathrow-landings) integration to also obtain three additional sensors showing scheduled runway usage, giving you a full view of arrival flight paths for the morning, afternoon and night.

You could also add this superb [Home Assistant Flightradar24](https://github.com/AlexandrErohin/home-assistant-flightradar24) integration to count the number of aircraft flying over your location (combine it with the Utility Meter Helper to get the incremental counts you need).

## Installation

### HACS (recommended)

Have [HACS](https://hacs.xyz/) installed, this will allow you to update easily.

1. Go to the <b>HACS</b>-><b>Integrations</b>.
2. Add this repository (https://github.com/anthonyjhicks/heathrow-arrival-rwy) as a [custom repository](https://hacs.xyz/docs/faq/custom_repositories/)
3. Click on `+ Explore & Download Repositories`.
4. Search for `Heathrow Arrival Runway`. 
5. Navigate to `Heathrow Arrival Runway` integration 
6. Press `DOWNLOAD` and in the next window also press `DOWNLOAD`. 
7. After download, restart Home Assistant.

### Manual

1. Locate the `custom_components` directory in your Home Assistant configuration directory. It may need to be created.
2. Copy the `custom_components/heathrow_arrival_rwy` directory into the `custom_components` directory.
3. Restart Home Assistant.

## Configuration

There is no configuration UI.  You must add the following to the sensor section of your configuration.yaml and restart Home Assistant:

```markdown
sensor:
  - platform: heathrow_arrival_rwy
```

## Usage

This will create three sensors you can use in your Dashboards, Automations etc.

| Entity | Name | State | Attributes |
| -- | -- | -- | -- |
| sensor.heathrow_landings_0600_1500 | Heathrow Landings 0600-1500 | 27L | friendly_name: Heathrow Landings 0600-1500 |
| sensor.heathrow_landings_1500 | Heathrow Landings 1500 | 27R * |	friendly_name: Heathrow Landings 1500 | 
| sensor.heathrow_night | Heathrow Night | 27L * | friendly_name: Heathrow Night |

## Issues

Please report any [Issues](http://github.com/anthonyjhicks/heathrow-landings/issues)
