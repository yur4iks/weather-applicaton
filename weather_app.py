import datetime as dt
import json
import requests
from flask import Flask, jsonify, request


API_TOKEN = ""

API_KEY = ""

BASE_URL = "http://api.weatherapi.com/v1"

AI_API_KEY = ""
AI_BASE_URL = "https://api.openai.com/v1/chat/completions"

app = Flask(__name__)

class InvalidUsage(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv["message"] = self.message
        return rv

@app.errorhandler(InvalidUsage)
def handle_invalid_usage(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response

@app.route("/")
def home_page():
    return "<p><h2>Weather will be revealed soon.</h2></p>"

@app.route("/content/api/v1/integration/generate", methods=["POST"])
def weather_endpoint():
    json_data = request.get_json()
    
    if json_data.get("token") is None:
        raise InvalidUsage("Token is required", status_code=400)
    
    token = json_data.get("token")
    
    if token != API_TOKEN:
        raise InvalidUsage("Wrong API token", status_code=403)
    
    required_fields = ["requester_name", "location", "date"]
    for field in required_fields:
        if field not in json_data:
            raise InvalidUsage(f"Missing field: {field}", status_code=400)
    
    try:
        date_obj = dt.datetime.strptime(json_data["date"], "%Y-%m-%d")
        if date_obj.year < 2010:
            raise InvalidUsage("Дата повинна бути не раніше 2010-01-01.", status_code=400)
    except ValueError:
        raise InvalidUsage("Невірний формат дати. Використовуйте YYYY-MM-DD.", status_code=400)
    
    if date_obj >= dt.datetime.today():
        api_method = "forecast.json"
    else:
        api_method = "history.json"
    
    url = f"{BASE_URL}/{api_method}?key={API_KEY}&q={json_data['location']}&dt={json_data['date']}"
    response = requests.get(url)
    
    if response.status_code != 200:
        raise InvalidUsage("Не вдалося отримати дані про погоду", status_code=response.status_code, payload={"details": response.text})
    
    data = response.json()
    weather_data = data["forecast"]["forecastday"][0]["day"]
    
    prompt = f"The weather is {weather_data['avgtemp_c']}°C with {weather_data['condition']['text']}. What should I wear?"
    ai_response = requests.post(
        AI_BASE_URL,
        headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
        json={"model": "gpt-3.5-turbo", "messages": [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": prompt}], "max_tokens": 50}
    )
    
    clothing_advice = "No advice available."
    if ai_response.status_code == 200:
        choices = ai_response.json().get("choices", [])
        if choices:
            clothing_advice = choices[0].get("message", {}).get("content", "No advice available.").strip()
    
    response_data = {
        "requester_name": json_data["requester_name"],
        "timestamp": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "location": json_data["location"],
        "date": json_data["date"],
        "weather": {
            "temp_c": weather_data['avgtemp_c'],
            "max_temp_c": weather_data['maxtemp_c'],
            "min_temp_c": weather_data['mintemp_c'],
            "wind_kph": weather_data['maxwind_kph'],
            "pressure_mb": weather_data['avghumidity'],
            "humidity": weather_data['avghumidity'],
            "condition": weather_data['condition']['text'],
            "precip_mm": weather_data['totalprecip_mm'],
            "uv_index": weather_data['uv'],
            "clothing_advice": clothing_advice
        }
    }
    return jsonify(response_data)

if __name__ == '__main__':
    app.run(debug=True)
