---
name: viral-ugc-ads
description: >-
  Create scroll-stopping viral UGC video ads with the higgsfield-unlimited MCP.
  Use whenever the task is making ads, UGC clips, TikTok/Reels/Shorts/Facebook
  video creative, hooks, testimonials, product demos, or "viral" short-form video
  — especially with generate_image / generate_video. Bundles the UGC prompt
  formula, 12 copy-paste ad templates, 40+ viral hook patterns, a photoreal
  character/headshot formula, human-imperfection realism rules, best-model
  selection, and the image→2-part-video pipeline for consistent characters.
---

# Viral UGC Ads (higgsfield-unlimited)

Build native-feeling, scroll-stopping short-form video ads. Native UGC feels
**specific, casual, and lightly imperfect** — not a polished commercial. Describe
*creator behavior*, not just the product.

## 0. Golden rules

1. **First 2 seconds decide everything.** Lead every prompt with the hook — a
   problem, contradiction, curiosity gap, or hyper-specific moment.
2. **Make people slightly imperfect.** Real humans have small flaws. Add them
   explicitly to every character/person prompt (see §4) or output looks fake.
3. **Use the best unlimited model, always.** Unlimited is free — never settle for
   a weaker model to save cost. Pick by job (see §5).
4. **Test angles, change one variable at a time.** Per concept generate ≥3
   variations: problem-led, curiosity-led, benefit-led. Keep the rest constant.
5. **Research the GENERAL viral category, not only your niche.** Copy the *format*
   of what's viral broadly (POV, "tell me without telling me", green-screen react,
   day-in-the-life, text-message story, satisfying loop) and pour your product in.
6. **Vertical 9:16, leave caption room** (lower third + center), many watch muted.
7. **Claim safety.** No medical/financial/body/unrealistic guarantees. Use
   experience wording ("here's what I noticed", "I like how…"). Never imply a
   fictional/AI creator is a real customer; no real celebrities or copied likeness.

## 1. The UGC prompt formula

```
Creator type + product + setting + first-2s hook + demo action + proof point
+ camera style + lighting + voiceover line + caption text + CTA + 9:16
```

Every field ties the output to a testable ad job. Be specific about the hook and
the proof point ("my desk felt less cluttered" beats "amazing results").

## 2. The 12 copy-paste templates

Replace every `[bracket]`. Generate 3 hook variations of each.

1. **Talking-head review** — "Create a vertical UGC talking-head of a [creator]
   reviewing [product] in [setting]. Hook: 'I didn't expect [benefit] to be this
   easy.' Handheld phone footage, natural indoor light, slight framing
   imperfections, captions <8 words, CTA: 'Try it if you want [benefit].' 9:16."
2. **Problem-solution** — frustrated-with-[problem] shot → "This is what finally
   helped me with [problem]" → quick demo → soft result. Casual home light.
3. **Unboxing** — hands opening package, texture close-up, reaction, one practical
   feature. Daylight, small camera shake, captions "First impression / Actually
   useful", CTA "Would you try this?"
4. **Beauty/skincare demo** — mirror + soft morning light. Hook "My routine
   needed one simple upgrade." Texture on hand, natural application, calm reaction.
   NO before/after or medical claims.
5. **Fashion try-on** — neck-down mirror, outfit reveal, 3 angles (front/side/
   walk), fast jump cuts, captions "fit check / easy to style".
6. **App / SaaS walkthrough** — "I found a faster way to [task]" → phone-screen
   shots of 3 simple steps. Show ONE task, not every feature.
7. **Gadget demo** — "This tiny thing fixed my [problem]" → pick up/use → one
   clear result. Hands-on close-ups.
8. **Food / beverage** — open on pour/bite/steam/plating. "I tried this because I
   wanted something [benefit]." Texture, serving, reaction. Warm kitchen light.
9. **Fitness product** — "I needed something simple for [goal]." Use in home
   gym/outdoor, detail shots, realistic effort. No body-transformation claims.
10. **Faceless UGC** — hands, product close-ups, phone screen, lifestyle only.
    Text overlay "I wish I found this earlier." Captions <8 words, CTA "See how
    it works." Great for product-image→video.
11. **Testimonial-style** — "I've been using this for [time], here's what I
    noticed." Experience wording only; don't imply a real customer.
12. **Hook variation test** — same demo, 3 openings: 1) problem 2) curiosity
    3) result. Change ONLY the first line so you can judge the hook.

## 3. Viral hook patterns (the part most people miss)

The trend is *away* from "guru" hooks toward lines that read like **a genuine
human moment someone articulated perfectly.** Steal these structures:

- **Contradiction / contrast** (in ~30% of top performers): "Terrified?
  Absolutely. Ready? Not really. Worth it? 100%." Unresolved tension = can't scroll.
