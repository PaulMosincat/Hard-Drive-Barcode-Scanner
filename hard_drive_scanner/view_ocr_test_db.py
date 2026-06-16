import ocr_test_database


def main():
    ocr_test_database.create_tables()
    runs = ocr_test_database.view_runs()
    if not runs:
        print("No OCR test runs saved yet.")
        return

    for run in runs:
        print("-" * 60)
        print(f"Run ID: {run['run_id']}")
        print(f"Profile: {run['profile']}")
        print(f"Image: {run['image_path']}")
        print(f"Date: {run['date_created']}")

        results = ocr_test_database.view_results_for_run(run["run_id"])
        if not results:
            print("No results.")
            continue

        for result in results:
            print()
            print(f"  Result ID: {result['result_id']}")
            print(f"  Value: {result['barcode_value']}")
            print(f"  Format: {result['barcode_format']}")
            print(f"  Suggested Type: {result['barcode_type_suggested']}")
            print(f"  Profile Decision: {result['profile_decision']}")
            print(f"  Match Status: {result['match_status']}")
            print(f"  OCR Text: {result['nearby_ocr_text']}")
            print(f"  Crop: {result['crop_path']}")


if __name__ == "__main__":
    main()
