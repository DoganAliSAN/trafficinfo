from pyrogram import Client
import requests
import ast
import folium
import asyncio
import time
import datetime
import json
import os
from datetime import timedelta
import re
from geopy.geocoders import Nominatim
import locale

locale.setlocale(locale.LC_ALL, "tr_TR.UTF-8")

def read_config(section, option,file_path="keys.ini"):
    """Incase of an api usage keys must be stored carefully.
    To do so a settings.ini file may be used which this function reads from.
    
    Parameters:
        * section = Name of the section that holds several keys
        * option = Key from selected section
    """
    from configparser import RawConfigParser

    config = RawConfigParser()
    config.read(file_path)
    return config.get(section, option)


async def last_2_hours(chat_id, app):
    """
    Fetch messages from the last 2 hours from the specified chat.

    Args:
        chat_id (int): The chat ID to fetch messages from.
        app: The client instance of the Telegram library.
    """
    all_messages = []
    offset_id = 0

    # Calculate the timestamp for 2 hours ago
    two_hours_ago = datetime.datetime.now() - timedelta(hours=2)
    # Ensure the client is started
    async with app:
        # This ensures app.start() and app.stop() are managed correctly
        while True:

            # Fetch messages with date filtering
            async for message in app.get_chat_history(
                chat_id,
                limit=100,
                offset_id=offset_id,
            ):
                # If the message timestamp is within the last 2 hours,
                # add it to the list
                if message.date >= two_hours_ago:
                    all_messages.append([message.text, message.date])
                else:
                    # Stop processing further messages if they are older
                    # than 2 hours
                    return all_messages

                # Update offset_id to process the next batch
                offset_id = message.id

            # If no more messages to process, break
            if not all_messages or all_messages[-1][1] < two_hours_ago:
                break

            # Sleep to avoid hitting rate limits
            await asyncio.sleep(1)

    return all_messages


# Example center location
INITIAL_LOCATION = json.loads(read_config("INITIAL_LOCATION","location"))
my_map = folium.Map(location=INITIAL_LOCATION, zoom_start=11)
markers = []
unclear_messages = []

def return_necessary_lists():
    return [markers, unclear_messages]
def add_marker(lat, lon, popup_text="Marker", color="green"):
    folium.Marker(
        location=[lat, lon],
        popup=popup_text,
        icon=folium.Icon(color=color),  # Set the marker color here
    ).add_to(my_map)
    markers.append(popup_text)


def extract_place_names(user_prompt):
    API_KEY = read_config("DEEPINFRA", "api_key")
    URL = (
        "https://api.deepinfra.com/v1/"
        "inference/meta-llama/Meta-Llama-3.1-70B-Instruct"
    )

    HEADERS = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }

    data = {
        "input": (
            "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
            "You will be given Turkish sentences. Extract place names located "
            "in Denizli/Turkey. "
            "Identify local road and potential place names as well."
            "Remove explanations, "
            "and only respond with road names or place names without any"
            "additional words in a python list."
            "just a python list nothing else do not use words like python"
            "or anything like that"
            "You responding with only road, place names is important because"
            "i'll use your response in a python code"
            "You not including anything else is a must if you understand that"
            "answer accordingly"
            "You including anything but the python list is forbidden"
            "You shall not respond with any understoodment notes,"
            "you responding"
            "with a python list is a way of telling me you understood"
            "<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n"
            f"{user_prompt}<|eot_id|><|start_header_id|>assistant<|"
            "end_header_id>\n\n"
        ),
        "stop": ["<|eot_id|>", "<|end_of_text|>", "<|eom_id|>"],
    }

    response = requests.post(URL, headers=HEADERS, json=data)

    if response.status_code == 200:
        result = response.json()["results"][0]["generated_text"]
        try:
            # Return only the extracted place names
            return ast.literal_eval(result.strip().replace("'", '"'))
        except Exception:
            return "Merkezefendi"  # !WARNING
    else:
        return f"Error: {response.status_code} - {response.text}"


def get_status(message):
    pattern_danger = (
        r"(\bcevirme\b| c\b| c |çevirme\b| ç\b| ç |ç\b| ç\b |"
        "\buygulama\b | uygulama\b| uygulama )"
    )
    pattern_clear = r"(\btemiz\b| t\b| t |t\b| t |t\b| t\b)"

    danger = re.search(pattern_danger, message.lower())
    clear = re.search(pattern_clear, message.lower())
    if danger:
        return 1
    elif clear:
        return 0
    else:
        return 2


