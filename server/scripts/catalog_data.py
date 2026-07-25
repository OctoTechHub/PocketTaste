"""Curated, Pocket-FM-flavoured seed catalog.

Hindi + English dominate (as on the real platform) with a few regional titles.
Each entry is intentionally rich in genre/tone so the recommender has real signal.
"""
from __future__ import annotations

# (id, title, language, genres, tone, pacing, episode_count, avg_min, is_original,
#  is_new, popularity, coin_price, synopsis, tags)
RAW_CATALOG = [
    ("insaaf-ki-raat", "Insaaf Ki Raat", "Hindi", ["thriller", "crime"], ["dark", "suspenseful"], "fast", 84, 12, True, False, 0.92, 320, "A suspended cop hunts a serial killer who only strikes on moonless nights, while the city sleeps.", ["cop", "serial-killer", "revenge", "night"]),
    ("office-wale-dil", "Office Wale Dil", "Hindi", ["romance", "drama"], ["romantic", "emotional"], "slow-burn", 120, 15, True, False, 0.88, 280, "A driven intern and her guarded CEO fall for each other across late nights and quarterly deadlines.", ["office", "slow-burn", "ceo", "workplace"]),
    ("rakt-rahasya", "Rakt Rahasya", "Hindi", ["horror", "thriller"], ["dark", "gritty"], "medium", 66, 14, False, False, 0.71, 240, "A haveli's new caretaker discovers the walls remember every scream from a century of secrets.", ["haunted", "haveli", "ghost", "mystery"]),
    ("mumbai-mafia", "Mumbai Mafia", "Hindi", ["crime", "thriller"], ["gritty", "dark"], "fast", 98, 13, True, False, 0.9, 360, "A chawl boy climbs the underworld ladder, discovering loyalty is the deadliest currency.", ["mafia", "underworld", "gangster", "rise"]),
    ("premika", "Premika", "Hindi", ["romance"], ["romantic", "wholesome"], "slow-burn", 110, 16, False, False, 0.83, 200, "Childhood sweethearts separated by families reunite years later, both pretending they've moved on.", ["second-chance", "childhood", "small-town"]),
    ("shaktimaan-legacy", "Shaktimaan Legacy", "Hindi", ["fantasy", "mythology"], ["inspirational", "suspenseful"], "medium", 72, 18, True, True, 0.79, 300, "A modern teenager inherits an ancient guardian's powers and the war that comes with them.", ["superhero", "powers", "guardian", "destiny"]),
    ("chudail-ki-diary", "Chudail Ki Diary", "Hindi", ["horror"], ["dark", "suspenseful"], "medium", 54, 12, False, True, 0.68, 180, "A journalist reads a cursed diary aloud on a live podcast — and something starts answering back.", ["curse", "podcast", "witch", "possession"]),
    ("startup-sapne", "Startup Sapne", "Hindi", ["drama"], ["inspirational", "emotional"], "medium", 60, 17, True, False, 0.66, 160, "Three college friends bet everything on an app, only to learn the real product was their friendship.", ["startup", "friendship", "ambition"]),
    ("ishq-e-lucknow", "Ishq-e-Lucknow", "Hindi", ["romance", "drama"], ["romantic", "emotional"], "slow-burn", 96, 15, False, False, 0.74, 220, "In old Lucknow, a shayar and a courtesan's daughter write a love the city refuses to allow.", ["period", "poetry", "forbidden", "lucknow"]),
    ("kaal-chakra", "Kaal Chakra", "Hindi", ["mythology", "fantasy"], ["suspenseful", "inspirational"], "slow-burn", 88, 20, True, False, 0.81, 340, "A historian is pulled into the churn of an epic war where every choice rewrites a god's fate.", ["epic", "time", "war", "gods"]),

    ("midnight-frequency", "Midnight Frequency", "English", ["thriller", "scifi"], ["suspenseful", "dark"], "fast", 40, 22, True, True, 0.77, 300, "A night-shift radio host receives broadcasts from a station that was demolished thirty years ago.", ["radio", "time", "mystery", "signal"]),
    ("the-quiet-office", "The Quiet Office", "English", ["romance", "comedy"], ["lighthearted", "romantic"], "medium", 64, 18, False, False, 0.7, 180, "Two rival consultants stuck on the same doomed project discover sabotage is a love language.", ["office", "enemies-to-lovers", "workplace", "comedy"]),
    ("crimson-protocol", "Crimson Protocol", "English", ["scifi", "thriller"], ["gritty", "suspenseful"], "fast", 36, 24, True, True, 0.75, 280, "A memory-hacker is hired to steal a thought that could topple a government — it's her own.", ["cyberpunk", "memory", "heist", "identity"]),
    ("saltwater-hearts", "Saltwater Hearts", "English", ["romance", "drama"], ["emotional", "romantic"], "slow-burn", 80, 19, False, False, 0.72, 200, "A marine biologist and a lighthouse keeper find each other in the space between tides.", ["coastal", "slow-burn", "healing"]),
    ("the-hollow-house", "The Hollow House", "English", ["horror", "drama"], ["dark", "emotional"], "medium", 48, 20, False, False, 0.64, 160, "A grieving family moves into a home that grieves back, feeding on what they can't let go.", ["haunted", "grief", "family"]),
    ("board-room-blood", "Boardroom Blood", "English", ["thriller", "crime"], ["dark", "gritty"], "medium", 52, 21, True, False, 0.69, 240, "A whistleblower inside a trillion-dollar firm has 30 days before the audit — and the assassins — arrive.", ["corporate", "conspiracy", "whistleblower"]),
    ("last-laugh-comedy", "Last Laugh", "English", ["comedy", "drama"], ["lighthearted", "inspirational"], "medium", 44, 16, False, True, 0.62, 120, "A washed-up standup gets one final open-mic to prove his best joke is his own second chance.", ["standup", "comeback", "feel-good"]),
    ("neon-monsoon", "Neon Monsoon", "English", ["scifi", "romance"], ["emotional", "suspenseful"], "slow-burn", 42, 23, True, True, 0.73, 260, "In a flooded future Mumbai, two strangers share the same recurring dream of a city that never drowned.", ["dystopia", "dream", "climate", "romance"]),
    ("the-alibi-club", "The Alibi Club", "English", ["crime", "comedy"], ["lighthearted", "suspenseful"], "fast", 38, 17, False, False, 0.6, 140, "Four retirees run a discreet business manufacturing perfect alibis — until a real murder uses one.", ["heist", "comedy", "whodunit"]),

    ("nadhi-oram", "Nadhi Oram", "Tamil", ["romance", "drama"], ["emotional", "romantic"], "slow-burn", 70, 16, True, False, 0.67, 180, "Along a river town, a schoolteacher and a fisherman's daughter fall in love against the current of caste.", ["riverside", "period", "forbidden"]),
    ("iravu-kolai", "Iravu Kolai", "Tamil", ["crime", "thriller"], ["dark", "suspenseful"], "fast", 58, 14, False, True, 0.65, 200, "A rookie inspector races a killer who leaves classical ragas at every crime scene.", ["detective", "music", "serial"]),
    ("prema-pandiri", "Prema Pandiri", "Telugu", ["romance", "comedy"], ["romantic", "lighthearted"], "medium", 62, 15, True, False, 0.63, 160, "A fake engagement to satisfy two villages becomes dangerously real for a reluctant couple.", ["fake-relationship", "village", "family"]),
    ("maya-nagaram", "Maya Nagaram", "Telugu", ["thriller", "scifi"], ["suspenseful", "gritty"], "fast", 46, 18, True, True, 0.61, 220, "A city planner realizes the smart-city AI is quietly redesigning citizens, not streets.", ["ai", "city", "conspiracy"]),
    ("mon-er-manush", "Moner Manush", "Bengali", ["romance", "drama"], ["emotional", "wholesome"], "slow-burn", 68, 17, False, False, 0.62, 150, "Two pen-pals who have written for a decade finally agree to meet — on the day a storm hits Kolkata.", ["letters", "slow-burn", "kolkata"]),
    ("andhakar", "Andhakar", "Bengali", ["horror", "thriller"], ["dark", "suspenseful"], "medium", 50, 15, True, True, 0.59, 170, "A folklore professor returns to her village to debunk a legend and becomes its next chapter.", ["folklore", "village", "curse"]),
    ("zid", "Zid", "Marathi", ["drama", "thriller"], ["gritty", "inspirational"], "medium", 56, 16, True, False, 0.6, 150, "A Kabaddi coach from the slums builds a team of outcasts to take on the state champions.", ["sports", "underdog", "kabaddi"]),
    ("samudra-katha", "Samudra Katha", "Marathi", ["mythology", "fantasy"], ["inspirational", "suspenseful"], "slow-burn", 64, 19, False, False, 0.58, 190, "A fisherwoman strikes a bargain with a sea-deity and must repay it before the next full moon.", ["sea", "deity", "bargain", "coastal"]),

    ("dilli-heist", "Dilli Heist", "Hindi", ["crime", "comedy"], ["lighthearted", "gritty"], "fast", 40, 13, True, True, 0.7, 160, "A gang of small-time cons attempt to rob a corrupt minister during a live TV awards night.", ["heist", "comedy", "delhi"]),
    ("aakhri-station", "Aakhri Station", "Hindi", ["drama", "romance"], ["emotional", "romantic"], "slow-burn", 92, 15, False, False, 0.76, 210, "Strangers on a stranded night train share the stories that made them, before the tracks clear at dawn.", ["train", "anthology", "strangers"]),
    ("code-name-ananya", "Code Name Ananya", "English", ["thriller", "crime"], ["suspenseful", "gritty"], "fast", 48, 20, True, True, 0.74, 300, "A RAW analyst goes off-book when the mole she's hunting turns out to be wearing her own face.", ["spy", "espionage", "double-agent"]),
]
