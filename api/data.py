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
]

CITIES = [
    {
        "id": "lisbon", "name": "Lisbon", "country": "Portugal",
        "first_time_pitch": "Great for: Fado & Portuguese seafood",
        "return_pitch": "New spots since your last trip: 4 fresh picks",
    },
    {
        "id": "paris", "name": "Paris", "country": "France",
        "first_time_pitch": "Great for: Chanson & French bistros",
        "return_pitch": "New spots since your last trip: 6 fresh picks",
    },
    {
        "id": "tokyo", "name": "Tokyo", "country": "Japan",
        "first_time_pitch": "Great for: City pop & izakaya crawls",
        "return_pitch": "New spots since your last trip",
    },
    {
        "id": "mexico-city", "name": "Mexico City", "country": "Mexico",
        "first_time_pitch": "Great for: Cumbia & street tacos",
        "return_pitch": "New spots since your last trip",
    },
    {
        "id": "bangkok", "name": "Bangkok", "country": "Thailand",
        "first_time_pitch": "Great for: Thai street food & rooftop DJs",
        "return_pitch": "New spots since your last trip",
    },
    {
        "id": "seoul", "name": "Seoul", "country": "South Korea",
        "first_time_pitch": "Great for: K-indie & Korean BBQ",
        "return_pitch": "New spots since your last trip",
    },
]

# city_id -> list of picks. Each pick's "why" is written as if generated from a taste
# profile; in the real pipeline this line is produced server-side from the user's actual
# cuisine picks / Spotify taste, not hardcoded per pick.
RESULTS = {
    "lisbon": [
        {
            "id": "ramiro", "type": "food", "name": "Cervejaria Ramiro",
            "meta": "Alfama · Seafood tavern", "rating": 4.8,
            "addr": "Av. Almirante Reis 1",
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
            "addr": "Av. 24 de Julho 49",
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
            "addr": "R. Dom Pedro V 129",
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
