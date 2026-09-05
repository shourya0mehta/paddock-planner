# Email to send Fabien two days before the call

Reply in the existing thread so Alex stays cc'd. Keep the recording under 90 seconds and don't narrate your background in it.

---

**Subject:** Re: Interest in Joining NoFence

Hi Fabien,

Looking forward to Wednesday. After talking with Alex I wanted to come with something concrete rather than a resume, so I built a small tool around one idea: virtual paddocks that follow the forage instead of the fence line.

You draw a pasture, it reads satellite forage for every 30 m pixel inside it, and it cuts the pasture into strips of equal feed rather than equal area, with dates and a confidence grade per strip. The interesting part is what it can't see. It knows what grew, but only the collars know what was eaten, so I think it belongs inside a product like yours rather than next to one.

Repo: {REPO_URL}
Live: {LIVE_URL}
90-second walkthrough: {LOOM_URL}

Happy to walk through it on the call, or skip it entirely if you'd rather just talk.

Best,
Shourya

---

Notes on the placeholders: put the live URL on something that survives a cold start (Fly.io, Render, or Cloud Run all take the Dockerfile as is). Record the walkthrough on the Colorado preset with real RAP data, and toggle the equal-area overlay on camera; that is the shot.
