# Demo script for the Fabien call

Ten minutes, then questions. The point is not the tool. The point is that he watches you think like someone who already works on the pasture team, and never feels the need to test you.

## Two days before the call: send it

Email Fabien (Alex cc'd) with the repo link, the live URL, and a 90-second screen recording. Suggested text is in `docs/email-to-fabien.md`. The recording should be you drawing a pasture, hitting Plan, and toggling equal-area on. No narration about yourself. Let the strips narrow over the swale and say one sentence about why.

If he opens it before the call, the call is a code review you are running. If he doesn't, you demo it live and nothing is lost.

## 0:00 The one sentence

"Satellites tell you what grew, the collars tell you what got eaten, and the difference is what's left to graze. Nobody but Nofence and Halter has both halves at pasture resolution, and Nofence has the goat and sheep half Halter doesn't."

Stop. Let him react. This sentence is the whole pitch and he will either nod or push on it, and either is good.

## 0:30 Why this and not something else

"Alex said you're splitting into an animal team and a pasture team. I wanted to show up with a piece of the pasture team's problem already worked, so you could judge the work instead of the resume. I picked the piece that virtual fencing makes possible and physical fencing never did: paddocks that follow the feed."

## 1:00 Live: Colorado

Load the Colorado preset. Say what the grey and green mean (RAP herbaceous production, 30 m, lb per acre). Hit Plan.

Point at the strips narrowing over the swale. "Same forage in every strip, so the same number of days in every strip. Equal-area paddocks would put the herd on strip 1 for ten days and strip 16 for four."

Toggle **Overlay the other cut**. That is the picture. Let it sit for a few seconds.

## 2:30 Live: California, goats

Load California. Point at the *medium* and *low* grades under the oaks. "This is the tool telling you where not to trust it. Above about 30 percent canopy the satellite is looking at leaves, and for goats the herbaceous number leaves out the browse they actually eat. I'd rather the app say 'I don't know' here than give a confident wrong number."

This is the moment that maps onto the culture Alex described. Say it plainly: "I built the limitations panel before I built the download button."

## 4:00 What it can't see

Walk the list quickly. Production not standing crop. Trees. Browse. Annual latency, 16-day exists but only in Earth Engine. US only.

Then the turn: "The first one is the important one. The only instrument that knows what was already eaten is your collar. The heat maps you already ship are the missing input. That's why this belongs inside the product and not next to it."

## 5:30 How it would plug in

Keep it to the shape, not the details, and use their names for things: RAP ingest as a Windmill job, per-pasture biomass in ClickHouse next to the collar series, pastures and strips in PostGIS, the cut is a pure function in the Python service, the screen is the existing strip-grazing screen plus a forage layer and a "suggest strips" button. Then: "My first month would be replacing my synthetic 'what was eaten' gap with your grazing records."

## 6:30 Hand it to him

"Where does this break on real farms?" Then be quiet.

He will tell you things about their data you cannot learn any other way: how pastures are actually drawn, how often people move strips, what the heat map resolution is, whether they already have forage estimates in the roadmap. Every answer is a follow-up you can write in the thank-you note.

Other questions that are worth asking if there's room:

- "Is the pasture team starting from the app side or the data side?"
- "How much of the 20 million grazing days is queryable today, and at what resolution?"
- "What's the state of pasture geometry in the backend? Are boundaries versioned when a strip moves?"

## Closing

"If it's useful, I'll write up a one-page note on where I'd take this in the first month and send it over." That note is your second touch and it is the thing that turns this from a call into a start date.

## If he asks something you can't answer

One sentence naming the gap, one sentence on the adjacent thing you do know, then stop. Fabien built HerdNet; he can tell a bluff at 100 metres.

## Things not to do

- Don't demo the Norway preset unless he asks about Europe. It is synthetic and you don't want the first thing he sees to be fake data.
- Don't say "AI". Nothing in this tool is a model you trained, and he will respect that more than the alternative.
- Don't discuss hours or pay unless he raises it. Alex has that conversation.
