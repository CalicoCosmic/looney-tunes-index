#!/usr/bin/env python3
"""
Looney Tunes Master Catalog Scraper & Database Generator
--------------------------------------------------------
1. Ingests the complete theatrical filmography of all 1,000+ classic
   Warner Bros. cartoons (1929–1969):
     - 1929–1939 (272 shorts)
     - 1940–1949 (306 shorts)
     - 1950–1959 (278 shorts)
     - 1960–1969 (146 shorts)
   Extracts: Title, Year, Series, Director, Animators, Recurring Characters, Synopsis.

2. Merges Home Media releases:
     - Porky Pig 101 (101 shorts)
     - Golden Collection (Volumes 1-6, 356 shorts)
     - Platinum Collection (Volumes 1-3, 150 shorts)
     - The Golden Age of Looney Tunes (LaserDisc sets)

3. Generates:
     - database.json
     - database.js (loads directly in browser on file:// without CORS issues)
"""

import datetime
import json
import os
import re
import time
import urllib.parse
import urllib.request

HEADERS = {
    "User-Agent": "LooneyTunesMasterCatalog/2.0 (https://en.wikipedia.org; looney_catalog@example.com)"
}

DIRECTOR_MAP = {
    "Chuck Jones": ["Charles M. Jones", "Charles Jones", "Chuck Jones"],
    "Friz Freleng": ["Isadore Freleng", "I. Freleng", "Friz Freleng"],
    "Tex Avery": ["Fred Avery", "J. Fred Avery", "Tex Avery"],
    "Bob Clampett": ["Robert Clampett", "Bob Clampett"],
    "Robert McKimson": ["Bob McKimson", "Robert McKimson"],
    "Frank Tashlin": ["Frank Tash", "Tish Tash", "Frank Tashlin"],
    "Art Davis": ["Arthur Davis", "Art Davis"],
    "Norm McCabe": ["Norman McCabe", "Norm McCabe"],
    "Hugh Harman": ["Hugh Harman"],
    "Rudolf Ising": ["Rudy Ising", "Rudolf Ising"],
    "Hawley Pratt": ["Hawley Pratt"],
    "Abe Levitow": ["Abe Levitow"],
    "Maurice Noble": ["Maurice Noble"],
    "Ted Bonnicksen": ["Ted Bonnicksen"],
    "Phil Monroe": ["Phil Monroe"],
    "Richard Thompson": ["Richard Thompson"],
    "Gerry Chiniquy": ["Gerry Chiniquy"],
    "Rudy Larriva": ["Rudy Larriva"],
    "Alex Lovy": ["Alex Lovy"],
    "Ben Hardaway": ["Ben Hardaway", "Bugs Hardaway"],
    "Cal Dalton": ["Cal Dalton"],
    "Cal Howard": ["Cal Howard"],
    "Jack King": ["Jack King"],
    "Bernard B. Brown": ["Bernard B. Brown"],
    "Earl Duvall": ["Earl Duvall"],
    "Tom Palmer": ["Tom Palmer"],
    "Ub Iwerks": ["Ub Iwerks"],
    "Ken Harris": ["Ken Harris"],
    "Irv Spector": ["Irv Spector"]
}


def clean(text: str) -> str:
    if not text:
        return ""
    # Handle {{sort|key|display}} -> display
    text = re.sub(r"\{\{sort\|[^|}]*\|([^}]*)\}\}", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\{\{sortname\|([^|}]*)\|([^|}]*)\}\}", r"\1 \2", text, flags=re.IGNORECASE)
    # Strip <ref> tags
    text = re.sub(r"<ref.*?</ref>", "", text, flags=re.DOTALL)
    text = re.sub(r"<ref.*?/>", "", text)
    # Strip remaining templates
    text = re.sub(r"\{\{.*?\}\}", "", text)
    # Replace <br> and variants with space so words never mash
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    # Extract wiki links [[Target|Display]] -> Display, [[Target]] -> Target
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", text)
    # Strip HTML tags, replacing with space
    text = re.sub(r"<[^>]+>", " ", text)
    # Strip wikitable markup artifacts like !MM or !LT
    text = re.sub(r"[\r\n]+\s*!.*", "", text)
    text = re.sub(r"!MM\b", "", text)
    text = re.sub(r"!LT\b", "", text)
    # Clean quotes and italics
    text = text.replace("''", "").replace('"', '')
    # Normalize multiple whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def slugify(title: str, year=None) -> str:
    clean_t = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")
    return clean_t


def resolve_director(raw_name: str):
    if not raw_name:
        return "Unknown", "Unknown", [], []

    t = raw_name
    # Strip wikitable artifacts
    t = re.sub(r"[\r\n]+\s*!.*", "", t)
    t = re.sub(r"!MM\b|!LT\b", "", t)
    # Replace <br> with & between names
    t = re.sub(r"<br\s*/?>", " & ", t, flags=re.IGNORECASE)
    # Extract wiki links
    t = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", t)
    # Strip HTML tags with space
    t = re.sub(r"<[^>]+>", " ", t)
    t = t.replace("''", "").replace('"', '')
    # Fix mashed co-director or combined words
    t = re.sub(r"(?<=\S)Co-Director", r" Co-Director", t)
    t = re.sub(r"ClampettNorman", r"Clampett & Norman", t)
    t = re.sub(r"\s*Co-Director(s?):\s*", r" (Co-Director\1: ", t)
    if "(Co-Director" in t and not t.endswith(")"):
        t = t.strip() + ")"
    t = re.sub(r"\s*&\s*\((Co-Director)", r" (\1", t)
    t = re.sub(r"\s+&\s+Co-Director", " Co-Director", t)
    display_credit = re.sub(r"\s+", " ", t).strip()

    if not display_credit or display_credit in ["N/A", "—", "-"]:
        return "Unknown", "Unknown", [], []

    # Find matched canonical directors in order of appearance
    found_spans = []
    for can, alts in DIRECTOR_MAP.items():
        for cand in [can] + alts:
            m = re.search(r"\b" + re.escape(cand) + r"\b", display_credit, re.I)
            if m:
                found_spans.append((m.start(), can))
                break
    found_spans.sort(key=lambda x: x[0])

    directors_list = []
    for _, can in found_spans:
        if can not in directors_list:
            directors_list.append(can)

    primary_director = directors_list[0] if directors_list else display_credit

    aliases = []
    for d in directors_list:
        for a in DIRECTOR_MAP.get(d, []):
            if a not in directors_list and a not in aliases:
                aliases.append(a)

    return primary_director, display_credit, directors_list, aliases


