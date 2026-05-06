# MP3Wrapped

MP3Wrapped is a tool that generates a **Spotify Wrapped–style summary** for users of MP3 players running Rockbox. It provides listening insights for locally stored music, allowing users to analyze their habits without relying on streaming platforms.

---

## Features

* Parses Rockbox listening history logs
* Generates Spotify Wrapped–style summaries (top artists, albums, listening trends)
* Integrates with external APIs for metadata enrichment
* Uses a fallback system for improved reliability
* Caches processed data for faster subsequent runs
* Outputs an interactive HTML report

---

## How It Works

MP3Wrapped processes listening history data from Rockbox and builds a structured dataset of your music activity. It then:

1. Parses and aggregates listening data
2. Enriches metadata using external APIs
3. Generates a formatted HTML summary

The result is a visual, easy-to-navigate “Wrapped”-style report for your local music library.

---

## Setup

### 1. Download the Project

* Download the repository as a `.zip` file and extract it

### 2. Create API Accounts

You will need API access for metadata:

* Register at https://musicbrainz.org/register
* Visit https://developer.spotify.com/documentation/web-api to obtain:

  * `CLIENT_ID`
  * `CLIENT_SECRET`

### 3. Configure the Project

* Open `config.json` in the root directory
* Add your API credentials
* Set the path to your music folder (or place your music inside the provided folder)

### 4. Run the Program

* Run `MP3Wrapped.bat`

> Note: The first run may take longer as the program catalogs your music. Future runs are significantly faster due to caching.

---

## Output

After execution, the program generates a `wrapped.html` file that automatically opens in your browser. This file contains your personalized listening summary.

---

## API Design

MP3Wrapped uses a dual-source approach for metadata:

* **Primary:** MusicBrainz API
* **Fallback:** Spotify API

This improves reliability and ensures more complete album and artist data when one source is missing information.

---

## Example Output

![Screenshot](images/Screenshot%202026-05-06%20131522.png)
![Screenshot](images/Screenshot%202026-05-06%20131531.png)
![Screenshot](images/Screenshot%202026-05-06%20131538.png)
![Screenshot](images/Screenshot%202026-05-06%20131552.png)
![Screenshot](images/Screenshot%202026-05-06%20131618.png)
![Screenshot](images/Screenshot%202026-05-06%20131837.png)
![Screenshot](images/Screenshot%202026-05-06%20131912.png)

---

## Notes

* This project is actively being developed and may have rough edges
* Feedback and suggestions are welcome

---