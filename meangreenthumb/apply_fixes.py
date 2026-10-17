import os

print("Applying review fixes...")

# 1. suggestions.html
path = "app/templates/suggestions.html"
if os.path.exists(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    text = text.replace('placeholder="e.g., Tomato, Basil"', 'placeholder="Search by plant name"')
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

# 2. test_sudip_features.py
path = "tests/test_sudip_features.py"
if os.path.exists(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    text = text.replace('assert html_time.index("April - June") < html_time.index("March - May")', 'assert html_time.index("March - May") < html_time.index("April - June")')
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

# 3. zone_lookup.py
path = "app/services/zone_lookup.py"
if os.path.exists(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    text = text.replace('# Reserved invalid / non-existent test ranges (000xx, 999xx)', '# 000xx is not assigned to any US location')
    text = text.replace('if cleaned.startswith("000") or cleaned.startswith("999"):', 'if cleaned.startswith("000"):')
    text = text.replace('TIMEOUT = 4', 'TIMEOUT = 2')
    text = text.replace('with a comprehensive local fallback table and prefix mapping so lookups succeed', 'with a comprehensive local fallback table so lookups succeed')
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

# 4. admin_plants.html
path = "app/templates/admin_plants.html"
if os.path.exists(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    old_str = 'action="{{ url_for(\'admin.remove_plant\', plant_id=plant.plant_id) }}" style="margin: 0;">'
    new_str = 'action="{{ url_for(\'admin.remove_plant\', plant_id=plant.plant_id) }}" style="margin: 0;"\n      onsubmit="return confirm(\'Remove this plant from the catalog?\');">'
    text = text.replace(old_str, new_str)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

# 5. plants.py
path = "app/routes/plants.py"
if os.path.exists(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    sorting_func = """
def first_planting_month(recommended_time: str | None) -> int:
    \"\"\"Return the month number (1-12) of the earliest month named in the
    planting-time text, or 13 if none is named (sorts those last).\"\"\"
    text = (recommended_time or "").lower()
    hits = [(text.find(abbr), num) for abbr, num in _MONTH_ABBR_TO_NUM.items() if abbr in text]
    return min(hits)[1] if hits else 13
"""
    if "def first_planting_month" not in text:
        text = text.replace("def ensure_seed_catalog() -> None:", sorting_func + "\ndef ensure_seed_catalog() -> None:")
    text = text.replace(
        "matched_plants.sort(key=lambda p: ((p.recommended_planting_time or \"\").lower(), p.name.lower()))",
        "matched_plants.sort(key=lambda p: (first_planting_month(p.recommended_planting_time), p.name.lower()))"
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

# 6. admin.py
path = "app/routes/admin.py"
if os.path.exists(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    
    old_block = """    plant = Plant(
        name=name,
        description=description,
        recommended_planting_time=planting_time,
    )
    for code in zone_codes:
        zone = GrowingZone.query.filter_by(zone_code=code).first()
        if zone is None:
            zone = GrowingZone(zone_code=code)
            db.session.add(zone)
            db.session.flush()
        plant.zones.append(zone)

    db.session.add(plant)"""

    new_block = """    plant = Plant(
        name=name,
        description=description,
        recommended_planting_time=planting_time,
    )
    db.session.add(plant)
    for code in zone_codes:
        zone = GrowingZone.query.filter_by(zone_code=code).first()
        if zone is None:
            zone = GrowingZone(zone_code=code)
            db.session.add(zone)
            db.session.flush()
        plant.zones.append(zone)"""

    text = text.replace(old_block, new_block)
    text = text.replace("if target_user.user_id == current_user.user_id or target_user.is_admin:", "    # Alternative flow 3b: Cannot suspend own account or another administrator\n    if target_user.user_id == current_user.user_id or target_user.is_admin:")
    text = text.replace("if remove_tips:", "    # Main flow 4-6: Cascade delete tips if admin confirmed\n    if remove_tips:")

    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

print("All fixes applied successfully!")
