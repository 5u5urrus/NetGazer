#Scan for web servers, capture their screens and place them in an HTML or word document table (docx)
#Author: Vahe Demirkhanyan
import base64
import os
import sys
import tempfile
import argparse
import ipaddress
from itertools import product
import asyncio
import aiohttp

parser = argparse.ArgumentParser(description='Scan and capture web server screenshots.')

parser.add_argument('input', help='Input hosts file, CIDR notation, or IP range')
parser.add_argument('output_file', help='Output file name (.docx or .html)')

args = parser.parse_args()

async def save_docx_async(document, path):
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor() as pool:
        await loop.run_in_executor(pool, document.save, path)


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
#from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import ThreadPoolExecutor, as_completed


from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options
from webdriver_manager.firefox import GeckoDriverManager

import docx
from docx.shared import Inches

executor = ThreadPoolExecutor(max_workers=50)  # Adjust the number of workers based on your needs

async def capture_screenshot_async(driver, url, screenshot_path):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, capture_screenshot, driver, url, screenshot_path)

def capture_screenshot_concurrent(driver, host_scheme):
    host, scheme = host_scheme
    url = f"{scheme}://{host}"
    screenshot_filename = f'temp_screenshot_{host.replace(".", "_")}.png'
    screenshot_path = os.path.join(os.getcwd(), screenshot_filename)
    if capture_screenshot(driver, url, screenshot_path):
        whisperWinds(f"Successfully captured {url}")
        return url, screenshot_path
    return None

def whisperWinds(text):
    print(f"\033[92m{text}\033[0m")

async def peekPortals(host, port, timeout=10):
    # Determine the correct protocol based on the port
    protocol = 'https' if port == 443 else 'http'
    url = f"{protocol}://{host}:{port}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=timeout) as response:
                if response.status:
                    print(f"Port {port} is open on {host}, received HTTP status: {response.status}")
                    return True
                else:
                    # This branch might never be executed as non-2XX responses still have status codes
                    return False
    except Exception as e:
        return False

hosts_to_capture = []

async def scoutLands(host):
    schemes = []
    if await peekPortals(host, 443):  # Using await here
        schemes.append('https')
    if await peekPortals(host, 80):  # And here
        schemes.append('http')
    if schemes:
        hosts_to_capture.append((host, schemes))

def summonSteeds():
    options = Options()
    #options.headless = True
    #options.page_load_strategy = 'eager'
    options.add_argument("--headless")

    # Check if the GeckoDriver is already downloaded and use the existing path, otherwise install it
    driver_path = GeckoDriverManager().install()
    
    service = FirefoxService(executable_path=driver_path)
    
    # instantiate the Firefox WebDriver with the updated arguments
    driver = webdriver.Firefox(service=service, options=options)
    driver.set_page_load_timeout(30)
    return driver


def capture_screenshot(driver, url, screenshot_path):
    try:
        driver.get(url)
        if driver.save_screenshot(screenshot_path):
            whisperWinds(f"Successfully captured {url}")
            return True
        else:
            print(f"Failed to save screenshot for {url}")
            return False
    except Exception as e:
        #print(f"Failed to capture {url}: {e}")
        return False

async def captureVisionsHTMLAsync(driver, output_file):
    tasks = []
    temp_files_to_delete = []
    for host, schemes in hosts_to_capture:
        for scheme in schemes:
            url = f"{scheme}://{host}"
            screenshot_filename = f'temp_screenshot_{host.replace(".", "_")}.png'
            screenshot_path = os.path.join(os.getcwd(), screenshot_filename)
            # Create the coroutine for the screenshot and store it along with URL and path
            task = asyncio.create_task(capture_screenshot_async(driver, url, screenshot_path))
            tasks.append((task, url, screenshot_path))  # Store task with its metadata
            temp_files_to_delete.append(screenshot_path)

    # Wait for all tasks to complete
    results = await asyncio.gather(*[t[0] for t in tasks])  # Only gather the task part

    # Prepare the HTML content
    html_content = ["<html><head><title>Web Server Screenshots</title></head><body>",
                    "<h1>Web Server Screenshots</h1>",
                    "<table border='1'>",
                    "<tr><th>Web Request Info</th><th>Web Screenshot</th></tr>"]

    # Process results and corresponding metadata
    for result, (_, url, screenshot_path) in zip(results, tasks):  # Correctly access stored URL and path
        if result:
            try:
                with open(screenshot_path, "rb") as image_file:
                    base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                html_content.append(f"<tr><td>{url}</td><td><img src='data:image/png;base64,{base64_image}' width='350'></td></tr>")
            except IOError as e:
                print(f"Error reading screenshot file {screenshot_path}: {e}")

    html_content.append("</table></body></html>")

    # Write to the output file
    with open(output_file, 'w') as file:
        file.writelines(html_content)

    clean_up_files(temp_files_to_delete)

