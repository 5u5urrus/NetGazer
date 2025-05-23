# Scan for web servers, capture their screens and place them in an HTML or word document table (docx)
# Author: Vahe Demirkhanyan
#!/usr/bin/env python3
import base64
import os
import sys
import argparse
import ipaddress
from itertools import product
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
import socket
from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options
from webdriver_manager.firefox import GeckoDriverManager
import docx
from docx.shared import Inches
from io import BytesIO
import logging
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

parser = argparse.ArgumentParser(description='Scan and capture web server screenshots.')
parser.add_argument('input', help='Input hosts file, CIDR notation, or IP range')
parser.add_argument('output_file', help='Output file name (.docx or .html)')
args = parser.parse_args()

def initial_checks():
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        print("Run as a regular user, not root.")
        sys.exit(1)
    try:
        test_file_path = os.path.join(os.getcwd(), "temp_test_file")
        with open(test_file_path, 'w') as f:
            f.write("test")
        os.remove(test_file_path)
    except IOError:
        print("No write permissions in current directory.")
        sys.exit(1)

initial_checks()

def handle_input(input_value):
    if os.path.isfile(input_value):
        all_hosts = []
        with open(input_value, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    all_hosts.extend(parse_single_host_or_range(line))
        return all_hosts
    else:
        return parse_single_host_or_range(input_value)
    
def parse_single_host_or_range(text):
    # strip off any URL scheme
    for prefix in ("http://", "https://", "ftp://"):
        if text.lower().startswith(prefix):
            text = text[len(prefix):].rstrip("/")
            break

    # ---- NEW: if there's any letter, it's a hostname, not an IP range ----
    if re.search(r"[A-Za-z]", text):
        return [text]

    # now only numeric inputs remain
    if '/' in text:
        return expand_cidr(text)
    if '-' in text:
        return expand_any_dash_range(text)
    return parse_single_ip_or_domain(text)

def parse_single_ip_or_domain(input_str):
    try:
        ip_obj = ipaddress.ip_address(input_str)
        return [str(ip_obj)]
    except ValueError:
        return [input_str]

def expand_cidr(cidr_str):
    try:
        network = ipaddress.ip_network(cidr_str, strict=False)
        return [str(ip) for ip in network.hosts()]
    except ValueError:
        return parse_single_ip_or_domain(cidr_str)

def expand_any_dash_range(range_str):
    if range_str.count('-') > 1:
        return generate_ips_from_complex_range(range_str)
    else:
        try:
            return expand_ip_range(range_str)
        except ValueError:
            return generate_ips_from_complex_range(range_str)

def generate_ips_from_complex_range(range_str):
    octet_parts = range_str.split('.')
    octet_ranges = []
    for part in octet_parts:
        if '-' in part:
            start_s, end_s = part.split('-')
            octet_ranges.append(range(int(start_s), int(end_s) + 1))
        else:
            octet_ranges.append([int(part)])
    expanded_ips = []
    for combo in product(*octet_ranges):
        try:
            ip_obj = ipaddress.ip_address('.'.join(map(str, combo)))
            expanded_ips.append(str(ip_obj))
        except ValueError:
            continue
    return expanded_ips

def expand_ip_range(ip_range_str):
    start_ip_str, end_ip_str = ip_range_str.split('-')
    if '.' not in end_ip_str:
        base = '.'.join(start_ip_str.split('.')[:-1])
        end_ip_str = f"{base}.{end_ip_str}"
    start_ip = ipaddress.ip_address(start_ip_str)
    end_ip = ipaddress.ip_address(end_ip_str)
    return [str(ipaddress.ip_address(ip_int)) for ip_int in range(int(start_ip), int(end_ip) + 1)]

def gather_tomes():
    required_libraries = ['selenium', 'docx', 'webdriver_manager', 'ipaddress', 'tqdm']
    missing = []
    for lib in required_libraries:
        try:
            __import__(lib)
        except ImportError:
            missing.append(lib)
    if missing:
        print("Missing libraries: " + ", ".join(missing))
        sys.exit(1)

gather_tomes()

def whisper_winds(text):
    tqdm.write(f"\033[92m{text}\033[0m")

def peek_portals(host, port, timeout=10):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            tqdm.write(f"Port {port} is open on {host}")
            return True
    except Exception:
        return False

hosts_to_capture = []

def scout_lands(host, progress_bar):
    schemes = []
    if peek_portals(host, 443):
        schemes.append('https')
    if peek_portals(host, 80):
        schemes.append('http')
    if schemes:
        hosts_to_capture.append((host, schemes))
    progress_bar.update(1)

def summon_steeds():
    options = Options()
    options.headless = True
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    service = FirefoxService(executable_path=GeckoDriverManager().install())
    driver = webdriver.Firefox(service=service, options=options)
    driver.set_page_load_timeout(30)
    return driver

def capture_screenshot_data(driver, url):
    try:
        driver.get(url)
        png_data = driver.get_screenshot_as_png()
        base64_data = base64.b64encode(png_data).decode('utf-8')
        return True, png_data, base64_data
    except Exception as e:
        tqdm.write(f"Failed to capture screenshot for {url}: {e}")
        return False, None, None

def capture_visions_html(driver, output_file, progress_bar):
    items = []
    for host, schemes in hosts_to_capture:
        for scheme in schemes:
            url = f"{scheme}://{host}"
            success, _, b64_data = capture_screenshot_data(driver, url)
            if success:
                items.append((url, b64_data))
                whisper_winds(f"Successfully captured {url}")
            progress_bar.update(1)
    html_lines = [
        "<html>",
        "<head>",
        "  <title>Web Server Screenshots</title>",
        "  <style>",
        "    body { font-family: Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 20px; color: #333; }",
        "    h1 { text-align: center; margin-bottom: 30px; }",
        "    table { margin: 0 auto; border-collapse: collapse; width: 90%; max-width: 1000px; box-shadow: 0 2px 5px rgba(0,0,0,0.15); }",
        "    th, td { border: 1px solid #ccc; padding: 12px; text-align: center; }",
        "    th { background-color: #e0e0e0; }",
        "    tr:nth-child(even) { background-color: #fafafa; }",
        "    img { max-width: 700px; border-radius: 5px; }",
        "  </style>",
        "</head>",
        "<body>",
        "  <h1>Web Server Screenshots</h1>",
        "  <table>",
        "    <tr><th>Web Request Info</th><th>Web Screenshot</th></tr>"
    ]
    for url, b64 in items:
        html_lines.append(f"    <tr><td>{url}</td><td><img src='data:image/png;base64,{b64}'></td></tr>")
    html_lines.append("  </table>")
    html_lines.append("</body>")
    html_lines.append("</html>")
    with open(output_file, 'w') as f:
        f.write("\n".join(html_lines))

def capture_visions_docx(driver, output_file, progress_bar):
    import docx.shared
    from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
    from docx.shared import Pt
    doc = docx.Document()
    title_paragraph = doc.add_paragraph()
    title_paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
    title_run = title_paragraph.add_run("Web Server Screenshots")
    title_run.bold = True
    title_run.font.size = Pt(24)
    doc.add_paragraph("")
    table = doc.add_table(rows=1, cols=2)
    table.style = 'Light Grid Accent 1'
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = 'Web Request Info'
    hdr_cells[1].text = 'Web Screenshot'
    for host, schemes in hosts_to_capture:
        for scheme in schemes:
            url = f"{scheme}://{host}"
            success, png_data, _ = capture_screenshot_data(driver, url)
            if success:
                row_cells = table.add_row().cells
                row_cells[0].text = url
                image_stream = BytesIO(png_data)
                paragraph = row_cells[1].paragraphs[0]
                run = paragraph.add_run()
                run.add_picture(image_stream, width=docx.shared.Inches(3.5))
                whisper_winds(f"Successfully captured {url}")
            progress_bar.update(1)
    section = doc.sections[0]
    footer = section.footer
    footer_paragraph = footer.paragraphs[0]
    footer_paragraph.text = "Generated by NetGazer"
    footer_paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
    doc.save(output_file)

def unravel_scrolls(hosts):
    expanded = []
    for host in hosts:
        try:
            network = ipaddress.ip_network(host, strict=False)
            expanded.extend([str(ip) for ip in network.hosts()])
        except ValueError:
            expanded.append(host)
    return expanded

def embark_quest(input_value, output_file):
    hosts = handle_input(input_value)
    expanded_hosts = unravel_scrolls(hosts)
    print("Starting port scan...")
    progress_bar_scan = tqdm(total=len(expanded_hosts), unit='host', desc="Port scanning", leave=False)
    with ThreadPoolExecutor(max_workers=30) as executor:
        futures = [executor.submit(scout_lands, host, progress_bar_scan) for host in expanded_hosts]
        for future in futures:
            future.result()
    progress_bar_scan.close()
    print("Port scan finished.")
    print("Beginning screen capture...")
    progress_bar_capture = tqdm(total=len(hosts_to_capture), unit='host', desc="Screen capturing", leave=False)
    driver = summon_steeds()
    if output_file.endswith('.docx'):
        capture_visions_docx(driver, output_file, progress_bar_capture)
    elif output_file.endswith('.html'):
        capture_visions_html(driver, output_file, progress_bar_capture)
    else:
        print("Unsupported file format. Please use .docx or .html.")
        driver.quit()
        sys.exit(1)
    progress_bar_capture.close()
    print("Screen capture finished.")
    driver.quit()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python netgazer.py <hosts_file | IP/CIDR/range/domain> <output_file>")
    else:
        embark_quest(sys.argv[1], sys.argv[2])

