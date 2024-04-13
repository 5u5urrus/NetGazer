#Scan for web servers, capture their screens and place them in an HTML or word document table (docx)
#Author: Vahe Demirkhanyan
import base64
import os
import sys
import tempfile
import argparse
import ipaddress
from itertools import product

parser = argparse.ArgumentParser(description='Scan and capture web server screenshots.')

parser.add_argument('input', help='Input hosts file, CIDR notation, or IP range')
parser.add_argument('output_file', help='Output file name (.docx or .html)')

args = parser.parse_args()


def initialChecks():
    # Check for root permissions
    if os.geteuid() == 0:
        print("This script is being attempted to run with root permissions. Please run as a regular user because it is insecure visiting pages with root permissions.")
        sys.exit(1)

    # Check for write permissions in the current directory
    try:
        test_file_path = os.path.join(os.getcwd(), "temp_test_file")
        with open(test_file_path, 'w') as test_file:
            test_file.write("test")
        os.remove(test_file_path)
    except IOError as e:
        print("The script does not have write permissions in the current directory.")
        print("Please change to a directory with write permissions or adjust the permissions of the current directory.")
        sys.exit(1)

# Call the initial checks function
initialChecks()

def is_ip_range(ip_range):
    return '-' in ip_range

def generateIpsFromComplexRange(range_str):
    octet_parts = range_str.split('.')
    octet_ranges = [range(int(part.split('-')[0]), int(part.split('-')[1]) + 1) if '-' in part else [int(part)] for part in octet_parts]
    return ['.'.join(map(str, combination)) for combination in product(*octet_ranges)]


def expandIPRange_or_singleIP(input_value):
    return expandIPrange(input_value) if '-' in input_value else [input_value]

def expandIPRange(ip_range):
    start_ip, end_ip = ip_range.split('-')
    if '.' not in end_ip:
        start_ip_base = '.'.join(start_ip.split('.')[:-1])
        end_ip = f"{start_ip_base}.{end_ip}"
    start = ipaddress.IPv4Address(start_ip)
    end = ipaddress.IPv4Address(end_ip)
    return [str(ip) for ip in range(int(start), int(end) + 1)]

def handleInput(input_value):
    if '/' in input_value:
        # Handle CIDR notation more robustly, including error handling
        try:
            return [str(ip) for ip in ipaddress.ip_network(input_value, strict=False).hosts()]
        except ValueError as e:
            print(f"Error parsing CIDR notation '{input_value}': {e}")
            return []

    elif '-' in input_value and input_value.count('.') == 3:
        # Simplified decision tree for handling complex ranges directly
        return generateIpsFromComplexRange(input_value) if input_value.count('-') >= 1 else expandIPRange_or_singleIP(input_value)

    else:
        # Default case handles single IPs or unexpected formats gracefully
        return expandIPRange_or_singleIP(input_value)


def gatherTomes():
    required_libraries = ['selenium', 'docx', 'webdriver_manager', 'ipaddress']
    missing_libraries = []

    for library in required_libraries:
        try:
            __import__(library)
        except ImportError:
            missing_libraries.append(library)
    
    if missing_libraries:
        print("Missing some libraries. Please install them before running this good script.")
        for lib in missing_libraries:
            print(f"- {lib}")
        sys.exit(1)

# Checking if libraries are present
gatherTomes()

# The rest of imports and script
import socket
from concurrent.futures import ThreadPoolExecutor

from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options
from webdriver_manager.firefox import GeckoDriverManager

import docx
from docx.shared import Inches

def whisperWinds(text):
    print(f"\033[92m{text}\033[0m")

def peekPortals(host, port, timeout=10):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            print(f"Port {port} is open on {host}")
            return True
    except Exception:
        return False

hosts_to_capture = []

def scoutLands(host):
    schemes = []
    if peekPortals(host, 443):
        schemes.append('https')
    if peekPortals(host, 80):
        schemes.append('http')
    if schemes:
        hosts_to_capture.append((host, schemes))

def summonSteeds():
    options = Options()
    options.headless = True
    options.add_argument("--headless")
    service = FirefoxService(executable_path=GeckoDriverManager().install())
    
    #instantiate the Firefox WebDriver with the updated arguments
    driver = webdriver.Firefox(service=service, options=options)
    driver.set_page_load_timeout(30)
    return driver
#    return webdriver.Firefox(executable_path=GeckoDriverManager().install(), firefox_options=options)