def encodeImageBase64(screenshot_path):
    try:
        with open(screenshot_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        print(f"Failed to read or encode the file {screenshot_path}: {e}")
        return None

def captureVisionsHTML(driver, output_file):
    with ThreadPoolExecutor(max_workers=20) as executor:
        # Submit screenshot capture tasks
        future_to_url = {executor.submit(capture_screenshot_concurrent, driver, (host, scheme)): (host, scheme)
                         for host, schemes in hosts_to_capture for scheme in schemes}

        items = []
        temp_files_to_delete = []

        for future in as_completed(future_to_url):
            result = future.result()
            if result:
                url, screenshot_path = result
                items.append((url, screenshot_path))
                temp_files_to_delete.append(screenshot_path)

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

    clean_up_files(temp_files_to_delete)  # Clean up files

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

async def captureVisions(driver, output_file):
    doc = docx.Document()
    table = doc.add_table(rows=1, cols=2)
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = 'Web Request Info'
    hdr_cells[1].text = 'Web Screenshot'

    tasks = []
    for host, schemes in hosts_to_capture:
        for scheme in schemes:
            url = f"{scheme}://{host}"
            #screenshot_path = 'temp_screenshot.png'
            #screenshot_path = f'temp_screenshot_{host.replace('.', '_')}_{scheme}.png'
            replaced_host = host.replace('.', '_')
            screenshot_path = f'temp_screenshot_{replaced_host}_{scheme}.png'
            task = asyncio.create_task(capture_screenshot_async(driver, url, screenshot_path))
            tasks.append((task, url, screenshot_path, table))

    results = await asyncio.gather(*[t[0] for t in tasks])

    for result, (task, url, screenshot_path, table) in zip(results, tasks):
        if result:
            row_cells = table.add_row().cells
            row_cells[0].text = url
            paragraph = row_cells[1].paragraphs[0]
            run = paragraph.add_run()
            run.add_picture(screenshot_path, width=Inches(3.5))
            os.remove(screenshot_path)
            whisperWinds(f"Successfully captured {url}")

    await save_docx_async(doc, output_file)


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


async def perform_port_scans(hosts):
    print(f"Preparing to scan {len(hosts)} hosts...")  # How many hosts are being scanned
    tasks = [scoutLands(host) for host in hosts]
    await asyncio.gather(*tasks)
    print("All hosts have been scanned.")  # Confirmation that all tasks were awaited


def embarkQuest(input_value, output_file):
    try:
        with open(input_value, 'r') as file:
            hosts = [host.strip() for host in file if host.strip()]
    except IOError:
        # If an error occurs, assume input is not a file but direct input
        hosts = handleInput(input_value)

    expanded_hosts = unravelScrolls(hosts)

    print("Starting port scan...")
    asyncio.run(perform_port_scans(expanded_hosts))  # Use asyncio.run to run the async port scan
    print("Port scan finished. Beginning screen capture...")

    driver = summonSteeds()

    # Determine output format and call appropriate function
    if output_file.endswith('.docx'):
        asyncio.run(captureVisions(driver, output_file))
    elif output_file.endswith('.html'):
        asyncio.run(captureVisionsHTMLAsync(driver, output_file))  # Already async
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
        print(f"Starting the script for {sys.argv[1]} outputting to {sys.argv[2]}")
        embarkQuest(sys.argv[1], sys.argv[2])
