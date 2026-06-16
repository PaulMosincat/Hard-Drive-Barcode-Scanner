import shutil
import subprocess

import cv2


def scan_barcode():
    try:
        import zxingcpp
    except Exception:
        zxingcpp = None

    try:
        from pyzbar.pyzbar import decode
    except Exception:
        decode = None

    if zxingcpp is None and decode is None:
        print("No barcode decoder is installed.")
        print("Install with: python3 -m pip install pyzbar zxing-cpp --break-system-packages")
        return None

    rpicam_command = find_rpicam_command()
    if rpicam_command:
        return scan_with_rpicam_still(rpicam_command, zxingcpp, decode)

    return scan_with_usb_camera(zxingcpp, decode)


def find_rpicam_command():
    for command in ("rpicam-still", "libcamera-still"):
        if shutil.which(command):
            return command
    return None


def scan_with_rpicam_still(rpicam_command, zxingcpp, decode):
    print("Using Raspberry Pi still capture mode.")
    print("Place one barcode under the camera and hold it still.")

    while True:
        choice = input("Press Enter to capture and scan, or q to quit: ").strip().lower()
        if choice == "q":
            return None

        image_path = "last_pi_capture.jpg"
        try:
            subprocess.run(
                [
                    rpicam_command,
                    "-o",
                    image_path,
                    "--width",
                    "1280",
                    "--height",
                    "720",
                    "--timeout",
                    "1000",
                    "--nopreview",
                ],
                check=True,
                timeout=15,
            )
        except Exception as exc:
            print(f"Camera capture failed: {exc}")
            return None

        frame = cv2.imread(image_path)
        if frame is None:
            print("Could not load captured image.")
            continue

        cv2.imwrite("last_scan_frame.jpg", frame)
        barcode_value = decode_frame(frame, zxingcpp, decode)
        if barcode_value:
            return barcode_value

        print("No barcode found. Try repositioning or enter it manually after quitting.")


def scan_with_usb_camera(zxingcpp, decode):
    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        print("Could not open USB webcam.")
        return None

    print("Using USB webcam mode.")
    print("Press C to capture and scan, or Q to quit.")

    while True:
        success, frame = camera.read()
        if not success:
            print("Could not read from USB webcam.")
            break

        cv2.putText(
            frame,
            "Press C to scan, Q to quit",
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 255),
            2,
        )
        cv2.imshow("Barcode Scanner", frame)
        key = cv2.waitKey(1) & 0xFF

        if key == ord("c"):
            cv2.imwrite("last_scan_frame.jpg", frame)
            barcode_value = decode_frame(frame, zxingcpp, decode)
            if barcode_value:
                camera.release()
                cv2.destroyAllWindows()
                return barcode_value
            print("No barcode found. Reposition and press C again.")

        if key == ord("q"):
            break

    camera.release()
    cv2.destroyAllWindows()
    return None


def decode_frame(frame, zxingcpp, decode):
    if zxingcpp is not None:
        results = zxingcpp.read_barcodes(frame)
        if results:
            barcode = results[0]
            print(f"Scanned barcode: {barcode.text}")
            print(f"Barcode format: {barcode.format}")
            return barcode.text

    if decode is not None:
        results = decode(frame)
        if results:
            barcode = results[0]
            value = barcode.data.decode("utf-8")
            print(f"Scanned barcode: {value}")
            print(f"Barcode format: {barcode.type}")
            return value

    return None
