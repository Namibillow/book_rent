from collections import defaultdict, namedtuple
import datetime as dt
import dateutil.parser
import itertools
import logging
import random
import sqlite3
from typing import Any, Text, Dict, List, Optional
import os

from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, FollowupAction, AllSlotsReset
from rasa_sdk.types import DomainDict

from . import library_config as config
from . import search

logger = logging.getLogger(__name__)

dir_path = os.path.dirname(os.path.realpath(__file__))

def format_opentime(open_hours):
    """Format the opening hours into strings.
    :params
        open_hours: list of datetime.date
    :return
        hour_min_str: str of formatted time
    """
    hour_min_str = "from "

    for begin_time, end_time in open_hours[:-1]:
        bt = format_time(begin_time)
        et = format_time(end_time)
        hour_min_str += f"{bt} to {et}, "

    bt = format_time(open_hours[-1][0])
    et = format_time(open_hours[-1][1])

    if hour_min_str != "from ":
        hour_min_str += "and then "
    hour_min_str += f"{bt} to {et}"
    return hour_min_str

def format_time(time):
    """Format the given time into string
    :params
        time: datetime.time

    :return
        string of formatted time
    """
    return '{0:%-I} {0:%M}{0:%p}'.format(time) if time.minute != 0 else '{0:%-I}{0:%p}'.format(time)

def get_suffix(day):
    """Get the corresponding suffix given a day 
    :params
        day: int 
    :returns
        suffix: str
    """
    if 4 <= day <= 20 or 24 <= day <= 30:
        suffix = "th"
    else:
        suffix = ["st", "nd", "rd"][day % 10 - 1]
    return suffix

def format_query_list(lenl, query):
    """Format a query with appropriate number of placeholders for parameters
    :params
        lenl: int length for how many placeholder to be placed
        query: str of sqlite query 
    :return
        formatted_query: str of sqlite query 
    """
    placeholder = '?'  
    placeholders = ', '.join([placeholder]*lenl)
    formatted_query = query % placeholders
    return formatted_query

def find_next_open_date(next_open_day):
    """Fine next open dates for a given date
    :params
        next_open_day: datetime.date 
    :return
        day_of_week: str
        new_open_hours: list of tuple
        month: str
        day: int
        year: int
    """
    while next_open_day in config.YEARLY_HOLIDAYS:
        next_open_day += dt.timedelta(days=1)
    day_of_week = next_open_day.strftime('%A').lower()
    new_open_hours = config.OPEN_HOURS[day_of_week]
    month = next_open_day.strftime("%B").lower()
    day = next_open_day.day
    year = next_open_day.year 
    return (day_of_week, new_open_hours, month, day, year)

def create_connection(db_file):
    """Create a database connection to the SQLite database
        specified by the db_file
    :param 
        db_file: database file
    :return: 
        Connection object or None
    """
    db = None
    try:
        db = sqlite3.connect(db_file)
    except Error as e:
        logger.debug(e)

    return db

def get_overlapped_names(book_title_index, book_authors_indexes, book_authors):
    """Get the name overlaps
    :params
        book_title_index: int
        book_authors_indexes: list of int
        book_authors: list of str
    :return
        overlapped_authors: list of str
    """
    overlapped_authors = []
    for i, aindex in enumerate(book_authors_indexes):
        astart, aend = aindex
        bstart, bend = book_title_index
        if bstart <= astart <= aend <= bend:
            overlapped_authors.append(book_authors[i])
    return overlapped_authors

class ActionTellTime(Action):
    """Tell the opening/closing time of the library."""
    def name(self):
        return "action_tell_opentime"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        logger.debug(f"naamtokyam: action_tell_opentime is called.")

        datetime = next(tracker.get_latest_entity_values('time'), "")
        logger.debug(f"naamtokyam: action_tell_opentime: setting datetime to {datetime}")
        if datetime:
            datetime_obj = dateutil.parser.parse(datetime)
            day_of_week = datetime_obj.strftime('%A').lower()
            month = datetime_obj.strftime("%B").lower()
            day = datetime_obj.day
            hour = datetime_obj.hour
            minuite = datetime_obj.minute
            year = datetime_obj.year
            hour_minuite = datetime_obj.time()

            logger.debug(f"""naamtokyam: action_tell_opentime: given datetime info
                            (day_of_week: {day_of_week}),  
                            (month: {month}), 
                            (day: {str(day)}), 
                            (hour: {str(hour)}), 
                            (minuite: {str(minuite)}), 
                            (year: {str(year)})""")

            # check relativness if we could store. eg. today, tomorrow, yesterday
            today = dt.datetime.today().date()
            requested_day = datetime_obj.date()

            logger.debug(
                f"naamtokyam: action_tell_opentime: diff calculated: {today} - {requested_day} = {(today - requested_day).days}")
            diff = abs((today - requested_day).days)
            future = today <= requested_day

            relative_time = ""
            for delta, names in [(1, ["yesterday", "tomorrow"]), (2, ["the day before yesterday", "the day after tomorrow"])]:
                if diff == delta:
                    relative_time = names[future]

            verb_open = "open" if future else "opened"
            be_tense = "is" if future else "was"
            logger.debug(f"naamtokyam: action_tell_opentime: verb_open is {verb_open}, be_tense is {be_tense}")
            logger.debug(f"naamtokyam: action_tell_opentime: relative day is set as {relative_time}")

            # check if the date is open
            if requested_day in config.YEARLY_HOLIDAYS:
                # requested_day is library holiday
                dispatcher.utter_message(response="utter_specified_date_closed",
                                         be_tense=be_tense,
                                         day_of_week=day_of_week,
                                         month=month,
                                         day=day,
                                         year=year)

                # if the requested day was past, then return
                if not future:
                    return []

                # if future (including today) suggest next open day
                next_open_day_of_week, new_open_hours, next_open_month, next_open_day, next_open_year = find_next_open_date(requested_day)

                dispatcher.utter_message(response="utter_next_open_date",
                                         day_of_week=next_open_day_of_week,
                                         month=next_open_month,
                                         day=str(next_open_day),
                                         year=str(next_open_year),
                                         hour_min=format_opentime(new_open_hours))
            else:
                # requested_day is open
                open_hours = config.OPEN_HOURS[day_of_week]
                hour_min_str = format_opentime(open_hours)
                time_specified = bool(hour | minuite)
                # use numbers and time, check if number in numbers match with hour or min
                if time_specified:
                    # check hours if specified and within the opening range
                    if any([(hour_minuite >= begin_time and hour_minuite <= end_time) for begin_time, end_time in open_hours]):
                        # it is open
                        dispatcher.utter_message(response="utter_affirm_open",
                                                 verb_open=verb_open,
                                                 relative_time=relative_time,
                                                 day_of_week=day_of_week,
                                                 hour_min=hour_min_str)
                    else:
                        # it is closed
                        dispatcher.utter_message(response="utter_specified_date_time_closed",
                                                 be_tense=be_tense,
                                                 day_of_week=day_of_week,
                                                 month=month,
                                                 day=str(day),
                                                 year=str(year),
                                                 hour_min=format_time(hour_minuite))

                        # suggest next open date/hour
                        # first check if any hours open in same day
                        begin_time = None
                        end_time = None
                        found_next = False
                        for begin_time, end_time in open_hours:
                            if hour_minuite < begin_time:
                                found_next = True
                                break
                        logger.debug(f"naamtokyam: action_tell_opentime: found_next is set to {found_next}")
                        if not found_next:
                            logger.debug(f"naamtokyam: action_tell_opentime: finding new date")
                            next_open_day = requested_day
                            # then check holiday requirement for next day
                            next_open_day += dt.timedelta(days=1)
                            day_of_week, new_open_hours, month, day, year = find_next_open_date(next_open_day)

                        dispatcher.utter_message(response="utter_next_open_date",
                                                 day_of_week=day_of_week,
                                                 month=month,
                                                 day=str(day),
                                                 year=str(year),
                                                 hour_min=format_opentime([new_open_hours[0]]))
                else:
                    # just reply with date's open day
                    dispatcher.utter_message(response="utter_affirm_open",
                                             verb_open=verb_open,
                                             relative_time=relative_time,
                                             day_of_week=day_of_week,
                                             hour_min=hour_min_str)

        else:
            dispatcher.utter_message(response="utter_default_datetime")

        return []
 
