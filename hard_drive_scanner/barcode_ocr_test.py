import argparse
from difflib import SequenceMatcher
import json
import re
import shutil
import subprocess
from pathlib import Path

import cv2

import database
import ocr_test_database


SCAN_ZONE_PATH = Path(__file__).with_name("scan_zones.json")


SCAN_ZONE_PRESETS = {
    "center_medium": {"x": 20, "y": 20, "width": 60, "height": 60},
    "center_wide": {"x": 10, "y": 15, "width": 80, "height": 70},
    "top_half": {"x": 0, "y": 0, "width": 100, "height": 55},
    "bottom_half": {"x": 0, "y": 45, "width": 100, "height": 55},
    "left_half": {"x": 0, "y": 0, "width": 55, "height": 100},
    "right_half": {"x": 45, "y": 0, "width": 55, "height": 100},
}


PROFILE_SCHEMES = {
    "dell_constellation_es": {
        "name": "Dell Constellation ES",
        "brand": "Dell / Seagate",
        "drive_type": "SAS",
        "fields": ["Model Number", "Part Number", "Serial Number", "Date Code", "WWN", "Firmware", "Config"],
        "required_fields": ["Serial Number", "Part Number"],
    },
    "dell_constellation_es3": {
        "name": "Dell Constellation ES.3",
        "brand": "Dell / Seagate",
        "drive_type": "SAS",
        "fields": ["Model Number", "Part Number", "Serial Number", "WWN", "Date Code", "Firmware", "Config"],
        "required_fields": ["Serial Number", "Part Number"],
    },
    "savvio": {
        "name": "Seagate Savvio",
        "brand": "Seagate",
        "drive_type": "SAS",
        "fields": ["Model Number", "Lot Number", "Part Number", "Serial Number", "Factory Number", "Firmware", "Config"],
        "required_fields": ["Lot Number", "Part Number", "Serial Number"],
    },
    "savvio_10k2": {
        "name": "Seagate Savvio 10K.2",
        "brand": "Seagate",
        "drive_type": "SAS",
        "fields": ["Model Number", "Lot Number", "Part Number", "Serial Number", "Factory Number", "Firmware", "Config"],
        "required_fields": ["Lot Number", "Part Number", "Serial Number"],
    },
    "savvio_15k1": {
        "name": "Seagate Savvio 15K.1",
        "brand": "Seagate",
        "drive_type": "SAS",
        "fields": ["Model Number", "Lot Number", "Part Number", "Serial Number", "Factory Number", "Firmware", "Config"],
        "required_fields": ["Lot Number", "Part Number", "Serial Number"],
    },
    "savvio_15k3": {
        "name": "Seagate Savvio 15K.3",
        "brand": "Seagate",
        "drive_type": "SAS",
        "fields": ["Model Number", "Lot Number", "Part Number", "Serial Number", "Factory Number", "Firmware", "Config"],
        "required_fields": ["Lot Number", "Part Number", "Serial Number"],
    },
    "hgst_oracle": {
        "name": "HGST Sun Oracle",
        "brand": "HGST / Sun Oracle",
        "drive_type": "SAS",
        "fields": ["Firmware", "Config", "Serial Number", "Model Number", "Part Number", "WWN"],
        "required_fields": ["Serial Number", "Part Number"],
    },
    "hitachi_oracle": {
        "name": "Hitachi Sun Oracle",
        "brand": "Hitachi / Sun Oracle",
        "drive_type": "SAS",
        "fields": ["Firmware", "Config", "Serial Number", "Model Number", "Part Number", "WWN"],
        "required_fields": ["Serial Number", "Part Number"],
    },
    "western_digital": {
        "name": "Western Digital",
        "brand": "Western Digital",
        "drive_type": "SAS",
        "fields": ["Model Number", "Serial Number", "Part Number", "WWN", "Date Code", "DCM", "Firmware", "Config"],
        "required_fields": ["Serial Number", "Model Number"],
    },
    "misc": {
        "name": "Miscellaneous / Other",
        "brand": "",
        "drive_type": "SAS",
        "fields": [
            "Model Number",
            "Serial Number",
            "Part Number",
            "Lot Number",
            "Factory Number",
            "Firmware",
            "Config",
            "WWN",
            "Date Code",
            "DCM",
            "Asset Tag",
            "Oracle/Sun Part Number",
        ],
        "required_fields": [],
    },
    "unknown": {
        "name": "Unknown / Manual",
        "brand": "",
        "drive_type": "SAS",
        "fields": [],
        "required_fields": [],
    },
}


PROFILE_RULES = {profile: set(scheme["fields"]) for profile, scheme in PROFILE_SCHEMES.items()}


KEYWORD_RULES = [
    ("Lot Number", ("LOT", "LOT NUMBER")),
    ("Part Number", ("PART", "PART NUMBER", "P/N", "PN ", "P N")),
    ("Serial Number", ("SERIAL", "SERIAL NUMBER", "S/N", "SN ", "S N")),
    ("Factory Number", ("FACTORY", "FACTORY NUMBER", "MFG", "MANUFACTURING")),
    ("Firmware", ("FIRMWARE", "FW", "F/W")),
    ("Config", ("CONFIG", "CONF")),
    ("Date Code", ("DATE", "DATE CODE", "DOM")),
    ("DCM", ("DCM",)),
    ("WWN", ("WWN", "WORLD WIDE", "WORLDWIDE")),
    ("Model Number", ("MODEL", "MODEL NUMBER")),
    ("Oracle/Sun Part Number", ("ORACLE", "SUN", "BASEPN", "BASE PN")),
]