def get_wikipedia_wikitext(page_title: str) -> str:
    url = f"https://en.wikipedia.org/w/api.php?action=query&titles={urllib.parse.quote(page_title)}&prop=revisions&rvslots=*&rvprop=content&format=json"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            page = list(data["query"]["pages"].values())[0]
            if "revisions" in page:
                return page["revisions"][0]["slots"]["main"]["*"]
    except Exception as e:
        print(f"[-] Error fetching {page_title}: {e}")
    return ""


def parse_template_fields(block: str) -> dict:
    depth_curly = 0
    depth_square = 0
    i = 0
    n = len(block)
    parts = []
    curr = []
    while i < n:
        c = block[i]
        if c == '{' and i + 1 < n and block[i+1] == '{':
            depth_curly += 1
            curr.append('{{')
            i += 2
            continue
        elif c == '}' and i + 1 < n and block[i+1] == '}':
            depth_curly = max(0, depth_curly - 1)
            curr.append('}}')
            i += 2
            continue
        elif c == '[' and i + 1 < n and block[i+1] == '[':
            depth_square += 1
            curr.append('[[')
            i += 2
            continue
        elif c == ']' and i + 1 < n and block[i+1] == ']':
            depth_square = max(0, depth_square - 1)
            curr.append(']]')
            i += 2
            continue
        elif c == '|' and depth_curly == 0 and depth_square == 0:
            parts.append(''.join(curr))
            curr = []
            i += 1
            continue
        curr.append(c)
        i += 1
    if curr:
        parts.append(''.join(curr))

    fields = {}
    for p in parts:
        if '=' in p:
            k, v = p.split('=', 1)
            v_clean = v.rstrip('}\n ')
            fields[k.strip()] = v_clean.strip()
    return fields


