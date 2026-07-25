"""Synthetic catalog and behaviour simulator.

Everything produced here carries ``is_synthetic=True`` and a
``synthetic_simulation`` provenance tag that survives all the way to the API
response. This data exists to prove the pipeline computes correctly. It is not
evidence about any real audience and the reports say so.

The simulator is not random noise. It plants specific structure so the pipeline has
something real to find:

  * **latent taste**   — each listener has a genre/language preference and a
                         patience parameter; their events follow from it, so the
                         ranker has a recoverable signal rather than uniform noise.
  * **duplicate family** — one story is re-uploaded three times under season/part
                         titles with paraphrased text. The similarity gate should
                         catch all three.
  * **supply/demand gap** — one genre/language cell is deliberately under-supplied
                         while attracting zero-result searches, so the demand engine
                         has a real gap to surface.
  * **a weak chapter**  — one story has a mid-runtime chapter that bleeds listeners,
                         so the retention curve and chapter-interest features have a
                         cliff to detect.

Fully seeded: the same seed always yields the same catalog, the same events and
therefore the same metrics.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from app.core.clock import days_ago, utcnow
from app.domain.enums import ContentSource, EventType
from app.domain.models import ActivityEvent, Chapter, ContentItem

SEED = 20260725

# --- catalog vocabulary -----------------------------------------------------

_GENRE_LANGUAGE_PLAN: list[tuple[str, str, int]] = [
    # (genre, language, how many titles) — 'thriller/hi' is deliberately starved.
    ("fantasy", "en", 6),
    ("fantasy", "hi", 5),
    ("romance", "en", 6),
    ("romance", "hi", 4),
    ("thriller", "en", 5),
    ("thriller", "hi", 1),      # under-supplied on purpose
    ("horror", "en", 3),
    ("horror", "hi", 2),
    ("sci-fi", "en", 3),
    ("mythology", "hi", 3),
]

_TITLE_PARTS: dict[str, tuple[list[str], list[str]]] = {
    "fantasy": (
        ["The Awakened", "Gate of", "Shadow", "The Last", "Ashen", "Crimson", "Iron", "Silent"],
        ["Hunter", "Dungeon", "Throne", "Sovereign", "Blade", "Realm", "Ascent", "Monarch"],
    ),
    "romance": (
        ["Contract With", "Falling For", "Second", "The Billionaire's", "Married To", "Wild"],
        ["the Billionaire", "Chance", "Heart", "Promise", "Stranger", "Vow", "Monsoon"],
    ),
    "thriller": (
        ["Last Train to", "The Missing", "Midnight", "Cold", "Silent", "The Ninth"],
        ["Nocturne", "Witness", "Confession", "Case", "Alibi", "Hour", "Verdict"],
    ),
    "horror": (
        ["The House That", "Whispers of", "The Cursed", "Night of the", "The Hollow"],
        ["Remembers", "Bhoot Bangla", "Well", "Veil", "Chants", "Mirror"],
    ),
    "sci-fi": (
        ["Orbit of", "The Last", "Signal from", "Terminal", "The Quantum"],
        ["Ash", "Colony", "Kepler", "Drift", "Archive", "Divide"],
    ),
    "mythology": (
        ["The Curse of", "Rise of", "The Forgotten", "War of the", "The Divine"],
        ["Karna", "the Asura", "Yuga", "Devas", "Astra", "Vow"],
    ),
}

_PREMISE: dict[str, list[str]] = {
    "fantasy": [
        "An overlooked {role} is granted a levelling system after surviving a dungeon collapse, and must climb ranks before the gates overrun the city.",
        "A disgraced guild {role} discovers that monster cores can be refined into forbidden power, and every rank gained costs a memory.",
        "When gates open across the country, a low-rank {role} finds a blade that grows stronger each time its wielder loses something.",
        "A cartographer {role} maps a kingdom that rearranges itself each time a border treaty is signed.",
        "The last {role} of a dissolved order takes a teaching post and finds the students already know the sealed techniques.",
        "A {role} inherits a debt payable only in years of life, and the collector is patient.",
    ],
    "romance": [
        "A sharp {role} signs a two-year marriage contract with a guarded heir to save her father's firm, and the terms keep changing.",
        "Two rival {role}s are forced to share a flat during a monsoon posting and negotiate a truce that neither wants to end.",
        "A widowed {role} returns to her home town to sell a bakery and finds the man she left standing behind the counter.",
        "A {role} agrees to ghostwrite love letters for a stranger and starts recognising her own handwriting in the replies.",
        "Two {role}s meet every year on the same delayed flight and never once exchange surnames.",
        "A matchmaking {role} takes on the one client whose file she has been quietly refusing for a decade.",
    ],
    "thriller": [
        "A {role} boards the last overnight train after a witness vanishes, and every compartment holds a different version of the same lie.",
        "A {role} receives a confession recorded in her own voice for a murder she has not committed.",
        "After a body is found in a dry well, a small-town {role} realises the entire village has agreed on the same alibi.",
        "A night auditor {role} finds a hotel room billed continuously for eleven years and never once entered.",
        "A {role} investigating insurance fraud keeps finding her own signature on claims she never filed.",
        "A retired {role} is sent a jigsaw puzzle that assembles into a photograph of next Tuesday.",
    ],
    "horror": [
        "A family returns to an ancestral house where each locked room replays a memory none of them survived.",
        "A night-shift {role} starts receiving calls from a number that belongs to a building demolished a decade ago.",
        "A village bans singing after dusk; a visiting {role} learns what answers when someone forgets.",
        "A {role} cataloguing a flooded library finds the water has been rewriting the margins.",
        "Every mirror in a new housing block shows the room one second late, and a {role} is the only tenant who notices.",
        "A {role} adopts a stray that every photograph refuses to record.",
    ],
    "sci-fi": [
        "A salvage {role} recovers an archive from a dead colony that contains a recording of a conversation she has not had yet.",
        "A terraforming crew wakes to find their planet already inhabited by people with their own names and faces.",
        "A quantum courier smuggles memories between stations until one of them refuses to be delivered.",
        "A translation {role} on a first-contact team realises the aliens are quoting her back to herself.",
        "An orbital {role} maintains a station whose crew roster grows by one name every rotation.",
        "A {role} sells surplus sleep on the open market until a buyer returns a dream that is not hers.",
    ],
    "mythology": [
        "A charioteer's son is offered divine armour on the condition that he never learns who his mother is.",
        "An exiled prince bargains with an asura for a weapon that answers only to the unforgiven.",
        "A temple sculptor carves a deity that begins correcting his work at night.",
        "A river goddess is summoned to testify in a land dispute and asked to swear on herself.",
        "A {role} tasked with guarding a sleeping god must decide what to do when it starts dreaming aloud.",
        "The scribe of a great war discovers the victors have been editing the verses he has not written yet.",
    ],
}

_ROLES = ["hunter", "lawyer", "detective", "engineer", "student", "nurse", "guard", "archivist"]

# Per-item vocabulary pools. Transcripts must differ substantially between items,
# otherwise the shingle signal reports near-duplicates that are artefacts of the
# generator rather than of the story.
_NAME_SYLLABLES = ["ar", "ve", "mi", "ka", "sha", "ta", "ni", "ro", "lek", "sun", "dha", "pri", "ish", "bha"]
_PLACES = [
    "Kalighat", "Mehrangarh", "the Vashi flats", "Old Panvel", "the Dhauli ridge",
    "Sector 21", "the Ranipur mill", "Bandra Reclamation", "the Chorla pass", "Kurla depot",
    "the Wagholi yard", "Nagda junction", "the Barabanki fields", "Fort Kochi",
]
_OBJECTS = [
    "a cracked ledger", "an unsigned letter", "a burnt sim card", "a locked steel almirah",
    "a stolen relay key", "a broken tabla", "a chipped brass idol", "an inherited debt",
    "a photograph with one face cut out", "a recording nobody claims to have made",
    "a key that fits no door", "a ration card in a dead man's name",
]
_COMPLICATIONS = [
    "the police close the file too quickly",
    "a witness recants on the record",
    "the money arrives before the request does",
    "an old promise is called in",
    "the only copy is destroyed",
    "someone confesses to the wrong crime",
    "a debt is transferred without consent",
    "the timeline refuses to line up",
]
_SENTENCE_FORMS = [
    "{name} returns to {place} carrying {object}, and {complication}.",
    "In {place}, {name} learns that {object} was never theirs to hold; {complication}.",
    "{complication}. {name} answers by going back to {place} for {object}.",
    "What {name} finds in {place} is {object}, and after that {complication}.",
    "Between {place} and the next stop, {name} decides about {object}. Then {complication}.",
]

_TAGS: dict[str, list[str]] = {
    "fantasy": ["dungeon", "progression", "system", "guild", "monsters"],
    "romance": ["contract-marriage", "slow-burn", "billionaire", "second-chance"],
    "thriller": ["mystery", "detective", "small-town", "twist"],
    "horror": ["haunted", "supernatural", "curse", "folk-horror"],
    "sci-fi": ["space", "colony", "ai", "time"],
    "mythology": ["epic", "devotional", "war", "curse"],
}

#: Searches that return nothing. Concentrated in the starved cell so the demand
#: engine surfaces a gap that is actually there.
_ZERO_RESULT_QUERIES = [
    "हिंदी क्राइम थ्रिलर सीरीज",
    "हिंदी डिटेक्टिव मर्डर मिस्ट्री",
    "हिंदी सस्पेंस थ्रिलर नई कहानी",
    "हिंदी पुलिस जांच कहानी",
    "hindi detective murder mystery audio",
    "hindi crime thriller full series",
]

_NORMAL_QUERIES = [
    "dungeon hunter leveling story",
    "contract marriage romance",
    "haunted house horror hindi",
    "space colony sci-fi",
    "mythology karna story",
    "slow burn romance english",
]


@dataclass(slots=True)
class SimulationResult:
    catalog: list[ContentItem]
    events: list[ActivityEvent]
    notes: dict


@dataclass(slots=True)
class _Listener:
    user_id: str
    genre: str
    second_genre: str
    language: str
    patience: float          # 0..1 — probability of reaching the end
    replay_tendency: float
    sessions: int


class BehaviourSimulator:
    """Generates a catalog and a behaviour log with recoverable latent structure."""

    def __init__(self, *, seed: int = SEED, user_count: int = 300) -> None:
        self._rng = random.Random(seed)
        self._user_count = user_count
        self._used_titles: set[str] = set()

    def run(self) -> SimulationResult:
        catalog = self._build_catalog()
        duplicates = self._build_duplicate_family(catalog)
        catalog.extend(duplicates)
        listeners = self._build_listeners(catalog)
        events = self._build_events(catalog, listeners)
        events.extend(self._build_searches(listeners))
        events.sort(key=lambda event: event.occurred_at)

        return SimulationResult(
            catalog=catalog,
            events=events,
            notes={
                "seed": SEED,
                "catalog_items": len(catalog),
                "planted_duplicate_family": [item.content_id for item in duplicates],
                "planted_duplicate_source": duplicates[0].tags[-1] if duplicates else None,
                "under_supplied_cell": "thriller/hi",
                "weak_chapter_item": next(
                    (item.content_id for item in catalog if "weak-chapter" in item.tags), None
                ),
                "listeners": len(listeners),
                "events": len(events),
                "zero_result_searches": sum(
                    1 for event in events if event.event_type is EventType.SEARCH and event.result_count == 0
                ),
                "warning": (
                    "SYNTHETIC DATA. Generated by BehaviourSimulator for pipeline validation. "
                    "Not real listeners; not evidence about any real market."
                ),
            },
        )

    # --- catalog ------------------------------------------------------------

    def _build_catalog(self) -> list[ContentItem]:
        items: list[ContentItem] = []
        counter = 0
        for genre, language, count in _GENRE_LANGUAGE_PLAN:
            for _ in range(count):
                counter += 1
                items.append(self._make_item(counter, genre, language))
        # Plant the retention cliff on one well-populated title.
        weak = items[2]
        weak.tags = [*weak.tags, "weak-chapter"]
        return items

    def _make_item(self, index: int, genre: str, language: str) -> ContentItem:
        title = self._unique_title(genre)
        role = self._rng.choice(_ROLES)
        # Each description gets its own place and object. Without this, items sharing a
        # premise template produce near-identical narrative fingerprints and the
        # duplicate gate flags the whole genre — an artefact, not a finding.
        description = (
            f"{self._rng.choice(_PREMISE[genre]).format(role=role)} "
            f"Set around {self._rng.choice(_PLACES)}, it turns on {self._rng.choice(_OBJECTS)}, "
            f"and by the midpoint {self._rng.choice(_COMPLICATIONS)}."
        )
        chapter_count = self._rng.randint(6, 12)
        chapter_length = self._rng.randint(420, 900)
        duration = chapter_count * chapter_length

        return ContentItem(
            content_id=f"cnt_{index:04d}",
            title=title,
            description=description,
            transcript=self._make_transcript(genre, role, description, chapter_count, index),
            creator_id=f"creator_{(index % 14) + 1:02d}",
            language=language,
            genres=[genre],
            tags=self._rng.sample(_TAGS[genre], k=min(3, len(_TAGS[genre]))),
            duration_seconds=duration,
            chapters=[
                Chapter(
                    index=chapter,
                    title=f"Chapter {chapter + 1}",
                    start_seconds=chapter * chapter_length,
                    end_seconds=(chapter + 1) * chapter_length,
                    summary=f"{genre} beat {chapter + 1}: the {role} is pushed further from safety.",
                )
                for chapter in range(chapter_count)
            ],
            source=ContentSource.SYNTHETIC,
            is_synthetic=True,
            published_at=days_ago(self._rng.uniform(1, 240)),
        )

    def _make_transcript(
        self, genre: str, role: str, description: str, chapters: int, index: int
    ) -> str:
        """Each item gets its own cast, places and objects.

        Without this every item in a genre shares a sentence template and the 5-gram
        shingle signal flags the whole genre as near-duplicate — an artefact of the
        generator, not a property of the stories.
        """
        cast = [self._make_name() for _ in range(3)]
        places = self._rng.sample(_PLACES, k=3)
        objects = self._rng.sample(_OBJECTS, k=3)
        complications = self._rng.sample(_COMPLICATIONS, k=min(4, len(_COMPLICATIONS)))
        vocabulary = _TAGS[genre]

        lines = [description]
        for chapter in range(chapters):
            form = self._rng.choice(_SENTENCE_FORMS)
            lines.append(
                f"Chapter {chapter + 1}. "
                + form.format(
                    name=self._rng.choice(cast),
                    place=self._rng.choice(places),
                    object=self._rng.choice(objects),
                    complication=self._rng.choice(complications),
                )
                + f" The {role} weighs the {self._rng.choice(vocabulary)} against what it costs."
            )
        return "\n".join(lines)

    def _unique_title(self, genre: str) -> str:
        """Titles must be distinct across the catalog.

        Two unrelated stories drawing the same random title would normalise to the
        same key and be flagged as series variants — a generator collision presented
        as a duplicate finding.
        """
        prefixes, suffixes = _TITLE_PARTS[genre]
        for _ in range(200):
            candidate = f"{self._rng.choice(prefixes)} {self._rng.choice(suffixes)}"
            if candidate not in self._used_titles:
                self._used_titles.add(candidate)
                return candidate
        candidate = f"{self._rng.choice(prefixes)} {self._rng.choice(suffixes)} {len(self._used_titles)}"
        self._used_titles.add(candidate)
        return candidate

    def _make_name(self) -> str:
        return (
            self._rng.choice(_NAME_SYLLABLES) + self._rng.choice(_NAME_SYLLABLES)
        ).capitalize()

    def _build_duplicate_family(self, catalog: list[ContentItem]) -> list[ContentItem]:
        """Re-upload one story three times: a season variant, a 'the end' variant and a
        paraphrased rewrite. Exactly the pattern the brief describes."""
        source = next(item for item in catalog if item.genres == ["fantasy"] and item.language == "en")
        variants = [
            (f"{source.title} Season 3", source.transcript, "creator_copy_a"),
            (f"{source.title}: The End", source.transcript, "creator_copy_b"),
            (
                f"{source.title.replace('The ', '')} Reborn",
                self._paraphrase(source.transcript),
                "creator_copy_c",
            ),
        ]
        return [
            ContentItem(
                content_id=f"cnt_dup_{position + 1:02d}",
                title=title,
                description=source.description,
                transcript=transcript,
                creator_id=creator,
                language=source.language,
                genres=source.genres,
                tags=[*source.tags, f"duplicate-of:{source.content_id}"],
                duration_seconds=source.duration_seconds,
                chapters=source.chapters,
                source=ContentSource.SYNTHETIC,
                is_synthetic=True,
                published_at=days_ago(self._rng.uniform(1, 60)),
            )
            for position, (title, transcript, creator) in enumerate(variants)
        ]

    def _paraphrase(self, transcript: str) -> str:
        """Rewrite the surface heavily while leaving the story skeleton intact.

        This is the case the narrative-arc signal exists for: the rewrite is thorough
        enough to push 5-gram shingle overlap below the verbatim threshold, so the
        lexical signal alone would miss it. Only the arc embedding still matches.
        """
        swaps = {
            "Chapter": "Episode",
            "returns to": "makes her way back to",
            "carrying": "holding on to",
            "learns that": "comes to understand that",
            "was never theirs to hold": "had never belonged to them",
            "answers by going back to": "responds by returning to",
            "What": "The thing",
            "finds in": "uncovers at",
            "Between": "Somewhere between",
            "decides about": "makes a choice regarding",
            "Then": "After that",
            "weighs the": "measures the",
            "against what it costs": "against the price it demands",
            "the police close the file too quickly": "the case is shut far sooner than it should be",
            "a witness recants on the record": "a witness takes back their statement in public",
            "the money arrives before the request does": "payment turns up ahead of any demand",
            "an old promise is called in": "a long-standing vow is finally collected",
            "the only copy is destroyed": "the sole remaining copy is lost",
            "someone confesses to the wrong crime": "a confession is given for the wrong offence",
            "a debt is transferred without consent": "an obligation changes hands unasked",
            "the timeline refuses to line up": "the sequence of events will not reconcile",
        }
        for source, target in swaps.items():
            transcript = transcript.replace(source, target)
        return transcript

    # --- listeners ----------------------------------------------------------

    def _build_listeners(self, catalog: list[ContentItem]) -> list[_Listener]:
        genres = sorted({item.genres[0] for item in catalog})
        languages = sorted({item.language for item in catalog})
        listeners: list[_Listener] = []
        for index in range(self._user_count):
            primary = self._rng.choice(genres)
            listeners.append(
                _Listener(
                    user_id=f"user_{index + 1:04d}",
                    genre=primary,
                    second_genre=self._rng.choice([g for g in genres if g != primary]),
                    language=self._rng.choices(languages, weights=[3 if lang == "hi" else 4 for lang in languages])[0],
                    patience=self._rng.betavariate(2.4, 2.0),
                    replay_tendency=self._rng.betavariate(1.5, 6.0),
                    sessions=self._rng.randint(1, 6),
                )
            )
        return listeners

    # --- events -------------------------------------------------------------

    def _build_events(self, catalog: list[ContentItem], listeners: list[_Listener]) -> list[ActivityEvent]:
        events: list[ActivityEvent] = []
        for listener in listeners:
            picks = self._pick_content(catalog, listener)
            for session_index, item in enumerate(picks):
                events.extend(self._simulate_session(listener, item, session_index))
        return events

    def _pick_content(self, catalog: list[ContentItem], listener: _Listener) -> list[ContentItem]:
        """Weighted sampling: strong pull toward the listener's genre and language."""
        weights = []
        for item in catalog:
            weight = 1.0
            if item.genres[0] == listener.genre:
                weight *= 6.0
            elif item.genres[0] == listener.second_genre:
                weight *= 2.5
            if item.language == listener.language:
                weight *= 3.0
            else:
                weight *= 0.4
            weights.append(weight)

        count = min(listener.sessions + self._rng.randint(0, 2), len(catalog))
        picks: list[ContentItem] = []
        pool = list(catalog)
        pool_weights = list(weights)
        for _ in range(count):
            if not pool:
                break
            chosen = self._rng.choices(pool, weights=pool_weights, k=1)[0]
            position = pool.index(chosen)
            pool.pop(position)
            pool_weights.pop(position)
            picks.append(chosen)
        return picks

    def _simulate_session(
        self, listener: _Listener, item: ContentItem, session_index: int
    ) -> list[ActivityEvent]:
        session_id = f"sess_{listener.user_id}_{session_index}_{uuid4().hex[:6]}"
        start = utcnow() - timedelta(
            days=self._rng.uniform(0, 90), hours=self._rng.uniform(0, 23)
        )
        events: list[ActivityEvent] = []
        clock = start

        def emit(event_type: EventType, position: int, chapter: int | None, elapsed: int) -> None:
            nonlocal clock
            clock = clock + timedelta(seconds=max(1, elapsed))
            events.append(
                ActivityEvent(
                    event_id=f"evt_{uuid4().hex[:16]}",
                    user_id=listener.user_id,
                    content_id=item.content_id,
                    session_id=session_id,
                    event_type=event_type,
                    position_seconds=min(position, item.duration_seconds),
                    chapter_index=chapter,
                    session_seconds=int((clock - start).total_seconds()),
                    device=self._rng.choice(["android", "ios", "web"]),
                    is_synthetic=True,
                    occurred_at=clock,
                )
            )

        emit(EventType.PLAY, 0, 0, 5)

        # Genre/language fit is the latent signal the ranker is supposed to recover.
        fit = 1.0
        if item.genres[0] != listener.genre:
            fit *= 0.72 if item.genres[0] == listener.second_genre else 0.42
        if item.language != listener.language:
            fit *= 0.55

        chapter_count = len(item.chapters) or 1
        weak_chapter = chapter_count // 2 if "weak-chapter" in item.tags else -1

        # Decide completion directly rather than deriving it from a reach threshold —
        # it keeps the resulting completion rate controllable and realistic.
        completes = self._rng.random() < min(0.92, max(0.02, listener.patience * fit))
        chapters_reached = (
            chapter_count
            if completes
            else max(1, int(chapter_count * self._rng.uniform(0.12, 0.88) * (0.5 + 0.5 * fit)))
        )

        for chapter_index in range(chapters_reached):
            chapter = item.chapters[chapter_index] if item.chapters else None
            position = chapter.start_seconds if chapter else 0
            length = chapter.duration_seconds if chapter else item.duration_seconds

            # The planted weak chapter bleeds listeners regardless of taste fit.
            if chapter_index == weak_chapter and self._rng.random() < 0.55:
                emit(EventType.DROP_OFF, position + length // 3, chapter_index, length // 3)
                return events

            if self._rng.random() < 0.18:
                emit(EventType.PAUSE, position + length // 2, chapter_index, length // 2)
                if self._rng.random() < 0.7:
                    emit(EventType.RESUME, position + length // 2, chapter_index, 60)
            if self._rng.random() < listener.replay_tendency:
                emit(EventType.REPLAY, position + length // 4, chapter_index, length // 4)
            if self._rng.random() < 0.12:
                emit(EventType.SKIP, position + length, chapter_index, 20)
            if chapter_index > 0 and self._rng.random() < 0.10:
                emit(EventType.CHAPTER_JUMP, position, chapter_index, 10)

        if completes:
            emit(EventType.COMPLETE, item.duration_seconds, chapter_count - 1, 120)
            if self._rng.random() < 0.25 + listener.replay_tendency:
                emit(EventType.REVISIT, 0, 0, 3600)
        else:
            last = item.chapters[chapters_reached - 1] if item.chapters else None
            emit(
                EventType.DROP_OFF,
                (last.end_seconds if last else item.duration_seconds // 2),
                chapters_reached - 1,
                60,
            )
        return events

    def _build_searches(self, listeners: list[_Listener]) -> list[ActivityEvent]:
        """Search log, including zero-result searches concentrated in the starved cell."""
        events: list[ActivityEvent] = []
        for listener in self._rng.sample(listeners, k=min(120, len(listeners))):
            for _ in range(self._rng.randint(1, 3)):
                zero_result = self._rng.random() < 0.42
                query = self._rng.choice(_ZERO_RESULT_QUERIES if zero_result else _NORMAL_QUERIES)
                events.append(
                    ActivityEvent(
                        event_id=f"evt_{uuid4().hex[:16]}",
                        user_id=listener.user_id,
                        content_id=None,
                        session_id=f"sess_search_{listener.user_id}_{uuid4().hex[:6]}",
                        event_type=EventType.SEARCH,
                        query=query,
                        result_count=0 if zero_result else self._rng.randint(2, 12),
                        device=self._rng.choice(["android", "ios", "web"]),
                        is_synthetic=True,
                        occurred_at=utcnow() - timedelta(days=self._rng.uniform(0, 90)),
                    )
                )
        return events