MANUAL_BARCODE_TYPES = [
    "Lot Number",
    "Part Number",
    "Serial Number",
    "Factory Number",
    "Firmware",
    "Config",
    "Date Code",
    "DCM",
    "Model Number",
    "WWN",
    "Oracle/Sun Part Number",
    "Asset Tag",
    "Unknown",
]


def main():
    parser = argparse.ArgumentParser(
        description="Capture or load a drive label image, decode all barcodes, OCR nearby text, and suggest barcode types."
    )
    parser.add_argument(
        "--view",
        action="store_true",
        help="Show saved OCR test database results and exit.",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="With --view, show only the latest test run.",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run an interactive menu for repeated scans.",
    )
    parser.add_argument(
        "--image",
        help="Use an existing image instead of capturing a new one.",
    )
    parser.add_argument(
        "--profile",
        default="unknown",
        choices=sorted(PROFILE_RULES.keys()),
        help="Drive profile used to keep/ignore suggested barcode types.",
    )
    parser.add_argument(
        "--out",
        default="last_ocr_capture.jpg",
        help="Capture output image path when using the Pi camera.",
    )
    args = parser.parse_args()

    if args.interactive:
        interactive_loop()
        return

    if args.view:
        ocr_test_database.set_database_profile(args.profile)
        view_test_database(latest_only=args.latest)
        return

    ocr_test_database.set_database_profile(args.profile)
    image_path = Path(args.image) if args.image else capture_image(Path(args.out))
    if image_path is None:
        return

    image = cv2.imread(str(image_path))
    if image is None:
        print(f"Could not load image: {image_path}")
        return

    process_image(image, image_path, args.profile)


def process_image(image, image_path, profile):
    ocr_test_database.set_database_profile(profile)
    ocr_test_database.create_tables()
    run_id = ocr_test_database.add_test_run(profile, image_path)

    print(f"Image: {image_path}")
    print(f"Profile: {profile}")
    print(f"Database: {ocr_test_database.current_database_path().name}")
    print(f"Test run ID: {run_id}")

    raw_barcodes = decode_barcodes_for_profile(image, profile)
    print(f"Raw barcode hits before cleanup: {len(raw_barcodes)}")
    barcodes = dedupe_and_sort_barcodes(raw_barcodes)
    if not barcodes:
        print("No barcodes decoded.")
        ocr_test_database.add_test_result(
            run_id=run_id,
            barcode_value="",
            barcode_format="",
            barcode_type_suggested="",
            nearby_ocr_text="",
            profile_decision="NO BARCODE",
            match_status="NO BARCODE",
            crop_path="",
        )
        return run_id

    allowed_types = PROFILE_RULES[profile]
    print(f"Decoded {len(barcodes)} barcode(s).\n")

    barcodes = apply_profile_fallbacks(barcodes, profile)

    saved_results = []
    for index, barcode in enumerate(barcodes, start=1):
        crop_source = barcode.get("source_image", image)
        nearby_crop = crop_near_barcode(crop_source, barcode["rect"])
        crop_path = Path(f"ocr_crop_{index}.jpg")
        cv2.imwrite(str(crop_path), nearby_crop)

        ocr_text = read_text(nearby_crop)
        suggested_type = barcode.get("profile_type") or classify_barcode(barcode["value"], ocr_text)
        profile_decision = decide_profile_action(suggested_type, allowed_types, profile)
        match_status = compare_barcode_to_ocr(barcode["value"], ocr_text)

        ocr_test_database.add_test_result(
            run_id=run_id,
            barcode_value=barcode["value"],
            barcode_format=barcode["format"],
            barcode_type_suggested=suggested_type,
            nearby_ocr_text=ocr_text,
            profile_decision=profile_decision,
            match_status=match_status,
            crop_path=crop_path,
        )
        saved_results.append(
            {
                "value": barcode["value"],
                "type": suggested_type,
                "decision": profile_decision,
                "match": match_status,
            }
        )

        print(f"Barcode {index}")
        print(f"  value: {barcode['value']}")
        print(f"  format: {barcode['format']}")
        print(f"  orientation: {barcode.get('orientation', 'normal')}")
        print(f"  rect: {barcode['rect']}")
        print(f"  nearby OCR: {ocr_text or '[none]'}")
        print(f"  suggested type: {suggested_type}")
        print(f"  profile decision: {profile_decision}")
        print(f"  match status: {match_status}")
        print(f"  crop saved: {crop_path}")
        print()

    print_summary(saved_results)
    return run_id


