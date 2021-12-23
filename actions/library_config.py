"""
file storing library constant settings
"""

from datetime import time, date

USER_ID = 1

MAX_BOOK = 15

# response needs AM PM
OPEN_HOURS = {
    "monday" : [(time(5,0),time(7,0)), (time(8, 0), time(23,45))],
    "tuesday" : [(time(8, 0), time(23,45))],
    "wednesday": [(time(8, 0), time(23,45))],
    "thursday": [(time(8, 0), time(23,45))],
    "friday": [(time(8, 0), time(23,45))],
    "saturday": [(time(8, 0), time(23,45))],
    "sunday": [(time(14, 0), time(20,45))]
}

YEAR = 2021

YEARLY_HOLIDAYS = (
    date(YEAR, 12, 24),
    date(YEAR, 12, 25),
    date(YEAR, 12, 26),
    date(YEAR, 12, 31),
    date(YEAR+1, 1,1),
    date(YEAR+1,1,2),
    date(YEAR+1,1,6)
)

LOCATION = "Via Adalberto Libera, 3 - 38122 Trento, Italy"

EMAIL = "my_library@gmail.com"

PHONE = "39-0461-283011"