class ActionTellContactInfo(Action):
    """Tell the requested contact info."""
    def name(self):
        return "action_tell_contact_info"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        slot_value = tracker.get_slot("contact_type")

        logger.debug(f"naamtokyam: action_tell_contact_info is called.")
        if slot_value == "phone":
            dispatcher.utter_message(response="utter_library_phone")
        elif slot_value == "email":
            dispatcher.utter_message(response="utter_library_email")

        return [SlotSet("contact_type", None), SlotSet("form_flag", True)]

class ValidateContactForm(FormValidationAction):
    """Validates slots of the validate_contact_form."""
    def name(self) -> Text:
        return "validate_contact_form"

    async def required_slots(
        self,
        slots_mapped_in_domain: List[Text],
        dispatcher: "CollectingDispatcher",
        tracker: "Tracker",
        domain: "DomainDict") -> Optional[List[Text]]:

        if tracker.get_intent_of_latest_message() == "terminate_conversation":
            logger.debug(f"naamyamtok: validate_contact_form hit the terminate_conversation")
            return []

        return slots_mapped_in_domain

    def validate_contact_type(
            self,
            slot_value: Any,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: DomainDict) -> Dict[Text, Any]:
        logger.debug(
            f"naamtokyam: validate_contact_form is called. slot_value is {slot_value}")

        if tracker.get_intent_of_latest_message() == "repeat_again": # slot_value should be None as only one message is followed before.
            dispatcher.utter_message(text="sure.")
        elif slot_value not in ["email", "phone"] and not tracker.get_slot("form_flag"):
            dispatcher.utter_message(
                text=f"Hmm I don't have that option... Could you say it again?")
            slot_value = None
        return {"contact_type": slot_value, "form_flag": False}

    # having this seem to prevent other intents to get triggered as i want to handle invalid input by the form and not trigger other intents
    async def extract_contact_type(
        self, dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict) -> Dict[Text, Any]:
        slot_value = tracker.get_slot("contact_type")
        logger.debug(
            f"naamtokyam: extract_contact_type is called. slot_value is {slot_value}")

        return {"contact_type" : slot_value}  
        
