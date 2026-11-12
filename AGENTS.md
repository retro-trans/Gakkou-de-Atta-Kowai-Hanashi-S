** Organize folder like this **
work - work folder
    output - contains the file for testing (iso, zip, etc...)
    glossary - contains the one or many json files for glossary
    ui - contains screenshot of actual UI element ingame with label on screenshot if possible, contains files (json,py,...) describe the coordinate, width and height, id and other attributes
    translation/<language code> - contains the target translation of ui element or dialogues or anything that need translation
docs - documents
tools - any tools help with translation
incoming - outside files that need agent to look into

** SOME RULES **
- Avoid contains extensive Japanese scripts (UI elements is fine)
- Identified each build with version 0.x.y (start at 0.1.0)
- Always write change log
- If user told you to remember anything write it down here, make sure to ask user if the new one conflict with old one
- Be conscious of subscription limit before creating sub-agents
- When using emulator turn the volume down to zero
- For console game: make sure the patch only modify things around real hardware boundary, if not sure document any change that could break the game when running on real hardware
- Keep only latest version output, the other versions keep as xdelta (dcp for dreamcast) but only at most 10 recent version

** REMEMBER **
- Follow the editorial-pass workflow in `BASE_RULES.md` for translated scripts: accuracy review, editorial review for clarity and character voice, then final proofreading.
- Build debug tool using `debug_tools_guide.md`
- Do not create or publish a GitHub release until the user explicitly requests a release for that build. Translation and local builds do not imply release permission.
- Japanese script text must never be committed to git. Keeping it in local working files is fine: `.gitignore` covers `work/source/` and the translation working files. Commit only the `*.en.json` copies written by `tools/strip_jp.py` (run it before committing). Names and UI terms in Japanese are allowed.
