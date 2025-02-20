from flask import Flask, render_template, request, jsonify
import sqlite3
from apscheduler.schedulers.background import BackgroundScheduler
import requests

app = Flask(__name__)
DB_NAME = 'velos_station.db'

# Initialize the database
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS stations (
        ville TEXT,
        nom TEXT,
        adresse TEXT,
        velos_disponibles INTEGER,
        places_disponibles INTEGER,
        statut TEXT,
        latitude REAL,
        longitude REAL,
        UNIQUE(nom, adresse)
    )
    ''')
    conn.commit()
    conn.close()

init_db()

# Fetch data for Lille
def fetch_data_lille():
    url = "https://data.lillemetropole.fr/data/ogcapi/collections/vlille_temps_reel/items"
    response = requests.get(url, params={"limit": 289, "offset": 0})
    if response.status_code == 200:
        data = response.json()
        stations = []
        for station in data['features']:
            info = station['properties']
            stations.append({
                "nom": info.get("nom"),
                "adresse": info.get("adresse"),
                "velos_disponibles": info.get("nb_velos_dispo"),
                "places_disponibles": info.get("nb_places_dispo"),
                "statut": info.get("etat"),
                "coordonnees": station['geometry']['coordinates']
            })
        return stations
    else:
        print(f"Erreur {response.status_code} pour Lille")
        return []

# Fetch data for Strasbourg
def fetch_data_strasbourg():
    url = "https://data.strasbourg.eu/api/explore/v2.1/catalog/datasets/stations-velhop/records?"
    response = requests.get(url, params={"limit": 100, "offset": 0})
    if response.status_code == 200:
        data = response.json()
        stations = []
        for record in data['results']:
            stations.append({
                "nom": record.get("na"),
                "adresse": record.get("id"),
                "velos_disponibles": record.get("av"),
                "places_disponibles": record.get("fr"),
                "statut": "ouverte" if record.get("is_renting") == 1 else "fermée",
                "coordonnees": [record["lon"], record["lat"]]
            })
        return stations
    else:
        print(f"Erreur {response.status_code} pour Strasbourg")
        return []

# Fetch data for Toulouse
def fetch_data_toulouse():
    url = "https://data.toulouse-metropole.fr/api/explore/v2.1/catalog/datasets/api-velo-toulouse-temps-reel/records?"
    response = requests.get(url, params={"start": 0, "rows": 100})
    if response.status_code == 200:
        data = response.json()
        stations = []
        for record in data['results']:
            stations.append({
                "nom": record.get("name"),
                "adresse": record.get("address"),
                "velos_disponibles": record.get("available_bikes"),
                "places_disponibles": record.get("available_bike_stands"),
                "statut": "ouverte" if record.get("status") == "OPEN" else "fermée",
                "coordonnees": [record["position"]["lon"], record["position"]["lat"]]
            })
        return stations
    else:
        print(f"Erreur {response.status_code} pour Toulouse")
        return []

# Insert data into SQLite
def insert_data(ville, stations):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.executemany('''
        INSERT OR REPLACE INTO stations (ville, nom, adresse, velos_disponibles, places_disponibles, statut, latitude, longitude)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', [
        (
            ville,
            station['nom'],
            station['adresse'],
            station['velos_disponibles'],
            station['places_disponibles'],
            station['statut'],
            station['coordonnees'][1],
            station['coordonnees'][0]
        )
        for station in stations
    ])
    conn.commit()
    conn.close()

# Update data for all cities
def update_all_cities():
    stations_lille = fetch_data_lille()
    stations_strasbourg = fetch_data_strasbourg()
    stations_toulouse = fetch_data_toulouse()
    insert_data('Lille', stations_lille)
    insert_data('Strasbourg', stations_strasbourg)
    insert_data('Toulouse', stations_toulouse)
    print("Données mises à jour.")

# Scheduler for updating data every 5 minutes
scheduler = BackgroundScheduler()
scheduler.add_job(update_all_cities, 'interval', minutes=5)
scheduler.start()

# Get stations by city
def get_stations_by_city(city):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM stations WHERE ville = ?', (city,))
    stations = cursor.fetchall()
    conn.close()
    return stations

# Home route
@app.route("/", methods=["GET", "POST"])
def index():
    city = request.form.get("city") if request.method == "POST" else None
    return render_template("index.html", city=city)

# API route to get stations data
@app.route("/api/stations/<city>")
def api_stations(city):
    stations = get_stations_by_city(city)
    return jsonify(stations)

if __name__ == "__main__":
    update_all_cities()  # Initial data update
    app.run(debug=True)