class ActionUserInventory(Action):
    """Check user inventory."""
    def name(self):
        return "action_user_inventory"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        logger.debug(f"naamtokyam: action_user_inventory is called")

        entities = tracker.latest_message['entities']
        book_authors = []
        book_authors_indexes = []
        book_titles = []
        book_title_index = ()
        # extract required entities (not using slots_mapping)
        for entity in entities:
            name = entity["entity"]
            value = entity["value"]
            if name == "PERSON":
                book_authors.append(value)
                book_authors_indexes.append((entity["start"], entity["end"]))
            elif name == "book_title":
                book_titles.append(value)
                book_title_index = (entity["start"], entity["end"])

        logger.debug(f"naamtokyam: action_user_inventory: Getting the info from entities: book_titles = {book_titles}, book_authors = {book_authors}")
        overlapped_authors = get_overlapped_names(book_title_index, book_authors_indexes, book_authors)
        if overlapped_authors:
            new_book_authors = []
            for name in book_authors:
                if name not in overlapped_authors:
                    new_book_authors.append(entity["value"])
            book_authors = new_book_authors
            logger.debug(f"naamtokyam: action_user_inventory: updated the book_authors to {book_authors}")

        if not book_titles and book_authors:
            logger.debug(f"naamtokyam: action_user_inventory: missing book title and only author is provided.")

        if book_titles and not book_authors:
            logger.debug(f"naamtokyam: action_user_inventory: missing author and only book title is provided.")

        if len(book_titles) > 1:
            logger.debug(f"naamtokyam: action_user_inventory: multiple books were detected: {book_titles}")
            dispatcher.utter_message(response="utter_multiple_search_not_supported")
            return []

        book_title = book_titles[0] if book_titles else ""
        intent = tracker.get_intent_of_latest_message()

        db = create_connection(os.path.join(dir_path, config.DATABASE))
        c = db.cursor()
        book_fts = search.FTS4SpellfixSearch(
            db, './spellfix', table_name="fts4_book")
        author_fts = search.FTS4SpellfixSearch(
            db, './spellfix', table_name="fts4_author")

        logger.debug(f"naamtokyam: action_user_inventory: current intent is: {intent}")

        if intent == "user_inventory_check_current_borrowing":
            self.check_current_borrowing(
                c, dispatcher, book_fts, author_fts, book_authors, book_title)
        elif intent == "user_inventory_check_remaining":
            self.check_remaining(c, dispatcher)
        elif intent == "user_inventory_check_return":
            self.check_return(c, dispatcher, book_fts,
                              author_fts, book_authors, book_title)

        db.close()

        return []

    def get_book_title_id(self, book_fts, book_title_wanted):
        """Given a book title user want, find corresponding book id 
        :params
            book_fts: db 
            book_title_wanted: str 
        :return
            int id if found else -1 
        """
        book_wanted = book_fts.search(book_title_wanted)["results"]
            # only take most relevant book_id
        return book_wanted[0][0] if book_wanted else -1 

    def get_book_authors_ids(self, author_fts, book_authors_wanted):
        """Given a list of author names user want, find corresponding author ids 
        :params
            author_fts: db 
            book_authors_wanted: list of str 
        :return
            list of int ids if found else [-1]
        """
        authors_wanted_ids = []
        for book_author_wanted in book_authors_wanted:
            author_wanted = author_fts.search(
                book_author_wanted)["results"]
            if author_wanted:
                # only keep first search result
                authors_wanted_ids.append(author_wanted[0][0])
        return authors_wanted_ids if authors_wanted_ids else [-1]

    def check_current_borrowing(self, c, dispatcher, book_fts, author_fts, book_authors_wanted, book_title_wanted=""):
        """Return user's currently borrowing books information."""
        slots_to_set = []
        logger.debug(f"naamtokyam: action_user_inventory - check_current_borrowing is called!")
        c.execute(
            '''SELECT book_id FROM user_book WHERE user_id = ?''', (config.USER_ID,))
        rows = c.fetchall()
        count = len(rows)
        logger.debug(
            f"naamtokyam: Given user id {config.USER_ID}, there are {count} books borrowed right now.")

        if count: # if borrowing
            book_wanted_id = self.get_book_title_id(book_fts, book_title_wanted)
            authors_wanted_ids = self.get_book_authors_ids(author_fts, book_authors_wanted)
            
            found_count = 0 # track how many exact results were found for given queries
            books_info_str = ""
            global_book_info_by_title = []
            global_book_info_by_author = []
            for i, row in enumerate(rows): # iterate current borrowings
                if i > 0 and i == len(rows)-1: # last book 
                    books_info_str += "and "
                # get a book information
                book_id = row[0]
                book_title = book_fts.search_by_rowid(book_id)[0]
                books_info_str += book_title + " by "
                logger.debug(f"naamyamtok: book_title is {book_title}")
                # get all authors' ids
                c.execute(
                    "SELECT author_id FROM book_authors WHERE book_id=?", (book_id,))
                author_ids = [aid[0] for aid in c.fetchall()]

                # get authors' name
                author_names = []
                author_id_match = False

                for j, author_id in enumerate(author_ids):
                    author_name = author_fts.search_by_rowid(author_id)[0]
                    logger.debug(
                        f"akazawan: author_id = {author_id}, author name = {author_name}")
                    author_names.append(author_name)
                    # as long as one author name matches, then mark as true
                    if book_authors_wanted and author_id in authors_wanted_ids:
                        author_id_match = True

                author_names_str = ' and '.join(author_names)

                book_id_match = book_wanted_id == book_id
                if book_id_match:
                    global_book_info_by_title.append(
                        (book_title, author_names_str))
                elif author_id_match:
                    global_book_info_by_author.append(
                        (book_title, author_names_str))

                if (book_id_match and author_id_match) or (book_id_match and not book_authors_wanted) or (author_id_match and not book_title_wanted):
                    if found_count == 0:
                        dispatcher.utter_message(
                            response="utter_yes_borrowing")
                    dispatcher.utter_message(
                        response="utter_book_is_borrowed", book_title=book_title, author_name=author_names_str)
                    found_count += 1

                books_info_str += author_names_str
                if len(rows) > 1:
                    books_info_str += ", "

            if (book_authors_wanted or book_title_wanted) and found_count == 0:
                # for the case if book title and author name were provided and one of them were no match
                if global_book_info_by_title or global_book_info_by_author:
                    dispatcher.utter_message(
                        response="utter_yes_borrowing")

                    global_book_info = []
                    if global_book_info_by_title:
                        global_book_info = global_book_info_by_title
                    else:
                        global_book_info = global_book_info_by_author

                    for book_title, author_names_str in global_book_info:
                        dispatcher.utter_message(
                            response="utter_book_is_borrowed", book_title=book_title, author_name=author_names_str)
                else:
                    dispatcher.utter_message(
                        response="utter_borrowed_book_no_match")
            elif found_count==0:
                dispatcher.utter_message(response="utter_user_inventory_tell_current_borrowing", num_books=str(
                    count), books_info=books_info_str)
        else:
            dispatcher.utter_message(
                response="utter_user_inventory_tell_no_borrowing")
    
    def check_remaining(self, c, dispatcher):
        """Return message with number of remaining books for user."""
        logger.debug(f"naamtokyam: action_user_inventory - check_remaining is called!")
        c.execute(
            '''SELECT COUNT(*) FROM user_book WHERE user_id = ?''', (config.USER_ID,))
        count = c.fetchone()
        if count:
            count = count[0]
        else:
            count = 0 

        logger.debug(f"naamtokyam: action_user_inventory - check_remaining: returned count for user {config.USER_ID}: {count}")

        remaining = config.MAX_BOOK-count
        if remaining:
            dispatcher.utter_message(
                response="utter_user_inventory_tell_remaining", num_books=str(remaining))
        else:
            dispatcher.utter_message(
                response="utter_user_inventory_tell_no_remaining")

    def check_return(self, c, dispatcher, book_fts, author_fts, book_authors_wanted, book_title_wanted=""):
        """Return user's return dates for the currently borrowing books."""
        logger.debug(f"naamtokyam: check_return is called!")
        c.execute(
            '''SELECT book_id, return_date FROM user_book WHERE user_id = ? AND is_returned = 0''', (config.USER_ID,))
        rows = c.fetchall()

        logger.debug(
            f"naamtokyam: Given user id {config.USER_ID}, there are {len(rows)} books borrowed right now.")

        if len(rows):
            book_wanted_id = self.get_book_title_id(book_fts, book_title_wanted)
            authors_wanted_ids = self.get_book_authors_ids(author_fts, book_authors_wanted)

            found_count = 0
            books_return_dates = ""
            global_book_info_by_title = []
            global_book_info_by_author = []
            for i, row in enumerate(rows):
                if i > 0 and i == len(rows)-1:
                    books_return_dates += "and "
                # get book information
                book_id = row[0]
                book_title = book_fts.search_by_rowid(book_id)[0]
                logger.debug(f"naamyamtok: book_title is {book_title}")
                # get all author's ids
                c.execute(
                    "SELECT author_id FROM book_authors WHERE book_id=?", (book_id,))
                author_ids = [aid[0] for aid in c.fetchall()]

                # get authors' name
                author_names = []
                author_id_match = False

                for j, author_id in enumerate(author_ids):
                    author_name = author_fts.search_by_rowid(author_id)[0]
                    logger.debug(
                        f"akazawan: author_id = {author_id}, author name = {author_name}")
                    author_names.append(author_name)
                    if book_authors_wanted and author_id in authors_wanted_ids:
                        author_id_match = True

                author_names_str = ' and '.join(author_names)

                # assuming return-date is formatted as mm/dd/YY
                month, day, year = row[1].split("/")
                month, day, year = int(month), int(day), int(year)
                date = dt.datetime(year, month, day)

                suffix = get_suffix(day)

                # prints "Monday March 3rd, 2022"
                book_return_str = book_title + " by " + author_names_str + \
                    " by " + date.strftime(f"%A %B %-d{suffix}, %Y")

                book_id_match = book_wanted_id == book_id
                if book_id_match:
                    global_book_info_by_title.append(book_return_str)
                elif author_id_match:
                    global_book_info_by_author.append(book_return_str)

                if (book_id_match and author_id_match) or (book_id_match and not book_authors_wanted) or (author_id_match and not book_title_wanted):
                    logger.debug(f"naamyamtok: run twice")
                    logger.debug(f"{book_id_match} - {author_id_match}")
                    if found_count == 0:
                        dispatcher.utter_message(response="utter_return_by")
                    dispatcher.utter_message(
                        response="utter_user_inventory_tell_return", books_return_dates=book_return_str)
                    found_count += 1

                books_return_dates += book_return_str

                if len(rows) > 1:
                    books_return_dates += ", "

            if (book_authors_wanted or book_title_wanted) and found_count == 0:
                # for the case if book title and author name were provided and one of them were no match 
                if global_book_info_by_title or global_book_info_by_author:
                    dispatcher.utter_message(response="utter_return_by")

                    global_book_info = []
                    if global_book_info_by_title:
                        global_book_info = global_book_info_by_title
                    else:
                        global_book_info = global_book_info_by_author

                    for book_return_str in global_book_info:
                        dispatcher.utter_message(
                            response="utter_user_inventory_tell_return", books_return_dates=book_return_str)
                else: # nothing in inventory that matched
                    dispatcher.utter_message(
                        response="utter_borrowed_book_no_match")
            elif found_count==0: # return all the books info
                dispatcher.utter_message(response="utter_return_by")
                dispatcher.utter_message(
                    response="utter_user_inventory_tell_return", books_return_dates=books_return_dates)
        else: # nothing in inventory 
            dispatcher.utter_message(
                response="utter_user_inventory_tell_no_borrowing")