def interactive_loop():
    profile = "unknown"
    ocr_test_database.set_database_profile(profile)

    while True:
        print("\nBarcode OCR Test")
        print(f"Current profile: {profile}")
        print(f"Current database: {ocr_test_database.current_database_path().name}")
        print("1. Choose profile")
        print("2. Capture and scan")
        print("3. Scan existing image")
        print("4. View latest result")
        print("5. View all results")
        print("6. Set scan zone")
        print("7. Clear scan zone")
        print("8. Exit")

        choice = input("Choose an option: ").strip()

        if choice == "1":
            profile = choose_profile()
            ocr_test_database.set_database_profile(profile)
        elif choice == "2":
            ocr_test_database.set_database_profile(profile)
            run_scan_review_loop(profile=profile)
        elif choice == "3":
            image_path = input("Image path: ").strip()
            if image_path:
                ocr_test_database.set_database_profile(profile)
                run_scan_review_loop(profile=profile, image_path=Path(image_path))
        elif choice == "4":
            ocr_test_database.set_database_profile(profile)
            view_test_database(latest_only=True)
        elif choice == "5":
            ocr_test_database.set_database_profile(profile)
            view_test_database(latest_only=False)
        elif choice == "6":
            set_scan_zone_for_profile(profile)
        elif choice == "7":
            clear_scan_zone_for_profile(profile)
        elif choice == "8":
            break
        else:
            print("Invalid option.")


def choose_profile():
    profiles = sorted(PROFILE_RULES.keys())
    print("\nProfiles")
    for index, profile in enumerate(profiles, start=1):
        print(f"{index}. {profile}")

    choice = input("Choose profile: ").strip()
    if not choice.isdigit():
        print("Keeping current/default profile.")
        return "unknown"

    index = int(choice)
    if index < 1 or index > len(profiles):
        print("Keeping current/default profile.")
        return "unknown"

    return profiles[index - 1]


def set_scan_zone_for_profile(profile):
    print(f"\nSet scan zone for profile: {profile}")
    print("The scan zone is a percent-based crop of the camera image.")
    print("Use the preset that best covers the magnifying-glass sweet spot.")
    presets = list(SCAN_ZONE_PRESETS.items())
    for index, (name, zone) in enumerate(presets, start=1):
        print(
            f"{index}. {name} "
            f"(x={zone['x']}%, y={zone['y']}%, width={zone['width']}%, height={zone['height']}%)"
        )
    print(f"{len(presets) + 1}. Custom percent crop")
    print("0. Cancel")

    choice = input("Choose scan zone: ").strip()
    if choice in {"", "0"}:
        return
    if not choice.isdigit():
        print("Invalid option.")
        return

    index = int(choice)
    if 1 <= index <= len(presets):
        zone = dict(presets[index - 1][1])
    elif index == len(presets) + 1:
        zone = prompt_custom_scan_zone()
        if zone is None:
            return
    else:
        print("Invalid option.")
        return

    zones = load_scan_zones()
    zones[profile] = zone
    save_scan_zones(zones)
    print(
        f"Saved scan zone for {profile}: "
        f"x={zone['x']}%, y={zone['y']}%, width={zone['width']}%, height={zone['height']}%"
    )


def prompt_custom_scan_zone():
    try:
        x = int(input("x percent from left (0-100): ").strip())
        y = int(input("y percent from top (0-100): ").strip())
        width = int(input("width percent (1-100): ").strip())
        height = int(input("height percent (1-100): ").strip())
    except ValueError:
        print("Custom crop values must be numbers.")
        return None

    if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > 100 or y + height > 100:
        print("Invalid crop. Make sure x+width and y+height are not over 100.")
        return None

    return {"x": x, "y": y, "width": width, "height": height}


def clear_scan_zone_for_profile(profile):
    zones = load_scan_zones()
    if profile not in zones:
        print(f"No scan zone saved for {profile}.")
        return

    del zones[profile]
    save_scan_zones(zones)
    print(f"Cleared scan zone for {profile}.")


def load_scan_zones():
    if not SCAN_ZONE_PATH.exists():
        return {}

    try:
        return json.loads(SCAN_ZONE_PATH.read_text())
    except Exception:
        return {}


def save_scan_zones(zones):
    SCAN_ZONE_PATH.write_text(json.dumps(zones, indent=2, sort_keys=True))


def run_scan(profile, image_path=None):
    image_path = image_path if image_path else capture_image(Path("last_ocr_capture.jpg"))
    if image_path is None:
        return

    image = cv2.imread(str(image_path))
    if image is None:
        print(f"Could not load image: {image_path}")
        return

    return process_image(image, image_path, profile)


def run_scan_review_loop(profile, image_path=None):
    while True:
        run_id = run_scan(profile=profile, image_path=image_path)
        if run_id is None:
            return

        prompt_correct_result_types(run_id, profile)
        prompt_remove_bad_results(run_id)
        prompt_manual_missing_barcodes(run_id, profile)
        print_expected_field_checklist(run_id, profile)

        action = prompt_run_action(run_id)
        if action == "keep":
            prompt_save_run_to_inventory(run_id, profile)
            return

        ocr_test_database.delete_test_run(run_id)
        print(f"Deleted test run {run_id}.")

        if action == "delete":
            return

        image_path = None


def prompt_run_action(run_id):
    print("\nReview result")
    print(f"Current test run: {run_id}")
    print("k = keep this run")
    print("r = delete this run and retake")
    print("d = delete this run and stop")

    while True:
        choice = input("Choose k/r/d: ").strip().lower()
        if choice in {"", "k", "keep"}:
            return "keep"
        if choice in {"r", "retake"}:
            return "retake"
        if choice in {"d", "delete", "n", "no"}:
            return "delete"
        print("Invalid choice.")


