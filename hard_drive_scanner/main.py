import database
from camera_scanner import scan_barcode


BARCODE_TYPES = {
    "1": "Serial Number",
    "2": "Lot Number",
    "3": "Part Number",
    "4": "WWN",
    "5": "Asset Tag",
    "6": "Oracle/Sun Part Number",
    "7": "Firmware",
    "8": "Model Number",
    "9": "Factory Number",
    "10": "Unknown",
    "11": "Config",
    "12": "Date Code",
    "13": "DCM",
}


DRIVE_PROFILES = {
    "1": {
        "key": "savvio",
        "name": "Seagate Savvio",
        "brand": "Seagate",
        "drive_type": "SAS",
        "orientation": "Place label side up. Use the side-to-side barcode orientation. Add model, firmware, or config when visible.",
        "fields": ["Model Number", "Lot Number", "Part Number", "Serial Number", "Factory Number", "Firmware", "Config"],
    },
    "2": {
        "key": "savvio_10k2",
        "name": "Seagate Savvio 10K.2",
        "brand": "Seagate",
        "drive_type": "SAS",
        "orientation": "Place label side up. Use the bottom-to-top orientation if that scans better. Add model, firmware, or config when visible.",
        "fields": ["Model Number", "Lot Number", "Part Number", "Serial Number", "Factory Number", "Firmware", "Config"],
    },
    "3": {
        "key": "savvio_15k1",
        "name": "Seagate Savvio 15K.1",
        "brand": "Seagate",
        "drive_type": "SAS",
        "orientation": "Place label side up. Scan model, lot number, part number, serial number, factory number, firmware, and config if present.",
        "fields": ["Model Number", "Lot Number", "Part Number", "Serial Number", "Factory Number", "Firmware", "Config"],
    },
    "4": {
        "key": "savvio_15k3",
        "name": "Seagate Savvio 15K.3",
        "brand": "Seagate",
        "drive_type": "SAS",
        "orientation": "Place label side up. Align the barcode row that is most readable through the scan point. Add model, firmware, or config when visible.",
        "fields": ["Model Number", "Lot Number", "Part Number", "Serial Number", "Factory Number", "Firmware", "Config"],
    },
    "5": {
        "key": "hgst_oracle",
        "name": "HGST Sun Oracle",
        "brand": "HGST / Sun Oracle",
        "drive_type": "SAS",
        "orientation": "Place the HGST/Oracle label side up. Scan firmware/config, serial, then model if readable; use P/N if model will not scan.",
        "fields": ["Firmware", "Config", "Serial Number", "Model Number", "Part Number"],
    },
    "6": {
        "key": "hitachi_oracle",
        "name": "Hitachi Sun Oracle",
        "brand": "Hitachi / Sun Oracle",
        "drive_type": "SAS",
        "orientation": "Place the Hitachi/Oracle label side up. Scan firmware/config, serial, then model if readable; use P/N if model will not scan.",
        "fields": ["Firmware", "Config", "Serial Number", "Model Number", "Part Number"],
    },
    "7": {
        "key": "western_digital",
        "name": "Western Digital",
        "brand": "Western Digital",
        "drive_type": "SAS",
        "orientation": "Place label side up. Scan model, serial, part number, WWN, date code, DCM, firmware, and config when present.",
        "fields": ["Model Number", "Serial Number", "Part Number", "WWN", "Date Code", "DCM", "Firmware", "Config"],
    },
    "8": {
        "key": "dell_constellation_es3",
        "name": "Dell Constellation ES.3",
        "brand": "Dell / Seagate",
        "drive_type": "SAS",
        "orientation": "Place label side up. Scan model, part number, serial number, WWN, date code, firmware, and config.",
        "fields": ["Model Number", "Part Number", "Serial Number", "WWN", "Date Code", "Firmware", "Config"],
    },
    "9": {
        "key": "dell_constellation_es",
        "name": "Dell Constellation ES",
        "brand": "Dell / Seagate",
        "drive_type": "SAS",
        "orientation": "Place label side up. Scan model, part number, serial number, date code, firmware, and config. WWN may need manual entry if it is text-only.",
        "fields": ["Model Number", "Part Number", "Serial Number", "Date Code", "WWN", "Firmware", "Config"],
    },
    "10": {
        "key": "misc",
        "name": "Miscellaneous / Other",
        "brand": "",
        "drive_type": "SAS",
        "orientation": "Use this for Dell non-Constellation drives and one-off drives that do not match the main profiles.",
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
    },
    "11": {
        "key": "unknown",
        "name": "Unknown / Manual",
        "brand": "",
        "drive_type": "SAS",
        "orientation": "Use whichever orientation gives the clearest barcode image.",
        "fields": [],
    },
}