class ActionPerformBorrow(Action):
    """Validate if the wanted book is available and perform borrowing for the user."""
    def name(self) -> Text:
        return "action_perform_borrow"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        logger.debug(f"naamtokyam: action_perform_borrow is called")
        logger.debug(f"naamtokyam: action_perform_borrow: is_ambiguous {tracker.get_slot('is_ambiguous')}")
        logger.debug(f"naamtokyam: action_perform_borrow: found_books {tracker.get_slot('found_books')}")
        logger.debug(f"naamtokyam: action_perform_borrow: narrowed_found_books {tracker.get_slot('narrowed_found_books')}")
        
        found_books = tracker.get_slot("found_books") if not tracker.get_slot("is_ambiguous") else tracker.get_slot("narrowed_found_books")
        selected_list_index = tracker.get_slot("selected_list_index")

        logger.debug(
            f"naamtokyam: action_perform_borrow: len(found_books) = {len(found_books)}, found_books = {found_books}, selected_list_index = {selected_list_index}")

        db = create_connection(os.path.join(dir_path, config.DATABASE))
        c = db.cursor()

        c.execute(
            '''SELECT COUNT(*) FROM user_book WHERE user_id = ?''', (config.USER_ID,))
        num_borrowing = c.fetchone()
        if num_borrowing:
            num_borrowing = num_borrowing[0]
        else:
            num_borrowing = 0 
        
        selected_book = found_books[selected_list_index]
        # check availability
        logger.debug(
            f"naamtokyam: action_perform_borrow: selected_book is: {selected_book}, type(selected_book) is : {type(selected_book)}")
        c.execute(
            '''SELECT user_id, return_date FROM user_book WHERE book_id = ? AND is_returned = 0''', (selected_book[0],))
        record = c.fetchone()

        if num_borrowing == config.MAX_BOOK: # max-ed the borrowing limit already
            dispatcher.utter_message(response=f"utter_cannot_borrow")   
        elif record: # someone is borrowing 
            logger.debug(
                f"naamtokyam: action_perform_borrow: Someone is borrowing the requested book")
            if record[0] == config.USER_ID:  # actually the user itself is already borrowing it
                dispatcher.utter_message(
                    response="utter_tell_you_already_borrowing")
            else:
                dispatcher.utter_message(response="utter_tell_not_available")
        else:
            current_date_temp = dt.datetime.date(dt.datetime.now())
            return_date = current_date_temp + \
                dt.timedelta(days=config.MAX_RENT_DAYS)
            try:
                logger.debug("naamtokyam: action_perform_borrow: inserting to the database!")
                c.execute("""INSERT INTO user_book (user_id, book_id, return_date, is_returned) VALUES (?,?,?,?)""",
                          (config.USER_ID, selected_book[0], return_date.strftime("%m/%d/%Y"), 0))
                db.commit()
            except sqlite3.Error as er:
                logger.debug('SQLite error: %s' % (' '.join(er.args)))
                logger.debug(
                    f"naamtokyam: action_perform_borrow: Error at inserting book record into user_book table")
                dispatcher.utter_message(text="Sorry, something went wrong. Failed to perform the borrowing. Please start again.")

            book_info = selected_book[1] + " written by " + ",".join(selected_book[3])
            suffix = get_suffix(return_date.day)
            dispatcher.utter_message(response="utter_borrow_complete", book_info=book_info,
                                     return_date=return_date.strftime(f"%A %B %-d{suffix}, %Y"))
        return [FollowupAction("action_reset_slots")] 

