#Scan for web servers, capture their screens and place them in a word document table (docx)
#Author: Vahe Demirkhanyan

import sys

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
import os
import socket
from concurrent.futures import ThreadPoolExecutor
import ipaddress
from selenium import webdriver
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
    return webdriver.Firefox(executable_path=GeckoDriverManager().install(), firefox_options=options)

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
                whisperWinds(f"Successfully captured {url}")
            except Exception as e:
                print(f"Failed to capture {url}: {e}")
    
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

def embarkQuest(hosts_file, output_file):
    with open(hosts_file, 'r') as file:
        hosts = [host.strip() for host in file if host.strip()]
    expanded_hosts = unravelScrolls(hosts)

    print("Starting port scan...")
    with ThreadPoolExecutor(max_workers=30) as executor:
        executor.map(scoutLands, expanded_hosts)
    
    print("Port scan finished. Beginning screen capture...")

    driver = summonSteeds()
    captureVisions(driver, output_file)
    print("Screen capture finished.")
    driver.quit()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python netgazer.py <hosts_file> <output_file>")
    else:
        embarkQuest(sys.argv[1], sys.argv[2])