def prompt_correct_result_types(run_id, profile):
    results = ocr_test_database.view_results_for_run(run_id)
    results = [result for result in results if result["barcode_value"]]
    if not results:
        return

    choice = input("Correct any scanned barcode type? (y/n): ").strip().lower()
    if choice != "y":
        return

    while True:
        print("\nScanned results")
        for index, result in enumerate(results, start=1):
            print(
                f"{index}. {result['barcode_value']} "
                f"[{result['barcode_type_suggested']}, {result['match_status']}]"
            )
        print("0. Done correcting")

        choice = input("Choose result to correct: ").strip()
        if choice in {"", "0"}:
            return
        if not choice.isdigit():
            print("Invalid result.")
            continue

        index = int(choice)
        if index < 1 or index > len(results):
            print("Invalid result.")
            continue

        selected = results[index - 1]
        new_type = choose_manual_barcode_type(profile)
        if new_type is None:
            continue

        allowed_types = PROFILE_RULES.get(profile, set())
        decision = decide_profile_action(new_type, allowed_types, profile)
        ocr_test_database.update_test_result_type(
            selected["result_id"],
            new_type,
            decision,
        )
        selected["barcode_type_suggested"] = new_type
        selected["profile_decision"] = decision
        print(f"Updated {selected['barcode_value']} to {new_type}.")


def prompt_remove_bad_results(run_id):
    while True:
        results = ocr_test_database.view_results_for_run(run_id)
        results = [result for result in results if result["barcode_value"]]
        if not results:
            return

        choice = input("Remove any bad/random scanned barcode? (y/n): ").strip().lower()
        if choice != "y":
            return

        print("\nScanned results")
        for index, result in enumerate(results, start=1):
            print(
                f"{index}. {result['barcode_value']} "
                f"[{result['barcode_type_suggested']}, {result['match_status']}]"
            )
        print("0. Done removing")

        choice = input("Choose result to remove: ").strip()
        if choice in {"", "0"}:
            return
        if not choice.isdigit():
            print("Invalid result.")
            continue

        index = int(choice)
        if index < 1 or index > len(results):
            print("Invalid result.")
            continue

        selected = results[index - 1]
        confirm = input(f"Remove {selected['barcode_value']}? (y/n): ").strip().lower()
        if confirm != "y":
            continue

        ocr_test_database.delete_test_result(selected["result_id"])
        print(f"Removed {selected['barcode_value']}.")


def prompt_manual_missing_barcodes(run_id, profile):
    choice = input("Add missing barcodes manually to this test run? (y/n): ").strip().lower()
    if choice != "y":
        return

    while True:
        barcode_type = choose_manual_barcode_type(profile)
        if barcode_type is None:
            return

        barcode_value = input(f"{barcode_type} value: ").strip().upper()
        if not barcode_value:
            print("No value entered.")
            continue

        save_manual_result(run_id, profile, barcode_value, barcode_type)
        another = input("Add another missing barcode? (y/n): ").strip().lower()
        if another != "y":
            return


def choose_manual_barcode_type(profile):
    allowed_types = PROFILE_SCHEMES.get(profile, PROFILE_SCHEMES["unknown"])["fields"]
    if allowed_types:
        barcode_types = allowed_types + ["Unknown"]
    else:
        barcode_types = MANUAL_BARCODE_TYPES

    print("\nManual barcode type")
    for index, barcode_type in enumerate(barcode_types, start=1):
        print(f"{index}. {barcode_type}")
    print("0. Cancel manual entry")

    choice = input("Choose barcode type: ").strip()
    if choice in {"0", ""}:
        return None
    if not choice.isdigit():
        print("Invalid type.")
        return None

    index = int(choice)
    if index < 1 or index > len(barcode_types):
        print("Invalid type.")
        return None

    return barcode_types[index - 1]


def save_manual_result(run_id, profile, barcode_value, barcode_type):
    allowed_types = PROFILE_RULES.get(profile, set())
    decision = decide_profile_action(barcode_type, allowed_types, profile)
    ocr_test_database.add_test_result(
        run_id=run_id,
        barcode_value=barcode_value,
        barcode_format="MANUAL",
        barcode_type_suggested=barcode_type,
        nearby_ocr_text="[manual entry]",
        profile_decision=decision,
        match_status="MANUAL ENTRY",
        crop_path="",
    )
    print(f"Added manual {barcode_type}: {barcode_value}")


def print_expected_field_checklist(run_id, profile):
    scheme = PROFILE_SCHEMES.get(profile, PROFILE_SCHEMES["unknown"])
    fields = scheme["fields"]
    required_fields = set(scheme.get("required_fields", []))
    results_by_type = group_run_results_by_type(run_id)

    print("\nExpected fields checklist")
    print(f"Profile: {scheme['name']}")
    if not fields:
        print("No fixed field scheme for this profile.")
        print_clean_results(run_id)
        return

    for field in fields:
        values = results_by_type.get(field, [])
        requirement = "REQUIRED" if field in required_fields else "optional"
        if values:
            print(f"{field}: FOUND {requirement} - {', '.join(values)}")
        elif field in required_fields:
            print(f"{field}: MISSING REQUIRED")
        else:
            print(f"{field}: missing optional")

    extra_types = sorted(set(results_by_type) - set(fields))
    for barcode_type in extra_types:
        values = results_by_type[barcode_type]
        print(f"{barcode_type}: EXTRA/REVIEW - {', '.join(values)}")


def print_clean_results(run_id):
    results = get_clean_run_results(run_id)
    if not results:
        print("No cleaned barcode values saved in this run.")
        return

    for result in results:
        print(f"{result['barcode_type_suggested']}: {result['barcode_value']}")