class ValidateSelectFromList(FormValidationAction):
    """Ask user to select one book from multiple results """
    def name(self) -> Text:
        return "validate_select_from_list_form"

    async def required_slots(
        self,
        slots_mapped_in_domain: List[Text],
        dispatcher: "CollectingDispatcher",
        tracker: "Tracker",
        domain: "DomainDict") -> Optional[List[Text]]:

        if tracker.get_intent_of_latest_message() == "terminate_conversation":
            logger.debug(f"naamyamtok: validate_select_from_list_form hit the terminate_conversation")
            return []

        return slots_mapped_in_domain

    def validate_selected_list_index(self,
                                     slot_value: Any,
                                     dispatcher: CollectingDispatcher,
                                     tracker: Tracker,
                                     domain: DomainDict) -> Dict[Text, Any]:
        logger.debug(f"naamtokyam: validate_select_from_list_form: validate_selected_list_index is called")

        selected_list_index = tracker.get_slot("selected_list_index")
        logger.debug(f"naamtokyam: validate_select_from_list_form: validate_selected_list_index (selected_list_index = {selected_list_index}), (type(selected_list_index) = {type(selected_list_index)})")

        found_books = tracker.get_slot("found_books") if not tracker.get_slot("is_ambiguous") else tracker.get_slot("narrowed_found_books")
        logger.debug(f"naamtokyam: validate_select_from_list_form: validate_selected_list_index (found_books = {found_books}")
        
        has_list_selection = tracker.get_slot("has_list_selection")
        # make sure the index is within valid range. Only can be invalid by either initial trigger of the form, ambiguous index selected (due to title name multiple match), or invalid index (wrong ordinal, non existing title/authors)
        if selected_list_index == -2:
            selected_list_index = None 
        elif selected_list_index < 0 or selected_list_index >= len(found_books):
            selected_list_index = None
            if tracker.get_intent_of_latest_message() != "repeat_again":  
                if not tracker.get_slot("is_ambiguous"): # wrong ordinal, no mathced title/author names
                    dispatcher.utter_message(response="utter_invalid_list_index")
                else: # umbiguous answer (same title name etc.)
                    logger.debug(f"naamtokyam: validate_select_from_list_form: validate_selected_list_index (narrowed_found_books = {tracker.get_slot('narrowed_found_books')}")
                    dispatcher.utter_message(response="utter_ambiguous_result")

            multiple_books_info = ""
            for i, record in enumerate(found_books):
                if i == len(found_books) - 1:
                    multiple_books_info += " and "
                multiple_books_info += record[1] + " written by " + ",".join(record[-1]) + ", "
            dispatcher.utter_message(
                response="utter_found_multiple_book", num_books=len(found_books), multiple_books_info=multiple_books_info)
        else: # valid index
            has_list_selection = False

        logger.debug(f"naamtokyam: validate_select_from_list_form: validate_selected_list_index: (selected_list_index = {selected_list_index}), (has_list_selection = {has_list_selection})")
        return {"selected_list_index": selected_list_index, "has_list_selection": has_list_selection} # and other slot is_ambiguous and narrowed_found_books should be setted already

    async def extract_selected_list_index(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict) -> Dict[Text, Any]:
        logger.debug(f"naamtokyam: validate_select_from_list_form: extract_selected_list_index is called")
        logger.debug(f"naamtokyam: validate_select_from_list_form: extract_selected_list_index ( selected_list_index = {tracker.get_slot('selected_list_index')})")
        
        # check all which entities : ordinal, person, book_title
        book_authors = []
        book_title = ""
        ordinal = tracker.get_slot("selected_list_index") if next(tracker.get_latest_entity_values("ordinal"), None) else -1
        entities = tracker.latest_message['entities']
        book_authors_indexes = []
        book_title_index = ()
        logger.debug(f"naamtokyam: validate_select_from_list_form: latest text message is: {tracker.latest_message.get('text')}")
        user_utter = tracker.latest_message.get('text') # must be in the text when checking the extracted entities (to avoid extraction from previous user utter for ActionSearchBook)
        for entity in entities:
            name = entity["entity"]
            value = entity["value"]
            if name == "PERSON" and value in user_utter:
                book_authors.append(value)
                book_authors_indexes.append((entity["start"], entity["end"]))
            elif name == "book_title" and value in user_utter:
                book_title = value
                book_title_index = (entity["start"], entity["end"])

        if book_title_index and book_authors_indexes:
            overlapped_authors = []
            logger.debug(f"naamtokyam: validate_select_from_list_form: extract_selected_list_index: getting the overlapped author name")
            overlapped_authors = get_overlapped_names(book_title_index, book_authors_indexes, book_authors)
            if overlapped_authors:
                new_book_authors = []
                for name in book_authors:
                    if name not in overlapped_authors:
                        new_book_authors.append(entity["value"])
                book_authors = new_book_authors
                logger.debug(f"naamtokyam: validate_select_from_list_form: extract_selected_list_index: removed the overlapped author name (book_authors - {book_authors})")

        logger.debug(f"naamtokyam: validate_select_from_list_form: extract_selected_list_index: found (book_authors = {book_authors}), (book_title = {book_title}), (ordinal = {ordinal})")
        selected_list_index = -1
        is_ambiguous = False
        narrowed_found_books = []

        extracted_slots = dict()
        found_books = tracker.get_slot("found_books")
        if tracker.get_slot("is_ambiguous"):
            found_books = tracker.get_slot("narrowed_found_books")
        # book_authors and book_title has precedence over ordinal
        if tracker.get_slot("form_flag"): # denotes as first step is running for this form
            logger.debug(f"naamtokyam: validate_select_from_list_form: extract_selected_list_index: first time running this function!!")
            extracted_slots["form_flag"] = False
            selected_list_index = -2 # as first run, mark as not invalid 
        elif book_authors or book_title:
            db = create_connection(os.path.join(dir_path, config.DATABASE))
            book_fts = search.FTS4SpellfixSearch(db, './spellfix', table_name="fts4_book")
            author_fts = search.FTS4SpellfixSearch(db, './spellfix', table_name="fts4_author")

            logger.debug(f"naamtokyam: validate_select_from_list_form: extract_selected_list_index: found (book_authors = {book_authors}), (book_title = {book_title})")

            book_wanted = book_fts.search(book_title)["results"]
            book_wanted_title = book_wanted[0][1] if book_wanted else ""

            authors_wanted_names = []
            for name in book_authors:
                author_wanted = author_fts.search(name)["results"]
                if author_wanted:
                    authors_wanted_names.append(author_wanted[0][1])
            authors_wanted_names = authors_wanted_names if authors_wanted_names else [""]

            matched_book_title_indexes = []
            matched_book_author_indexes = []
            for i, record in enumerate(found_books):
                if record[1] == book_wanted_title:
                    matched_book_title_indexes.append(i)
                if set(authors_wanted_names).issubset(set(record[-1])):
                    matched_book_author_indexes.append(i)

            # as soon as one matched by given book_title then ignore authors
            # only one matched given book_title or (book_title and author_name)
            if len(matched_book_title_indexes) == 1:
                selected_list_index = matched_book_title_indexes[0]
            # if only author names were specified
            elif len(matched_book_author_indexes) == 1 and not matched_book_title_indexes:
                selected_list_index = matched_book_author_indexes[0]
            # both exist and multiple results
            elif matched_book_title_indexes and matched_book_author_indexes:
                intersection = list(set(matched_book_title_indexes) & set(matched_book_author_indexes))
                if len(intersection) == 1:
                    selected_list_index = intersection[0]
                elif len(intersection) > 1:
                    is_ambiguous = True
                    narrowed_found_books = [found_books[index]
                                            for index in intersection]
            # only title with multiple books or only author with multiple books
            elif matched_book_title_indexes or matched_book_author_indexes:
                is_ambiguous = True
                indexes = matched_book_title_indexes or matched_book_author_indexes
                narrowed_found_books = [found_books[index]
                                        for index in indexes]
                # selected_list_index setted to -1

            # else: book_authors or book_title is not existing at all in the found_books then set -1
        elif ordinal != -1:
            ordinal_maps = {"first": 0, "second": 1, "third": 2, "fourth": 3, "fifth": 4, "sixth": 5, "seventh": 6, "eighth": 7, "nineth": 8, "tenth": 9, "1st": 0, "2nd":1, "3rd":2, "4th":3, "5th":4, "6th":5, "7th": 6, "8th":7, "9th":8}
            if ordinal == "last":
                selected_list_index = len(found_books) - 1
            elif type(ordinal) == str:
                selected_list_index = ordinal_maps.get(ordinal, -1)
            else:
                selected_list_index = ordinal - 1 # shift by one
        #else: no entity were passed. Possibly random sententce with no required entities detected.

        logger.debug(f"""naamtokyam: validate_select_from_list_form: extract_selected_list_index: end of the function (selected_list_index: {selected_list_index}, 
        is_ambiguous: {is_ambiguous}, narrowed_found_books: {narrowed_found_books}""")

        extracted_slots.update({"selected_list_index": selected_list_index,
                "is_ambiguous": is_ambiguous,
                "narrowed_found_books": narrowed_found_books})

        return extracted_slots

