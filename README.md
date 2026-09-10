# 🎬 Looney Tunes Shorts Index & Collector's Archive (1929–1969)

An interactive search engine, historical credits archive, and home media track index for all **1,039 classic and revival Looney Tunes and Merrie Melodies shorts (1929–2014)**.

Built as a lightweight, zero-dependency web app with instant client-side search, chronological era filtering, multi-format media tracking, and private visitor personalization.

---

## 🌟 Features for Visitors

* **⚡ Real-Time Instant Search:**
  * Search across cartoon titles, directors, voice actors, animators, featured characters, media sets, and your own personal notes.
  * Accent & diacritic insensitive (e.g., searching `Pepe` immediately finds `Pepé Le Pew`).
* **⏳ Interactive Theatrical Era Timeline:**
  * Dual-range year slider (1929–1969) with 1-click era presets:
    * 🎞️ **Black & White Era** (1929–1943)
    * 🎖️ **War Years** (1941–1945)
    * ⭐ **Golden Age Technicolor** (1946–1959)
    * 📺 **TV & Late Theatrical Era** (1960–1969)
* **📀 Home Media Releases & "My Library":**
  * Tracks disc numbers, titles, and track locations across **30 physical releases** (Blu-ray, DVD, and LaserDisc).
  * Grouped by format first (`Blu-ray`, `DVD`, `LaserDisc`) and sorted alphabetically.
  * **Strict Inclusion Search:** Check off the sets you own to filter exclusively to released shorts in your collection.
  * **Clear All:** Searches the entire 1,039 title catalog (including unreleased cartoons).
  * **Multi-User Profiles:** Save different library setups (e.g. "Living Room", "LaserDiscs", etc.) directly in your browser.
* **⭐ Private Star Ratings (1–5 ★):**
  * Rate any short with 1 to 5 stars directly on its card.
  * Filter to your rated shorts (`Any`, `5★`, `4+★`, `3+★`, or `Unrated`).
* **📝 Private Notes & Reviews:**
  * Write notes, restoration impressions, or favorite gags on any cartoon card.
  * Automatically auto-saves to your browser.
  * Search your own notes in the search bar or click the `📝 Has Notes` filter pill!
* **📤 Backup & Restore:**
  * Export your star ratings, notes, and collections as a `.json` backup file anytime.
  * Restore your data on any computer or browser with one click.

---

## 🔒 100% Private, Client-Side Architecture

* **Zero Tracking / Pure Client-Side:** All searches, ratings, notes, and collection customizations happen 100% locally within your browser using `localStorage`.
* **Public Reference Catalog:** The master records are strictly read-only for all visitors, serving as a clean, fast reference tool without login gates or passwords.

---

## 🚀 How to Host on GitHub Pages (Step-by-Step)

Because this web app is 100% static on the client, it hosts free forever with unlimited bandwidth on GitHub Pages.

### Step 1: Initialize Git and Commit
In your terminal, navigate to this folder:
```bash
cd /Users/sean/.gemini/antigravity/scratch/ae_centroid/looney_tunes_search
git init
git add .
git commit -m "Initial release of Looney Tunes Shorts Index"
```

### Step 2: Create a New Repository on GitHub
1. Go to [github.com/new](https://github.com/new) in your browser.
2. Name the repository (for example: `looney-tunes-index`).
3. Set it to **Public**.
4. Leave "Add a README" unchecked, then click **Create repository**.

### Step 3: Push Your Code
Copy the commands shown on GitHub (or run):
```bash
git remote add origin https://github.com/<YOUR-USERNAME>/looney-tunes-index.git
git branch -M main
git push -u origin main
```

### Step 4: Enable GitHub Pages
1. On your GitHub repository page, click **Settings** (tab at the top).
2. On the left sidebar, click **Pages**.
3. Under **Build and deployment > Source**, select **Deploy from a branch**.
4. Under **Branch**, select `main` and `/ (root)`, then click **Save**.

🎉 Within ~60 seconds, your web app will be live at:
```
https://<YOUR-USERNAME>.github.io/looney-tunes-index/
```

---

## 📁 File Structure

* `index.html`: Complete web application UI, search engine, era timeline, and ratings/notes system.
* `database.json`: Master JSON catalog of all 1,039 theatrical and revival shorts.
* `database.js`: Offline/CORS-safe fallback database definition.
* `custom_overrides.json`: Protected manual overrides (never overwritten by scraper runs).
* `server.py`: Zero-dependency local editing server with REST endpoints.
* `scraper.py`: Wikipedia wikitext parser for filmographies and home media collections.
* `edit.py`: Command-line interface for fast terminal edits.
* `run_editor.command`: Double-clickable macOS launcher for the local editor.
