#Scan for web servers, capture their screens and place them in a word document table (docx)
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
    octet_ranges = []

    for part in octet_parts:
        if '-' in part:
            start, end = map(int, part.split('-'))
            octet_ranges.append(range(start, end + 1))
        else:
            octet_ranges.append([int(part)])

    return ['.'.join(map(str, combination)) for combination in product(*octet_ranges)]

def expandIPRange_or_singleIP(input_value):
    if '-' in input_value:
        return expandIPRange(input_value)
    else:
        return [input_value]

def expandIPRange(ip_range):
    if '-' in ip_range:
        start_ip, end_ip = ip_range.split('-')
        # Check if shorthand notation is used (e.g., "8.8.8.1-254")
        if not '.' in end_ip:
            start_ip_base = '.'.join(start_ip.split('.')[:-1])
            end_ip = f"{start_ip_base}.{end_ip}"
        
        start = ipaddress.IPv4Address(start_ip)
        end = ipaddress.IPv4Address(end_ip)
        return [str(ip) for ip in range(int(start), int(end) + 1)]
    else:
        # In case the input is directly a single IP, not a range
        return [ip_range]

def handleInput(input_value):
    # CIDR notation
    if '/' in input_value:
        return [str(ip) for ip in ipaddress.ip_network(input_value, strict=False).hosts()]

    # Complex IP range (e.g., "8.8.8-9.1-3")
    elif '-' in input_value and input_value.count('.') == 3 and input_value.count('-') >= 1:
        return generateIpsFromComplexRange(input_value)

    # Simple IP range (e.g., "8.8.8.1-254") or single IP
    else:
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

def captureVisionsHTML(driver, output_file):
    items = []
    temp_files_to_delete = []  # List to keep track of temporary screenshot file paths

    for host, schemes in hosts_to_capture:
        for scheme in schemes:
            url = f"{scheme}://{host}"
            screenshot_filename = f'temp_screenshot_{host.replace(".", "_")}.png'
            screenshot_path = os.path.join(os.getcwd(), screenshot_filename)
            try:
                driver.get(url)
                if driver.save_screenshot(screenshot_path):
                    with open(screenshot_path, "rb") as image_file:
                        base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                    items.append((url, f"data:image/png;base64,{base64_image}"))
                    temp_files_to_delete.append(screenshot_path)  # Add path to list for later deletion
                    whisperWinds(f"Successfully captured {url}")
                else:
                    print(f"Failed to save screenshot for {url}")
            except Exception as e:
                pass #print(f"Failed to capture {url}: {e}")

    with open(output_file, 'w') as file:
        file.write("<html><head><title>Web Server Screenshots</title></head><body>")
        file.write("<h1>Web Server Screenshots</h1>")
        file.write("<table border='1'>")
        file.write("<tr><th>Web Request Info</th><th>Web Screenshot</th></tr>")
        
        for url, base64_image in items:
            file.write(f"<tr><td>{url}</td><td><img src='{base64_image}' width='350'></td></tr>")
        
        file.write("</table>")
        file.write("</body></html>")

    # Now delete the temporary screenshot files
    for file_path in temp_files_to_delete:
        try:
            os.remove(file_path)
        except Exception as e:
            pass #print(f"Error deleting temporary file {file_path}: {e}")

def captureVisions(driver, output_file):
    doc = docx.Document()
    table = doc.add_table(rows=1, cols=2)
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = 'Web Request Info'
    hdr_cells[1].text = 'Web Screenshot'
    
    for host, schemes in hosts_to_capture:
        for scheme in schemes:
            url = f"{scheme}://{host}"
            try:
                driver.get(url)
                screenshot_path = 'temp_screenshot.png'
                driver.save_screenshot(screenshot_path)
                row_cells = table.add_row().cells
                row_cells[0].text = url
                paragraph = row_cells[1].paragraphs[0]
                run = paragraph.add_run()
                run.add_picture(screenshot_path, width=Inches(3.5))
                os.remove(screenshot_path)
                try:
                    os.remove(screenshot_path)
                except FileNotFoundError as e:
                    pass #print(f"Could not delete screenshot {screenshot_path}: {e}")

                whisperWinds(f"Successfully captured {url}")
            except Exception as e:
                pass #print(f"Failed to capture {url}: {e}")
    
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