class ActionSearchBook(Action):
    """ Performs action for the search book."""
    def name(self) -> Text:
        return "action_search_book"

    def utter_found_no_book(self, dispatcher, book_title_wanted, author_names_wanted):
        """Tell user as no matched book existed in the library database.
        :params
            book_title_wanted: str 
            author_names_wanted: list of str 
        """
        book_info = book_title_wanted if book_title_wanted else ""
        if book_info and author_names_wanted:
            book_info += " by "
        book_info += " and ".join(author_names_wanted) if author_names_wanted else ""
        dispatcher.utter_message(response="utter_found_no_book", book_info=book_info)

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        logger.debug(f"naamtokyam: action_search_book")
       
        book_title_wanted = tracker.get_slot("book_title")
        author_names_wanted = tracker.get_slot("book_authors")
        if book_title_wanted == "skip":
            book_title_wanted = ""
        if author_names_wanted == ["skip"]:
            author_names_wanted = []
        logger.debug(
            f"naamtokyam: action_search_book: searching queries are book_title_wanted = {book_title_wanted}, author_names_wanted = {author_names_wanted}")

        db = create_connection(os.path.join(dir_path, config.DATABASE))
        c = db.cursor()
        book_fts = search.FTS4SpellfixSearch(db, './spellfix', table_name="fts4_book")
        author_fts = search.FTS4SpellfixSearch(db, './spellfix', table_name="fts4_author")

        logger.debug(f"naamtokyam: action_search_book: getting the book_title_wanted from database")
        book_title_ids = []
        book_results = book_fts.search(book_title_wanted)["results"]
        for b in book_results:  # getting all the possible title results
            logger.debug(f"naamtokyam: action_search_book = {b}")
            book_title_ids.append(b[0])

        logger.debug(
            f"naamtokyam: action_search_book: getting the author_names_wanted from database")
        authors_wanted_ids = []
        for author_name in author_names_wanted:
            author_wanted = author_fts.search(author_name)["results"]
            author_ids = []
            for a in author_wanted:
                logger.debug(f"naamtokyam: action_search_book = {a}")
                author_ids.append(a[0])
            if author_ids:
                authors_wanted_ids.append(author_ids)
        logger.debug(
            f"naamtokyam: action_search_book: authors_wanted_ids = {authors_wanted_ids}, len(authors_wanted_ids) = {len(authors_wanted_ids)}")
        if len(authors_wanted_ids) > 1:
            # list of tuples of all possible combinations
            authors_wanted_ids = list(itertools.product(*authors_wanted_ids))
        elif authors_wanted_ids:
            authors_wanted_ids = [[aid] for aid in authors_wanted_ids[0]]

        logger.debug(
            f"naamtokyam: action_search_book: book_title_ids = {book_title_ids}, authors_wanted_ids = {authors_wanted_ids}")

        columns = [
            "book_id",
            "title",
            "author_ids",
            "author_names"
        ]
        BookRecord = namedtuple("BookRecord", columns)
        found_books = []
        
        if book_title_wanted and author_names_wanted and (not book_title_ids or not authors_wanted_ids):
            # both fields were provided but either one was not found from our database
            logger.debug(f"naamtokyam: action_search_book: no found books for a given search query even though ")
            pass
        elif book_title_ids:  # book_title_ids given
            logger.debug(
                f"naamtokyam: action_search_book: book_title_ids were given (not skip)")

            # TODO(akazawan): Find a better way to perform the query
            query = """SELECT bi.book_id, ftsb.title, GROUP_CONCAT(ban.author_id), GROUP_CONCAT(ban.author_name)
                       FROM book_info bi 
                       INNER JOIN 
                       (
                           SELECT * FROM book_authors ba 
                           INNER JOIN fts4_author ftsa 
                           ON ba.author_id=ftsa.rowid
                        ) ban 
                        ON bi.book_id=ban.book_id
                        INNER JOIN fts4_book ftsb
                        ON bi.book_id=ftsb.rowid
                        WHERE bi.book_id = %s"""

            book_records = []
            for bid in book_title_ids:
                row = c.execute(format_query_list(1, query), (bid,))
                if row:
                    book_records.append(c.fetchone())

            logger.debug(
                f"naamtokyam: action_search_book: len(book_records) = {len(book_records)}")
            logger.debug(
                f"naamtokyam: action_search_book: taking only unique records (duplicate happens as same book but different format is available) ")

            unique_title_author = set()
            for record in book_records:
                logger.debug(f"record {record}")
                *binfo, aids, anames = record
                aids = list(map(int, aids.split(",")))
                # logger.debug(f"naamtokyam: aids = {aids}")
                anames = anames.split(",")
                # only keep unique records by title and author names (disgard uniquness of the book's format for now)
                if (record[1], tuple(aids)) in unique_title_author:
                    continue
                unique_title_author.add((record[1], tuple(aids)))
                if authors_wanted_ids:  # both slots exist
                    for pair in authors_wanted_ids: # check if given book info is containing user requested authors 
                        if set(pair).issubset(set(aids)):
                            found_books.append(BookRecord(*(binfo + [aids, anames])))
                else:
                    found_books.append(BookRecord(*(binfo + [aids, anames])))

            logger.debug(
                f"naamtokyam: action_search_book: len(found_books) = {len(found_books)}")
        elif authors_wanted_ids:  # only authors names were given
            logger.debug(
                f"naamtokyam: only authors_wanted_ids names were given")
            # TODO(akazawan): Need a better way to extract book record with matching tuple of author_ids. Multiple queries vs one query
            query = """SELECT bi.book_id, ftsb.title, ban.author_id, ban.author_name
                       FROM book_info bi 
                       INNER JOIN 
                       (
                           SELECT * FROM book_authors ba 
                           INNER JOIN fts4_author fts 
                           ON ba.author_id=fts.rowid
                        ) ban 
                        ON bi.book_id=ban.book_id
                        INNER JOIN fts4_book ftsb
                        ON bi.book_id=ftsb.rowid
                        WHERE ban.author_id in (%s)"""

            unique_title_author = set()
            for pair in authors_wanted_ids:
                # get the book_ids that match one
                c.execute(format_query_list(len(pair), query), pair)
                possible_books = c.fetchall()
                sort_by_bids = defaultdict(list)
                for pb in possible_books: # take by unique book_ids
                    bid = pb[0]
                    sort_by_bids[bid].append(pb)

                for k, vs in sort_by_bids.items():
                    aids = {v[-2] for v in vs}
                    anames = {v[-1] for v in vs}
                    if (vs[0][1], tuple(aids)) in unique_title_author: # unique (book_title, tuple of author_ids)
                        continue
                    unique_title_author.add((vs[0][1], tuple(aids)))
                    if set(pair).issubset(aids):  # if exact author ids match
                        found_books.append(BookRecord(
                            *(list(vs[0][:-2]) + [list(aids), list(anames)])))
            logger.debug(
                f"naamtokyam: action_search_book: len(found_books) = {len(found_books)}")

        # utter a result if any
        if found_books:
            # TODO(naamtokyam): Better way to handle resulst more than 4
            found_books = found_books[:min(len(found_books), 4)]
            logger.debug(f"naamtokyam: action_search_book: found some results!")
            if len(found_books) == 1:  # only one match
                logger.debug(f"naamtokyam: action_search_book: only one found_books result!")
                name_str = self.format_author_names_str(found_books[0].author_names)
                book_info =  found_books[0].title + " written by " + \
                    name_str
                dispatcher.utter_message(
                    response="utter_found_one_book", book_info=book_info)
            else:
                logger.debug(f"naamtokyam: action_search_book: multiple found_books result!")
                multiple_books_info = ""
                for i, record in enumerate(found_books):
                    name_str = self.format_author_names_str(record.author_names)
                    if i == len(found_books) - 1:
                        multiple_books_info += "and "
                    multiple_books_info += record.title + " written by " + \
                        name_str + ", "
                dispatcher.utter_message(
                    response="utter_found_multiple_book", num_books=len(found_books), multiple_books_info=multiple_books_info)
        else:
            found_books = None
            logger.debug(f"naamtokyam: no found books for a given search query")
            self.utter_found_no_book(dispatcher, book_title_wanted,author_names_wanted)

        num_found_books = len(found_books) if found_books else 0
        reset_slots = [SlotSet("book_title", None), SlotSet("book_authors", None), SlotSet(
            "wrong_author_names", None), SlotSet("book_info_prefilled", False)]

        selected_list_index = [None, 0][num_found_books == 1]
        has_found_book = num_found_books > 0
        has_list_selection = num_found_books > 1

        return reset_slots + [SlotSet("found_books", found_books), SlotSet("selected_list_index", selected_list_index), SlotSet("has_found_book", has_found_book), SlotSet("has_list_selection", has_list_selection)] #+ addtional_actions

    def format_author_names_str(self, names):
        """Format given names to proper string
        :params
            names: list of str 
        :return 
            formatted str
        """
        if len(names) == 1:
            return ",".join(names)
        else:
            return  ",".join(names[:-1]) + " and " + names[-1]

