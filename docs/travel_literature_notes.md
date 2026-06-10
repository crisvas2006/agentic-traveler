# Travel literature notes

> Seed corpus for the curiosity-prompts library (`backend/.../content/curiosity_prompts.yaml`)
> and a future Aletheia blog. Each note pairs a short, fair-use passage (or a
> clearly-marked paraphrase where I'm not certain of the exact wording) with how
> it shaped a design choice, and lists the prompt ids it seeded.
>
> **Founder note:** verify exact quotations and page references against your own
> copies before any public/blog use; paraphrases are marked *(paraphrase)*.
> This is founder-voice content — edit freely.

---

## Alain de Botton — *The Art of Travel* (2002)

> *(paraphrase)* de Botton opens by arguing that few activities reveal as much
> about the search for happiness — in all its ardour and its paradoxes — as our
> travels.

This is the sentence that reorders how Aletheia begins. Most travel apps start
with a form: dates, destination, budget. De Botton's insight is that the *wanting*
comes first, and that the wanting is itself part of the trip — sometimes the best
part. So the dashboard's vision banner is not a field labelled "Vision." It's a
sentence we coax out of the traveller while they're still dreaming, because the
act of saying what you hope for is where a trip quietly begins. The same idea
makes us ask for the *image* in someone's head rather than their "goals" — an
image is concrete and kind to answer; a goal sounds like work. We resist the urge
to be efficient too early. A person who can already name their dates doesn't need
us; a person staring at a blank map needs a friend who asks the right small
question and then gets out of the way.

Seeded prompts: `anticipation`, `one_word`, `first_morning`, `stayed_with_you`.

---

## Pico Iyer — *The Art of Stillness* (2014)

> *(paraphrase)* Iyer suggests that in an age of acceleration, the real luxury —
> and sometimes the whole point of going somewhere — is to sit still.

We built a travel product, and then Iyer talked us out of assuming that travel
means *doing*. A surprising number of trips are really about subtraction: fewer
emails, slower mornings, one genuinely empty afternoon. If we only ever optimise
for more — more sights, more steps, more value — we quietly punish the traveller
who came to switch off. So the planner offers stillness as a first-class option,
not an apology ("want a genuinely empty afternoon built in, or keep it full?"),
and the in-trip check-in asks the lightest possible question — too much, too
little, or about right? — and then actually adjusts. Iyer is also why our prompts
always offer the *no*: "one small intention — or would you rather not set one?"
The freedom to decline is part of stillness.

Seeded prompts: `doing_or_nothing`, `empty_afternoon`, `too_much_or_right`,
`one_intention`.

---

## Pico Iyer — *"Why We Travel"* (Salon essay, 2000)

> *(paraphrase)* We travel, Iyer writes, initially to lose ourselves, and then to
> find ourselves; we go to bring home the stories.

The essay gave us two design instincts. First: motive is mixed and a little
embarrassing, so we ask for it gently and let "getting away from something" be a
perfectly respectable answer alongside "heading toward something." Second: if the
souvenir of a trip is the story you tell afterwards, then the post-trip moment
deserves more than a star rating. The journal prompt "what surprised you that
you'd actually tell a friend about?" is lifted straight from this — the
"tell-a-friend" frame keeps reflection social and low-stakes, which matters
doubly when the listener is an AI.

Seeded prompts: `away_or_toward`, `would_tell_friend`.

---

## Rebecca Solnit — *Wanderlust: A History of Walking* (2000)

> *(paraphrase)* Solnit treats walking as a way of thinking and of knowing a
> place — the pace at which the body and the mind keep company.

Solnit is why "pace" in Aletheia is never just a slider. Some places are for
walking until you're a little lost; others are for settling into. Knowing which
changes everything downstream — how dense we make the days, whether we cluster by
neighbourhood, how much transit we tolerate. Rather than ask an abstract "what's
your pace?", we offer the felt binary: *wander till I'm a little lost*, or *know
roughly where I'm headed*. It's answerable in three words and it tells us more
than a number would.

Seeded prompts: `lost_or_mapped`, `walk_or_settle`.

---

## Rick Steves — *Travel as a Political Act* (2009)

> *(paraphrase)* Steves argues that travel done well gets you past the postcard —
> into the quiet corner, the ordinary street, the local rhythm.

Steves is the patron saint of our "famous-or-quiet" instinct. The product should
never just list the top-ten temples; it should ask whether you want the famous
thing or the quiet corner near the famous thing, and plan accordingly. He's also
behind our experiential anchoring: "if you only got one afternoon there, where
would you want to be?" forces the single thing that matters and gives the whole
itinerary a centre of gravity. And his attention to season and timing — without
preaching about it — shaped how we ask "any reason this time of year, or just
when life allows?", with the non-answer made explicitly fine.

Seeded prompts: `famous_or_quiet`, `one_afternoon`, `anchor_day`, `why_now`,
`today_one_good`.

---

## Seneca — *Letters from a Stoic*, Letter XXVIII (c. 65 CE)

> *(paraphrase)* Seneca's traveller is restless because, as he puts it, they
> change their climate but not their soul — the self comes along for the ride.

This is the most dangerous idea to put near a travel product, because taken
badly it says "don't bother going." Taken well, it's a gift: a trip is a chance
to set something down for a week — a workload, a phone habit, a mood — even if you
can't outrun yourself entirely. We let Seneca in only at the threshold, just
before departure, and only as a light, opt-out-friendly aside: "anything you're
hoping to leave behind for a week?" Never as a lecture. The Stoics are wonderful
right up until they're preachy; our job is to borrow the wisdom and leave the
sermon.

Seeded prompts: `leave_behind`.

---

## Philip L. Pearce — *Travel Career Ladder* (1988)

> *(paraphrase)* Pearce models travel motivation as a ladder — needs that change
> over a person's travelling life, from novelty and escape up toward fulfilment
> and self-development.

Pearce is the academic spine under a lot of the soft questions. Two of his axes
do real work for us: social vs. self-directed ("people around, or mostly you and
the place?") and depth vs. breadth ("one place gone deep, or a few, lighter
touch?"). His ladder also justifies treating each trip as shaping the next — so
the post-trip prompt "would you go back, or did it make you curious about
somewhere new?" isn't idle; it's the seed of the following trip. We keep his
framework invisible: the traveller feels asked a friendly either/or, never sat
down for a motivation inventory.

Seeded prompts: `people_or_place`, `deep_or_wide`, `gutted_to_miss`,
`back_or_new`.

---

## Rolf Potts — *Vagabonding* (2003)

> *(paraphrase)* Potts frames travel as a deliberate use of time and money — and
> a practice of staying open to the trip changing under your feet.

Potts keeps us honest about two things. One: spending is a values statement, so
"if you splurged on exactly one thing, what would it be?" reveals priorities
without a budget interrogation. Two: improvisation is a personality, not a
failure of planning — some travellers want the plan to hold, others want it to
bend. Asking "how open are you to the plan changing once you're there?" tells the
in-trip companion how tightly to hold the itinerary, which is exactly the kind of
thing a good human guide reads intuitively and a bad app ignores.

Seeded prompts: `move_or_sit`, `one_splurge`, `open_to_change`, `do_differently`.

---

## Bruce Chatwin — *The Songlines* (1987)

> *(paraphrase)* Chatwin's central image is of land sung into meaning — places as
> carriers of story, mapped by the tales told across them.

Chatwin reminds us that a destination is rarely chosen at random; it's usually
been *sung* to us first — by a film, a grandparent, a novel, a photograph. So
instead of asking the blank "why here?", we offer the hooks: "any reason this
place has been on your mind — a story, a person, a film?" And his sense of memory
as something you carry shapes the journal: "if you kept just one memory from it,
which would you keep?" forces a single vivid thing worth saving, rather than a
dutiful recap.

Seeded prompts: `why_on_your_mind`, `keep_one_memory`.

---

## Robert Macfarlane — *The Old Ways* (2012)

> *(paraphrase)* Macfarlane walks old paths and attends to the small, overlooked
> textures of a landscape — what the inattentive eye walks straight past.

Macfarlane trained our attention on texture. A place doesn't just have a
temperature; it has a *feel* — warm and slow, or crisp and alive. Offering those
two as a mood choice gives us more usable signal than "what's the weather you
like." And his noticing is the model for the gentlest in-trip prompt we have:
"anything catch your eye today you didn't expect?" — a question that asks nothing
of the traveller's plans and everything of their attention, which is where the
good memories actually live.

Seeded prompts: `warm_or_crisp`, `noticed_today`.

---

## Patrick Leigh Fermor — *A Time of Gifts* (1977)

> *(paraphrase)* Leigh Fermor crosses Europe on foot, in no hurry, letting the
> journey be long and the days be deep.

Leigh Fermor is the antidote to itinerary-stuffing. His whole posture says: the
extra days don't have to mean extra places. So when a trip has slack in it, we
ask the question he'd ask — "would a few extra days mean more places, or just
more time in the ones you've got?" Most over-packed itineraries come from never
asking it. He's a reminder that depth is a legitimate, even superior, use of
time, and that a good planner should make slowing down as easy to choose as
adding more.

Seeded prompts: `more_or_slower`.

---

## Bill Bryson — *Notes from a Small Island* (1995)

> *(paraphrase)* Bryson's travel writing is affectionate and very funny —
> deflating his own grand intentions, often via lunch.

Bryson earns a place here for tone, which is a design decision too. Not every
curiosity prompt should be earnest; an AI asking sincere questions all day gets
tiresome and a little uncanny. Humour is permission. "Be honest — how much of
this trip is secretly about the food?" lets the traveller answer playfully, and a
playful answer is still real signal (it usually is about the food). Bryson keeps
our literate streak from tipping into solemnity.

Seeded prompts: `food_share`.

---

## Maya Angelou — *All God's Children Need Traveling Shoes* (1986)

> *(paraphrase)* Angelou's account of seeking belonging in Ghana turns travel
> into a question about home as much as away.

Angelou complicates the cheerful "broaden your horizons" cliché. Travel can
change how you see the place you came from — sometimes that's the whole point,
and sometimes it's an unexpected ache. We hold this lightly in the post-trip
prompt "did it shift how you see anything back home, even a little?" The "even a
little" is deliberate: it invites a modest, honest answer instead of demanding a
transformation. Belonging is a big theme; we ask about it with a small door.

Seeded prompts: `shifted_anything`.
