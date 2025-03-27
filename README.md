# <center>**Desktop Automation**</center>

<video controls autoplay muted>
  <source src="demo.mp4" type="video/mp4">
</video>

This project demonstrates desktop automation using Python, Tesseract OCR, and AI. It extracts text from images and leverages AI to perform actions based on that extracted text.

- It's divided into two main parts:
  1.  Extracting text from an image using Tesseract OCR.
  2.  Using AI to perform a task based on the extracted text.

- Tested on Windows 10, Windows 11, macOS, and Ubuntu Linux.
- Compatible with AI models like `gpt-4o-mini`, `gemini-3-4b`, `gemini-3-12b`, and `gemini-pro-2.5-experimental`.  You can adapt it to use any AI model that accepts an image as input and returns text as output.


## Examples

### Example 1: Creating folder in desktop(if desktop is opened)
```bash
Click at (1800, 73)
rightClick (500,500)
Click on New
Click on Folder
type 'TodoList'
press enter
```

### Example 2: Post on Facebook
```bash
Click at (1800, 73)
Click at (500,500)
Click at (748,1051) <== Browser Icon on Taskbar (Replace the cordinates with yours)
press ctrl+t
type facebook.com
press enter
wait 5
click at (791,239)
type 'this message is from jarvis'
press tab x15
press enter
```
`Note: Click at (748,1051) is the location of the browser icon on the taskbar. You can find the location of the browser icon on your taskbar and replace it with the location in the script.`

## Requirements
- Python 3
- Tessaract OCR
- PyAutoGUI
- OpenAI or Any other AI service (Free or Paid)
- A good internet connection

### Tesseract OCR Engine: This is crucial and must be installed separately from the Python library.
- Windows: Download from the official Tesseract GitHub (https://github.com/tesseract-ocr/tesseract) or use installers like the one provided by UB Mannheim (https://github.com/UB-Mannheim/tesseract/wiki). Make sure to add Tesseract to your system's PATH during installation.
- macOS: ```brew install tesseract```
- Linux (Debian/Ubuntu): ```sudo apt update && sudo apt install tesseract-ocr```
- Linux (Fedora): ```sudo dnf install tesseract```

Python Library:
```bash
pip install pytesseract
# Ensure Pillow is also installed (usually a dependency)
pip install Pillow
```

## FAQ
- **Q:** Can I use this project to automate any task on my desktop?
- **A:** Yes, you can use this project to automate any task on your desktop.
- A good internet connection

### Tesseract OCR Engine: This is crucial and must be installed separately from the Python library.
- Windows: Download from the official Tesseract GitHub (https://github.com/tesseract-ocr/tesseract) or use installers like the one provided by UB Mannheim (https://github.com/UB-Mannheim/tesseract/wiki). Make sure to add Tesseract to your system's PATH during installation.
- macOS: ```brew install tesseract```
- Linux (Debian/Ubuntu): ```sudo apt update && sudo apt install tesseract-ocr```
- Linux (Fedora): ```sudo dnf install tesseract```

Python Library:
```bash
pip install pytesseract
# Ensure Pillow is also installed (usually a dependency)
pip install Pillow
```

## FAQ
- **Q:** Can I use this project to automate any task on my desktop?
- **A:** Yes, you can use this project to automate any task on your desktop.