def capture_screenshot(driver, url, screenshot_path):
    try:
        driver.get(url)
        if driver.save_screenshot(screenshot_path):
            return True
        else:
            print(f"Failed to save screenshot for {url}")
            return False
    except Exception as e:
        #print(f"Failed to capture {url}: {e}")
        return False

def encodeImageBase64(screenshot_path):
    try:
        with open(screenshot_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        print(f"Failed to read or encode the file {screenshot_path}: {e}")
        return None

def captureVisionsHTML(driver, output_file):
    items = []
    temp_files_to_delete = []  # List to keep track of temporary screenshot file paths

    for host, schemes in hosts_to_capture:
        for scheme in schemes:
            url = f"{scheme}://{host}"
            screenshot_filename = f'temp_screenshot_{host.replace(".", "_")}.png'
            screenshot_path = os.path.join(os.getcwd(), screenshot_filename)
            if capture_screenshot(driver, url, screenshot_path):
                items.append((url, screenshot_path))
                temp_files_to_delete.append(screenshot_path)
                whisperWinds(f"Successfully captured {url}")

    html_content = ["<html><head><title>Web Server Screenshots</title></head><body>",
                    "<h1>Web Server Screenshots</h1>",
                    "<table border='1'>",
                    "<tr><th>Web Request Info</th><th>Web Screenshot</th></tr>"]
    
    for url, screenshot_path in items:
        try:
            with open(screenshot_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            html_content.append(f"<tr><td>{url}</td><td><img src='data:image/png;base64,{base64_image}' width='350'></td></tr>")
        except IOError as e:
            print(f"Error reading screenshot file {screenshot_path}: {e}")

    html_content.append("</table></body></html>")

    with open(output_file, 'w') as file:
        file.writelines(html_content)

    clean_up_files(temp_files_to_delete)  # Utilize a helper function to clean up files

def clean_up_files(file_paths):
    for file_path in file_paths:
        if os.path.exists(file_path):  # Check if the file exists before trying to delete it
            try:
                os.remove(file_path)
                #print(f"Successfully deleted {file_path}")
            except Exception as e:
                pass #print(f"Error deleting temporary file {file_path}: {e}")
        else:
            pass #print(f"File not found, could not delete: {file_path}")

def captureVisions(driver, output_file):
    doc = docx.Document()
    table = doc.add_table(rows=1, cols=2)
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = 'Web Request Info'
    hdr_cells[1].text = 'Web Screenshot'
    
    for host, schemes in hosts_to_capture:
        for scheme in schemes:
            url = f"{scheme}://{host}"
            screenshot_path = 'temp_screenshot.png'
            if capture_screenshot(driver, url, screenshot_path):
                row_cells = table.add_row().cells
                row_cells[0].text = url
                paragraph = row_cells[1].paragraphs[0]
                run = paragraph.add_run()
                run.add_picture(screenshot_path, width=Inches(3.5))
                os.remove(screenshot_path)
                whisperWinds(f"Successfully captured {url}")

    doc.save(output_file)

def unravelScrolls(hosts):
    expanded_hosts = []
    for host in hosts:
        try:
            network = ipaddress.ip_network(host, strict=False)
            for ip in network.hosts():
                expanded_hosts.append(str(ip))
        except ValueError:
            expanded_hosts.append(host)
    return expanded_hosts

def embarkQuest(input_value, output_file):
    # Determine if input is a file or direct IP/CIDR/range input
    try:
        # Attempt to treat the input as a file path
        with open(input_value, 'r') as file:
            hosts = [host.strip() for host in file if host.strip()]
    except IOError:
        # If an error occurs, assume input is not a file but direct input
        hosts = handleInput(input_value)

    expanded_hosts = unravelScrolls(hosts)

    print("Starting port scan...")
    with ThreadPoolExecutor(max_workers=30) as executor:
        executor.map(scoutLands, expanded_hosts)

    print("Port scan finished. Beginning screen capture...")

    driver = summonSteeds()

    # Determine output format and call appropriate function
    if output_file.endswith('.docx'):
        captureVisions(driver, output_file)
    elif output_file.endswith('.html'):
        captureVisionsHTML(driver, output_file)
    else:
        print("Unsupported file format. Please use .docx or .html.")
        driver.quit()
        sys.exit(1)

    print("Screen capture finished.")
    driver.quit()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python netgazer.py <hosts_file> <output_file>")
    else:
        embarkQuest(sys.argv[1], sys.argv[2])
