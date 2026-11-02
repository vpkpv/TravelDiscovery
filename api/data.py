# Placeholder data standing in for the real pipeline described in the architecture doc:
# YouTube transcript extraction -> Gemini structured extraction -> Google Places grounding
# (food) and Spotify taste matching (music). Only Lisbon has full sample results for now —
# every other city returns an empty result set so the UI's empty state is exercised too.

CUISINES = [
    "Italian", "Japanese", "Mexican", "Thai", "French", "Indian",
    "Mediterranean", "Korean", "Vietnamese", "Peruvian", "Ethiopian",
    "Spanish", "Turkish", "Southern & BBQ",
]

MUSIC_GENRES = [
    "Jazz", "Fado / World", "Classical", "Rock", "Indie",
    "Electronic", "Soul / R&B", "Country", "Blues", "Folk",
    "Pop", "Hip-Hop / Rap", "Latin",
]

CITIES = [
    {"id": "lisbon", "name": "Lisbon", "country": "Portugal", "pitch": "Great for: Fado & Portuguese seafood"},
    {"id": "paris", "name": "Paris", "country": "France", "pitch": "Great for: Chanson & French bistros"},
    {"id": "tokyo", "name": "Tokyo", "country": "Japan", "pitch": "Great for: City pop & izakaya crawls"},
    {"id": "mexico-city", "name": "Mexico City", "country": "Mexico", "pitch": "Great for: Cumbia & street tacos"},
    {"id": "bangkok", "name": "Bangkok", "country": "Thailand", "pitch": "Great for: Thai street food & rooftop DJs"},
    {"id": "seoul", "name": "Seoul", "country": "South Korea", "pitch": "Great for: K-indie & Korean BBQ"},
    {"id": "mumbai", "name": "Mumbai", "country": "India", "pitch": "Great for: Street food crawls & spice-forward classics"},
    {"id": "new-york", "name": "New York", "country": "USA", "pitch": "Great for: Delis, pizza slices & late-night bites"},
    {"id": "rome", "name": "Rome", "country": "Italy", "pitch": "Great for: Trattoria classics & gelato hunting"},
    {"id": "chicago", "name": "Chicago", "country": "USA", "pitch": "Great for: Deep dish & tavern-style pizza tours"},
    {"id": "los-angeles", "name": "Los Angeles", "country": "USA", "pitch": "Great for: Taco trucks & backyard DJ sets"},
    {"id": "las-vegas", "name": "Las Vegas", "country": "USA", "pitch": "Great for: Celebrity-chef outposts & late-night residencies"},
    {"id": "new-delhi", "name": "New Delhi", "country": "India", "pitch": "Great for: Mughlai classics & modern Indian fine dining"},
]

# city_id -> list of picks. Each pick's "why" is written as if generated from a taste
# profile; in the real pipeline this line is produced server-side from the user's actual
# cuisine picks / Spotify taste, not hardcoded per pick.
RESULTS = {
    "lisbon": [
        {
            "id": "ramiro", "type": "food", "name": "Cervejaria Ramiro",
            "meta": "Alfama · Seafood tavern", "rating": 4.8,
            "addr": "Av. Almirante Reis 1", "cuisine": "Mediterranean",
            "why": "Because you picked Mediterranean & seafood-forward cuisines",
        },
        {
            "id": "tascadochico", "type": "music", "name": "Tasca do Chico",
            "meta": "Live Fado, nightly", "genre": "Fado / Acoustic",
            "addr": "R. do Diario de Noticias 39",
            "why": "Because your taste leans heavy on acoustic & world music",
        },
        {
            "id": "timeout", "type": "food", "name": "Time Out Market",
            "meta": "24 kitchens, small plates", "rating": 4.6,
            "addr": "Av. 24 de Julho 49", "cuisine": "Other",
            "why": "Because you like exploring variety over one cuisine",
        },
        {
            "id": "luxfragil", "type": "music", "name": "Lux Fragil",
            "meta": "Club, house / electronic", "genre": "House / Electronic",
            "addr": "Av. Infante D. Henrique",
            "why": "Because your taste skews electronic late at night",
        },
        {
            "id": "cevicheria", "type": "food", "name": "A Cevicheria",
            "meta": "Peruvian ceviche bar", "rating": 4.7,
            "addr": "R. Dom Pedro V 129", "cuisine": "Peruvian",
            "why": "Because you picked Peruvian cuisine",
        },
        {
            "id": "hotclube", "type": "music", "name": "Hot Clube de Portugal",
            "meta": "Jazz club, since 1948", "genre": "Jazz",
            "addr": "Praca da Alegria 39",
            "why": "Because you have jazz artists in heavy rotation",
        },
    ],
}
