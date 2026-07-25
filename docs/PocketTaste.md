# Tab 1

**Points to keep in mind:**  
1\. Memory for agents so the story is unique and not repetitive  
2\.  IMDB and YT clone but only for PocketFM  
3\.  Education and knowledge vertical :self‑improvement platform: language courses, business case studies, book summaries, and structured curricula; it became India’s largest audio learning platform by leaning into this niche   
4\. Live Platform (PocketLive)  
5\. 

**References:**  
[https://github.com/Xerophayze/TTS-Story](https://github.com/Xerophayze/TTS-Story)  
[https://github.com/GOAT-AI-lab/GOAT-Storytelling-Agent](https://github.com/GOAT-AI-lab/GOAT-Storytelling-Agent)  
[https://github.com/Picrew/ConStory-Bench](https://github.com/Picrew/ConStory-Bench)  
[https://github.com/Finrandojin/alexandria-audiobook](https://github.com/Finrandojin/alexandria-audiobook)  
[https://github.com/NVIDIA-NeMo/Guardrails](https://github.com/NVIDIA-NeMo/Guardrails)  
[https://github.com/RUCAIBox/RecBole-GNN](https://github.com/RUCAIBox/RecBole-GNN)

Align everything to **Theme 3 – AI‑Driven Content Discovery & Personalization** and build a serious, infra‑level project around that.

Use case: **a multi‑stage recommendation and search engine that makes every listener’s “Next Episode / Next Series” feel made‑for‑them, built on top‑tier open‑source recommender frameworks (NVIDIA Merlin, RecBole) and an LLM search layer (Haystack).**\[[developer.nvidia](https://developer.nvidia.com/merlin)\]

---

## **Chosen theme and core problem**

**Theme:** 3\. AI‑Driven Content Discovery & Personalization.

PocketTaste is an AI-first recommendation engine for long-form audio, designed to learn each listener's narrative taste profile, and fuel a hyper‑personalized ‘For You' feed and conversational discovery in Pocket FM. It doesn't just focus on clicks as its core, but it specifically aims at binge behavior, such as episode completion, multi-episode streaks, and coin unlocks. It has a multi-stage design under the hood: first, the candidates are rapidly generated from a sequence‑aware model trained on listening histories; then, the top candidates are refined using deep ranking models which combine behavioural features with story metadata (such as genre, pacing, emotional tone); finally, the most promising candidates are selected by a layer built on an LLM that enables users to describe what they want in natural language, like “dark office romance, Hindi, 15-minute episodes, no horror”. This same engine can help provide recommendations (because they finished X and didn't finish Y we recommend Z) and can help in the speedy A/B testing of new ranking goals. PocketTaste is built as a production-ready module that can be integrated into Pocket FM's current catalog and AI framework and can therefore be shipped and moved key metrics—rather than just be a prototype.

**Real problem (not just theme words):**

* Pocket FM has a huge and fast‑growing catalog of long‑form audio series across genres and languages, and its business depends on listeners continuously finding the *next* story worth spending coins and time on.\[[fortuneindia](https://www.fortuneindia.com/business-news/how-pocketfm-is-leveraging-ai-to-become-the-next-big-thing-in-audio/127054)\]  
* Today, a lot of discovery is based on broad categories, popularity, and basic personalization; compared to platforms like Spotify or Ximalaya, which run very sophisticated recommender stacks, there is clear room to push **session‑aware, taste‑graph, and LLM‑aware discovery**.\[[play.google](https://play.google.com/store/apps/details?id=com.spotify.music&hl=en_IN)\]

So the **one problem** you attack is:

> “How do we build a production‑grade engine that always recommends the next episode/series that maximizes completion and monetization, using all the behavioral data Pocket FM already has?”

---

## **Proper use case: PocketTaste – Next‑Gen Recommender for Long‑Form Audio**

**Name:** PocketTaste (you can rename).

**One‑line:**  
A **Merlin/RecBole‑powered recommendation and search engine** that learns each listener’s narrative taste from their full behavior (skips, completions, coin unlocks, session patterns) and serves a **hyper‑personal ‘For You’ feed and conversational discovery** inside Pocket FM.\[[developer.nvidia](https://developer.nvidia.com/merlin)\]

What it does (listener side):

* Shows a **personal Home / For You feed** ranked specifically to maximize long‑form engagement and paid unlocks, not just clicks.  
* Powers a **“What should I listen to next?” chat/search box** that understands natural language like “Hindi underdog office romance, 15‑min episodes, no horror.”  
* Continuously adapts in‑session: if user skips 3 intros or bounces at episode 2, feed reshapes in real time.

What it does (Pocket FM side):

* Gives a **pluggable recommender pipeline** they can run at scale (GPU‑accelerated with Merlin) instead of hand‑built heuristics.\[[developer.nvidia](https://developer.nvidia.com/merlin)\]  
* Lets data team experiment quickly with SOTA recsys models (from RecBole2.0 / RecBole‑GNN) on offline data.\[[github](https://github.com/RUCAIBox/RecBole-GNN)\]  
* Adds an LLM‑based semantic and conversational layer on top of the catalog with Haystack.\[[github](https://github.com/deepset-ai/haystack)\]

---

## **Open‑source foundation (high‑star projects)**

You explicitly anchor on **popular, battle‑tested OSS**:

1. **NVIDIA Merlin (framework for large‑scale recommenders)**  
   * End‑to‑end pipeline: feature engineering (NVTabular), training deep recsys models (Merlin Models, HugeCTR), and deployment at scale (GPU‑accelerated).\[[developer.nvidia](https://developer.nvidia.com/merlin)\]  
   * Designed to handle hundreds of TB of data in retrieval, filtering, scoring, and ordering, which is directly relevant to Pocket FM’s large catalog and userbase.\[[developer.nvidia](https://developer.nvidia.com/merlin)\]  
2. **RecBole / RecBole2.0 / RecBole‑GNN (research‑grade recsys library)**  
   * Unified, comprehensive libraries that implement a wide range of classical and deep recommendation models, plus GNN‑enhanced recommenders.\[[github](https://github.com/RUCAIBox/RecBole)\]  
   * Great for rapid experimentation and benchmarking different models (MF, GRU4Rec, SASRec, GNN‑based) on Pocket‑like data.\[[github](https://github.com/topics/recbole)\]  
3. **Haystack (deepset) for LLM‑based semantic search & conversational layer**  
   * Open‑source AI orchestration framework for building production‑ready LLM apps with retrieval, semantic search, and agent pipelines.\[[github](https://github.com/deepset-ai/haystack/tree/v1.x)\]  
   * Ideal for a **“conversational discovery”** feature that lets users describe what they want, then maps that to the catalog.\[[github](https://github.com/deepset-ai)\]

You’re **not** writing models from scratch; you are **integrating and productizing** these high‑star ecosystems for Pocket FM’s specific long‑form audio use case.

---

## **System design: how PocketTaste works**

## **1\. Data & features (feeding Merlin / RecBole)**

Pocket FM has rich behavioral signals:

* Play, pause, seek, skip, completion % per episode.  
* Time of day, session length, device type.  
* Coin unlocks, drop‑off before/after paywalls.  
* Genre, language, narrator, episode length, emotional intensity tags.\[[fortuneindia](https://www.fortuneindia.com/business-news/how-pocketfm-is-leveraging-ai-to-become-the-next-big-thing-in-audio/127054)\]

You build a schema for **Merlin \+ RecBole**:

* Use **Merlin NVTabular** for large‑scale preprocessing: embedding categorical features (user ID, series ID, genre, source, language) and normalizing continuous ones (dwell time, completion rate, recency).\[[developer.nvidia](https://developer.nvidia.com/merlin)\]  
* Use **RecBole/RecBole2.0** on smaller dev datasets to benchmark models and choose a good architecture (e.g., SASRec or GRU4Rec2 for sequence modeling of episode streams).\[[github](https://github.com/RUCAIBox/RecBole2.0)\]

Outputs:

* Candidate retrieval embeddings.  
* Ranking model weights tuned to metrics Pocket cares about: completion rate, “coins spent per impression,” long‑term retention.

## **2\. Multi‑stage recommender pipeline**

Use a **standard 3‑stage recsys architecture** tuned for long‑form audio:

1. **Candidate generation (fast, coarse)**  
   * Use Merlin Models or RecBole sequence models to quickly retrieve N candidates per user — series and episodes.\[[developer.nvidia](https://developer.nvidia.com/merlin)\]  
2. **Ranking (deep model)**  
   * Use Merlin’s deep CTR / CVR models (e.g., DLRM‑like or Transformer‑based) to score candidates on:  
     * Probability of starting.  
     * Probability of finishing 3 episodes.  
     * Expected revenue (coins).\[[developer.nvidia](https://developer.nvidia.com/merlin)\]  
3. **Re‑ranking / diversification**  
   * Add business logic: explore vs exploit, language diversity, avoid repeating same series too many times.  
   * Optionally add a rule‑based layer for new launches (e.g., give a boost to new originals).

Everything is implemented with **Merlin** so that scaling to production is realistic—GPU training, serving, and integration with typical infra.\[[developer.nvidia](https://developer.nvidia.com/merlin)\]

## **3\. Conversational & semantic discovery layer**

On top of the ranking engine, you integrate **Haystack**:

* Index series \+ episodes with dense embeddings (genre, blurb, tags, maybe transcripts).\[[github](https://github.com/deepset-ai/haystack)\]  
* Build an LLM‑backed pipeline where user queries like:  
  * “Dark office romance, 20 minute episodes, Hindi only, no horror.”  
  * “Something like this show but shorter and funny.”  
* Haystack retrieves candidate series and passes them to your recsys for personalized ranking before returning results.\[[github](https://github.com/deepset-ai/haystack/tree/v1.x)\]

Result: **AI‑assisted “search \+ recommend”** that feels like talking to a friend who knows the catalog.

---

## **How this improves on other companies (and Pocket FM’s position)**

* Spotify has world‑class recommenders, but they’re tuned for **music & podcasts**, not deep series with micro‑transactions and 100‑episode arcs.\[[support.spotify](https://support.spotify.com/in-hi/article/podcasts-and-shows/)\]  
* Ximalaya and Tencent Music (Kuwo) have large‑scale recommenders and rich signals but in different content mixes (music, talk, live, etc.).\[[tanayj](https://www.tanayj.com/p/ximalaya-and-the-economy-of-ears)\]  
* Pocket FM’s differentiation is **serialized audio \+ AI creator stack \+ paid creator economy**; a Merlin/RecBole‑based recommendation engine tuned for *this* content is a moat competitors don’t have.\[[thehindubusinessline](https://www.thehindubusinessline.com/companies/pocket-fms-creator-economy-crosses-300-crore-eyes-1000-crore-by-2026/article70642447.ece)\]

Your project is: **“Spotify‑level recsys, but specialized for long‑form audio series with coins and episodes.”**

---

## **Hackathon‑ready MVP plan**

You cannot train full Merlin on Pocket data in 36 hours, but you can build a **credible offline prototype** that clearly maps to production.

1. **Offline dataset**  
   * Use a public recsys dataset (e.g., MovieLens) or synthetic Pocket‑like data to prove the pipeline.  
   * Map movies → series, and ratings → completion/coin events.  
2. **RecBole experimentation**  
   * Train 1–2 sequence models with RecBole (e.g., SASRec) and show offline metrics (NDCG@10, Recall@10).\[[github](https://github.com/RUCAIBox/RecBole-GNN)\]  
   * Show that sequence‑aware models beat simple popularity for long‑form engagement.  
3. **Merlin mini‑pipeline**  
   * Use NVTabular to preprocess features and Merlin Models to train a small ranking model.\[[developer.nvidia](https://developer.nvidia.com/merlin)\]  
   * Demonstrate candidate → ranking pipeline on sample users (e.g., notebooks / logs).  
4. **Haystack semantic search**  
   * Index a small catalog of series descriptions.\[[github](https://github.com/deepset-ai)\]  
   * Build a simple API: text query in, list of series out, re‑ranked by RecBole/Merlin scores.  
5. **Frontend demo**  
   * Minimal React/Next UI mimicking Pocket FM’s home tab:  
     * “Because you listened to…” row from RecBole/Merlin.  
     * Search box powered by Haystack \+ recsys.  
     * Show quickly how changing behavior (simulated) changes the feed.

In the pitch, you explicitly say:

> “We used RecBole to quickly benchmark sequence models, Merlin to build a scalable ranking pipeline, and Haystack to add conversational discovery. All are high‑star, production‑proven frameworks. We’ve wired them into a multi‑stage architecture that Pocket FM can realistically adopt and scale.”\[[developer.nvidia](https://developer.nvidia.com/merlin)\]

---

## **Why this is a strong, single‑theme idea**

* **Aligned to ONE theme:**  
  Everything is under **AI‑Driven Content Discovery & Personalization** – the core deliverable is the recommendation \+ discovery engine.  
* **Uses and upgrades existing open‑source** instead of reinventing:  
  * RecBole for fast model R\&D.\[[github](https://github.com/RUCAIBox/RecBole-GNN)\]  
  * Merlin for scalable training/serving.\[[developer.nvidia](https://developer.nvidia.com/merlin)\]  
  * Haystack for semantic search & LLM orchestration.\[[github](https://github.com/deepset-ai/haystack)\]  
* **Impactful for Pocket FM’s real business:**  
  * Better “next series” predictions mean more completed episodes, more coin unlocks, and happier creators.\[[thehindubusinessline](https://www.thehindubusinessline.com/companies/pocket-fms-creator-economy-crosses-300-crore-eyes-1000-crore-by-2026/article70642447.ece)\]

If you want, I can next help you break this into a very concrete task split for your team (you on backend/infra, someone on UI, someone on model experiments) plus repo links and commands to get Merlin, RecBole, and Haystack running quickly.

Short answer: **yes, PocketTaste is a very good fit**, but you should tune the description so it clearly matches the **“Entertainment Discovery”** sub‑problem under the Discovery & Personalization theme (Mood‑First Search, Explain Why I Will Love This, Cross‑Media Discovery, AI Concierge, AI‑Curated Festivals).\[[ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/61971276/7d7926b1-680d-48ae-840c-6a1ea6b89852/Problem-statements.pdf?AWSAccessKeyId=ASIA2F3EMEYE7LAQKY2B&Signature=38uGjhkzHQ8WqyNcnHnK0mIpCYw%3D&x-amz-security-token=IQoJb3JpZ2luX2VjEE8aCXVzLWVhc3QtMSJHMEUCIQDGTRCOdwkFRdDhQ2wmnINN7S4Ag2UuuhyEFqgnVlVU5gIgc6UhAUfGVVfCJ85ut89NEYwSn%2BkgOihd6haJuxkyp0Qq8wQIFxABGgw2OTk3NTMzMDk3MDUiDFD%2FIEQbXCyZkjOfSSrQBNT1gOpKRJjb1sx7pbwnqSlnsHuQDz5Qa9ffpBkawuU9hTKpBnZr0h0PVcjDwqVuiODRLZD0JMLP84caVGiVFu9RzL3xSKkvmojo02uYBScdeyes5DzCjKqETCqhAKVlnZ4mHR6NqAtlMA27WwB0eQAIz0B39oPATwy9tFSZPAPZJ4ZtIXenxc3iaR6Q4UO5DCbLfVaaN3EDJPnzo13Zim713wtK0Q2PtkgxYowaXR6%2BhdusItNcOZ8lUJFmETw3EUJ6sqkt5BwN2nOGMqUjHM5BYKuftzk3imfxARRxndrXTRGY4i%2FbmIy5lR9wy3raAenSc%2FEpeFLLquEdNzwEzvN9pJPo1KqHx5S9yeX03142DAWCll4o9II9zDRLRy4svzlZnFJ4zbMpWbyARWoGa62qtDWxfG%2FTnyNv%2FHsV7cPdPL0mdOTCXLQh33jLvax1DBwFStJEUeCD34pU0qyQV2SUzj%2BL1OBb%2Br9FT8ex%2BLiZW9YWc4CbYQ9ooxnIkftMj2KkqmNfZAjHckhpgfH9BhC8VrY1W7rV991WgALrYzFLq%2FheVVo7BjGAC3iq6jvFWJoBosmcB%2FUuU9CoHAeCaOjTbdJpu3suhQCeuluNZ7eI8Qv%2FWkc3dRHN1gFgCr5%2BqRvOnd5N4uVuFIUYIrt%2BneJCpXnmrmb34DiuJLM%2F69SVJAMuwDlhcxJc4mpXIHoKWduIxzKQS63tAnM3KyxiZca3QPxEzi4SCCOJJ02eSlBr%2FYX1O4406VT8yoroJ5WM%2FbDpLntbjUZSISQB3L%2FNiOEwpquR0wY6mAFjByGh84wzfRmShNAQbtJ9oNbAOu8DNrCAG%2FPc%2BlvzqOKYByS6ViR7W6x3IC%2BUG1kPeHUg83TautY26vZblH3bS1foPOEyivHCByyHxmoR1tVMBmRRzPs3xPTM%2FM%2FBJtpYnEzkp0wHd0SfUrDOCfi2AQJTmD5oJoY2aKGDPdGPIq9L3CZFAMhJCM%2BiV9pUqfWB0%2BC0e7eFEQ%3D%3D&Expires=1784963961)\]

Below I’ll:

1. Show exactly **where PocketTaste fits** in the official problem PDF.  
2. List **existing products / OSS** that map to each of the 6 problem clusters (P1–P6) so you can see the ecosystem.  
3. Refine **one strong, production‑ready use case** (PocketTaste) that you can build now by upgrading those projects.

---

## **1\. Is PocketTaste a fit?**

From the PDF, under **P5: Creator Superpowers** there’s a separate block called **Entertainment Discovery** with these ideas:\[[ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/61971276/7d7926b1-680d-48ae-840c-6a1ea6b89852/Problem-statements.pdf?AWSAccessKeyId=ASIA2F3EMEYE7LAQKY2B&Signature=38uGjhkzHQ8WqyNcnHnK0mIpCYw%3D&x-amz-security-token=IQoJb3JpZ2luX2VjEE8aCXVzLWVhc3QtMSJHMEUCIQDGTRCOdwkFRdDhQ2wmnINN7S4Ag2UuuhyEFqgnVlVU5gIgc6UhAUfGVVfCJ85ut89NEYwSn%2BkgOihd6haJuxkyp0Qq8wQIFxABGgw2OTk3NTMzMDk3MDUiDFD%2FIEQbXCyZkjOfSSrQBNT1gOpKRJjb1sx7pbwnqSlnsHuQDz5Qa9ffpBkawuU9hTKpBnZr0h0PVcjDwqVuiODRLZD0JMLP84caVGiVFu9RzL3xSKkvmojo02uYBScdeyes5DzCjKqETCqhAKVlnZ4mHR6NqAtlMA27WwB0eQAIz0B39oPATwy9tFSZPAPZJ4ZtIXenxc3iaR6Q4UO5DCbLfVaaN3EDJPnzo13Zim713wtK0Q2PtkgxYowaXR6%2BhdusItNcOZ8lUJFmETw3EUJ6sqkt5BwN2nOGMqUjHM5BYKuftzk3imfxARRxndrXTRGY4i%2FbmIy5lR9wy3raAenSc%2FEpeFLLquEdNzwEzvN9pJPo1KqHx5S9yeX03142DAWCll4o9II9zDRLRy4svzlZnFJ4zbMpWbyARWoGa62qtDWxfG%2FTnyNv%2FHsV7cPdPL0mdOTCXLQh33jLvax1DBwFStJEUeCD34pU0qyQV2SUzj%2BL1OBb%2Br9FT8ex%2BLiZW9YWc4CbYQ9ooxnIkftMj2KkqmNfZAjHckhpgfH9BhC8VrY1W7rV991WgALrYzFLq%2FheVVo7BjGAC3iq6jvFWJoBosmcB%2FUuU9CoHAeCaOjTbdJpu3suhQCeuluNZ7eI8Qv%2FWkc3dRHN1gFgCr5%2BqRvOnd5N4uVuFIUYIrt%2BneJCpXnmrmb34DiuJLM%2F69SVJAMuwDlhcxJc4mpXIHoKWduIxzKQS63tAnM3KyxiZca3QPxEzi4SCCOJJ02eSlBr%2FYX1O4406VT8yoroJ5WM%2FbDpLntbjUZSISQB3L%2FNiOEwpquR0wY6mAFjByGh84wzfRmShNAQbtJ9oNbAOu8DNrCAG%2FPc%2BlvzqOKYByS6ViR7W6x3IC%2BUG1kPeHUg83TautY26vZblH3bS1foPOEyivHCByyHxmoR1tVMBmRRzPs3xPTM%2FM%2FBJtpYnEzkp0wHd0SfUrDOCfi2AQJTmD5oJoY2aKGDPdGPIq9L3CZFAMhJCM%2BiV9pUqfWB0%2BC0e7eFEQ%3D%3D&Expires=1784963961)\]

* Mood‑First Search (“I want something that feels like a rainy Sunday after heartbreak” instead of picking genres).  
* AI Entertainment Concierge (plans a whole weekend of books/podcasts/movies/games).  
* Cross‑Media Discovery (finish a movie → unlock related books, podcasts, comics, games).  
* “Explain Why I Will Love This” instead of opaque similarity.  
* AI‑Curated Festivals (personal weekly film/audiobook festivals).

Your **PocketTaste** concept — a multi‑stage recsys \+ conversational discovery engine specifically for long‑form audio — fits **squarely inside this Entertainment Discovery block**:

* It learns a **taste profile** from behavior (completion, skips, coins), and recommends the **next binge‑worthy series**.  
* It supports **natural‑language discovery** (“dark office romance, Hindi, 20‑min episodes, no horror”).  
* It can add **explanations** (“because you finished X and dropped Y, we recommend Z”) and even “mood playlists” or “audio festivals.”

So: keep your official hackathon theme as **“Discovery & Personalization – AI‑Driven Content Discovery & Personalization”**, and explicitly say:

> “We are implementing the *Entertainment Discovery* problem: Mood‑First Search \+ Explain‑Why \+ AI‑curated sessions for Pocket FM’s long‑form audio.”

That keeps you 100% on‑label.

---

## **2\. Ecosystem scan: examples for each problem cluster**

I’ll keep this high‑level so you can see “what already exists” and where to improve.

## **P1 – AI Native Storytelling (Infinite Universes, Story Time Machine, Story Genome)\[[ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/61971276/7d7926b1-680d-48ae-840c-6a1ea6b89852/Problem-statements.pdf?AWSAccessKeyId=ASIA2F3EMEYE7LAQKY2B&Signature=38uGjhkzHQ8WqyNcnHnK0mIpCYw%3D&x-amz-security-token=IQoJb3JpZ2luX2VjEE8aCXVzLWVhc3QtMSJHMEUCIQDGTRCOdwkFRdDhQ2wmnINN7S4Ag2UuuhyEFqgnVlVU5gIgc6UhAUfGVVfCJ85ut89NEYwSn%2BkgOihd6haJuxkyp0Qq8wQIFxABGgw2OTk3NTMzMDk3MDUiDFD%2FIEQbXCyZkjOfSSrQBNT1gOpKRJjb1sx7pbwnqSlnsHuQDz5Qa9ffpBkawuU9hTKpBnZr0h0PVcjDwqVuiODRLZD0JMLP84caVGiVFu9RzL3xSKkvmojo02uYBScdeyes5DzCjKqETCqhAKVlnZ4mHR6NqAtlMA27WwB0eQAIz0B39oPATwy9tFSZPAPZJ4ZtIXenxc3iaR6Q4UO5DCbLfVaaN3EDJPnzo13Zim713wtK0Q2PtkgxYowaXR6%2BhdusItNcOZ8lUJFmETw3EUJ6sqkt5BwN2nOGMqUjHM5BYKuftzk3imfxARRxndrXTRGY4i%2FbmIy5lR9wy3raAenSc%2FEpeFLLquEdNzwEzvN9pJPo1KqHx5S9yeX03142DAWCll4o9II9zDRLRy4svzlZnFJ4zbMpWbyARWoGa62qtDWxfG%2FTnyNv%2FHsV7cPdPL0mdOTCXLQh33jLvax1DBwFStJEUeCD34pU0qyQV2SUzj%2BL1OBb%2Br9FT8ex%2BLiZW9YWc4CbYQ9ooxnIkftMj2KkqmNfZAjHckhpgfH9BhC8VrY1W7rV991WgALrYzFLq%2FheVVo7BjGAC3iq6jvFWJoBosmcB%2FUuU9CoHAeCaOjTbdJpu3suhQCeuluNZ7eI8Qv%2FWkc3dRHN1gFgCr5%2BqRvOnd5N4uVuFIUYIrt%2BneJCpXnmrmb34DiuJLM%2F69SVJAMuwDlhcxJc4mpXIHoKWduIxzKQS63tAnM3KyxiZca3QPxEzi4SCCOJJ02eSlBr%2FYX1O4406VT8yoroJ5WM%2FbDpLntbjUZSISQB3L%2FNiOEwpquR0wY6mAFjByGh84wzfRmShNAQbtJ9oNbAOu8DNrCAG%2FPc%2BlvzqOKYByS6ViR7W6x3IC%2BUG1kPeHUg83TautY26vZblH3bS1foPOEyivHCByyHxmoR1tVMBmRRzPs3xPTM%2FM%2FBJtpYnEzkp0wHd0SfUrDOCfi2AQJTmD5oJoY2aKGDPdGPIq9L3CZFAMhJCM%2BiV9pUqfWB0%2BC0e7eFEQ%3D%3D&Expires=1784963961)\]**

**What it’s really about:**  
Persistent story worlds, editable timelines, and understanding “what makes a hit story” at the pattern level.

**Existing products / OSS:**

* **Sudowrite** – AI fiction co‑writer focused on long‑form, character‑consistent, plot‑aware help.\[[sudowrite](https://sudowrite.com/)\]  
* **NovelAI** – AI story generator with memory, lore books, and character sheets (closed‑source but important benchmark).\[[sudowrite](https://sudowrite.com/blog/sudowrite-vs-novelai-which-ai-writing-tool-will-unleash-your-creative-genius-in-2025/)\]  
* **GOAT‑Storytelling‑Agent (OSS)** – Agent for writing consistent, long stories in any fiction form.\[[github](https://github.com/GOAT-AI-lab/GOAT-Storytelling-Agent)\]  
* **ConStory‑Bench (research)** – Benchmark for long‑story consistency.\[[picrew.github](https://picrew.github.io/constory-bench.github.io/)\]\[[ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/61971276/7d7926b1-680d-48ae-840c-6a1ea6b89852/Problem-statements.pdf?AWSAccessKeyId=ASIA2F3EMEYE7LAQKY2B&Signature=38uGjhkzHQ8WqyNcnHnK0mIpCYw%3D&x-amz-security-token=IQoJb3JpZ2luX2VjEE8aCXVzLWVhc3QtMSJHMEUCIQDGTRCOdwkFRdDhQ2wmnINN7S4Ag2UuuhyEFqgnVlVU5gIgc6UhAUfGVVfCJ85ut89NEYwSn%2BkgOihd6haJuxkyp0Qq8wQIFxABGgw2OTk3NTMzMDk3MDUiDFD%2FIEQbXCyZkjOfSSrQBNT1gOpKRJjb1sx7pbwnqSlnsHuQDz5Qa9ffpBkawuU9hTKpBnZr0h0PVcjDwqVuiODRLZD0JMLP84caVGiVFu9RzL3xSKkvmojo02uYBScdeyes5DzCjKqETCqhAKVlnZ4mHR6NqAtlMA27WwB0eQAIz0B39oPATwy9tFSZPAPZJ4ZtIXenxc3iaR6Q4UO5DCbLfVaaN3EDJPnzo13Zim713wtK0Q2PtkgxYowaXR6%2BhdusItNcOZ8lUJFmETw3EUJ6sqkt5BwN2nOGMqUjHM5BYKuftzk3imfxARRxndrXTRGY4i%2FbmIy5lR9wy3raAenSc%2FEpeFLLquEdNzwEzvN9pJPo1KqHx5S9yeX03142DAWCll4o9II9zDRLRy4svzlZnFJ4zbMpWbyARWoGa62qtDWxfG%2FTnyNv%2FHsV7cPdPL0mdOTCXLQh33jLvax1DBwFStJEUeCD34pU0qyQV2SUzj%2BL1OBb%2Br9FT8ex%2BLiZW9YWc4CbYQ9ooxnIkftMj2KkqmNfZAjHckhpgfH9BhC8VrY1W7rV991WgALrYzFLq%2FheVVo7BjGAC3iq6jvFWJoBosmcB%2FUuU9CoHAeCaOjTbdJpu3suhQCeuluNZ7eI8Qv%2FWkc3dRHN1gFgCr5%2BqRvOnd5N4uVuFIUYIrt%2BneJCpXnmrmb34DiuJLM%2F69SVJAMuwDlhcxJc4mpXIHoKWduIxzKQS63tAnM3KyxiZca3QPxEzi4SCCOJJ02eSlBr%2FYX1O4406VT8yoroJ5WM%2FbDpLntbjUZSISQB3L%2FNiOEwpquR0wY6mAFjByGh84wzfRmShNAQbtJ9oNbAOu8DNrCAG%2FPc%2BlvzqOKYByS6ViR7W6x3IC%2BUG1kPeHUg83TautY26vZblH3bS1foPOEyivHCByyHxmoR1tVMBmRRzPs3xPTM%2FM%2FBJtpYnEzkp0wHd0SfUrDOCfi2AQJTmD5oJoY2aKGDPdGPIq9L3CZFAMhJCM%2BiV9pUqfWB0%2BC0e7eFEQ%3D%3D&Expires=1784963961)\]

**Upgrade angle:**  
Use GOAT \+ ConStory‑style metrics to build a **Story Genome Service**: analyze Pocket FM hits, extract “DNA” (pacing, arc types, trope patterns), and feed that into tools that help creators and recommenders.

---

## **P2 – AI Characters & Companions (Living Characters, Mentor, Marketplace)\[[ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/61971276/7d7926b1-680d-48ae-840c-6a1ea6b89852/Problem-statements.pdf?AWSAccessKeyId=ASIA2F3EMEYE7LAQKY2B&Signature=38uGjhkzHQ8WqyNcnHnK0mIpCYw%3D&x-amz-security-token=IQoJb3JpZ2luX2VjEE8aCXVzLWVhc3QtMSJHMEUCIQDGTRCOdwkFRdDhQ2wmnINN7S4Ag2UuuhyEFqgnVlVU5gIgc6UhAUfGVVfCJ85ut89NEYwSn%2BkgOihd6haJuxkyp0Qq8wQIFxABGgw2OTk3NTMzMDk3MDUiDFD%2FIEQbXCyZkjOfSSrQBNT1gOpKRJjb1sx7pbwnqSlnsHuQDz5Qa9ffpBkawuU9hTKpBnZr0h0PVcjDwqVuiODRLZD0JMLP84caVGiVFu9RzL3xSKkvmojo02uYBScdeyes5DzCjKqETCqhAKVlnZ4mHR6NqAtlMA27WwB0eQAIz0B39oPATwy9tFSZPAPZJ4ZtIXenxc3iaR6Q4UO5DCbLfVaaN3EDJPnzo13Zim713wtK0Q2PtkgxYowaXR6%2BhdusItNcOZ8lUJFmETw3EUJ6sqkt5BwN2nOGMqUjHM5BYKuftzk3imfxARRxndrXTRGY4i%2FbmIy5lR9wy3raAenSc%2FEpeFLLquEdNzwEzvN9pJPo1KqHx5S9yeX03142DAWCll4o9II9zDRLRy4svzlZnFJ4zbMpWbyARWoGa62qtDWxfG%2FTnyNv%2FHsV7cPdPL0mdOTCXLQh33jLvax1DBwFStJEUeCD34pU0qyQV2SUzj%2BL1OBb%2Br9FT8ex%2BLiZW9YWc4CbYQ9ooxnIkftMj2KkqmNfZAjHckhpgfH9BhC8VrY1W7rV991WgALrYzFLq%2FheVVo7BjGAC3iq6jvFWJoBosmcB%2FUuU9CoHAeCaOjTbdJpu3suhQCeuluNZ7eI8Qv%2FWkc3dRHN1gFgCr5%2BqRvOnd5N4uVuFIUYIrt%2BneJCpXnmrmb34DiuJLM%2F69SVJAMuwDlhcxJc4mpXIHoKWduIxzKQS63tAnM3KyxiZca3QPxEzi4SCCOJJ02eSlBr%2FYX1O4406VT8yoroJ5WM%2FbDpLntbjUZSISQB3L%2FNiOEwpquR0wY6mAFjByGh84wzfRmShNAQbtJ9oNbAOu8DNrCAG%2FPc%2BlvzqOKYByS6ViR7W6x3IC%2BUG1kPeHUg83TautY26vZblH3bS1foPOEyivHCByyHxmoR1tVMBmRRzPs3xPTM%2FM%2FBJtpYnEzkp0wHd0SfUrDOCfi2AQJTmD5oJoY2aKGDPdGPIq9L3CZFAMhJCM%2BiV9pUqfWB0%2BC0e7eFEQ%3D%3D&Expires=1784963961)\]**

**About:**  
Persistent conversational characters with memory and evolving relationships.

**Existing products:**

* **Character.AI** – Chat with persistent AI characters; memory and long‑term relationships. (Closed, but the category benchmark.)  
* **Replika** – AI companion with emotional memory across sessions.  
* **AutoGen / LangGraph (OSS frameworks)** – Multi‑agent conversation frameworks where each “character” can be modeled as an agent.\[[microsoft](https://www.microsoft.com/en-us/research/publication/autogen-enabling-next-gen-llm-applications-via-multi-agent-conversation-framework/)\]

**Upgrade idea:**  
Instead of generic companions, build **Pocket FM character agents** that are:

* Grounded in actual Pocket stories (canon) and  
* Tied back into discovery (“if you like chatting with X, you’ll probably love this audio series”).

---

## **P3 – Interactive Entertainment (different endings, escape rooms, AI dungeon)\[[ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/61971276/7d7926b1-680d-48ae-840c-6a1ea6b89852/Problem-statements.pdf?AWSAccessKeyId=ASIA2F3EMEYE7LAQKY2B&Signature=38uGjhkzHQ8WqyNcnHnK0mIpCYw%3D&x-amz-security-token=IQoJb3JpZ2luX2VjEE8aCXVzLWVhc3QtMSJHMEUCIQDGTRCOdwkFRdDhQ2wmnINN7S4Ag2UuuhyEFqgnVlVU5gIgc6UhAUfGVVfCJ85ut89NEYwSn%2BkgOihd6haJuxkyp0Qq8wQIFxABGgw2OTk3NTMzMDk3MDUiDFD%2FIEQbXCyZkjOfSSrQBNT1gOpKRJjb1sx7pbwnqSlnsHuQDz5Qa9ffpBkawuU9hTKpBnZr0h0PVcjDwqVuiODRLZD0JMLP84caVGiVFu9RzL3xSKkvmojo02uYBScdeyes5DzCjKqETCqhAKVlnZ4mHR6NqAtlMA27WwB0eQAIz0B39oPATwy9tFSZPAPZJ4ZtIXenxc3iaR6Q4UO5DCbLfVaaN3EDJPnzo13Zim713wtK0Q2PtkgxYowaXR6%2BhdusItNcOZ8lUJFmETw3EUJ6sqkt5BwN2nOGMqUjHM5BYKuftzk3imfxARRxndrXTRGY4i%2FbmIy5lR9wy3raAenSc%2FEpeFLLquEdNzwEzvN9pJPo1KqHx5S9yeX03142DAWCll4o9II9zDRLRy4svzlZnFJ4zbMpWbyARWoGa62qtDWxfG%2FTnyNv%2FHsV7cPdPL0mdOTCXLQh33jLvax1DBwFStJEUeCD34pU0qyQV2SUzj%2BL1OBb%2Br9FT8ex%2BLiZW9YWc4CbYQ9ooxnIkftMj2KkqmNfZAjHckhpgfH9BhC8VrY1W7rV991WgALrYzFLq%2FheVVo7BjGAC3iq6jvFWJoBosmcB%2FUuU9CoHAeCaOjTbdJpu3suhQCeuluNZ7eI8Qv%2FWkc3dRHN1gFgCr5%2BqRvOnd5N4uVuFIUYIrt%2BneJCpXnmrmb34DiuJLM%2F69SVJAMuwDlhcxJc4mpXIHoKWduIxzKQS63tAnM3KyxiZca3QPxEzi4SCCOJJ02eSlBr%2FYX1O4406VT8yoroJ5WM%2FbDpLntbjUZSISQB3L%2FNiOEwpquR0wY6mAFjByGh84wzfRmShNAQbtJ9oNbAOu8DNrCAG%2FPc%2BlvzqOKYByS6ViR7W6x3IC%2BUG1kPeHUg83TautY26vZblH3bS1foPOEyivHCByyHxmoR1tVMBmRRzPs3xPTM%2FM%2FBJtpYnEzkp0wHd0SfUrDOCfi2AQJTmD5oJoY2aKGDPdGPIq9L3CZFAMhJCM%2BiV9pUqfWB0%2BC0e7eFEQ%3D%3D&Expires=1784963961)\]**

**About:**  
Stories as games with branching decisions and persistent consequences.

**Existing products:**

* **AI Dungeon** – Procedural text adventure where the whole world is dynamically generated.  
* **Choice of Games / Episode / Chapters** – Scripted interactive stories with branches, in‑app purchases.  
* **OSS text‑adventure engines** – e.g., various AI‑Dungeon‑like projects on GitHub.

**Upgrade idea:**  
A **Pocket FM “Story as a Game” engine** that:

* Takes a linear Pocket series  
* Lets listeners make key spoken choices  
* Logs those choices as personalization signals for PocketTaste (so discovery and interactivity reinforce each other).

---

## **P4 – Video & Visual AI (trailers, graphic novel, one‑prompt movie studio)\[[ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/61971276/7d7926b1-680d-48ae-840c-6a1ea6b89852/Problem-statements.pdf?AWSAccessKeyId=ASIA2F3EMEYE7LAQKY2B&Signature=38uGjhkzHQ8WqyNcnHnK0mIpCYw%3D&x-amz-security-token=IQoJb3JpZ2luX2VjEE8aCXVzLWVhc3QtMSJHMEUCIQDGTRCOdwkFRdDhQ2wmnINN7S4Ag2UuuhyEFqgnVlVU5gIgc6UhAUfGVVfCJ85ut89NEYwSn%2BkgOihd6haJuxkyp0Qq8wQIFxABGgw2OTk3NTMzMDk3MDUiDFD%2FIEQbXCyZkjOfSSrQBNT1gOpKRJjb1sx7pbwnqSlnsHuQDz5Qa9ffpBkawuU9hTKpBnZr0h0PVcjDwqVuiODRLZD0JMLP84caVGiVFu9RzL3xSKkvmojo02uYBScdeyes5DzCjKqETCqhAKVlnZ4mHR6NqAtlMA27WwB0eQAIz0B39oPATwy9tFSZPAPZJ4ZtIXenxc3iaR6Q4UO5DCbLfVaaN3EDJPnzo13Zim713wtK0Q2PtkgxYowaXR6%2BhdusItNcOZ8lUJFmETw3EUJ6sqkt5BwN2nOGMqUjHM5BYKuftzk3imfxARRxndrXTRGY4i%2FbmIy5lR9wy3raAenSc%2FEpeFLLquEdNzwEzvN9pJPo1KqHx5S9yeX03142DAWCll4o9II9zDRLRy4svzlZnFJ4zbMpWbyARWoGa62qtDWxfG%2FTnyNv%2FHsV7cPdPL0mdOTCXLQh33jLvax1DBwFStJEUeCD34pU0qyQV2SUzj%2BL1OBb%2Br9FT8ex%2BLiZW9YWc4CbYQ9ooxnIkftMj2KkqmNfZAjHckhpgfH9BhC8VrY1W7rV991WgALrYzFLq%2FheVVo7BjGAC3iq6jvFWJoBosmcB%2FUuU9CoHAeCaOjTbdJpu3suhQCeuluNZ7eI8Qv%2FWkc3dRHN1gFgCr5%2BqRvOnd5N4uVuFIUYIrt%2BneJCpXnmrmb34DiuJLM%2F69SVJAMuwDlhcxJc4mpXIHoKWduIxzKQS63tAnM3KyxiZca3QPxEzi4SCCOJJ02eSlBr%2FYX1O4406VT8yoroJ5WM%2FbDpLntbjUZSISQB3L%2FNiOEwpquR0wY6mAFjByGh84wzfRmShNAQbtJ9oNbAOu8DNrCAG%2FPc%2BlvzqOKYByS6ViR7W6x3IC%2BUG1kPeHUg83TautY26vZblH3bS1foPOEyivHCByyHxmoR1tVMBmRRzPs3xPTM%2FM%2FBJtpYnEzkp0wHd0SfUrDOCfi2AQJTmD5oJoY2aKGDPdGPIq9L3CZFAMhJCM%2BiV9pUqfWB0%2BC0e7eFEQ%3D%3D&Expires=1784963961)\]**

**About:**  
Auto‑converting stories or audio into visual media.

**Existing products:**

* **Runway Gen‑2 / Pika / Luma** – Text‑to‑video and video‑to‑video generation.  
* **Midjourney / Stable Diffusion / ComfyUI** – Generating consistent character art and frames from prompts.  
* **Kaiber / OpusClip‑style tools** – Auto‑trailer / auto‑highlight generation from audio \+ video.

**Upgrade idea:**  
“**Story‑to‑Trailer for Pocket Originals**”: take a hit audio episode, auto‑generate:

* A short style‑consistent 2D trailer  
* A static graphic‑novel sequence to promote on socials  
* Feed back performance data (click‑through, completion) into your discovery model.

---

## **P5 – Creator Superpowers & Entertainment Discovery\[[ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/61971276/7d7926b1-680d-48ae-840c-6a1ea6b89852/Problem-statements.pdf?AWSAccessKeyId=ASIA2F3EMEYE7LAQKY2B&Signature=38uGjhkzHQ8WqyNcnHnK0mIpCYw%3D&x-amz-security-token=IQoJb3JpZ2luX2VjEE8aCXVzLWVhc3QtMSJHMEUCIQDGTRCOdwkFRdDhQ2wmnINN7S4Ag2UuuhyEFqgnVlVU5gIgc6UhAUfGVVfCJ85ut89NEYwSn%2BkgOihd6haJuxkyp0Qq8wQIFxABGgw2OTk3NTMzMDk3MDUiDFD%2FIEQbXCyZkjOfSSrQBNT1gOpKRJjb1sx7pbwnqSlnsHuQDz5Qa9ffpBkawuU9hTKpBnZr0h0PVcjDwqVuiODRLZD0JMLP84caVGiVFu9RzL3xSKkvmojo02uYBScdeyes5DzCjKqETCqhAKVlnZ4mHR6NqAtlMA27WwB0eQAIz0B39oPATwy9tFSZPAPZJ4ZtIXenxc3iaR6Q4UO5DCbLfVaaN3EDJPnzo13Zim713wtK0Q2PtkgxYowaXR6%2BhdusItNcOZ8lUJFmETw3EUJ6sqkt5BwN2nOGMqUjHM5BYKuftzk3imfxARRxndrXTRGY4i%2FbmIy5lR9wy3raAenSc%2FEpeFLLquEdNzwEzvN9pJPo1KqHx5S9yeX03142DAWCll4o9II9zDRLRy4svzlZnFJ4zbMpWbyARWoGa62qtDWxfG%2FTnyNv%2FHsV7cPdPL0mdOTCXLQh33jLvax1DBwFStJEUeCD34pU0qyQV2SUzj%2BL1OBb%2Br9FT8ex%2BLiZW9YWc4CbYQ9ooxnIkftMj2KkqmNfZAjHckhpgfH9BhC8VrY1W7rV991WgALrYzFLq%2FheVVo7BjGAC3iq6jvFWJoBosmcB%2FUuU9CoHAeCaOjTbdJpu3suhQCeuluNZ7eI8Qv%2FWkc3dRHN1gFgCr5%2BqRvOnd5N4uVuFIUYIrt%2BneJCpXnmrmb34DiuJLM%2F69SVJAMuwDlhcxJc4mpXIHoKWduIxzKQS63tAnM3KyxiZca3QPxEzi4SCCOJJ02eSlBr%2FYX1O4406VT8yoroJ5WM%2FbDpLntbjUZSISQB3L%2FNiOEwpquR0wY6mAFjByGh84wzfRmShNAQbtJ9oNbAOu8DNrCAG%2FPc%2BlvzqOKYByS6ViR7W6x3IC%2BUG1kPeHUg83TautY26vZblH3bS1foPOEyivHCByyHxmoR1tVMBmRRzPs3xPTM%2FM%2FBJtpYnEzkp0wHd0SfUrDOCfi2AQJTmD5oJoY2aKGDPdGPIq9L3CZFAMhJCM%2BiV9pUqfWB0%2BC0e7eFEQ%3D%3D&Expires=1784963961)\]**

Creator side (AI Writers’ Room, Plot Hole Hunter, Cliffhanger Optimizer…) overlaps with Pocket Studio; we covered that earlier.

**Entertainment Discovery** is where **PocketTaste** lives: mood search, concierge, cross‑media, explain‑why, festivals.\[[ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/61971276/7d7926b1-680d-48ae-840c-6a1ea6b89852/Problem-statements.pdf?AWSAccessKeyId=ASIA2F3EMEYE7LAQKY2B&Signature=38uGjhkzHQ8WqyNcnHnK0mIpCYw%3D&x-amz-security-token=IQoJb3JpZ2luX2VjEE8aCXVzLWVhc3QtMSJHMEUCIQDGTRCOdwkFRdDhQ2wmnINN7S4Ag2UuuhyEFqgnVlVU5gIgc6UhAUfGVVfCJ85ut89NEYwSn%2BkgOihd6haJuxkyp0Qq8wQIFxABGgw2OTk3NTMzMDk3MDUiDFD%2FIEQbXCyZkjOfSSrQBNT1gOpKRJjb1sx7pbwnqSlnsHuQDz5Qa9ffpBkawuU9hTKpBnZr0h0PVcjDwqVuiODRLZD0JMLP84caVGiVFu9RzL3xSKkvmojo02uYBScdeyes5DzCjKqETCqhAKVlnZ4mHR6NqAtlMA27WwB0eQAIz0B39oPATwy9tFSZPAPZJ4ZtIXenxc3iaR6Q4UO5DCbLfVaaN3EDJPnzo13Zim713wtK0Q2PtkgxYowaXR6%2BhdusItNcOZ8lUJFmETw3EUJ6sqkt5BwN2nOGMqUjHM5BYKuftzk3imfxARRxndrXTRGY4i%2FbmIy5lR9wy3raAenSc%2FEpeFLLquEdNzwEzvN9pJPo1KqHx5S9yeX03142DAWCll4o9II9zDRLRy4svzlZnFJ4zbMpWbyARWoGa62qtDWxfG%2FTnyNv%2FHsV7cPdPL0mdOTCXLQh33jLvax1DBwFStJEUeCD34pU0qyQV2SUzj%2BL1OBb%2Br9FT8ex%2BLiZW9YWc4CbYQ9ooxnIkftMj2KkqmNfZAjHckhpgfH9BhC8VrY1W7rV991WgALrYzFLq%2FheVVo7BjGAC3iq6jvFWJoBosmcB%2FUuU9CoHAeCaOjTbdJpu3suhQCeuluNZ7eI8Qv%2FWkc3dRHN1gFgCr5%2BqRvOnd5N4uVuFIUYIrt%2BneJCpXnmrmb34DiuJLM%2F69SVJAMuwDlhcxJc4mpXIHoKWduIxzKQS63tAnM3KyxiZca3QPxEzi4SCCOJJ02eSlBr%2FYX1O4406VT8yoroJ5WM%2FbDpLntbjUZSISQB3L%2FNiOEwpquR0wY6mAFjByGh84wzfRmShNAQbtJ9oNbAOu8DNrCAG%2FPc%2BlvzqOKYByS6ViR7W6x3IC%2BUG1kPeHUg83TautY26vZblH3bS1foPOEyivHCByyHxmoR1tVMBmRRzPs3xPTM%2FM%2FBJtpYnEzkp0wHd0SfUrDOCfi2AQJTmD5oJoY2aKGDPdGPIq9L3CZFAMhJCM%2BiV9pUqfWB0%2BC0e7eFEQ%3D%3D&Expires=1784963961)\]

**Relevant products / OSS:**

* **Spotify / Netflix recsys** – Deep, multi‑stage recommenders tuned for engagement.\[[play.google](https://play.google.com/store/apps/details?id=com.spotify.music&hl=en_IN)\]  
* **Descript, YouTube, TikTok** – Use AI analytics for highlights and clip suggestions.\[[descript](https://www.descript.com/ai/edit-for-clarity)\]  
* **NVIDIA Merlin (OSS)** – End‑to‑end framework for training and serving large‑scale recsys on GPUs.\[[developer.nvidia](https://developer.nvidia.com/merlin)\]  
* **RecBole / RecBole2.0 / RecBole‑GNN (OSS)** – Very popular recsys libraries with many SOTA models.\[[github](https://github.com/RUCAIBox/RecBole)\]  
* **Haystack (deepset) (OSS)** – AI orchestration framework for LLM‑based search and conversational retrieval.\[[github](https://github.com/deepset-ai/haystack)\]

Your project is basically “**upgrade Pocket FM’s discovery layer using Merlin \+ RecBole \+ Haystack, specialized for serialized audio**.”

---

## **P6 – AI Agents (Producer Agent, CEO Agent, Creator Copilot)\[[ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/61971276/7d7926b1-680d-48ae-840c-6a1ea6b89852/Problem-statements.pdf?AWSAccessKeyId=ASIA2F3EMEYE7LAQKY2B&Signature=38uGjhkzHQ8WqyNcnHnK0mIpCYw%3D&x-amz-security-token=IQoJb3JpZ2luX2VjEE8aCXVzLWVhc3QtMSJHMEUCIQDGTRCOdwkFRdDhQ2wmnINN7S4Ag2UuuhyEFqgnVlVU5gIgc6UhAUfGVVfCJ85ut89NEYwSn%2BkgOihd6haJuxkyp0Qq8wQIFxABGgw2OTk3NTMzMDk3MDUiDFD%2FIEQbXCyZkjOfSSrQBNT1gOpKRJjb1sx7pbwnqSlnsHuQDz5Qa9ffpBkawuU9hTKpBnZr0h0PVcjDwqVuiODRLZD0JMLP84caVGiVFu9RzL3xSKkvmojo02uYBScdeyes5DzCjKqETCqhAKVlnZ4mHR6NqAtlMA27WwB0eQAIz0B39oPATwy9tFSZPAPZJ4ZtIXenxc3iaR6Q4UO5DCbLfVaaN3EDJPnzo13Zim713wtK0Q2PtkgxYowaXR6%2BhdusItNcOZ8lUJFmETw3EUJ6sqkt5BwN2nOGMqUjHM5BYKuftzk3imfxARRxndrXTRGY4i%2FbmIy5lR9wy3raAenSc%2FEpeFLLquEdNzwEzvN9pJPo1KqHx5S9yeX03142DAWCll4o9II9zDRLRy4svzlZnFJ4zbMpWbyARWoGa62qtDWxfG%2FTnyNv%2FHsV7cPdPL0mdOTCXLQh33jLvax1DBwFStJEUeCD34pU0qyQV2SUzj%2BL1OBb%2Br9FT8ex%2BLiZW9YWc4CbYQ9ooxnIkftMj2KkqmNfZAjHckhpgfH9BhC8VrY1W7rV991WgALrYzFLq%2FheVVo7BjGAC3iq6jvFWJoBosmcB%2FUuU9CoHAeCaOjTbdJpu3suhQCeuluNZ7eI8Qv%2FWkc3dRHN1gFgCr5%2BqRvOnd5N4uVuFIUYIrt%2BneJCpXnmrmb34DiuJLM%2F69SVJAMuwDlhcxJc4mpXIHoKWduIxzKQS63tAnM3KyxiZca3QPxEzi4SCCOJJ02eSlBr%2FYX1O4406VT8yoroJ5WM%2FbDpLntbjUZSISQB3L%2FNiOEwpquR0wY6mAFjByGh84wzfRmShNAQbtJ9oNbAOu8DNrCAG%2FPc%2BlvzqOKYByS6ViR7W6x3IC%2BUG1kPeHUg83TautY26vZblH3bS1foPOEyivHCByyHxmoR1tVMBmRRzPs3xPTM%2FM%2FBJtpYnEzkp0wHd0SfUrDOCfi2AQJTmD5oJoY2aKGDPdGPIq9L3CZFAMhJCM%2BiV9pUqfWB0%2BC0e7eFEQ%3D%3D&Expires=1784963961)\]**

**About:**  
Agentic systems that coordinate sub‑agents to manage production, funding, localization, etc.

**Existing frameworks:**

* **LangGraph** – Graph‑based agent orchestration; resilient, stateful multi‑agent workflows.\[[langchain](https://www.langchain.com/blog/langgraph-multi-agent-workflows)\]  
* **AutoGen (Microsoft)** – Multi‑agent conversation framework for LLM apps.\[[microsoft](https://www.microsoft.com/en-us/research/publication/autogen-enabling-next-gen-llm-applications-via-multi-agent-conversation-framework/)\]  
* **Haystack agents** – Agent orchestration for information workflows.\[[github](https://github.com/deepset-ai/haystack/tree/v1.x)\]

**Upgrade idea:**  
Wrap your **PocketTaste \+ analytics** into an **“Entertainment CEO” dashboard**: agent that proposes:

* Which shows to promote, localize, adapt to video  
* Which creators to invest in  
* Backed by your recommendation and performance data.

You probably won’t build that fully at a hackathon, but it’s the “future path” story.

---

## **3\. One strong, production‑style use case to build now**

Given all this, **PocketTaste is still the best single use case** for you: it hits a big business lever, uses powerful OSS, and aligns perfectly with the Entertainment Discovery block.

## **Refined PocketTaste use case (without using theme wording)**

> **PocketTaste is a multi‑stage recommendation and conversational discovery engine that ensures every Pocket FM listener always has a next series they’re likely to finish and pay for.** It learns from long‑form behavior (episode streaks, drop‑offs, coin unlocks, re‑listens, time of day) and uses that to drive the home feed, “because you listened to…” rails, and a natural‑language “find me something that feels like X” search box.

**Key capabilities you actually build:**

1. **Merlin‑based ranking pipeline**  
   * Use a sample dataset (MovieLens or synthetic Pocket‑like data) to show:  
     * Candidate generation (e.g., with simple two‑tower model).  
     * Ranking model that optimizes for a proxy of long‑form engagement.\[[developer.nvidia](https://developer.nvidia.com/merlin)\]  
2. **RecBole experimentation layer**  
   * Use RecBole to train a sequence model (e.g., SASRec/GRU4Rec) on the same data and show that it beats simple popularity on NDCG/Recall.\[[github](https://github.com/RUCAIBox/RecBole2.0)\]  
3. **Haystack conversational discovery**  
   * Index a small catalog of Pocket‑style series descriptions.  
   * Build an API where the user query (“I want a slow‑burn small‑town romance in Hindi, no cheating arcs”) goes to Haystack → candidate retrieval → re‑scored by your ranking model.\[[github](https://github.com/deepset-ai)\]  
4. **Explain‑why \+ mood search**  
   * For each recommendation, expose an “explanation string” (“because you completed 3 thrillers with strong female leads and dropped 2 horror series midway”).  
   * Implement a simple mapping from mood phrases (“rainy Sunday after heartbreak”) to embedding regions using Haystack’s retrieval \+ tag weights.\[[github](https://github.com/deepset-ai/haystack)\]\[[ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/61971276/7d7926b1-680d-48ae-840c-6a1ea6b89852/Problem-statements.pdf?AWSAccessKeyId=ASIA2F3EMEYE7LAQKY2B&Signature=38uGjhkzHQ8WqyNcnHnK0mIpCYw%3D&x-amz-security-token=IQoJb3JpZ2luX2VjEE8aCXVzLWVhc3QtMSJHMEUCIQDGTRCOdwkFRdDhQ2wmnINN7S4Ag2UuuhyEFqgnVlVU5gIgc6UhAUfGVVfCJ85ut89NEYwSn%2BkgOihd6haJuxkyp0Qq8wQIFxABGgw2OTk3NTMzMDk3MDUiDFD%2FIEQbXCyZkjOfSSrQBNT1gOpKRJjb1sx7pbwnqSlnsHuQDz5Qa9ffpBkawuU9hTKpBnZr0h0PVcjDwqVuiODRLZD0JMLP84caVGiVFu9RzL3xSKkvmojo02uYBScdeyes5DzCjKqETCqhAKVlnZ4mHR6NqAtlMA27WwB0eQAIz0B39oPATwy9tFSZPAPZJ4ZtIXenxc3iaR6Q4UO5DCbLfVaaN3EDJPnzo13Zim713wtK0Q2PtkgxYowaXR6%2BhdusItNcOZ8lUJFmETw3EUJ6sqkt5BwN2nOGMqUjHM5BYKuftzk3imfxARRxndrXTRGY4i%2FbmIy5lR9wy3raAenSc%2FEpeFLLquEdNzwEzvN9pJPo1KqHx5S9yeX03142DAWCll4o9II9zDRLRy4svzlZnFJ4zbMpWbyARWoGa62qtDWxfG%2FTnyNv%2FHsV7cPdPL0mdOTCXLQh33jLvax1DBwFStJEUeCD34pU0qyQV2SUzj%2BL1OBb%2Br9FT8ex%2BLiZW9YWc4CbYQ9ooxnIkftMj2KkqmNfZAjHckhpgfH9BhC8VrY1W7rV991WgALrYzFLq%2FheVVo7BjGAC3iq6jvFWJoBosmcB%2FUuU9CoHAeCaOjTbdJpu3suhQCeuluNZ7eI8Qv%2FWkc3dRHN1gFgCr5%2BqRvOnd5N4uVuFIUYIrt%2BneJCpXnmrmb34DiuJLM%2F69SVJAMuwDlhcxJc4mpXIHoKWduIxzKQS63tAnM3KyxiZca3QPxEzi4SCCOJJ02eSlBr%2FYX1O4406VT8yoroJ5WM%2FbDpLntbjUZSISQB3L%2FNiOEwpquR0wY6mAFjByGh84wzfRmShNAQbtJ9oNbAOu8DNrCAG%2FPc%2BlvzqOKYByS6ViR7W6x3IC%2BUG1kPeHUg83TautY26vZblH3bS1foPOEyivHCByyHxmoR1tVMBmRRzPs3xPTM%2FM%2FBJtpYnEzkp0wHd0SfUrDOCfi2AQJTmD5oJoY2aKGDPdGPIq9L3CZFAMhJCM%2BiV9pUqfWB0%2BC0e7eFEQ%3D%3D&Expires=1784963961)\]  
5. **Demo UI**  
   * React/Next UI styled like a mini Pocket FM home screen:  
     * “For You” rail driven by your recsys.  
     * Mood search box.  
     * Click on a title → show explanation \+ similar items.

You can clearly say you’re **standing on proven open‑source infra**:

* RecBole for model R\&D.\[[github](https://github.com/RUCAIBox/RecBole-GNN)\]  
* Merlin for scalable training/serving.\[[developer.nvidia](https://developer.nvidia.com/merlin)\]  
* Haystack for conversational search and orchestration.\[[github](https://github.com/deepset-ai/haystack/tree/v1.x)\]

And you are **upgrading it for Pocket FM’s reality**:

* Objective is **series completion \+ coins**, not just clicks.\[[thehindubusinessline](https://www.thehindubusinessline.com/companies/pocket-fms-creator-economy-crosses-300-crore-eyes-1000-crore-by-2026/article70642447.ece)\]  
* Catalog is **serialized fiction audio**, not songs.\[[economictimes.indiatimes](https://economictimes.indiatimes.com/tech/technology/pocket-fm-launches-ai-creator-studio-slashes-audio-series-production-time-to-a-day/articleshow/123949202.cms)\]  
* Discovery needs to support **Bharat languages and moods**, not only English keywords.\[[finance.yahoo](https://finance.yahoo.com/news/audio-platform-pocket-fm-taps-100100433.html)\]

---

## **4\. How to position this to judges**

You can summarize like this:

* **Problem:** “When a Pocket FM listener finishes a series, it’s hard to consistently surface the next one they’ll actually binge and pay for, especially across languages and moods.”  
* **Existing tools:** “Spotify/Netflix have strong recsys, but tuned for music/movies; Merlin, RecBole and Haystack are powerful OSS stacks but generic.”\[[developer.nvidia](https://developer.nvidia.com/merlin)\]  
* **Our innovation:** “We specialize these open‑source frameworks for long‑form, episodic, micro‑transaction‑driven audio, wiring them into a multi‑stage system (candidate → rank → conversational layer → explanations) that Pocket FM could realistically pilot.”

If you want, next step I can help you turn this into a concrete repo structure \+ task split (who sets up Merlin/RecBole, who does Haystack \+ UI, etc.) so you can execute fast during the hackathon.

# Tab 2

Your problem-statement list isn't hypothetical — nearly every bucket already has shipping products, and the last 30 days show the category consolidating fast. Here's the map from your P1–P6 themes to what people are actually building and arguing about right now.

P1 (AI-Native Storytelling) is where the money and the Big Tech moves are landing \- Meta is testing [StoryKit](https://techcrunch.com/2026/07/21/meta-is-testing-an-ai-bedtime-story-app-for-people-with-no-imagination/) (AI kids' stories with custom characters, settings, and music, spotted late July) and shipped [Pocket](https://techcrunch.com/2026/07/02/meta-quietly-launches-vibe-coded-gaming-app-pocket/) for vibe-coded interactive games from prompts. On the funding side, [Giant raised $8M](https://www.edtechinnovationhub.com/news/giant-raises-8m-to-scale-ai-driven-interactive-storytelling-for-children) for personalized kids' storytelling (200k+ episodes generated, kids cast as cartoon versions of themselves). Your "Dream to Story" audio-drama idea maps cleanly to [Musely's multi-voice audio drama generator](https://musely.ai/tools/audio-drama-generator) and [DreamPress AI](https://apps.apple.com/us/app/dreampress-ai-story-generator/id6739579863). The gap your list targets \- persistent side-character memory, story "time machines," collaborative live stories \- is exactly the hard part nobody has nailed yet.  
P2 (Characters and Companions) is the most mature and most competitive bucket \- your "Living Characters that remember every conversation" is the entire pitch of [Kindroid](https://kissable.app/blog/best-character-ai-alternatives-reddit) (r/KindroidAI \~43k members), [Nomi.ai](https://kissable.app/blog/best-character-ai-alternatives-reddit), and SpicyChat, all built on editable long-term memory banks. Your "Character Marketplace" already has a real analog: [WEBTOON partnered with Genies in April 2026](https://www.marketsandmarkets.com/PressReleases/character-based-ai-agents.asp) to turn webcomic characters into monetizable interactive avatars \- and the [character-based AI agents market](https://finance.yahoo.com/sectors/technology/articles/character-based-ai-agents-market-141500447.html) is projected to grow from $0.55B this year to $5.45B by 2032 (46.7% CAGR). Real differentiation is memory depth, not the chat itself.  
P3 (Interactive Entertainment) just got its flagship this quarter \- Latitude (the AI Dungeon team) launched [Voyage](https://howworks.ai/blog/best-ai-rpg-games), an invite-only beta built on a "World Engine" that tracks health, inventory, currency, geography, relationships, and long-term consequences across thousands of turns. That's almost a direct implementation of your "AI Dungeon where the entire world emerges dynamically." Your "Story as a Game / every listener gets a different ending" idea is live in [DramaGo](https://www.youtube.com/watch?v=i3RGZnYF5J8), an interactive short-drama app \- a reviewer with 3.6k views put the whole category's thesis plainly: *"What really makes this platform different is the interactive experience."*  
P4 (Video and Visual AI) is the most solved bucket \- and the most crowded \- "audio story to animated trailer in two minutes" is basically the [Veo 3.1 / Sora 2 Pro / Kling 2.5 / Runway Gen-4](https://outlierkit.com/blog/best-ai-tools-for-movie-creation) stack plus orchestration layers like [LTX Studio](https://en.wikipedia.org/wiki/LTX_Studio) and [Mootion](https://www.mootion.com/use-cases/en/AI-movie-trailer-creator). The live pain point creators actually voice is consistency, not generation: a Hindi tutorial on Google Flow's Storyboard Studio pulled [116k views](https://www.youtube.com/watch?v=JOaR-v2oPJg) precisely because it promised *consistent characters*, and the top comment (@priyatn24) is a creator frustrated with rival tools begging for exactly that. Your "graphic novel with visual consistency across hundreds of pages" is the unsolved white space here.  
P5 \+ P6 (Creator Superpowers and Agents) is where your list is most differentiated \- your "Plot Hole Hunter" already exists as three competing approaches: [Jenova](https://www.jenova.ai/en/resources/ai-plot-generator) (reviews outlines for logic holes), [Novarrium's "Logic-Locking"](https://novarrium.com/blog/ai-novel-plot-holes) (prevents contradictions at generation time rather than detecting them after), and [FinalBit's Plot Hole Detection Report](https://www.finalbitai.com/features/plot-hole-detection-report). But the "AI Writers Room" (multi-agent director/editor/critic/audience) and "Audience Simulator" concepts are barely built \- r/WritingWithAI power users are hand-assembling this today, like the ["Full AI Fiction Stack: How I Connect AI, Excel, and Other Apps"](https://www.reddit.com/r/WritingWithAI/comments/1v4skpn/my_full_ai_fiction_stack_how_i_connect_ai_excel/) thread. A packaged multi-agent writers' room is a genuinely open opportunity.  
The loudest cross-cutting theme is legitimacy backlash, and you should design around it \- the top-engagement Reddit thread in the whole pull was ["You write with AI? That's not real writing"](https://www.reddit.com/r/WritingWithAI/comments/1v1lhgc/you_write_with_ai_thats_not_real_writing/) (220 upvotes, 194 comments), and [Substack's new "made with AI" meter](https://www.reddit.com/r/artificial/comments/1v4kf7w/substack_launched_a_made_with_ai_meter_people_are/) set off r/artificial. On r/singularity the mood split hard: [u/Effective\_Coach7334](https://reddit.com/r/singularity/comments/1uxwzi4/comment/oxumnm5/) (435 upvotes) argued *"people that spend so much energy hating on it are wasting the energy they could be using to adapt to and steer the inevitable,"* while [u/martiantheory](https://reddit.com/r/singularity/comments/1uxwzi4/comment/oxum56e/) (449 upvotes) landed the darker one-liner: *"It's a little different when humans are the horses in this dynamic lol."*  
KEY PATTERNS from the research:

1. Persistent memory \+ continuity is the universal moat \- every mature product (Kindroid companions, Latitude's World Engine, plot-hole tools) competes on remembering state across long spans. Your P1/P2 differentiators (side-character memory, one-decision "time machine") all live here, per [r/KindroidAI](https://kissable.app/blog/best-character-ai-alternatives-reddit).  
2. Generation is commodity; consistency and coherence are not \- the 116k-view Storyboard Studio video and the plot-hole-tool trio both sell *consistency*, not raw output, per [Hindi AI Gyaan on YouTube](https://www.youtube.com/watch?v=JOaR-v2oPJg).  
3. Interactivity is the freshest 30-day wedge \- Voyage and DramaGo both launched/trended this window on "your choices change the story," matching your P3 bucket, per [AI Buildory on YouTube](https://www.youtube.com/watch?v=i3RGZnYF5J8).  
4. Multi-agent "writers room" and "audience simulator" are the least-built ideas on your list \- power users are duct-taping it manually, per [r/WritingWithAI](https://www.reddit.com/r/WritingWithAI/comments/1v4skpn/my_full_ai_fiction_stack_how_i_connect_ai_excel/).  
5. Build for the AI-legitimacy backlash, not around it \- provenance meters and "is this real writing" fights are the dominant discourse, per [r/artificial](https://www.reddit.com/r/artificial/comments/1v4kf7w/substack_launched_a_made_with_ai_meter_people_are/).

