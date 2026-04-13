# Project Goal

Build a single local study webpage from the files inside the `data` folder.

This is a prototype test only.
Do NOT build a multi-level platform yet.
Do NOT build multiple pages yet.
Do NOT change the folder structure.
Use the existing files in `data/` exactly as they are.

# Available Data Files

- data/00_meta.txt
- data/01_intro.txt
- data/02_core.txt
- data/03_summary.txt
- data/04_full_script.txt
- data/05_wordcard.txt

# Required Output Files

Create these files in the project root:

- index.html
- style.css
- script.js

# Main Objective

Create one English study webpage that works locally in a browser.

The webpage must read and render the existing text files in `data/`.

# Page Structure

Build one single-page website with these sections:

1. Hero title area
2. Intro section
3. Tab navigation
4. Tab content areas

# Tabs Required

Create these tabs:

- Intro
- Core Sentences
- Summary
- Full Script
- Word Cards

# Detailed Requirements

## 1. General UI
- Clean, readable, modern layout
- Mobile-friendly
- Korean UI labels are allowed
- English study content must remain exactly from the data files
- Do not hardcode story content into HTML if it can be loaded from files
- Prefer loading from `data/*.txt` using JavaScript fetch

## 2. Intro Tab
- Show title from 00_meta.txt
- Show level from 00_meta.txt
- Show intro EN and KR from 01_intro.txt

## 3. Core Sentences Tab
- Parse 02_core.txt
- Display all 12 sentences
- Each item must show:
  - English sentence
  - Korean translation
  - English TTS button

## 4. Summary Tab
- Parse 03_summary.txt
- Display all 5 summary parts
- Each item must show:
  - English summary
  - Korean translation
  - English TTS button

## 5. Full Script Tab
- Parse 04_full_script.txt
- Display all paragraphs in order
- Each paragraph must show:
  - Paragraph number
  - English paragraph block
  - Korean paragraph block
  - One English TTS button per paragraph
- Do NOT split paragraph into sentence-level buttons
- This tab is the most important one

## 6. Word Cards Tab
- Parse 05_wordcard.txt
- Display all 10 word cards
- Each card must show:
  - headword
  - part_of_speech
  - meaning_kr
  - definition_en
  - definition_kr_literal
  - example_en
  - example_kr_literal
  - TTS button for headword
  - TTS button for example_en

## 7. TTS
- Use browser built-in speech synthesis
- TTS only for English text
- Add reusable JavaScript function for speaking text
- Buttons should be simple and stable

## 8. Parsing
- script.js must parse the txt files robustly
- Handle line-based structured text carefully
- Do not assume JSON
- Build parser functions for each file type if needed

## 9. Technical Constraints
- Plain HTML, CSS, JavaScript only
- No framework
- No build tool
- Must run locally with Live Server
- Must work in a plain browser environment

## 10. File Safety
- Do not modify files in `data/`
- Only create or update:
  - index.html
  - style.css
  - script.js

# Design Preference

- Large readable title
- Soft card-style content sections
- Easy tab switching
- Comfortable spacing
- Good readability for long paragraphs
- Make Full Script especially easy to read for shadowing practice

# Final Success Condition

The user can open `index.html` locally and:
- switch tabs,
- read all sections,
- see all data from 00~05,
- click TTS buttons,
- use the page as a shadowing study page.