def prompt_barcode_type():
    print("\nBarcode type:")
    for number, barcode_type in BARCODE_TYPES.items():
        print(f"{number}. {barcode_type}")

    choice = input("Choose barcode type: ").strip()
    return BARCODE_TYPES.get(choice, "Unknown")


def prompt_drive_profile():
    print("\nDrive profile:")
    for number, profile in DRIVE_PROFILES.items():
        print(f"{number}. {profile['name']}")

    choice = input("Choose profile: ").strip()
    return DRIVE_PROFILES.get(choice, DRIVE_PROFILES["11"])


def add_new_hard_drive():
    print("\nAdd new hard drive")
    profile = prompt_drive_profile()
    print(f"\nSelected profile: {profile['name']}")
    print(f"Setup note: {profile['orientation']}")

    brand = input_with_default("Brand", profile["brand"])
    model = input("Model: ").strip()
    capacity = input("Capacity (example: 146GB): ").strip()
    drive_type = input_with_default("Drive type", profile["drive_type"])
    notes = input("Notes: ").strip()

    drive_id = database.add_drive(brand, model, capacity, drive_type, notes, profile=profile["key"])
    print(f"\nSaved drive. New drive_id: {drive_id}")

    while True:
        action = input("Add barcode? scan/manual/done (s/m/d): ").strip().lower()
        if action in {"d", "done", "n", "no"}:
            break
        if action in {"m", "manual"}:
            add_manual_barcode(drive_id)
            continue
        if action not in {"", "s", "scan", "y", "yes"}:
            print("Choose s to scan, m to type manually, or d when done.")
            continue

        barcode_value = capture_or_enter_barcode()
        if not barcode_value:
            print("No barcode saved.")
            continue
        barcode_type = prompt_barcode_type()
        save_barcode(drive_id, barcode_value, barcode_type)


def input_with_default(label, default):
    if not default:
        return input(f"{label}: ").strip()

    value = input(f"{label} [{default}]: ").strip()
    return value or default


def capture_or_enter_barcode():
    while True:
        print("Camera/capture mode is active. The terminal will continue after a scan or after you quit capture.")
        barcode_value = scan_barcode()
        if barcode_value and confirm_barcode_value(barcode_value):
            return barcode_value

        print("\nScan did not work or the value was not correct.")
        print("1. Try scanning again")
        print("2. Type barcode manually")
        print("3. Skip this barcode")
        choice = input("Choose an option: ").strip()

        if choice == "1":
            continue
        if choice == "2":
            return prompt_manual_barcode(require_yes=False)
        return None


def save_barcode(drive_id, barcode_value, barcode_type):
    barcode_id = database.add_barcode(drive_id, barcode_value, barcode_type)
    if barcode_id:
        print(f"Saved {barcode_type}: {barcode_value}.")
    else:
        print(f"Barcode {barcode_value} already exists and was not saved again.")


def add_manual_barcode(drive_id):
    barcode_type = prompt_barcode_type()
    barcode_value = prompt_manual_barcode(require_yes=False)
    if not barcode_value:
        print("No barcode saved.")
        return
    save_barcode(drive_id, barcode_value, barcode_type)


