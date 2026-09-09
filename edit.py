#!/usr/bin/env python3
"""
Looney Tunes Catalog Terminal Editor CLI
----------------------------------------
Quick command-line tool to view and manually edit any cartoon entry.
Automatically updates custom_overrides.json, database.json, and database.js.

Usage:
  python3 edit.py "Bully for Bugs" --add-character "Toro the Bull"
  python3 edit.py "Bully for Bugs" --show
  python3 edit.py "Bully for Bugs" --interactive
  python3 edit.py --list-overrides
"""

import argparse
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_JSON_PATH = os.path.join(BASE_DIR, 'database.json')
DB_JS_PATH = os.path.join(BASE_DIR, 'database.js')
OVERRIDES_PATH = os.path.join(BASE_DIR, 'custom_overrides.json')

def load_data():
    with open(DB_JSON_PATH, 'r', encoding='utf-8') as f:
        db = json.load(f)
    overrides = {}
    if os.path.exists(OVERRIDES_PATH):
        with open(OVERRIDES_PATH, 'r', encoding='utf-8') as f:
            overrides = json.load(f)
    return db, overrides

def save_all(database, overrides):
    with open(OVERRIDES_PATH, 'w', encoding='utf-8') as f:
        json.dump(overrides, f, indent=2, ensure_ascii=False)
        f.write('\n')
    with open(DB_JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(database, f, indent=2, ensure_ascii=False)
        f.write('\n')
    with open(DB_JS_PATH, 'w', encoding='utf-8') as f:
        f.write('window.LOONEY_TUNES_DATABASE = ' + json.dumps(database, indent=2, ensure_ascii=False) + ';\n')

import unicodedata

def normalize_text(s):
    if not s:
        return ''
    return ''.join(c for c in unicodedata.normalize('NFD', str(s)) if unicodedata.category(c) != 'Mn').lower()

def find_cartoon(query, db):
    q = normalize_text(query).strip()
    # Exact match on id or normalized title
    for c in db:
        if c.get('id') == q or normalize_text(c.get('title', '')) == q:
            return c
    # Substring match on normalized title or id
    matches = [c for c in db if q in normalize_text(c.get('title', '')) or q in normalize_text(c.get('id', ''))]
    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        print(f'Multiple matches found for "{query}":')
        for i, m in enumerate(matches, 1):
            print(f'  [{i}] {m.get("title")} ({m.get("year")}) [id: {m.get("id")}]')
        idx = input('Select number (or Enter to cancel): ').strip()
        if idx.isdigit() and 1 <= int(idx) <= len(matches):
            return matches[int(idx) - 1]
    return None

def main():
    parser = argparse.ArgumentParser(description='Edit Looney Tunes cartoon entries')
    parser.add_argument('query', nargs='?', help='Cartoon title or ID to search for')
    parser.add_argument('--add-character', help='Add a character to featured_characters')
    parser.add_argument('--remove-character', help='Remove a character from featured_characters')
    parser.add_argument('--set-director', help='Set director')
    parser.add_argument('--set-release-date', help='Set theatrical release date (e.g. "August 8, 1953")')
    parser.add_argument('--set-story', help='Set story / writer')
    parser.add_argument('--set-synopsis', help='Set synopsis')
    parser.add_argument('--show', action='store_true', help='Display cartoon details')
    parser.add_argument('--list-overrides', action='store_true', help='List all manual overrides')
    parser.add_argument('--interactive', action='store_true', help='Interactive prompt editor')
    args = parser.parse_args()

    db, overrides = load_data()

    if args.list_overrides:
        print(f'=== Custom Overrides ({len(overrides)}) ===')
        print(json.dumps(overrides, indent=2))
        return

    if not args.query:
        parser.print_help()
        return

    c = find_cartoon(args.query, db)
    if not c:
        print(f'[-] No cartoon found matching "{args.query}"')
        return

    cid = c['id']
    target_override = overrides.setdefault(cid, {})
    modified = False

    if args.add_character:
        chars = c.setdefault('featured_characters', [])
        if args.add_character not in chars:
            chars.append(args.add_character)
            target_override['featured_characters'] = chars
            modified = True
            print(f'[✓] Added character "{args.add_character}" to "{c["title"]}"')

    if args.remove_character:
        chars = c.get('featured_characters', [])
        if args.remove_character in chars:
            chars.remove(args.remove_character)
            target_override['featured_characters'] = chars
            modified = True
            print(f'[✓] Removed character "{args.remove_character}" from "{c["title"]}"')

    if args.set_director:
        c['director'] = args.set_director
        c['director_credit'] = args.set_director
        target_override['director'] = args.set_director
        target_override['director_credit'] = args.set_director
        modified = True

    if args.set_release_date:
        c['release_date'] = args.set_release_date
        target_override['release_date'] = args.set_release_date
        modified = True

    if args.set_story:
        c['story'] = args.set_story
        target_override['story'] = args.set_story
        modified = True

    if args.set_synopsis:
        c['synopsis'] = args.set_synopsis
        target_override['synopsis'] = args.set_synopsis
        modified = True

    if args.interactive:
        print(f'\nEditing: {c["title"]} ({c.get("year")})')
        print('Leave empty to keep current value.\n')
        
        new_title = input(f'Title [{c.get("title")}]: ').strip()
        if new_title:
            c['title'] = new_title
            target_override['title'] = new_title
            modified = True

        new_rel = input(f'Release Date [{c.get("release_date")}]: ').strip()
        if new_rel:
            c['release_date'] = new_rel
            target_override['release_date'] = new_rel
            modified = True

        current_chars = ", ".join(c.get("featured_characters", []))
        new_chars = input(f'Featured Characters (comma separated) [{current_chars}]: ').strip()
        if new_chars:
            chars = [x.strip() for x in new_chars.split(',') if x.strip()]
            c['featured_characters'] = chars
            target_override['featured_characters'] = chars
            modified = True

        new_dir = input(f'Director [{c.get("director_credit") or c.get("director")}]: ').strip()
        if new_dir:
            c['director'] = new_dir
            c['director_credit'] = new_dir
            target_override['director'] = new_dir
            target_override['director_credit'] = new_dir
            modified = True

        new_story = input(f'Story [{c.get("story")}]: ').strip()
        if new_story:
            c['story'] = new_story
            target_override['story'] = new_story
            modified = True

        new_synopsis = input(f'Synopsis [{c.get("synopsis")}]: ').strip()
        if new_synopsis:
            c['synopsis'] = new_synopsis
            target_override['synopsis'] = new_synopsis
            modified = True

    if modified:
        save_all(db, overrides)
        print('[✓] Saved changes to database.json, database.js, and custom_overrides.json!')

    if args.show or not modified:
        print(f'\n🎬 {c.get("title")} ({c.get("year")}) - {c.get("series")}')
        print(f'  Release Date: {c.get("release_date")}')
        print(f'  Director:   {c.get("director_credit") or c.get("director")}')
        print(f'  Characters: {c.get("featured_characters")}')
        print(f'  Story:      {c.get("story")}')
        print(f'  Animators:  {c.get("animation")}')
        print(f'  Synopsis:   {c.get("synopsis")}')
        if cid in overrides:
            print(f'  [★ Manual Overrides]: {json.dumps(overrides[cid])}')

if __name__ == '__main__':
    main()