def group_run_results_by_type(run_id):
    results_by_type = {}
    for result in get_clean_run_results(run_id):
        barcode_type = result["barcode_type_suggested"] or "Unknown"
        results_by_type.setdefault(barcode_type, []).append(result["barcode_value"])
    return results_by_type


def get_clean_run_results(run_id):
    results = ocr_test_database.view_results_for_run(run_id)
    clean_results = []
    for result in results:
        barcode_value = (result["barcode_value"] or "").strip()
        if not barcode_value:
            continue
        if result["profile_decision"] == "NO BARCODE":
            continue
        clean_results.append(result)
    return clean_results


def prompt_save_run_to_inventory(run_id, profile):
    results = get_clean_run_results(run_id)
    if not results:
        print("Nothing to save to inventory.")
        return

    choice = input("Approve and save this cleaned run to hard_drive_inventory.db? (y/n): ").strip().lower()
    if choice != "y":
        return

    scheme = PROFILE_SCHEMES.get(profile, PROFILE_SCHEMES["unknown"])
    print("\nInventory drive info")
    brand = input_with_default("Brand", scheme["brand"])
    model = input_with_default("Model", first_value_for_type(results, "Model Number"))
    capacity = input("Capacity (example: 146GB): ").strip()
    drive_type = input_with_default("Drive type", scheme["drive_type"])
    notes_default = f"Imported from OCR test run {run_id} using profile {profile}"
    notes = input_with_default("Notes", notes_default)

    if not confirm_inventory_save(brand, model, capacity, drive_type, notes, results):
        print("Inventory save cancelled.")
        return

    database.create_tables()
    drive_id = database.add_drive(brand, model, capacity, drive_type, notes, profile=profile)
    print(f"Saved drive to inventory. New drive_id: {drive_id}")

    saved_count = 0
    duplicate_count = 0
    for result in results:
        barcode_type = result["barcode_type_suggested"] or "Unknown"
        barcode_value = result["barcode_value"]
        barcode_id = database.add_barcode(drive_id, barcode_value, barcode_type)
        if barcode_id:
            saved_count += 1
            print(f"Saved {barcode_type}: {barcode_value}")
        else:
            duplicate_count += 1
            print(f"Skipped duplicate {barcode_type}: {barcode_value}")

    print(f"Inventory save complete: {saved_count} saved, {duplicate_count} duplicate(s) skipped.")
    print_saved_inventory_drive(drive_id)


def confirm_inventory_save(brand, model, capacity, drive_type, notes, results):
    print("\nFinal inventory save preview")
    print(f"Brand: {brand}")
    print(f"Model: {model}")
    print(f"Capacity: {capacity}")
    print(f"Drive Type: {drive_type}")
    print(f"Notes: {notes}")
    print("Barcodes:")
    for result in results:
        barcode_type = result["barcode_type_suggested"] or "Unknown"
        barcode_value = result["barcode_value"]
        duplicate = database.search_by_barcode(barcode_value)
        if duplicate:
            print(
                f"  {barcode_type}: {barcode_value} "
                f"[already exists on drive_id {duplicate['drive_id']}]"
            )
        else:
            print(f"  {barcode_type}: {barcode_value}")

    choice = input("Confirm save to inventory? (y/n): ").strip().lower()
    return choice == "y"


def print_saved_inventory_drive(drive_id):
    print("\nSaved inventory record")
    for drive in database.view_all_drives():
        if drive["drive_id"] == drive_id:
            print(f"Drive ID: {drive['drive_id']}")
            print(f"Brand: {drive['brand']}")
            print(f"Model: {drive['model']}")
            print(f"Capacity: {drive['capacity']}")
            print(f"Drive Type: {drive['drive_type']}")
            print(f"Notes: {drive['notes']}")
            break

    barcodes = database.view_barcodes_for_drive(drive_id)
    if not barcodes:
        print("No barcodes saved for this drive.")
        return

    print("Barcodes:")
    for barcode in barcodes:
        print(f"  {barcode['barcode_type']}: {barcode['barcode_value']}")


def first_value_for_type(results, barcode_type):
    for result in results:
        if result["barcode_type_suggested"] == barcode_type:
            return result["barcode_value"]
    return ""


def input_with_default(label, default):
    if not default:
        return input(f"{label}: ").strip()

    value = input(f"{label} [{default}]: ").strip()
    return value or default


def capture_image(output_path):
    command = find_camera_command()
    if command is None:
        print("No rpicam-still or libcamera-still command found.")
        print("Pass an image instead, for example: python3 barcode_ocr_test.py --image last_pi_capture.jpg")
        return None

    print("Capturing image with Raspberry Pi camera...")
    try:
        subprocess.run(
            [
                command,
                "-o",
                str(output_path),
                "--width",
                "1920",
                "--height",
                "1080",
                "--timeout",
                "1000",
                "--nopreview",
            ],
            check=True,
            timeout=20,
        )
    except Exception as exc:
        print(f"Camera capture failed: {exc}")
        return None

    return output_path


def find_camera_command():
    for command in ("rpicam-still", "libcamera-still"):
        if shutil.which(command):
            return command
    return None


def decode_barcodes(image):
    found = []

    for barcode in decode_with_zxing(image):
        found.append(barcode)

    for barcode in decode_with_pyzbar(image):
        found.append(barcode)

    return found