def search_by_barcode():
    input("\nPress Enter to scan a barcode...")
    print("Camera window is active. The terminal will continue after a scan or after you press Q.")
    barcode_value = scan_barcode()
    if not barcode_value:
        barcode_value = prompt_manual_barcode()
        if not barcode_value:
            print("No barcode entered.")
            return

    result = database.search_by_barcode(barcode_value)
    if not result:
        print("No matching drive was found.")
        return

    print("\nMatching drive found:")
    print_drive(result)
    print(f"Barcode: {result['barcode_value']} ({result['barcode_type']})")


def view_all_drives():
    drives = database.view_all_drives()
    if not drives:
        print("\nNo drives saved yet.")
        return

    print("\nSaved drives:")
    for drive in drives:
        print_drive(drive)
        print("-" * 40)


def prompt_manual_barcode(require_yes=True):
    if require_yes:
        use_manual = input("No barcode scanned. Type it manually instead? (y/n): ").strip().lower()
        if use_manual != "y":
            return None

    barcode_value = input("Barcode value: ").strip().upper()
    if not barcode_value:
        return None
    return barcode_value


def confirm_barcode_value(barcode_value):
    print(f"Scanned barcode: {barcode_value}")
    choice = input("Is this correct? (y/n): ").strip().lower()
    return choice == "y"


def view_barcodes_for_drive():
    drive_id = input("\nEnter drive_id: ").strip()
    if not drive_id.isdigit():
        print("Drive ID must be a number.")
        return

    barcodes = database.view_barcodes_for_drive(int(drive_id))
    if not barcodes:
        print("No barcodes found for that drive.")
        return

    print(f"\nBarcodes for drive_id {drive_id}:")
    for barcode in barcodes:
        print(
            f"{barcode['barcode_id']}: {barcode['barcode_value']} "
            f"({barcode['barcode_type']}) scanned {barcode['date_scanned']}"
        )


def view_inventory_by_drive_type():
    profiles = list(database.PROFILE_VIEWS.keys())
    print("\nDrive type tables:")
    for index, profile in enumerate(profiles, start=1):
        print(f"{index}. {profile}")

    choice = input("Choose drive type table: ").strip()
    if not choice.isdigit():
        print("Invalid option.")
        return

    index = int(choice)
    if index < 1 or index > len(profiles):
        print("Invalid option.")
        return

    profile = profiles[index - 1]
    rows = database.view_inventory_by_profile(profile)
    if not rows:
        print(f"No saved drives found in {profile}.")
        return

    print(f"\n{profile}:")
    for row in rows:
        print("-" * 40)
        for key, value in row.items():
            if value is None:
                value = ""
            print(f"{key}: {value}")


def print_drive(drive):
    print(f"Drive ID: {drive['drive_id']}")
    print(f"Brand: {drive['brand']}")
    print(f"Model: {drive['model']}")
    print(f"Capacity: {drive['capacity']}")
    print(f"Drive Type: {drive['drive_type']}")
    if drive.get("profile"):
        print(f"Profile: {drive['profile']}")
    print(f"Notes: {drive['notes']}")
    print(f"Date Added: {drive['date_added']}")


def main():
    database.create_tables()

    while True:
        print("\nHard Drive Barcode Scanner")
        print("1. Add new hard drive")
        print("2. Search by barcode")
        print("3. View all drives")
        print("4. View barcodes for a drive")
        print("5. View inventory by drive type")
        print("6. Exit")

        choice = input("Choose an option: ").strip()

        if choice == "1":
            add_new_hard_drive()
        elif choice == "2":
            search_by_barcode()
        elif choice == "3":
            view_all_drives()
        elif choice == "4":
            view_barcodes_for_drive()
        elif choice == "5":
            view_inventory_by_drive_type()
        elif choice == "6":
            print("Goodbye.")
            break
        else:
            print("Invalid option.")


if __name__ == "__main__":
    main()