class ValidateSearchBookForm(FormValidationAction):
    """Check the validity of book information passed from user."""
    def name(self) -> Text:
        return "validate_search_book_form"

    async def required_slots(self,
                             domain_slots: List[Text],
                             dispatcher: "CollectingDispatcher",
                             tracker: "Tracker",
                             domain: "DomainDict",
                             ) -> List[Text]:
        logger.debug(f"naamtokyam: validate_search_book_form: required_slots function is called")

        if tracker.get_intent_of_latest_message() == "terminate_conversation":
            logger.debug(f"naamyamtok: validate_search_book_form hit the terminate_conversation")
            return []
        
        required_slots = []
        # if the user provided book info in the triggered utterance for the intent, then we only need provided slot(s) as required
        logger.debug(f"naamtokyam: validate_search_book_form: required_slots (book_info_prefilled : {tracker.get_slot('book_info_prefilled')})")
        if tracker.get_slot("book_info_prefilled"):
            if tracker.get_slot('book_title'):
                logger.debug(f"naamtokyam: validate_search_book_form: required_slots book_info_prefilled (book_title : {tracker.get_slot('book_title')})")
                required_slots.append("book_title")
            if tracker.get_slot('book_authors'):
                logger.debug(f"naamtokyam: validate_search_book_form: required_slots book_info_prefilled (book_authors : {tracker.get_slot('book_authors')})")
                required_slots.append("book_authors")
        else:
            required_slots += ["book_title", "book_authors"]

        logger.debug(f"naamtokyam: validate_search_book_form: required_slots (book_title : {tracker.get_slot('book_title')})")
        logger.debug(f"naamtokyam: validate_search_book_form: required_slots (book_authors : {tracker.get_slot('book_authors')})")
        logger.debug(f"naamtokyam: validate_search_book_form: our current required slots are {required_slots}")
        return required_slots

    def validate_book_title(self,
                            slot_value: Any,
                            dispatcher: CollectingDispatcher,
                            tracker: Tracker,
                            domain: DomainDict) -> Dict[Text, Any]:
        logger.debug(
            f"naamtokyam: validate_search_book_form: validate_book_title is called")
        logger.debug(
            f"naamtokyam: validate_search_book_form: validate_book_title: (book_title = {slot_value})")

        if not slot_value and not tracker.get_slot('book_info_prefilled'): # if the slot was not prefilled as the first run 
            slot_value = None
        elif slot_value == "skip" and not tracker.get_slot("book_authors"): # if title was skipped and book_authors were skipped as well (validate_book_authors clears book_authors slot first)
            for e in reversed(tracker.events):
                if e["event"] == "bot":
                    # logger.debug(f"{e}")
                    try:
                        if e["metadata"]["utter_action"] == "utter_ask_book_authors": # only if this condition happened after specific utter
                            return {"book_title": None}
                        else:
                            break
                    except error:
                        logger.debug(f"{error}")

        logger.debug(
            f"naamtokyam: validate_search_book_form: validate_book_title: (book_title = {slot_value})")
        return {"book_title": slot_value}

    def validate_book_authors(self,
                              slot_value: Any,
                              dispatcher: CollectingDispatcher,
                              tracker: Tracker,
                              domain: DomainDict) -> Dict[Text, Any]:
        logger.debug(
            f"naamtokyam: validate_search_book_form: validate_book_authors is called")
        set_slots = dict()
        if not slot_value and not tracker.get_slot("book_info_prefilled"): # first run when no slots prefilled
            slot_value = None
        # if both were skip then alert
        elif slot_value == ["skip"] and tracker.get_slot("book_title") == "skip":
            dispatcher.utter_message(response="utter_need_one_book_info")
            slot_value = None
            logger.debug(f"naamtokyam: both slots were SKIPPED!! ")

        logger.debug(
            f"naamtokyam: validate_search_book_form: validate_book_authors: (book_authors = {slot_value})")
        set_slots.update({"book_authors": slot_value})
        return set_slots

    async def extract_book_title(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict) -> Dict[Text, Any]:
        logger.debug(f"naamtokyam: extract_book_title is called")
        logger.debug(
            f"naamtokyam: extract_book_title: checking if book_title slot is already setted (book_title = {tracker.get_slot('book_title')})")

        if tracker.get_slot('book_title'):  # prefilled valid value
            logger.debug(
                f"naamtokyam: extract_book_title: book_title already setted. {tracker.get_slot('book_title')}")
            return {"book_title": tracker.get_slot('book_title')}
        elif "skip" == tracker.latest_message.get("text"): # skipped
            for e in reversed(tracker.events):
                if e["event"] == "bot":
                    try:
                        if e["metadata"]["utter_action"] == "utter_ask_book_title": # only trigger this if utter was this otw skip could be detected when asked for author_names as well
                            return {"book_title": "skip"}
                        else:
                            break
                    except e:
                        logger.debug(f"{e}")

        entities = tracker.latest_message['entities']
        book_titles = []
        book_titles_indexes = []
        book_authors = []
        book_authors_indexes = []
        # extract required entities
        logger.debug(f"naamtokyam: {entities}")
        for entity in entities:
            if entity["entity"] == "book_title":
                book_titles.append(entity["value"])
                book_titles_indexes.append((entity["start"], entity["end"]))
            elif entity["entity"] == "PERSON": # as sometimes given title wrongly extracts as PERSON
                book_authors.append(entity["value"])
                book_authors_indexes.append((entity["start"], entity["end"]))

        if len(book_titles) > 1:
            logger.debug(
                f"naamtokyam: extract_book_title: multiple book titles detected")
            dispatcher.utter_message(
                response="utter_multiple_search_not_supported")
            return {"book_title": None}

        book_title = book_titles[0] if book_titles else ""
        book_title_index = book_titles_indexes[0] if book_title else ()

        logger.debug(
            f"naamtokyam: checking the user input text {tracker.latest_message.get('text')}")

        overlapped_authors = []
        if book_title_index and book_authors_indexes:
            overlapped_authors = get_overlapped_names(book_title_index, book_authors_indexes, book_authors)

        logger.debug(f"naamtokyam: setting entity book_title to {book_title}")
        return {"book_title": book_title, "wrong_author_names": overlapped_authors}

    async def extract_book_authors(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict) -> Dict[Text, Any]:
        logger.debug(f"naamtokyam: extract_book_authors is called")
        logger.debug(
            f"naamtokyam: extract_book_authors: checking if book_authors slot is already setted (book_authors = {tracker.get_slot('book_authors')})")

        if tracker.get_slot("book_authors"):  # case if prefilled
            logger.debug(
                f"naamtokyam: extract_book_authors: book_authors already filled (book_authors = {tracker.get_slot('book_authors')})")
            return {"book_authors": tracker.get_slot("book_authors")}
        elif "skip" == tracker.latest_message.get("text"):
            for e in reversed(tracker.events):
                if e["event"] == "bot":
                    try:
                        if e["metadata"]["utter_action"] == "utter_ask_book_authors":
                            return {"book_authors": ["skip"]}
                        else:
                            break
                    except e:
                        logger.debug(f"{e}")

        wrong_author_names = tracker.get_slot("wrong_author_names")
        wrong_author_names = wrong_author_names if wrong_author_names else []

        entities = tracker.latest_message['entities']
        book_authors = []
        # extract required entities
        for entity in entities:
            if entity["entity"] == "PERSON" and entity["value"] not in wrong_author_names:
                book_authors.append(entity["value"])

        logger.debug(
            f"naamtokyam: setting entity book_authors to {book_authors}")
        return {"book_authors": book_authors}