def locate(message, date=1):
    if date == 1:
        date = datetime.datetime.now()

    message = message.lower()

    status = get_status(message)  # 1 danger #0 clear

    with open("locations.json", "r") as f:
        locations = json.loads(f.read())

    def try_geopy(message, main_location):

        # Instantiate a new Nominatim client
        app = Nominatim(user_agent="tutorial")
        # Get location raw data from the user
        your_loc = main_location
        try:
            location = app.geocode(your_loc).raw

            return [location.get("lat"), location.get("lon")]
        except Exception:
            return None

    def try_geoapify(main_location):
        import requests

        API_KEY = read_config("GEOAPIFY", "api_key")
        url = f"https://api.geoapify.com/v1/geocode/search?text= \
                {main_location}&format=json&apiKey={API_KEY}"
        response = requests.get(url)
        k = response.json()
        try:
            lon = k["results"][0].get("lon")
            lat = k["results"][0].get("lat")
        except Exception:
            return None
        return [lat, lon]

    def try_keywords(message):
        from unidecode import unidecode

        keywords = ["karşısı", "önü", "yanı", "girişi", "çıkışı"]

        p_keyword = [
            unidecode(x)
            for x in keywords
            if unidecode(x) in unidecode(message)
        ]  # !WARNING

        if len(p_keyword) != 0:

            decoded_keyword = unidecode(p_keyword[0])
            decoded_message = unidecode(message)

            main_location = decoded_message.split(decoded_keyword)[0]

            return main_location

        else:

            return None

    def save_to_map(status, coords, message, main_location):

        message = str(message) + str(date)
        if status == 1:

            add_marker(coords[0], coords[1], message, color="red")
        elif status == 0:

            add_marker(coords[0], coords[1], message)
        else:
            pass

    location_found_with_keyword = 0
    method_3_found_coords = 0
    location_found_with_ai = 0
    method_2_found_coords = 0
    method_3_location = try_keywords(message)

    if method_3_location:
        # location was found with keyword try to get coords now
        location_found_with_keyword = 1
        method_3_location = method_3_location.lower().strip()

        matching_dict = next(
            (
                entry
                for entry in locations
                if method_3_location in entry["names"]
            ),
            None,  # Default if no match is found
        )
        if matching_dict is not None:

            method_3_coords = [
                matching_dict.get("lat"),
                matching_dict.get("lon"),
            ]
            method_3_found_coords = 1 if method_3_coords else 0
        else:
            method_3_coords = None

        if not method_3_coords:
            # location is not in saved locations try other methods

            method_3_coords = try_geopy(
                message, method_3_location + " denizli"
            )
            method_3_found_coords = 1 if method_3_coords else 0

            if not method_3_found_coords:
                geoapify_message = method_3_location + " Denizli"
                geo_coords = try_geoapify(geoapify_message)
                if geo_coords:
                    method_3_found_coords = 1
                    method_3_coords = geo_coords

    if method_3_found_coords == 0:
        # there is no keyword in message try other methods

        method_2_location = extract_place_names(message)
        method_2_location = (
            method_2_location[0].lower().strip()
            if len(method_2_location) > 0
            else None
        )

        if method_2_location:
            # location was found with ai check saved locations
            location_found_with_ai = 1

            matching_dict = next(
                (
                    entry
                    for entry in locations
                    if method_2_location in entry["names"]
                ),
                None,  # Default if no match is found
            )
            if matching_dict is not None:
                method_2_coords = [
                    matching_dict.get("lat"),
                    matching_dict.get("lon"),
                ]
                method_2_found_coords = 1 if method_2_coords else 0
            else:
                method_2_coords = None

            if not method_2_coords:
                # location is not saved in locations try other methods

                method_2_coords = try_geopy(
                    message, method_2_location + " denizli"
                )
                method_2_found_coords = 1 if method_2_coords else 0
                if not method_2_found_coords:

                    geo_coords = try_geoapify(method_2_location + " Denizli")
                    if geo_coords:
                        method_2_found_coords = 1
                        method_2_coords = geo_coords

    if (
        not location_found_with_ai == 0
        and not location_found_with_keyword == 0
    ):

        unclear_messages.append(message + str(date))


    elif location_found_with_keyword and method_3_found_coords:
        save_to_map(status, method_3_coords, message, method_3_location)

    elif location_found_with_ai and method_2_found_coords:
        save_to_map(status, method_2_coords, message, method_2_location)

    elif not method_3_found_coords or not method_2_found_coords:
        pass

    map_path = "static/map.html"
    my_map.save(map_path)


async def check_last_2_hours():
    # Replace these values with your API ID and hash
    API_ID = read_config("TELEGRAM", "api_id")
    API_HASH = read_config("TELEGRAM", "api_hash")
    # Replace 'your_username' with your Telegram username
    USERNAME = read_config("TELEGRAM", "username")
    app = Client(USERNAME, API_ID, API_HASH)

    # if exists remove markers.txt
    if os.path.exists("markers.txt"):
        os.remove("markers.txt")

    # if exists remove unclear_messages.json
    if os.path.exists("unclear_messages.json"):
        os.remove("unclear_messages.json")

    last_2_hour_messages = await last_2_hours("denizlicevirme20", app)

    for message in last_2_hour_messages:
        locate(message[0], message[1])  # text and date
