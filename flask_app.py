from flask import Flask, render_template, \
    request, jsonify, url_for, redirect
import json
import itertools
import locale
from support import check_last_2_hours,return_necessary_lists
import os
app = Flask(__name__)

# Set locale for Turkish language to handle special characters
locale.setlocale(locale.LC_ALL, "tr_TR.UTF-8")

# Load data from JSON file
with open("locations.json", "r", encoding="utf-8") as f:
    data = json.load(f)


def generate_variations(name):
    words = name.split()
    first_word = words[0]
    variations = []

    variations.append(first_word.lower())
    variations.append(first_word.capitalize())

    capitalized_variations = [[first_word.lower(), first_word.capitalize()]]
    combinations = list(itertools.product(*capitalized_variations))
    for combination in combinations:
        variations.append("".join(combination))
        variations.append(" ".join(combination))
    for i in range(len(first_word)):
        modified_first_word = first_word[:i] + first_word[i + 1:]
        variations.append(modified_first_word)
        if len(words) > 1:
            variations.append(" ".join([modified_first_word] + words[1:]))
    variations.append(name)
    if len(words) > 1:
        lower_word = words[0].lower() + words[1].lower()
        lower_word_2 = words[0].lower() + " " + words[1].lower()
        variations.append(lower_word)
        variations.append(lower_word_2)

    variations = list(dict.fromkeys(variations))
    return variations


def save_data():
    with open("locations.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


@app.route('/loc')
def loc():  # !WARNING
    return render_template("location.html")


@app.route('/')
def main():

    markers,data = return_necessary_lists()
    return render_template('index.html', data=data, markers=markers)


@app.route('/last_2')
async def last_2():  # !WARNING

    await check_last_2_hours()
    # reroute to main
    return redirect(
        url_for('main'))


@app.route('/search', methods=['POST'])
def search_location():
    with open("locations.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    req_data = request.json
    message = req_data.get('message', '')

    for i in data:
        names = i["names"]
        if message in names:
            return jsonify(
                {
                    "found": True,
                    "location": i
                }
            )
    return jsonify(
        {
            "found": False
        }
    )


@app.route('/add', methods=['POST'])
def add_location():
    req_data = request.json
    new_name = req_data.get('name')
    new_lat = req_data.get('lat')
    new_lon = req_data.get('lon')
    if not new_name or not new_lat or not new_lon:
        return jsonify(
            {
                "success": False,
                "message": "Missing required fields"
            }
        )
    variations = generate_variations(new_name)
    new_data = {"names": variations, "lat": new_lat, "lon": new_lon}
    data.append(new_data)
    save_data()
    return jsonify({"success": True, "location": new_data})


@app.route('/locations', methods=['GET'])
def get_locations():
    return jsonify(data)


if __name__ == '__main__':
    app.run()