class ActionResetSlots(Action):
    """Manually reset all the slots."""
    def name(self):
        return "action_reset_slots"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        logger.debug(
            f"naamtokyam: action_reset_slots: Resetting all the slots")

        return [AllSlotsReset()]

class ActionRepeat(Action):
    """Repeat the last bot utterance."""
    def name(self):
        return "action_repeat"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        logger.debug(f"naamtokyam: action_repeat: Repeating the previous text")

        user_ignore_count = 2
        count = 0
        tracker_list = []

        while user_ignore_count > 0:
            event = tracker.events[count].get('event')
            if event == 'user':
                user_ignore_count -= 1
            elif event == 'bot':
                tracker_list.append(tracker.events[count])
            count -= 1

        i = len(tracker_list) - 1
        while i >= 0:
            dispatcher.utter_message(text=tracker_list[i].get('text'))
            i -= 1

        return []

class ActionAssignBookInfoToForm(Action):
    """ Helper action to trigger search_book_form if inform_book_info was the trigger intent with entities pre-filled."""
    def name(self):
        return "action_assign_book_info_to_form"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        logger.debug(f"naamtokyam: action_assign_book_info_to_form")

        entities = tracker.latest_message['entities']
        book_authors = []
        book_authors_indexes = []
        book_title_index = (-1,-1)
        # extract required entities (not using slots_mapping)
        for entity in entities:
            name = entity["entity"]
            value = entity["value"]
            if name == "PERSON":
                book_authors.append(value)
                book_authors_indexes.append((entity["start"], entity["end"]))
            elif name == "book_title":
                book_title_index = (entity["start"], entity["end"])
        overlapped_authors = get_overlapped_names(book_title_index, book_authors_indexes, book_authors)
        if overlapped_authors:
            new_book_authors = []
            for name in book_authors:
                if name not in overlapped_authors:
                    new_book_authors.append(entity["value"])
            book_authors = new_book_authors

        return [SlotSet("book_authors", book_authors), 
                SlotSet("book_title", next(tracker.get_latest_entity_values('book_title'), "")), 
                SlotSet("book_info_prefilled", True),
                FollowupAction("search_book_form")
                ]
