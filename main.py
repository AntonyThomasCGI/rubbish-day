"""Check if it is bin day, and what bin needs taking out."""

import enum
import os
import time
from dataclasses import dataclass
from datetime import datetime

from bs4 import BeautifulSoup
import dotenv
import gpiozero
import requests


dotenv.load_dotenv()

STREET_ID = os.getenv("STREET_ID")
STREET_NAME = os.getenv("STREET_NAME")

URL = (
    "https://wellington.govt.nz/rubbish-recycling-and-waste"
    "/when-to-put-out-your-rubbish-and-recycling/components"
    "/collection-search-results"
)

BIN_COLLECTION_TIME = 7  # 7.00 AM

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
        self.red_led = gpiozero.LED(GPIO_PIN_RED)
        self.green_led = gpiozero.LED(GPIO_PIN_GREEN)
    
    def all_off(self):
        self.red_led.off()
        self.green_led.off()

    def turn_red(self):
        if not self.red_led.is_lit:
            self.red_led.on()
        if self.green_led.is_lit:
            self.green_led.off()
    
    def turn_green(self):
        if self.red_led.is_lit:
            self.red_led.off()
        if not self.green_led.is_lit:
            self.green_led.on()

    def turn_orange(self):
        if not self.red_led.is_lit:
            self.red_led.on()
        if not self.green_led.is_lit:
            self.green_led.on()


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

    if Bin.RECYCLING_BAG in rubbish_day.bins:
        led_controller.turn_red()
    elif Bin.GLASS_CRATE in rubbish_day.bins:
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

    time.sleep(5)

    return 0 if changed else 1


if __name__ == "__main__":
    raise SystemExit(main())