def decode_barcodes_for_profile(image, profile):
    zone = load_scan_zones().get(profile)
    if not zone:
        print("Scan zone: full image")
        return decode_barcodes(image)

    crop = crop_scan_zone(image, zone)
    cv2.imwrite("last_scan_zone.jpg", crop)
    print(
        "Scan zone: "
        f"x={zone['x']}%, y={zone['y']}%, width={zone['width']}%, height={zone['height']}%"
    )
    print("Saved scan zone crop to last_scan_zone.jpg")

    found = decode_barcodes(crop)
    if found:
        print(f"Decoded {len(found)} raw hit(s) from scan zone.")
        return found

    print("No barcode found in scan zone. Falling back to full image.")
    return decode_barcodes(image)


def crop_scan_zone(image, zone):
    image_height, image_width = image.shape[:2]
    x1 = int(image_width * zone["x"] / 100)
    y1 = int(image_height * zone["y"] / 100)
    x2 = int(image_width * (zone["x"] + zone["width"]) / 100)
    y2 = int(image_height * (zone["y"] + zone["height"]) / 100)
    x1 = clamp(x1, 0, image_width)
    y1 = clamp(y1, 0, image_height)
    x2 = clamp(x2, x1 + 1, image_width)
    y2 = clamp(y2, y1 + 1, image_height)
    return image[y1:y2, x1:x2]


def barcode_key(barcode):
    return normalize_identifier(barcode["value"])


def dedupe_and_sort_barcodes(barcodes):
    grouped = {}
    for barcode in barcodes:
        key = barcode_key(barcode)
        current = grouped.get(key)
        if current is None or barcode_score(barcode) > barcode_score(current):
            grouped[key] = barcode

    return sorted(grouped.values(), key=barcode_sort_key)


def barcode_score(barcode):
    score = 0
    if barcode["rect"] is not None:
        score += 10
        _x, _y, width, height = barcode["rect"]
        score += min(width * height, 100000) / 100000
    if barcode["format"] and barcode["format"].lower() != "none":
        score += 1
    return score


def barcode_sort_key(barcode):
    rect = barcode["rect"]
    if rect is None:
        return (999999, 999999)
    x, y, _width, _height = rect
    return (y, x)


def apply_profile_fallbacks(barcodes, profile):
    if profile in {"savvio", "savvio_10k2", "savvio_15k3"}:
        return apply_savvio_fallbacks(barcodes)

    if profile == "savvio_15k1":
        return apply_savvio_fallbacks(
            barcodes,
            fallback_order=["Lot Number", "Part Number", "Serial Number", "Factory Number", "Firmware"],
        )

    if profile == "western_digital":
        return apply_simple_fallbacks(
            barcodes,
            fallback_order=["Model Number", "Serial Number", "Part Number", "WWN", "Date Code", "DCM"],
        )

    if profile == "dell_constellation_es3":
        return apply_simple_fallbacks(
            barcodes,
            fallback_order=["Model Number", "Part Number", "Serial Number", "WWN", "Date Code"],
        )

    if profile == "dell_constellation_es":
        return apply_simple_fallbacks(
            barcodes,
            fallback_order=["Model Number", "Part Number", "Serial Number", "Date Code"],
        )

    if profile not in {"hgst_oracle", "hitachi_oracle"}:
        return barcodes

    typed_barcodes = []
    fallback_order = ["Part Number", "Config", "Firmware", "Serial Number"]
    for index, barcode in enumerate(barcodes):
        barcode = dict(barcode)
        if len(barcodes) >= 4 and index < len(fallback_order):
            barcode["profile_type"] = fallback_order[index]
        else:
            value_type = classify_hgst_value_pattern(barcode["value"])
            barcode["profile_type"] = value_type
        typed_barcodes.append(barcode)

    return typed_barcodes


def apply_simple_fallbacks(barcodes, fallback_order):
    typed_barcodes = []
    for index, barcode in enumerate(barcodes):
        barcode = dict(barcode)
        value_type = classify_general_value_pattern(barcode["value"])
        if value_type != "Unknown":
            barcode["profile_type"] = value_type
        elif index < len(fallback_order):
            barcode["profile_type"] = fallback_order[index]
        else:
            barcode["profile_type"] = "Unknown"
        typed_barcodes.append(barcode)

    return typed_barcodes


def apply_savvio_fallbacks(
    barcodes,
    fallback_order=None,
):
    typed_barcodes = []
    if fallback_order is None:
        fallback_order = ["Model Number", "Lot Number", "Part Number", "Serial Number", "Factory Number"]

    for index, barcode in enumerate(barcodes):
        barcode = dict(barcode)
        value_type = classify_savvio_value_pattern(barcode["value"])
        if value_type != "Unknown":
            barcode["profile_type"] = value_type
        elif len(barcodes) >= 5 and index < len(fallback_order):
            barcode["profile_type"] = fallback_order[index]
        else:
            barcode["profile_type"] = "Unknown"
        typed_barcodes.append(barcode)

    return typed_barcodes


def classify_savvio_value_pattern(value):
    value = normalize_identifier(value)

    if re.fullmatch(r"[0-9]{1,3}", value):
        return "Factory Number"

    if re.fullmatch(r"ST[0-9A-Z]{6,12}", value):
        return "Model Number"

    if re.fullmatch(r"[A-Z]-[0-9A-Z]{2}-[0-9A-Z]{3,6}-[0-9A-Z]", value):
        return "Lot Number"

    if "-" in value:
        return "Part Number"

    if re.fullmatch(r"[A-Z0-9]{6,16}", value):
        return "Serial Number"

    return "Unknown"


