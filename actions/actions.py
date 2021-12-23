# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions


# This is a simple example for a custom action which utters "Hello World!"

from typing import Any, Text, Dict, List

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

from rasa_sdk import Tracker, FormValidationAction
from rasa_sdk.types import DomainDict

import datetime as dt 
import dateutil.parser
import logging

from . import library_config as config

logger = logging.getLogger(__name__)

# class ActionShowCount(Action):
#     """
#     """
#     def name(self):
#         return "action_show_count"

#     def run(self, dispatcher, tracker, domain):
#         pass 

# class ActionTotalLimit(Action):
#     """
#     """
#     def name(self):
#         return "action_total_limit"

#     def run(self, dispatcher, tracker, domain):
#         pass 
    
def format_opentime(open_hours):
    hour_min_str = "from "

    for begin_time, end_time in open_hours[:-1]:
        bt = format_time(begin_time)
        et = format_time(end_time)
        hour_min_str+= f"{bt} to {et}, "
    
    bt = format_time(open_hours[-1][0])
    et = format_time(open_hours[-1][1])

    if hour_min_str != "from ":
        hour_min_str+= "and then "
    hour_min_str+= f"{bt} to {et}"
    return hour_min_str
                        
def format_time(time):
    return '{0:%-I} {0:%M}{0:%p}'.format(time) if time.minute != 0 else '{0:%-I}{0:%p}'.format(time)

class ActionTellTime(Action):
    def name(self):
        return "action_tell_opentime"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        logger.debug(f"akazawan: action_tell_opentime is called.")

        datetime = tracker.get_slot('time')

        if datetime:
            datetime_obj = dateutil.parser.parse(datetime)
            day_of_week = datetime_obj.strftime('%A').lower()
            month = datetime_obj.strftime("%B").lower()
            day = datetime_obj.day
            hour = datetime_obj.hour
            minuite = datetime_obj.minute
            year = datetime_obj.year
            hour_minuite = datetime_obj.time()

            logger.debug(f"""akazawan:
                            day_of_week: {day_of_week},  
                            month: {month}, 
                            day: {str(day)},  
                            hour: {str(hour)},  
                            minuite: {str(minuite)},  
                            year: {str(year)}  """)

            # check relativness if we could store. eg. today, tomorrow
            today = dt.datetime.today().date()
            requested_day = datetime_obj.date()

            logger.debug(f"akazawan: diff calculated: {today} - {requested_day} = {(today - requested_day).days}")
            diff = abs((today - requested_day).days)
            future = today < requested_day

            relative_time = ""
            for delta, names in [(1, ["yesterday", "tomorrow"]), (2, ["the day before yesterday", "the day after tomorrow"])]:  
                if diff == delta:
                    relative_time = names[future]
            
            logger.debug(f"akazawan: relative day is set as {relative_time}")

            # check if the date is open 1) date, 2) week of day with time specified, 3) week of day with only 
            if requested_day in config.YEARLY_HOLIDAYS:
                dispatcher.utter_message(response="utter_specified_date_closed",
                                        day_of_week=day_of_week, 
                                        month=month, 
                                        day=day, 
                                        year=year)

                # suggest next open day
                next_open_day = requested_day
                while next_open_day in config.YEARLY_HOLIDAYS:
                    next_open_day+= dt.timedelta(days=1)
                
                next_open_day_of_week = next_open_day.strftime('%A').lower()
                next_open_month = next_open_day.strftime("%B").lower()
                open_hours = config.OPEN_HOURS[next_open_day_of_week]

                hour_min_str = format_opentime(open_hours)

                dispatcher.utter_message(response="utter_next_open_date", 
                                        day_of_week=next_open_day_of_week, 
                                        month=next_open_month, 
                                        day=str(next_open_day.day), 
                                        year=str(next_open_day.year),
                                        hour_min=hour_min_str)
            else:
                open_hours = config.OPEN_HOURS[day_of_week]
                hour_min_str = format_opentime(open_hours)
                time_specified = bool(hour | minuite)
                # use numbers and time, check if number in numbers match with hour or min 
                if time_specified:
                # check if hours if specified and within the openingn range
                    if any([(hour_minuite >= begin_time and hour_minuite <= end_time) for begin_time, end_time in open_hours]):
                        # it is open 
                        dispatcher.utter_message(response="utter_affirm_open", 
                                                relative_time=relative_time, 
                                                day_of_week=day_of_week, 
                                                hour_min=hour_min_str)
                    else:
                        # it is closed
                        dispatcher.utter_message(response="utter_specified_date_time_closed", 
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
                        logger.debug(f"akazawan: found_next is set to {found_next}")
                        if not found_next:  
                            logger.debug(f"akazawan: finding new date")
                            next_open_day = requested_day
                            # then check holiday requirement for next day
                            next_open_day+= dt.timedelta(days=1)
                            while next_open_day in config.YEARLY_HOLIDAYS:
                                next_open_day+= dt.timedelta(days=1)
                            new_open_hours = config.OPEN_HOURS[next_open_day.strftime('%A').lower()]
                            day_of_week = next_open_day.strftime('%A').lower()
                            month = next_open_day.strftime("%B").lower()
                            day = next_open_day.day
                            year = next_open_day.year
                            begin_time, end_time = new_open_hours[0]

                        dispatcher.utter_message(response="utter_next_open_date", 
                                                day_of_week=day_of_week, 
                                                month=month, 
                                                day=str(day), 
                                                year=str(year), 
                                                hour_min="from "+ format_time(begin_time) + " to " + format_time(end_time))
                else:
                    # just reply with date's open day
                    dispatcher.utter_message(response="utter_affirm_open", 
                                            relative_time=relative_time, 
                                            day_of_week=day_of_week, 
                                            hour_min=hour_min_str)
                   
        else:
            dispatcher.utter_message(response="utter_default_datetime")

        return [SlotSet("time", None)]

class ActionTellContactInfo(Action):
    def name(self):
        return "action_tell_contact_info"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        slot_value = tracker.get_slot("contact_type")

        logger.debug(f"naamtokyam: action_tell_contact_info is called.")

        if slot_value == "phone":
            dispatcher.utter_message(response="utter_library_phone")
        else:
            dispatcher.utter_message(response="utter_library_email")

        return [SlotSet("contact_type", None)]

class ValidateContactForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_contact_form"

    def validate_contact_type(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        logger.debug(f"naamtokyam: ValidateContactForm is called. slot_value is {slot_value}")
        ans = slot_value
        if ans not in ["email", "phone"]:
            dispatcher.utter_message(text=f"Hmm I don't have that option... Could you say it again?")
            ans = None
        return {"contact_type": ans}

# ref: https://forum.rasa.com/t/how-to-repeat-the-last-bot-utterance/4743
class ActionRepeat(Action): 
    def name(self): 
        return "action_repeat"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        user_ignore_count = 2
        count = 0
        tracker_list = []

        while user_ignore_count > 0:
            event = tracker.events[count].get('event')
            if event == 'user':
                user_ignore_count-= 1
            if event == 'bot':
                tracker_list.append(tracker.events[count])
            count = count - 1

        i = len(tracker_list) - 1
        while i >= 0:
            dispatcher.utter_message(response=tracker_list[i].get('metadata').get('utter_action'))
            i -= 1

        return []