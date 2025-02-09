"""Check if it is bin day, and what bin needs taking out."""

import enum
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

import dotenv
import requests
from RPi import GPIO
from bs4 import BeautifulSoup


dotenv.load_dotenv()

STREET_ID = os.getenv("STREET_ID")
STREET_NAME = os.getenv("STREET_NAME")

URL = (
    "https://wellington.govt.nz/rubbish-recycling-and-waste"
    "/when-to-put-out-your-rubbish-and-recycling/components"
    "/collection-search-results"
)

BIN_COLLECTION_TIME = 7  # 7.00 AM
REMIND_HOURS_BEFORE = 16

GPIO_PIN_RED = 17
GPIO_PIN_GREEN = 27


class Bin(enum.Enum):
    RUBBISH = 0
    GLASS_CRATE = 1
    RECYCLING_BAG = 2


@dataclass
class RubbishDay:
    """RubbishDay is a dataclass for storing the next rubbish day
    date, and bin types.
    """

    date: datetime
    bins: list[Bin]


class LEDController:
    """LEDController provides methods for setting a 3-color LED bulb."""

    def __init__(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(GPIO_PIN_RED, GPIO.OUT)
        GPIO.setup(GPIO_PIN_GREEN, GPIO.OUT)

    def turn_off(self):
        GPIO.output(GPIO_PIN_RED, GPIO.LOW)
        GPIO.output(GPIO_PIN_GREEN, GPIO.LOW)

    def turn_red(self):
        GPIO.output(GPIO_PIN_RED, GPIO.HIGH)
        GPIO.output(GPIO_PIN_GREEN, GPIO.LOW)

    def turn_green(self):
        GPIO.output(GPIO_PIN_RED, GPIO.LOW)
        GPIO.output(GPIO_PIN_GREEN, GPIO.HIGH)

    def turn_orange(self):
        GPIO.output(GPIO_PIN_RED, GPIO.HIGH)
        GPIO.output(GPIO_PIN_GREEN, GPIO.HIGH)


def parse_response(html: bytes) -> RubbishDay:
    """Parses a raw html response to extract relevant bin information.
    """
    collection_date_class = ("p", "collection-date")
    collection_items_class = ("ul", "collection-items")

    soup = BeautifulSoup(html, "html.parser")

    collection_date_content = soup.find(
        collection_date_class[0],
        attrs={"class": collection_date_class[1]},
    )
    if not collection_date_content:
        raise ValueError("Could not find collection date in response!")

    collection_items_content = soup.find(
        collection_items_class[0],
        attrs={"class": collection_items_class[1]},
    )
    if not collection_items_content:
        raise ValueError("Could not find collection items in response!")

    date_time_raw = collection_date_content.text.replace('\n', '').replace(' ', '').strip('\r')
    date_raw = date_time_raw.split('(')[0]
    parsed_bin_date = datetime.strptime(date_raw, r'%A,%d%B')
    bin_date = datetime(datetime.now().year, parsed_bin_date.month, parsed_bin_date.day, BIN_COLLECTION_TIME)

    collection_items = []
    collection_map = {
        'Rubbish': Bin.RUBBISH,
        'Glass crate': Bin.GLASS_CRATE,
        'Wheelie bin or recycling bags': Bin.RECYCLING_BAG,
    }
    for li_item in collection_items_content.find_all('li'):
        bin_type = collection_map.get(li_item.text)
        if not bin_type:
            raise AttributeError("Unknown bin type: {}".format(bin_type))
        collection_items.append(bin_type)

    return RubbishDay(date=bin_date, bins=collection_items)


def query_rubbish_day() -> RubbishDay:
    """Query wellington council API for bin data."""
    params = {
        "streetId": STREET_ID,
        "streetName": STREET_NAME,
    }

    headers = {
        "Content-Length": "0",
        "Content-Type": "application/json",
        "Accept": "application/json, application/xml, */*",
    }

    response = requests.post(URL, headers=headers, params=params)
    if not response.ok:
        raise RuntimeError("Response not ok! {}".format(response.content))

    return parse_response(response.content)


def set_led_appropriately(rubbish_day: RubbishDay) -> bool:
    """Set LED light color based on bin type."""
    led_controller = LEDController()
    led_controller.turn_off()

    time_until_bin = rubbish_day.date - datetime.now()
    if time_until_bin > timedelta(hours=REMIND_HOURS_BEFORE):
        print('Bin day is still a way away')
        return False

    if Bin.RECYCLING_BAG in rubbish_day.bins:
        led_controller.turn_red()
        print('Take recycling bag out!')
    elif Bin.GLASS_CRATE in rubbish_day.bins:
        print('Take glass crate out!')
        led_controller.turn_green()
    else:
        raise AssertionError("Unreachable")

    return True


def main() -> int:
    """Main."""
    if not all(env for env in (STREET_ID, STREET_NAME)):
        raise RuntimeError("Make sure STREET_ID and STREET_NAME are defined!")

    rubbish_day = query_rubbish_day()
    changed = set_led_appropriately(rubbish_day)

    return 0 if changed else 1


if __name__ == "__main__":
    raise SystemExit(main())