def classify_general_value_pattern(value):
    value = normalize_identifier(value)

    if re.fullmatch(r"ST[0-9A-Z]{6,12}", value) or re.fullmatch(r"WD[0-9A-Z-]{6,20}", value):
        return "Model Number"

    if re.fullmatch(r"[0-9A-F]{16}", value):
        return "WWN"

    if re.fullmatch(r"[0-9]{4,8}", value):
        return "Date Code"

    if "-" in value:
        return "Part Number"

    if re.fullmatch(r"[A-Z0-9]{6,16}", value):
        return "Serial Number"

    return "Unknown"


def classify_hgst_value_pattern(value):
    value = normalize_identifier(value)

    if re.fullmatch(r"[0-9A-Z]{5,8}", value) and not value.isdigit():
        return "Serial Number"

    if re.fullmatch(r"[A-Z0-9]{2,5}", value) and any(char.isalpha() for char in value):
        return "Firmware"

    if re.fullmatch(r"[0-9]{1,4}", value):
        return "Config"

    if "-" in value or re.fullmatch(r"[0-9A-Z]{8,18}", value):
        return "Part Number"

    return "Unknown"


def decode_with_zxing(image):
    try:
        import zxingcpp
    except Exception as exc:
        print(f"zxing-cpp unavailable: {exc}")
        return []

    decoded = []
    for orientation, source_image, scan_image, scale in build_scan_images(image):
        try:
            results = zxingcpp.read_barcodes(scan_image)
        except Exception:
            continue

        for result in results:
            value = clean_value(getattr(result, "text", ""))
            if not value:
                continue

            rect = scale_rect(zxing_rect(result), scale)
            decoded.append(
                {
                    "value": value,
                    "format": str(getattr(result, "format", "zxing")),
                    "rect": rect,
                    "orientation": orientation,
                    "source_image": source_image,
                }
            )

    return decoded


def decode_with_pyzbar(image):
    try:
        from pyzbar.pyzbar import decode
    except Exception as exc:
        print(f"pyzbar unavailable: {exc}")
        return []

    decoded = []
    for orientation, source_image, scan_image, scale in build_scan_images(image):
        try:
            results = decode(scan_image)
        except Exception:
            continue

        for result in results:
            value = clean_value(result.data.decode("utf-8", errors="ignore"))
            if not value:
                continue

            x, y, width, height = result.rect
            rect = scale_rect((x, y, width, height), scale)
            decoded.append(
                {
                    "value": value,
                    "format": result.type,
                    "rect": rect,
                    "orientation": orientation,
                    "source_image": source_image,
                }
            )

    return decoded


