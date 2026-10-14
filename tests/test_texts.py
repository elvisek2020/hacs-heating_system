"""Times in sentences: "v 5:30", "zítra v 5:30", "ve čtvrtek do 5:30"."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.hydronic_heating.explain import DAYS, MARK, clock, finish, moment


def _at(days: int, hour: int, minute: int, second: int = 0):
    """Local time `days` from today."""
    today = dt_util.now().replace(hour=hour, minute=minute, second=second, microsecond=0)
    return today + timedelta(days=days)


async def test_czech_days_go_before_the_preposition(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    hass.config.language = "cs"
    freezer.move_to(_at(0, 11, 0))  # a Wednesday
    preheat = f"Od {moment(_at(1, 3, 18))} předtápění: Kuchyně (komfort v {moment(_at(1, 5, 30))})."
    assert finish(hass, preheat) == "Zítra od 3:18 předtápění: Kuchyně (komfort zítra v 5:30)."
    schedule = f"V {moment(_at(1, 5, 30))} komfort podle rozvrhu: Kuchyně."
    assert finish(hass, schedule) == "Zítra v 5:30 komfort podle rozvrhu: Kuchyně."
    # Today: no day, hours without the leading zero, seconds for the boiler.
    assert finish(hass, f"Kotel zapne v {clock(_at(0, 13, 5, 7))}.") == "Kotel zapne v 13:05:07."
    assert finish(hass, f"Start nejdříve v {clock(_at(0, 9, 5))}.") == "Start nejdříve v 9:05:00."
    # Later this week the day, then the date; a sentence without a preposition gets "v".
    in_two_days = DAYS["cs"][_at(2, 0, 0).weekday()]
    assert finish(hass, f"Útlum do {moment(_at(2, 5, 30))}.") == f"Útlum {in_two_days} do 5:30."
    far = _at(10, 5, 30)
    assert finish(hass, f"Návrat {moment(far)}.") == f"Návrat {far.day}. {far.month}. v 5:30."
    assert finish(hass, f"Návrat {moment(_at(1, 5, 30))}.") == "Návrat zítra v 5:30."
    assert finish(hass, f"Návrat {moment(_at(0, 17, 0))}.") == "Návrat v 17:00."
    assert MARK not in finish(hass, f"do {moment(_at(3, 6, 0))} a od {clock(_at(0, 6, 0))}")


async def test_english_days_follow_the_time(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    hass.config.language = "en"
    freezer.move_to(_at(0, 11, 0))
    assert finish(hass, f"At {moment(_at(1, 5, 30))} comfort by schedule.") == (
        "At 5:30 tomorrow comfort by schedule."
    )
    assert finish(hass, f"Back {moment(_at(1, 5, 30))}.") == "Back at 5:30 tomorrow."
    assert finish(hass, f"It stops at {clock(_at(0, 7, 2, 9))}.") == "It stops at 7:02:09."