def parse_release_date(raw_date: str):
    if not raw_date:
        return "", None
    raw = re.sub(r"<ref.*?</ref>", "", raw_date, flags=re.DOTALL)
    raw = re.sub(r"<ref.*?/>", "", raw)
    raw = re.sub(r"<[^>]+>", " ", raw)

    # 1. {{Start date|YYYY|M|D}} or {{Film date|YYYY|M|D}}
    m = re.search(r"\{\{(?:Start date|Film date|start-date)[^|}]*\|(\d{4})\|(\d{1,2})\|(\d{1,2})", raw, re.I)
    if m:
        y, mth, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        dt = datetime.date(y, mth, d)
        return dt.strftime("%B %-d, %Y"), y

    # 2. {{Start date|YYYY|M}}
    m2 = re.search(r"\{\{(?:Start date|Film date)[^|}]*\|(\d{4})\|(\d{1,2})", raw, re.I)
    if m2:
        y, mth = int(m2.group(1)), int(m2.group(2))
        dt = datetime.date(y, mth, 1)
        return dt.strftime("%B %Y"), y

    # 3. 'Month Day, Year'
    clean_txt = clean(raw)
    m3 = re.search(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", clean_txt)
    if m3:
        mth_str, d_str, y_str = m3.group(1), m3.group(2), m3.group(3)
        return f"{mth_str} {int(d_str)}, {y_str}", int(y_str)

    # 4. 'Day Month Year'
    m4 = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", clean_txt)
    if m4:
        d_str, mth_str, y_str = m4.group(1), m4.group(2), m4.group(3)
        return f"{mth_str} {int(d_str)}, {y_str}", int(y_str)

    # 5. 'Month Year'
    m5 = re.search(r"([A-Za-z]+)\s+(\d{4})", clean_txt)
    if m5:
        return f"{m5.group(1)} {m5.group(2)}", int(m5.group(2))

    # 6. 'Year'
    m6 = re.search(r"\b(19\d\d)\b", clean_txt)
    if m6:
        return m6.group(1), int(m6.group(1))

    return clean_txt, None


def extract_field_raw(block: str, field: str) -> str:
    m = re.search(r"\|\s*" + field + r"\s*=\s*(.*?)(?=\n\s*[|!\}])", block, re.DOTALL)
    return m.group(1).strip() if m else ""


def extract_field(block: str, field: str) -> str:
    raw = extract_field_raw(block, field)
    return clean(raw) if raw else ""


def parse_master_decade(decade_page: str):
    print(f"[+] Scraping master filmography: {decade_page}...")
    content = get_wikipedia_wikitext(decade_page)
    if not content:
        return []

    shorts = []
    blocks = re.split(r"\{\{#invoke:Episode list\|list", content)
    for b in blocks[1:]:
        f = parse_template_fields(b)
        title = clean(f.get("RTitle") or f.get("Title") or "")
        if not title:
            continue
        title = title.split("|")[0].split("\n")[0].strip().strip("'\"")

        dir_raw = f.get("DirectedBy", "")
        canonical_dir, display_credit, dir_list, aliases = resolve_director(dir_raw)

        anim_raw = f.get("Aux2", "")
        animators = []
        if anim_raw and not anim_raw.lower().startswith("n/a"):
            items = re.split(r"<br\s*/?>|[\r\n]+|;", anim_raw, flags=re.IGNORECASE)
            for it in items:
                for a in re.split(r",|\band\b|&", it):
                    ac = clean(a).strip()
                    if ac and len(ac) > 1 and ac.lower() not in ["none", "—", "-", "n/a"]:
                        animators.append(ac)

        chars_raw = f.get("Aux3", "")
        chars = []
        if chars_raw and not chars_raw.lower().startswith("n/a"):
            chars_raw = re.sub(r'(Duck|Pig|Bunny|Cat|Dog|Wolf|Mouse|Rooster|Stork|Fox|Bear)([A-Z])', r'\1<br />\2', chars_raw)
            items = re.split(r"<br\s*/?>|[\r\n]+|;", chars_raw, flags=re.IGNORECASE)
            for it in items:
                sub_items = it.split(',') if ',' in it and not any(k in it.lower() for k in ['jr.', 'sr.']) else [it]
                for sit in sub_items:
                    c = clean(sit).strip()
                    if c and len(c) > 1 and c.lower() not in ["none", "—", "-", "n/a"]:
                        if c not in chars:
                            chars.append(c)

        story_raw = f.get("WrittenBy") or f.get("Story") or ""
        story = clean(story_raw)
        if not story:
            m_story = re.search(r"''Story by''\s*([^\n\r<]+)", b, re.IGNORECASE)
            if m_story:
                story = clean(m_story.group(1)).strip()
        if not story:
            story = "—"

        series_raw = f.get("Aux1", "")
        series = "Looney Tunes"
        if "MM" in series_raw or "Merrie" in series_raw:
            series = "Merrie Melodies"

        summary = clean(f.get("ShortSummary", ""))

        airdate_raw = f.get("OriginalAirDate", "")
        rel_date, year_from_date = parse_release_date(airdate_raw)
        year_match = re.search(r"\b(19\d\d)\b", airdate_raw) or re.search(r"\b(19\d\d)\b", b)
        year = year_from_date or (int(year_match.group(1)) if year_match else None)

        shorts.append({
            "title": title,
            "year": year,
            "release_date": rel_date,
            "series": series,
            "director": canonical_dir,
            "director_credit": display_credit,
            "directors": dir_list,
            "director_aliases": aliases,
            "story": story,
            "animation": animators,
            "featured_characters": chars,
            "synopsis": summary,
            "media_locations": []
        })
    return shorts


def parse_porky_pig_101():
    print("[+] Scraping Porky Pig 101...")
    content = get_wikipedia_wikitext("Porky_Pig_101")
    if not content:
        return []

    shorts = []
    sections = re.split(r"==+\s*Disc\s*(\d+)\s*[-:]*\s*([^=]*)\s*==+", content)
    for i in range(1, len(sections), 3):
        disc_num = int(sections[i])
        disc_title = clean(sections[i + 1]) or f"Disc {disc_num}"
        sec_content = sections[i + 2]
        rows = sec_content.split("|-")

        for r in rows:
            cells = [clean(c) for c in re.split(r'\n[|!]|\|\||!!', r) if c.strip() and not c.startswith("}") and not c.startswith("{")]
            if cells and cells[0].isdigit():
                track_num = int(cells[0])
                title = cells[1].strip("'\"")
                if not title:
                    continue
                year = int(cells[2]) if len(cells) > 2 and cells[2].isdigit() else None
                dir_raw = cells[3] if len(cells) > 3 else "Unknown"
                canonical_dir, display_credit, dir_list, aliases = resolve_director(dir_raw)

                chars = ["Porky Pig"]
                if len(cells) > 4:
                    raw_stars = cells[4]
                    if raw_stars.lower() not in ["none", "—", "-", ""]:
                        for s in re.split(r",|\band\b", raw_stars):
                            sc = s.strip()
                            if sc and sc not in chars:
                                chars.append(sc)

                series = "Looney Tunes"
                if len(cells) > 5 and "MM" in cells[5]:
                    series = "Merrie Melodies"

                shorts.append({
                    "title": title,
                    "year": year,
                    "series": series,
                    "director": canonical_dir,
                    "director_credit": display_credit,
                    "directors": dir_list,
                    "director_aliases": aliases,
                    "featured_characters": chars,
                    "media_entry": {
                        "set_name": "Porky Pig 101",
                        "format": "DVD",
                        "disc_number": disc_num,
                        "disc_title": disc_title,
                        "track_number": track_num,
                        "audio_commentary": []
                    }
                })
    return shorts


def parse_golden_collection_volume(volume_num: int):
    page_title = f"Looney_Tunes_Golden_Collection:_Volume_{volume_num}"
    print(f"[+] Scraping {page_title}...")
    content = get_wikipedia_wikitext(page_title)
    if not content:
        return []

    shorts = []
    sections = re.split(r"==+\s*Disc\s*(\d+)\s*[-:]*\s*([^=]*)\s*==+", content)
    for i in range(1, len(sections), 3):
        disc_num = int(sections[i])
        disc_title = clean(sections[i + 1]) or f"Disc {disc_num}"
        sec_content = sections[i + 2]
        rows = sec_content.split("|-")

        for r in rows:
            cells = [clean(c) for c in re.split(r'\n[|!]|\|\||!!', r) if c.strip() and not c.startswith("}") and not c.startswith("{")]
            if cells and cells[0].isdigit():
                track_num = int(cells[0])
                title = cells[1].strip("'\"")
                if not title:
                    continue
                
                co_stars_raw = ""
                year = None
                dir_raw = "Unknown"
                series = "Looney Tunes"

                for cell in cells[2:]:
                    if cell.isdigit() and len(cell) == 4:
                        year = int(cell)
                    elif "MM" in cell or "Merrie" in cell:
                        series = "Merrie Melodies"
                    elif any(k in cell.lower() for k in ["jones", "freleng", "avery", "clampett", "mckimson", "tashlin", "davis", "harman", "ising"]):
                        dir_raw = cell

                if len(cells) > 2 and not cells[2].isdigit():
                    co_stars_raw = cells[2]

                canonical_dir, display_credit, dir_list, aliases = resolve_director(dir_raw)
                chars = []
                if "bugs" in disc_title.lower():
                    chars.append("Bugs Bunny")
                elif "daffy" in disc_title.lower():
                    chars.append("Daffy Duck")
                elif "porky" in disc_title.lower():
                    chars.append("Porky Pig")

                if co_stars_raw and co_stars_raw.lower() not in ["none", "—", "-"]:
                    for s in re.split(r",|\band\b", co_stars_raw):
                        sc = s.strip()
                        if sc and sc not in chars:
                            chars.append(sc)

                shorts.append({
                    "title": title,
                    "year": year,
                    "series": series,
                    "director": canonical_dir,
                    "director_credit": display_credit,
                    "directors": dir_list,
                    "director_aliases": aliases,
                    "featured_characters": chars,
                    "media_entry": {
                        "set_name": f"Looney Tunes Golden Collection: Volume {volume_num}",
                        "format": "DVD",
                        "disc_number": disc_num,
                        "disc_title": disc_title,
                        "track_number": track_num,
                        "audio_commentary": []
                    }
                })
    return shorts


def parse_platinum_collection_volume(volume_num: int):
    page_title = f"Looney_Tunes_Platinum_Collection:_Volume_{volume_num}"
    print(f"[+] Scraping {page_title}...")
    content = get_wikipedia_wikitext(page_title)
    if not content:
        return []

    shorts = []
    sections = re.split(r"==+\s*Disc\s*(\d+)\s*[-:]*\s*([^=]*)\s*==+", content)
    for i in range(1, len(sections), 3):
        disc_num = int(sections[i])
        disc_title = clean(sections[i + 1]) or f"Disc {disc_num}"
        sec_content = sections[i + 2]
        rows = sec_content.split("|-")

        for r in rows:
            cells = [clean(c) for c in re.split(r'\n[|!]|\|\||!!', r) if c.strip() and not c.startswith("}") and not c.startswith("{")]
            if cells and cells[0].isdigit():
                track_num = int(cells[0])
                title = cells[1].strip("'\"")
                if not title:
                    continue
                year = None
                dir_raw = "Unknown"
                series = "Looney Tunes"

                for cell in cells[2:]:
                    if cell.isdigit() and len(cell) == 4:
                        year = int(cell)
                    elif any(k in cell.lower() for k in ["jones", "freleng", "avery", "clampett", "mckimson", "tashlin", "davis", "harman", "ising"]):
                        dir_raw = cell

                canonical_dir, display_credit, dir_list, aliases = resolve_director(dir_raw)

                shorts.append({
                    "title": title,
                    "year": year,
                    "series": series,
                    "director": canonical_dir,
                    "director_credit": display_credit,
                    "directors": dir_list,
                    "director_aliases": aliases,
                    "featured_characters": [],
                    "media_entry": {
                        "set_name": f"Looney Tunes Platinum Collection: Volume {volume_num}",
                        "format": "Blu-ray",
                        "disc_number": disc_num,
                        "disc_title": disc_title,
                        "track_number": track_num,
                        "audio_commentary": []
                    }
                })
    return shorts


def parse_all_golden_age_laserdiscs():
    """
    Parses all 5 volumes of 'The Golden Age of Looney Tunes' LaserDisc box sets from Fandom.
    Extracts disc numbers, side titles, track numbers, and short titles.
    """
    page_title = "The Golden Age of Looney Tunes"
    print(f"[+] Scraping {page_title} (LaserDisc Volumes 1–5)...")
    url = "https://looneytunes.fandom.com/api.php?action=parse&page=" + urllib.parse.quote(page_title) + "&prop=wikitext&format=json"
    req = urllib.request.Request(url, headers={"User-Agent": "LooneyTunesMasterCatalog/2.0 (research@example.com)"})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            wikitext = data.get("parse", {}).get("wikitext", {}).get("*", "")
    except Exception as e:
        print(f"[-] Error fetching LaserDisc tracklists: {e}")
        return []

    if not wikitext:
        return []

    all_ld_shorts = []
    vol_sections = re.split(r"===+\s*Volume\s*(\d+)\s*===+", wikitext)
    for v in range(1, len(vol_sections), 2):
        vol_num = int(vol_sections[v])
        v_text = vol_sections[v + 1]

        subsections = v_text.split("|-")
        for s_idx in range(len(subsections) - 1):
            header_block = subsections[s_idx]
            cell_block = subsections[s_idx + 1]

            headers = [clean(h) for h in re.findall(r"!\s*(?:width=[^|]+\|)?\s*(Side\s*\d+[^|\n]+)", header_block)]
            cells = [c.strip() for c in cell_block.split("\n|") if c.strip() and not c.startswith("!") and not c.startswith("{") and not c.startswith("}")]

            if headers and len(headers) == len(cells):
                for h, c in zip(headers, cells):
                    side_num_match = re.search(r"Side\s*(\d+)", h)
                    side_num = int(side_num_match.group(1)) if side_num_match else 1
                    disc_num = (side_num + 1) // 2
                    side_title = h

                    track_items = [clean(t) for t in re.split(r"<br\s*/?>", c) if clean(t)]
                    for t_idx, item in enumerate(track_items):
                        title_match = re.search(r"^([^(]+)(?:\s*\(([^)]+)\))?", item)
                        title = clean(title_match.group(1)).strip("\"' ") if title_match else clean(item).strip("\"' ")
                        if title and not title.lower().startswith("side"):
                            all_ld_shorts.append({
                                "title": title,
                                "series": "Looney Tunes",
                                "director": "Unknown",
                                "director_credit": "Unknown",
                                "directors": [],
                                "director_aliases": [],
                                "featured_characters": [],
                                "media_entry": {
                                    "set_name": f"The Golden Age of Looney Tunes: Volume {vol_num}",
                                    "format": "LaserDisc",
                                    "disc_number": disc_num,
                                    "disc_title": side_title,
                                    "track_number": t_idx + 1,
                                    "audio_commentary": []
                                }
                            })
    return all_ld_shorts


def parse_collectors_choice():
    """
    Parses Looney Tunes Collector's Choice Volumes 1–4 from Wikipedia.
    Single-disc Blu-ray releases containing 20 to 25 shorts per volume plus bonus shorts.
    """
    page_title = "Looney_Tunes_Collector%27s_Choice"
    print(f"[+] Scraping {page_title} (Blu-ray Volumes 1–4)...")
    wikitext = ""
    local_cache = os.path.join(os.path.dirname(__file__), "scratch_choice.wiki")
    if os.path.exists(local_cache):
        with open(local_cache, "r", encoding="utf-8") as f:
            wikitext = f.read()
    else:
        url = WIKI_API + page_title + "&prop=wikitext&format=json"
        req = urllib.request.Request(url, headers={"User-Agent": "LooneyTunesMasterCatalog/2.0 (research@example.com)"})
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                wikitext = data.get("parse", {}).get("wikitext", {}).get("*", "")
        except Exception as e:
            print(f"[-] Error fetching Collector's Choice: {e}")
            return []

    if not wikitext:
        return []

    shorts = []
    sections = re.split(r"(==+[^=]+==+)", wikitext)
    current_vol = "Volume 1"

    for part in sections:
        header_m = re.match(r"==+\s*([^=]+?)\s*==+", part)
        if header_m:
            h = header_m.group(1).strip()
            if "Volume" in h:
                vm = re.search(r"Volume\s*(\d+)", h)
                if vm:
                    current_vol = f"Volume {vm.group(1)}"
            continue

        if '{|class="wikitable' in part:
            rows = part.split("|-")
            for r in rows:
                lines = [l.strip() for l in r.split("\n") if l.strip()]
                track_val = None
                title_raw = None
                year_val = None

                for l in lines:
                    if l.startswith("|") and not l.startswith("|-") and not l.startswith("|+"):
                        val = l[1:].strip()
                        tm = re.match(r"^(B?\d+)", val)
                        if tm and track_val is None:
                            track_val = tm.group(1)
                        elif "[[" in val and title_raw is None:
                            title_m = re.search(r"\[\[(?:[^|\]]+\|)?([^\]]+)\]\]", val)
                            if title_m:
                                title_raw = title_m.group(1).strip()
                            else:
                                title_raw = val.replace("''", "").strip()
                        elif re.match(r"^\d{4}$", val) and year_val is None:
                            year_val = int(val)

                if track_val and title_raw:
                    clean_t = re.sub(r"<[^>]+>", "", title_raw).replace("''", "").strip()
                    shorts.append({
                        "title": clean_t,
                        "year": year_val,
                        "series": "Looney Tunes",
                        "director": "Unknown",
                        "director_credit": "Unknown",
                        "directors": [],
                        "director_aliases": [],
                        "featured_characters": [],
                        "media_entry": {
                            "set_name": f"Looney Tunes Collector's Choice: {current_vol}",
                            "format": "Blu-ray",
                            "disc_number": 1,
                            "disc_title": f"Disc 1 ({current_vol})",
                            "track_number": int(track_val) if track_val.isdigit() else track_val,
                            "audio_commentary": []
                        }
                    })
    return shorts


def parse_collectors_vault():
    """
    Parses Looney Tunes Collector's Vault Volumes 1–3 from Wikipedia.
    Two-disc Blu-ray releases with 50+ cartoons per volume and audio commentaries.
    """
    page_title = "Looney_Tunes_Collector%27s_Vault"
    print(f"[+] Scraping {page_title} (Blu-ray Volumes 1–3)...")
    wikitext = ""
    local_cache = os.path.join(os.path.dirname(__file__), "scratch_vault.wiki")
    if os.path.exists(local_cache):
        with open(local_cache, "r", encoding="utf-8") as f:
            wikitext = f.read()
    else:
        url = WIKI_API + page_title + "&prop=wikitext&format=json"
        req = urllib.request.Request(url, headers={"User-Agent": "LooneyTunesMasterCatalog/2.0 (research@example.com)"})
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                wikitext = data.get("parse", {}).get("wikitext", {}).get("*", "")
        except Exception as e:
            print(f"[-] Error fetching Collector's Vault: {e}")
            return []

    if not wikitext:
        return []

    shorts = []
    sections = re.split(r"(==+[^=]+==+)", wikitext)
    current_vol = "Volume 1"
    current_disc = 1
    commentaries = {}

    # Pass 1: Extract all audio commentaries
    pass1_vol = "Volume 1"
    for part in sections:
        header_m = re.match(r"==+\s*([^=]+?)\s*==+", part)
        if header_m:
            h = header_m.group(1).strip()
            if "Volume" in h:
                vm = re.search(r"Volume\s*(\d+)", h)
                if vm:
                    pass1_vol = f"Volume {vm.group(1)}"
            continue

        if "Audio commentaries" in part:
            for comm_line in part.split("\n"):
                comm_m = re.search(r"\*+\s*(.+?)\s+on\s+(.+)", comm_line)
                if comm_m:
                    person = re.sub(r"\[\[(?:[^|\]]+\|)?([^\]]+)\]\]", r"\1", comm_m.group(1)).strip()
                    short_titles = [re.sub(r"\[\[(?:[^|\]]+\|)?([^\]]+)\]\]", r"\1", t).strip("'\" ")
                                    for t in re.findall(r"\[\[(?:[^|\]]+\|)?([^\]]+)\]\]", comm_m.group(2))]
                    for st in short_titles:
                        commentaries.setdefault((pass1_vol, st.lower()), []).append(person)

    # Pass 2: Extract shorts and attach commentaries
    for part in sections:
        header_m = re.match(r"==+\s*([^=]+?)\s*==+", part)
        if header_m:
            h = header_m.group(1).strip()
            if "Volume" in h:
                vm = re.search(r"Volume\s*(\d+)", h)
                if vm:
                    current_vol = f"Volume {vm.group(1)}"
                current_disc = 1
            elif "Disc" in h:
                dm = re.search(r"Disc\s*(\d+)", h)
                if dm:
                    current_disc = int(dm.group(1))
            continue

        if '{|class="wikitable' in part:
            rows = part.split("|-")
            for r in rows:
                lines = [l.strip() for l in r.split("\n") if l.strip()]
                track_val = None
                title_raw = None
                year_val = None

                for l in lines:
                    if l.startswith("|") and not l.startswith("|-") and not l.startswith("|+"):
                        val = l[1:].strip()
                        tm = re.match(r"^(B?\d+)", val)
                        if tm and track_val is None:
                            track_val = tm.group(1)
                        elif "[[" in val and title_raw is None:
                            title_m = re.search(r"\[\[(?:[^|\]]+\|)?([^\]]+)\]\]", val)
                            if title_m:
                                title_raw = title_m.group(1).strip()
                            else:
                                title_raw = val.replace("''", "").strip()
                        elif re.match(r"^\d{4}$", val) and year_val is None:
                            year_val = int(val)

                if track_val and title_raw:
                    clean_t = re.sub(r"<[^>]+>", "", title_raw).replace("''", "").strip()
                    comm_list = commentaries.get((current_vol, clean_t.lower()), [])
                    shorts.append({
                        "title": clean_t,
                        "year": year_val,
                        "series": "Looney Tunes",
                        "director": "Unknown",
                        "director_credit": "Unknown",
                        "directors": [],
                        "director_aliases": [],
                        "featured_characters": [],
                        "media_entry": {
                            "set_name": f"Looney Tunes Collector's Vault: {current_vol}",
                            "format": "Blu-ray",
                            "disc_number": current_disc,
                            "disc_title": f"Disc {current_disc}",
                            "track_number": int(track_val) if track_val.isdigit() else track_val,
                            "audio_commentary": comm_list
                        }
                    })
    return shorts


def parse_super_stars():
    """
    Parses the 8 Looney Tunes Super Stars DVD releases from Wikipedia:
    1. Bugs Bunny: Hare Extraordinaire
    2. Daffy Duck: Frustrated Fowl
    3. Foghorn Leghorn & Friends: Barnyard Bigmouth
    4. Tweety & Sylvester: Feline Fwenzy
    5. Road Runner & Wile E. Coyote: Supergenius Hijinks
    6. Pepé Le Pew: Zee Best of Zee Best
    7. Porky & Friends: Hilarious Ham
    8. Sylvester & Hippety Hopper: Marsupial Mayhem
    """
    print("[+] Scraping Looney Tunes Super Stars (8 DVD Releases)...")
    base_dir = os.path.dirname(__file__)

    def extract_title(val):
        m = re.search(r'\[\[(?:[^|\]]+\|)?([^\]]+)\]\]', val)
        if m:
            return m.group(1).strip()
        val = re.sub(r'<ref[^>]*>.*?</ref>', '', val, flags=re.DOTALL)
        val = re.sub(r'\{\{.*?\}\}', '', val)
        return val.replace("''", '').strip(' *^|')

    def parse_table_lines(text, set_name):
        entries = []
        if '{|class="wikitable' in text:
            table_part = text[text.find('{|class="wikitable'):]
            if '|}' in table_part:
                table_part = table_part[:table_part.find('|}')+2]
            rows = table_part.split('|-')
            for r in rows:
                lines = [l.strip() for l in r.split('\n') if l.strip()]
                track = None
                title = None
                year = None
                for l in lines:
                    if l.startswith('|') and not l.startswith('|-') and not l.startswith('|+'):
                        val = l[1:].strip()
                        tm = re.match(r'^(B?\d+)', val)
                        if tm and track is None:
                            track = tm.group(1)
                        elif '[[' in val and title is None:
                            title = extract_title(val)
                        elif re.match(r'^\d{4}$', val) and year is None:
                            year = int(val)
                if track and title:
                    entries.append({
                        'title': title,
                        'year': year,
                        'series': 'Looney Tunes',
                        'director': 'Unknown',
                        'director_credit': 'Unknown',
                        'directors': [],
                        'director_aliases': [],
                        'featured_characters': [],
                        'media_entry': {
                            'set_name': set_name,
                            'format': 'DVD',
                            'disc_number': 1,
                            'disc_title': 'Disc 1',
                            'track_number': int(track) if track.isdigit() else track,
                            'audio_commentary': []
                        }
                    })
        return entries

    all_ss = []

    # 1. Hare Extraordinaire
    f1 = os.path.join(base_dir, "scratch_hare_extraordinaire.wiki")
    if os.path.exists(f1):
        with open(f1, "r", encoding="utf-8") as f:
            all_ss.extend(parse_table_lines(f.read(), "Looney Tunes Super Stars: Bugs Bunny: Hare Extraordinaire"))

    # 2. Frustrated Fowl
    f2 = os.path.join(base_dir, "scratch_frustrated_fowl.wiki")
    if os.path.exists(f2):
        with open(f2, "r", encoding="utf-8") as f:
            all_ss.extend(parse_table_lines(f.read(), "Looney Tunes Super Stars: Daffy Duck: Frustrated Fowl"))

    # 3-8 from scratch_superstars.wiki
    fs = os.path.join(base_dir, "scratch_superstars.wiki")
    if os.path.exists(fs):
        with open(fs, "r", encoding="utf-8") as f:
            ts = f.read()
        remaining = [
            ("Foghorn Leghorn & Friends: Barnyard Bigmouth", "Looney Tunes Super Stars: Foghorn Leghorn & Friends: Barnyard Bigmouth"),
            ("Tweety & Sylvester: Feline Fwenzy", "Looney Tunes Super Stars: Tweety & Sylvester: Feline Fwenzy"),
            ("Road Runner & Wile E. Coyote: Supergenius Hijinks", "Looney Tunes Super Stars: Road Runner & Wile E. Coyote: Supergenius Hijinks"),
            ("Pepé Le Pew: Zee Best of Zee Best", "Looney Tunes Super Stars: Pepé Le Pew: Zee Best of Zee Best"),
            ("Porky & Friends: Hilarious Ham", "Looney Tunes Super Stars: Porky & Friends: Hilarious Ham"),
            ("Sylvester & Hippety Hopper: Marsupial Mayhem", "Looney Tunes Super Stars: Sylvester & Hippety Hopper: Marsupial Mayhem")
        ]
        sections = re.split(r"(==+\s*''[^']+''\s*==+)", ts)
        for i in range(1, len(sections), 2):
            raw_h = sections[i]
            content = sections[i+1]
            hm = re.search(r"''([^']+)''", raw_h)
            if not hm: continue
            sname = hm.group(1).strip()
            for key, formal_title in remaining:
                if key.lower() in sname.lower():
                    all_ss.extend(parse_table_lines(content, formal_title))

    return all_ss


def merge_into_master(master_db: dict, items: list):
    for item in items:
        title = item.get("title", "").strip()
        if not title:
            continue
        slug = slugify(title)
        if not slug:
            continue

        if slug not in master_db:
            # Check without apostrophes
            alt_slug = slugify(re.sub(r"['’]", "", title))
            if alt_slug in master_db:
                slug = alt_slug
            else:
                for s_key, s_val in master_db.items():
                    if s_val["title"].lower() == title.lower() or re.sub(r"['’]", "", s_val["title"].lower()) == re.sub(r"['’]", "", title.lower()):
                        slug = s_key
                        break

        if slug not in master_db:
            # Skip modern/post-1969 shorts that have only secondary media entries
            if "media_entry" in item:
                continue

        if slug not in master_db:
            master_db[slug] = {
                "id": slug,
                "title": title,
                "year": item.get("year"),
                "release_date": item.get("release_date", ""),
                "series": item.get("series", "Looney Tunes"),
                "director": item.get("director", "Unknown"),
                "director_credit": item.get("director_credit", item.get("director", "Unknown")),
                "directors": item.get("directors", [item.get("director", "Unknown")]),
                "director_aliases": item.get("director_aliases", []),
                "story": item.get("story", "—"),
                "layout": item.get("layout", "—"),
                "backgrounds": item.get("backgrounds", "—"),
                "animation": item.get("animation", []),
                "voice_actors": item.get("voice_actors", []),
                "featured_characters": item.get("featured_characters", []),
                "synopsis": item.get("synopsis", ""),
                "media_locations": []
            }
        else:
            rec = master_db[slug]
            if not rec.get("year") and item.get("year"):
                rec["year"] = item["year"]
            if not rec.get("release_date") and item.get("release_date"):
                rec["release_date"] = item["release_date"]
            if rec.get("director") in ["Unknown", "N/A", ""] and item.get("director") not in ["Unknown", "N/A", ""]:
                rec["director"] = item["director"]
                rec["director_credit"] = item.get("director_credit", item["director"])
                rec["directors"] = item.get("directors", [item["director"]])
                rec["director_aliases"] = item.get("director_aliases", [])
            elif item.get("director_credit") and ("Co-Director" in item["director_credit"] or "&" in item["director_credit"]):
                rec["director_credit"] = item["director_credit"]
                if item.get("directors"):
                    rec["directors"] = item["directors"]
            if not rec.get("synopsis") and item.get("synopsis"):
                rec["synopsis"] = item["synopsis"]
            if not rec.get("animation") and item.get("animation"):
                rec["animation"] = item["animation"]

        # Merge characters: master filmography is authoritative; only use collection characters as fallback if empty
        if item.get("featured_characters"):
            if not master_db[slug]["featured_characters"]:
                for c in item["featured_characters"]:
                    if c not in DIRECTOR_MAP and c not in ["None", "—", "-", "N/A"] and c not in master_db[slug]["featured_characters"]:
                        master_db[slug]["featured_characters"].append(c)

        # Merge media entry
        if "media_entry" in item:
            entry = item["media_entry"]
            exists = any(
                m.get("set_name") == entry.get("set_name") and
                m.get("disc_number") == entry.get("disc_number") and
                m.get("track_number") == entry.get("track_number")
                for m in master_db[slug]["media_locations"]
            )
            if not exists:
                master_db[slug]["media_locations"].append(entry)


def main():
    print("=" * 70)
    print("🎬 Looney Tunes Complete Filmography & Home Media Compiler")
    print("=" * 70)

    master_db = {}

    # 1. Master Filmographies across all four golden age decades (1,002 theatrical shorts)
    decades = [
        "Looney_Tunes_and_Merrie_Melodies_filmography_(1929–1939)",
        "Looney_Tunes_and_Merrie_Melodies_filmography_(1940–1949)",
        "Looney_Tunes_and_Merrie_Melodies_filmography_(1950–1959)",
        "Looney_Tunes_and_Merrie_Melodies_filmography_(1960–1969)"
    ]
    for d in decades:
        shorts = parse_master_decade(d)
        print(f"   ✓ Ingested {len(shorts)} theatrical shorts from {d}")
        merge_into_master(master_db, shorts)
        time.sleep(0.3)

    print(f"\n[+] Master filmography baseline: {len(master_db)} theatrical shorts.")

    # 2. Porky Pig 101
    porky = parse_porky_pig_101()
    print(f"   ✓ Extracted {len(porky)} shorts from Porky Pig 101")
    merge_into_master(master_db, porky)
    time.sleep(0.3)

    # 3. Golden Collection Volumes 1-6
    for vol in range(1, 7):
        gc = parse_golden_collection_volume(vol)
        print(f"   ✓ Extracted {len(gc)} shorts from Golden Collection Vol {vol}")
        merge_into_master(master_db, gc)
        time.sleep(0.3)

    # 4. Platinum Collection Volumes 1-3
    for vol in range(1, 4):
        plat = parse_platinum_collection_volume(vol)
        print(f"   ✓ Extracted {len(plat)} shorts from Platinum Collection Vol {vol}")
        merge_into_master(master_db, plat)
        time.sleep(0.3)

    # 5. LaserDisc Volumes 1-5 (All 330+ LaserDisc tracks)
    ld_shorts = parse_all_golden_age_laserdiscs()
    print(f"   ✓ Extracted {len(ld_shorts)} LaserDisc tracks across Volumes 1–5")
    merge_into_master(master_db, ld_shorts)

    # 6. Collector's Choice Volumes 1–4 (Blu-ray)
    choice_shorts = parse_collectors_choice()
    print(f"   ✓ Extracted {len(choice_shorts)} shorts from Collector's Choice Volumes 1–4")
    merge_into_master(master_db, choice_shorts)

    # 7. Collector's Vault Volumes 1–3 (Blu-ray)
    vault_shorts = parse_collectors_vault()
    print(f"   ✓ Extracted {len(vault_shorts)} shorts from Collector's Vault Volumes 1–3")
    merge_into_master(master_db, vault_shorts)

    # 8. Looney Tunes Super Stars (8 DVD Releases)
    superstars_shorts = parse_super_stars()
    print(f"   ✓ Extracted {len(superstars_shorts)} shorts from Looney Tunes Super Stars (8 DVD Sets)")
    merge_into_master(master_db, superstars_shorts)

    # 9. Apply manual user overrides (preserves custom edits like added characters)
    base_dir = os.path.dirname(__file__)
    overrides_path = os.path.join(base_dir, "custom_overrides.json")
    if os.path.exists(overrides_path):
        try:
            with open(overrides_path, "r", encoding="utf-8") as f:
                overrides = json.load(f)
            applied_count = 0
            for slug_or_id, fields in overrides.items():
                target_slug = slugify(slug_or_id)
                if target_slug in master_db:
                    master_db[target_slug].update(fields)
                    applied_count += 1
                else:
                    for rec in master_db.values():
                        if rec["title"].lower() == slug_or_id.lower() or rec.get("id") == slug_or_id:
                            rec.update(fields)
                            applied_count += 1
                            break
            print(f"\n[+] Applied {applied_count} manual overrides from custom_overrides.json")
        except Exception as e:
            print(f"[-] Warning: Failed to apply custom_overrides.json: {e}")

    final_list = [x for x in master_db.values() if x.get("title") and x.get("title").strip()]
    final_list.sort(key=lambda x: (x.get("year") or 9999, x["title"]))
    print(f"\n[★] FINAL TOTAL: {len(final_list)} unique Looney Tunes cartoons compiled!")

    base_dir = os.path.dirname(__file__)
    json_path = os.path.join(base_dir, "database.json")
    js_path = os.path.join(base_dir, "database.js")

    print(f"[+] Writing JSON to: {json_path}")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(final_list, f, indent=2, ensure_ascii=False)

    print(f"[+] Writing JS to:   {js_path}")
    with open(js_path, "w", encoding="utf-8") as f:
        f.write("window.LOONEY_TUNES_DATABASE = " + json.dumps(final_list, indent=2, ensure_ascii=False) + ";\n")

    print("\n[✓] All files updated successfully!")


if __name__ == "__main__":
    main()
