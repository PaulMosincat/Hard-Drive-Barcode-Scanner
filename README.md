# Hard-Drive-Barcode-Scanner
## Problem

Enterprise hard drives contain multiple barcodes, serial numbers, part numbers, firmware identifiers, and manufacturer-specific labels. One challenge is that hard drive labels are not standardized across manufacturers, models, or generations. Some drives contain damaged labels, faded text, poorly positioned barcodes, or information that cannot always be automatically detected.

Because of these inconsistencies, fully automated data collection is not always reliable. Manual inventory tracking is time-consuming, prone to human error, and difficult to scale when processing large numbers of drives. The goal of this project was to create a system that automates as much of the inventory process as possible while still allowing human verification when needed.

#Solution

This project combines barcode scanning, Optical Character Recognition (OCR), and database management to automate hard drive inventory tracking.

Using a webcam or Raspberry Pi camera, the system captures images of hard drive labels, detects and decodes barcodes, extracts nearby text using OCR, and stores the results in a SQLite database. When barcode scans are unsuccessful or information is ambiguous, the user can manually correct or enter data to ensure accuracy. This hybrid approach balances automation with human oversight, making the system practical for real-world inventory management.

#Technologies Used
Python
OpenCV
Tesseract OCR
SQLite
Pyzbar
ZXing-C++
Raspberry Pi Camera
Git & GitHub

$How It Works
Capture an image using a webcam or Raspberry Pi camera.
Detect and decode available barcodes.
Extract nearby text using OCR.
Classify scanned information such as serial numbers, part numbers, firmware, WWN, and model numbers.
Allow the user to verify, correct, or manually enter information when needed.
Store validated records in a SQLite inventory database.
Search and manage stored inventory records through the application interface.

#Key Features
Barcode scanning and decoding
OCR text extraction
SQLite inventory database
Duplicate detection and validation
Support for multiple enterprise hard drive profiles
Manual correction and data entry tools
Raspberry Pi deployment support
Searchable inventory records

#What I Learned

Through this project, I gained experience with computer vision, OCR processing, barcode recognition, database design, and inventory automation. I also learned how to integrate multiple Python libraries into a single workflow and improve system accuracy through iterative testing and real-world validation.

#Development Process

This project was developed using an iterative testing and validation approach. Generative AI tools, including OpenAI Codex, were used to assist with code generation, debugging, library integration, and rapid prototyping. All generated code was reviewed, tested, modified, and validated through real-world barcode scanning and inventory management workflows.

The use of AI-assisted development helped accelerate implementation while allowing focus on system design, testing, hardware integration, database architecture, and workflow optimization.

#Future Improvements
Graphical user interface (GUI)
Real-time video scanning
Cloud database integration
Web-based inventory dashboard
Improved OCR accuracy
Support for additional storage devices and hardware profiles
Automated barcode classification using machine learning