- **Specificity effect**: speak to ONE person. Not "if you get bloated after
  meals" → "if you've ever secretly unbuttoned your jeans at dinner and hoped no
  one noticed — this is for you." Weirdly specific = instant credibility.
- **Timeframe tension**: "3 years of progress in 30 seconds", "3 months ago 0
  followers, today 211K." Punchy timeframe = curiosity + hope.
- **POV = advice in disguise**: "POV: you figured out how to not overpay for
  [thing]." Defenses down because it feels like relating, not instruction.

Hook-type menu (test one at a time): **Problem** ("I kept running into [X]") ·
**Curiosity** ("I didn't think this would matter") · **Result** ("Here's what
changed for me") · **Demo** ("Watch how fast this works for [task]") ·
**Contrarian** ("I thought this was unnecessary until…").

CTA menu, match to funnel: cold → "Save this"; education → "See how it works";
warm → "Try it for [use case] / Worth checking out."

## 4. Photoreal character / headshot formula (with imperfections)

```
[role/context] + [wardrobe] + [background] + [expression] + [lighting]
+ [lens/camera] + [composition] + realistic skin texture with small natural
imperfections + [intended use]
```

**Always add imperfection cues** so faces read human, e.g.: *slightly uneven
skin, faint under-eye shadow, a few flyaway hairs, natural skin pores and texture,
tiny asymmetry, no retouching, minor blemish, real not airbrushed.* Avoid
"perfect / flawless / model-like." Handheld selfie framing + natural light sells
UGC. Examples: "Sales headshot of a friendly man in a navy blazer, bright office,
natural smile, softbox light, 70mm lens, realistic skin texture with pores and a
faint stubble shadow, LinkedIn-ready."

## 5. Model selection (higgsfield-unlimited)

Unlimited-eligible (free, prefer these): images — `seedream_v5_pro`
(best realism, v2), `nano_banana_pro`/`nano-banana-2`, `gpt_image_2`, `flux_2`,
`soul_2` (UGC). Video — `kling3_0` (multi-shot, audio sync), `seedance_2_0`
(ref-driven, motion, audio), `wan2_7` (character + synced speech), `gemini_omni`
(native audio). Check `list_models` each run for newer/better ids and prefer the
newest unlimited one.

- **Talking-head with spoken lines** → `wan2_7` or `gemini_omni` (native audio),
  image-to-video from a character still for consistency.
- **Dynamic multi-shot / cinematic B-roll** → `kling3_0` or `seedance_2_0`.
- **Photoreal character stills** → `seedream_v5_pro` (v2). Call form:
  `model="seedream_v5_pro", api_version="v2"` (v2 ids use underscores; the raw
  `soul_2` id is rejected — use `seedream_v5_pro`/`nano_banana_pro`).
- Settings for ads: `aspect_ratio="9:16"`, `duration=8`, `resolution="720p"`
  (unlimited caps ~720p; leave `resolution_fallback` on), `generate_audio=true`.
- Throughput: one job per account; spread across the account pool for parallelism.
  A single account handles ~2 concurrent before 429.

## 6. Image → 2-part video pipeline (consistent character, longer ads)

An 8s clip is short. For a ~16s viral ad with ONE consistent face:
1. Generate a character still (`generate_image`, `seedream_v5_pro`, 9:16, with
   imperfection cues from §4).
2. **Part 1 = HOOK** (`generate_video`, `input_files=[still]`, `wan2_7`,
   duration 8): person delivers the hook line, urgent/relatable energy.
3. **Part 2 = PAYOFF/CTA** (same still, same model): relief/benefit + soft CTA,
   briefly shows phone/product.
4. Stitch Part 1 + Part 2 in edit. Reuse the SAME still across parts so the face
   stays identical.

## 7. General-category viral formats to adapt (not niche-specific)

Pour the product into whatever is broadly viral right now, e.g.: green-screen
reaction, "tell me you're X without telling me", day-in-the-life, text-message /
DM story reveal, oddly-satisfying loop, "things I wish I knew", street-interview
vox-pop, ASMR/close-up, expectation-vs-reality split, whisper/confession,
"nobody's talking about this", rating/tier-list, before-the-chaos calm.
Keep the middle+CTA stable, swap the format shell → 10–20 distinct viral styles
fast.

## Workflow checklist

- [ ] Pick format (§2/§7) + hook type (§3).
- [ ] Character still with imperfections (§4) if a person appears.
- [ ] Best unlimited model (§5); 9:16 · 8s · 720p · audio on.
- [ ] 2-part hook+payoff (§6) for longer/consistent ads.
- [ ] 3 hook variations, one variable changed.
- [ ] Claim-safe, caption room, muted-viewer legible.