def build_scan_images(image):
    variants = [
        ("normal", image),
        ("rotated_90_clockwise", cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)),
        ("rotated_180", cv2.rotate(image, cv2.ROTATE_180)),
        ("rotated_90_counterclockwise", cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)),
    ]

    scan_images = []
    for orientation, source in variants:
        gray = cv2.cvtColor(source, cv2.COLOR_BGR2GRAY)
        equalized = cv2.equalizeHist(gray)
        resized = cv2.resize(gray, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
        enlarged = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        blurred = cv2.GaussianBlur(resized, (3, 3), 0)
        sharpened = cv2.addWeighted(resized, 1.5, blurred, -0.5, 0)
        threshold = cv2.adaptiveThreshold(
            resized,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            5,
        )
        scan_images.extend(
            [
                (orientation, source, source, 1.0),
                (orientation, source, gray, 1.0),
                (orientation, source, equalized, 1.0),
                (orientation, source, resized, 1.5),
                (orientation, source, enlarged, 2.0),
                (orientation, source, sharpened, 1.5),
                (orientation, source, threshold, 1.5),
            ]
        )

    return scan_images


def scale_rect(rect, scale):
    if rect is None or not scale:
        return rect

    x, y, width, height = rect
    return (
        int(x / scale),
        int(y / scale),
        int(width / scale),
        int(height / scale),
    )


def zxing_rect(result):
    position = getattr(result, "position", None)
    if position is None:
        return None

    points = []
    for name in ("top_left", "top_right", "bottom_right", "bottom_left"):
        point = getattr(position, name, None)
        if point is not None:
            points.append((int(point.x), int(point.y)))

    if not points:
        return None

    x_values = [point[0] for point in points]
    y_values = [point[1] for point in points]
    x_min, x_max = min(x_values), max(x_values)
    y_min, y_max = min(y_values), max(y_values)
    return x_min, y_min, x_max - x_min, y_max - y_min


def crop_near_barcode(image, rect):
    height, width = image.shape[:2]
    if rect is None:
        return image

    x, y, w, h = rect
    pad_x = max(int(w * 0.9), 90)
    pad_y = max(int(h * 2.8), 90)
    x1 = clamp(x - pad_x, 0, width)
    x2 = clamp(x + w + pad_x, 0, width)
    y1 = clamp(y - pad_y, 0, height)
    y2 = clamp(y + h + pad_y, 0, height)
    return image[y1:y2, x1:x2]


def read_text(image):
    try:
        import pytesseract
    except Exception as exc:
        return f"[OCR unavailable: {exc}]"

    if len(image.shape) == 2:
        gray = image
    else:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

    try:
        text = pytesseract.image_to_string(
            gray,
            config="--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789:/.- ",
        )
    except Exception as exc:
        return f"[OCR failed: {exc}]"

    return normalize_space(text)


def classify_barcode(value, ocr_text):
    text = normalize_for_compare(f"{ocr_text} {value}")
    value_text = normalize_for_compare(value)

    if looks_like_firmware_or_config(value_text, text):
        if "CONFIG" in text or "CONF" in text:
            return "Config"
        return "Firmware"

    for barcode_type, keywords in KEYWORD_RULES:
        if any(keyword in text for keyword in keywords):
            return barcode_type

    if looks_like_serial(value_text, text):
        return "Serial Number"

    if re.fullmatch(r"[A-Z0-9]{8,12}", value):
        return "Serial Number"

    if "-" in value:
        return "Part Number"

    return "Unknown"


def looks_like_firmware_or_config(value, context):
    firmware_keywords = ("FIRMWARE", "FW", "F/W", "CONFIG", "CONF")
    if any(keyword in context for keyword in firmware_keywords):
        return True
    return False


def looks_like_serial(value, context):
    serial_keywords = ("SERIAL", "S/N", "SN ", "S N")
    if any(keyword in context for keyword in serial_keywords):
        return True
    return bool(re.fullmatch(r"[A-Z0-9]{8,16}", value)) and not ("-" in value)


def should_keep(suggested_type, allowed_types):
    if not allowed_types:
        return True
    return suggested_type in allowed_types


def decide_profile_action(suggested_type, allowed_types, profile):
    if not allowed_types:
        return "KEEP"

    if suggested_type in allowed_types:
        return "KEEP"

    if profile in {"hgst_oracle", "hitachi_oracle"}:
        return "REVIEW"

    return "IGNORE / REVIEW"


def compare_barcode_to_ocr(value, ocr_text):
    if not ocr_text or ocr_text.startswith("[OCR "):
        return "OCR UNAVAILABLE"

    normalized_value = normalize_identifier(value)
    normalized_text = normalize_identifier(ocr_text)
    if normalized_value and normalized_value in normalized_text:
        return "MATCH"

    compact_value = normalized_value.replace("-", "")
    compact_text = normalized_text.replace("-", "")
    if compact_value and compact_value in compact_text:
        return "MATCH"

    value_variants = make_ocr_variants(compact_value)
    text_tokens = extract_identifier_tokens(ocr_text)
    text_variants = set()
    for token in text_tokens:
        text_variants.update(make_ocr_variants(token.replace("-", "")))

    if value_variants.intersection(text_variants):
        return "MATCH"

    for text_variant in text_variants:
        if is_close_match(compact_value, text_variant):
            return "FUZZY MATCH"

    return "NO MATCH"


def make_ocr_variants(value):
    value = normalize_identifier(value).replace("-", "")
    if not value:
        return set()

    variants = {value}
    replacements = {
        "0": "O",
        "O": "0",
        "1": "I",
        "I": "1",
        "5": "S",
        "S": "5",
        "8": "B",
        "B": "8",
    }
    translated = "".join(replacements.get(char, char) for char in value)
    variants.add(translated)
    return variants


def extract_identifier_tokens(text):
    normalized = text.upper()
    return re.findall(r"[A-Z0-9][A-Z0-9-]{2,}", normalized)


def is_close_match(value, candidate):
    if not value or not candidate:
        return False

    if len(value) < 4 or len(candidate) < 4:
        return False

    ratio = SequenceMatcher(None, value, candidate).ratio()
    return ratio >= 0.85


def normalize_identifier(text):
    return re.sub(r"[^A-Z0-9-]", "", text.upper())


def clean_value(value):
    return value.strip().upper()


def normalize_space(text):
    return " ".join(text.replace("\n", " ").split())


def normalize_for_compare(text):
    return normalize_space(text).upper()


def clamp(value, minimum, maximum):
    return max(minimum, min(int(value), maximum))


def print_summary(results):
    print("=" * 60)
    print("Summary")
    for index, result in enumerate(results, start=1):
        print(
            f"{index}. {result['type']}: {result['value']} "
            f"[{result['decision']}, {result['match']}]"
        )
    print("=" * 60)


def view_test_database(latest_only=False):
    ocr_test_database.create_tables()
    print(f"Database: {ocr_test_database.current_database_path().name}")
    runs = ocr_test_database.view_runs()
    if not runs:
        print("No OCR test runs saved yet.")
        return

    if latest_only:
        runs = [runs[-1]]

    for run in runs:
        print("=" * 80)
        print(
            f"Run {run['run_id']} | Profile: {run['profile']} | "
            f"Image: {run['image_path']} | Date: {run['date_created']}"
        )
        results = ocr_test_database.view_results_for_run(run["run_id"])
        if not results:
            print("No results.")
            continue

        for result in results:
            print("-" * 80)
            print(f"Result: {result['result_id']}")
            print(f"Value: {result['barcode_value']}")
            print(f"Suggested Type: {result['barcode_type_suggested']}")
            print(f"Decision: {result['profile_decision']}")
            print(f"Match: {result['match_status']}")
            print(f"OCR: {result['nearby_ocr_text']}")
            print(f"Crop: {result['crop_path']}")


if __name__ == "__main__":
    main()
