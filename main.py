"""Check if it is bin day, and what bin needs taking out."""

import enum
import os
from dataclasses import dataclass
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv


load_dotenv()

STREET_ID = os.getenv("STREET_ID")
STREET_NAME = os.getenv("STREET_NAME")

URL = (
    "https://wellington.govt.nz/rubbish-recycling-and-waste"
    "/when-to-put-out-your-rubbish-and-recycling/components"
    "/collection-search-results"
)

BIN_COLLECTION_TIME = 7  # 7.00 AM


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


def main() -> int:
    if not all(env for env in (STREET_ID, STREET_NAME)):
        raise RuntimeError("Make sure STREET_ID and STREET_NAME are defined!")

    rubbish_day = query_rubbish_day()
    print(rubbish_day)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())