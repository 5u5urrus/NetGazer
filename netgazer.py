#!/usr/bin/env python3
"""
Scan for web servers, capture their screens and place them in an HTML or word document table (docx)
Author: Vahe Demirkhanyan
"""

import base64
import os
import sys
import argparse
import ipaddress
import re
import socket
import time
import logging
from itertools import product
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path
from typing import List, Tuple, Optional, Iterator, Set, Dict, Union

import docx
from docx.shared import Inches, Pt
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.enum.table import WD_ALIGN_VERTICAL
from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.firefox import GeckoDriverManager
from tqdm import tqdm
from urllib.parse import urlparse

# Constants
WEB_HTTPS_PORTS: frozenset[int] = frozenset({443, 8443, 10443, 9443})
DEFAULT_PORTS: List[int] = [80, 443]
DEFAULT_TIMEOUT: int = 30
MAX_PORT_WORKERS: int = 50
MAX_PORT_CHECK_WORKERS: int = 10
PORT_CHECK_TIMEOUT: int = 3

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def is_ipv6(addr: str) -> bool:
    try:
        ipaddress.IPv6Address(addr)
        return True
    except ValueError:
        return False


def split_host_port_maybe(s: str) -> Tuple[str, Optional[int]]:
    """
    Best-effort split of 'host[:port]' that is safe for IPv6.
    - Supports '[IPv6]:port'
    - If exactly one colon and the right side is digits, treat as host:port
    - Otherwise, return (s, None)
    """
    s = s.strip()

    if s.startswith('['):
        # [IPv6] or [IPv6]:port
        if ']' in s:
            end = s.index(']')
            host = s[1:end]
            rest = s[end + 1:]
            if rest.startswith(':'):
                port_part = rest[1:]
                if port_part.isdigit():
                    return host, int(port_part)
            return host, None

    # Non-bracketed: treat single-colon + digits as port
    if s.count(':') == 1:
        left, right = s.rsplit(':', 1)
        if right.isdigit():
            return left, int(right)

    return s, None


class NetworkScanner:
    """Handles host parsing and network operations."""

    @staticmethod
    def parse_hosts(input_value: str) -> List[str]:
        """Parse input into list of hosts."""
        input_path = Path(input_value)
        return (NetworkScanner._parse_hosts_file(input_path)
                if input_path.is_file()
                else NetworkScanner._parse_single_input(input_value))

    @staticmethod
    def _parse_hosts_file(filepath: Path) -> List[str]:
        """Parse hosts from file."""
        hosts = []
        try:
            with filepath.open('r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if line and not line.startswith('#'):
                        try:
                            hosts.extend(NetworkScanner._parse_single_input(line))
                        except Exception as e:
                            logger.warning(f"Skipping invalid line {line_num} in {filepath}: {e}")
        except IOError as e:
            logger.error(f"Error reading file {filepath}: {e}")
            sys.exit(1)
        return hosts

    @staticmethod
    def _parse_single_input(text: str) -> List[str]:
        """
        Robustly parse a single host/range/CIDR/URL input.
        - Properly handles URLs (http/https/ftp etc.), stripping path/query/fragment.
        - Keeps IPv6 intact (supports [v6]:port syntax).
        - Detects CIDR/ranges.
        """
        raw = text.strip()

        # If it looks like a URL, use urlparse to extract the authority
        host_candidate = raw
        if '://' in raw:
            u = urlparse(raw)
            host_candidate = u.netloc or u.path
        else:
            # Support protocol-relative //host
            if raw.startswith('//'):
                u = urlparse(raw)
                host_candidate = u.netloc or u.path

        # Strip any trailing path if user pasted host/path by mistake
        host_candidate = host_candidate.split('/')[0]

        # Remove surrounding [] for IPv6 for internal handling
        if host_candidate.startswith('[') and ']' in host_candidate:
            host_inner = host_candidate[1:host_candidate.index(']')]
            rest = host_candidate[host_candidate.index(']') + 1:]
            if rest.startswith(':'):
                # keep port with host string, let PortScanner handle it
                host_candidate = f"{host_inner}{rest}"
            else:
                host_candidate = host_inner

        # Try exact IP first (v4/v6) – if this succeeds, it's a single host
        try:
            ipaddress.ip_address(host_candidate)
            return [host_candidate]
        except ValueError:
            pass

        # CIDR?
        if '/' in host_candidate:
            return NetworkScanner._expand_cidr(host_candidate)

        # Range?
        if '-' in host_candidate:
            return NetworkScanner._expand_range(host_candidate)

        # Hostname or host:port – keep as-is
        return [host_candidate]

    @staticmethod
    def _expand_cidr(cidr_str: str) -> List[str]:
        """Expand CIDR notation to IP list. Correctly handles /31 and /127."""
        try:
            network = ipaddress.ip_network(cidr_str, strict=False)
            if network.num_addresses == 1:
                return [str(network.network_address)]
            return [str(ip) for ip in network.hosts()]
        except ValueError as e:
            logger.error(f"Invalid CIDR notation '{cidr_str}': {e}")
            return []

    @staticmethod
    def _expand_range(range_str: str) -> List[str]:
        """Expand IP ranges like 192.168.1.1-10 or 192.168.1-2.1-10."""
        dash_count = range_str.count('-')
        if dash_count == 1:
            return NetworkScanner._expand_simple_range(range_str)
        elif dash_count > 1:
            return NetworkScanner._expand_complex_range(range_str)
        return []

    @staticmethod
    def _expand_simple_range(range_str: str) -> List[str]:
        """Expand simple range like 192.168.1.1-10."""
        try:
            start_ip_str, end_str = range_str.split('-', 1)

            # If end doesn't contain dots, append to start's base
            if '.' not in end_str:
                base = '.'.join(start_ip_str.split('.')[:-1])
                end_ip_str = f"{base}.{end_str}"
            else:
                end_ip_str = end_str

            start_ip = ipaddress.ip_address(start_ip_str)
            end_ip = ipaddress.ip_address(end_ip_str)

            return [str(ipaddress.ip_address(ip_int))
                    for ip_int in range(int(start_ip), int(end_ip) + 1)]
        except (ValueError, ipaddress.AddressValueError) as e:
            logger.error(f"Invalid IP range '{range_str}': {e}")
            return []

    @staticmethod
    def _expand_complex_range(range_str: str) -> List[str]:
        """Expand complex ranges like 192.168.1-2.1-10."""
        try:
            octet_parts = range_str.split('.')
            if len(octet_parts) != 4:
                raise ValueError("Invalid IP format")

            octet_ranges = []
            for part in octet_parts:
                if '-' in part:
                    start_s, end_s = part.split('-', 1)
                    start_val, end_val = int(start_s), int(end_s)
                    if not (0 <= start_val <= 255 and 0 <= end_val <= 255):
                        raise ValueError("Octet out of range")
                    octet_ranges.append(range(start_val, end_val + 1))
                else:
                    val = int(part)
                    if not (0 <= val <= 255):
                        raise ValueError("Octet out of range")
                    octet_ranges.append([val])

            return ['.'.join(map(str, combo)) for combo in product(*octet_ranges)]

        except (ValueError, IndexError) as e:
            logger.error(f"Invalid complex range '{range_str}': {e}")
            return []


class PortScanner:
    """Handles port scanning operations."""

    @staticmethod
    def check_port(host: str, port: int, timeout: int = PORT_CHECK_TIMEOUT) -> bool:
        """Fast port connectivity check (IPv4/IPv6)."""
        try:
            with socket.create_connection((host, port), timeout=timeout):
                tqdm.write(f"Port {port} is open on {host}")
                return True
        except OSError:
            return False

    @staticmethod
    def scan_host(host: str, ports: List[int], progress_bar: tqdm) -> Optional[Tuple[str, List[Tuple[int, str]]]]:
        """Scan all ports for a single host. Supports [IPv6]:port and host:port syntaxes."""
        # Handle explicit port in hostname safely (IPv6-aware)
        h, explicit_port = split_host_port_maybe(host)
        if explicit_port is not None:
            scheme = 'https' if explicit_port in WEB_HTTPS_PORTS else 'http'
            if PortScanner.check_port(h, explicit_port):
                progress_bar.update(1)
                return (f"{h}:{explicit_port}", [(explicit_port, scheme)])
            progress_bar.update(1)
            return None

        # Scan multiple ports concurrently
        open_ports = []
        max_workers = min(len(ports), MAX_PORT_CHECK_WORKERS)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_port = {
                executor.submit(PortScanner.check_port, h, port): port
                for port in ports
            }

            for future in as_completed(future_to_port):
                port = future_to_port[future]
                try:
                    if future.result():
                        scheme = 'https' if port in WEB_HTTPS_PORTS else 'http'
                        open_ports.append((port, scheme))
                except Exception as e:
                    logger.debug(f"Port check failed for {h}:{port}: {e}")

        progress_bar.update(1)
        return (h, open_ports) if open_ports else None


class WebDriverManager:
    """Manages Selenium WebDriver operations."""

    _driver_cache: Optional[webdriver.Firefox] = None
    _driver_options_cache: Optional[Options] = None

    @classmethod
    def _get_cached_options(cls) -> Options:
        """Get cached Firefox options to avoid recreating them."""
        if cls._driver_options_cache is None:
            options = Options()
            options.add_argument("--headless")

            # Firefox-specific preferences
            prefs = {
                "dom.webdriver.enabled": False,  # hide automation flag
                "media.volume_scale": "0.0",     # mute audio
            }
            for pref, value in prefs.items():
                options.set_preference(pref, value)

            # Accept self-signed/invalid certs to avoid interstitials
            options.set_capability("acceptInsecureCerts", True)

            cls._driver_options_cache = options

        return cls._driver_options_cache

    @classmethod
    def create_driver(cls, timeout: int = DEFAULT_TIMEOUT) -> webdriver.Firefox:
        """Create configured Firefox WebDriver with caching."""
        if cls._driver_cache is None:
            options = cls._get_cached_options()

            try:
                service = FirefoxService(executable_path=GeckoDriverManager().install())
                cls._driver_cache = webdriver.Firefox(service=service, options=options)
                cls._driver_cache.set_page_load_timeout(timeout)

                # Deterministic viewport
                try:
                    cls._driver_cache.set_window_size(1920, 1080)
                except Exception:
                    pass

                # Anti-detection spoof for navigator.webdriver
                try:
                    cls._driver_cache.execute_script(
                        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                    )
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Failed to create WebDriver: {e}")
                sys.exit(1)

        return cls._driver_cache

    @classmethod
    def cleanup_driver(cls) -> None:
        """Clean up cached driver."""
        if cls._driver_cache:
            try:
                cls._driver_cache.quit()
            except Exception:
                pass
            cls._driver_cache = None

    @staticmethod
    def capture_screenshot(
        driver: webdriver.Firefox,
        url: str,
        follow_redirects: bool = False,  # retained for compatibility (labeling only)
        timeout: int = DEFAULT_TIMEOUT,
        full_page: bool = False
    ) -> Tuple[bool, Optional[bytes], Optional[str], str]:
        """Capture screenshot of a web page."""
        try:
            driver.get(url)

            # Smart wait configuration
            js_wait_time = min(max(timeout // 4, 3), 15)

            # Initial wait for basic page load
            time.sleep(2)

            # Optimized waiting strategy
            try:
                # Wait for document ready state
                WebDriverWait(driver, js_wait_time).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )

                # Wait for Angular apps (non-blocking)
                try:
                    driver.execute_script(
                        "return typeof window.getAllAngularTestabilities === 'undefined' || "
                        "window.getAllAngularTestabilities().every(function(t) { return t.isStable(); })"
                    )
                except Exception:
                    pass  # Not Angular or timeout

                # Wait for some meaningful content (don’t be too strict)
                WebDriverWait(driver, js_wait_time).until(
                    lambda d: len(d.find_element(By.TAG_NAME, "body").text.strip()) >= 0
                )
            except TimeoutException:
                # Fallback wait
                time.sleep(min(js_wait_time, 5))

            body_text = driver.find_element(By.TAG_NAME, "body").text.strip()
            if len(body_text) < 50 and len(driver.page_source) < 1000:
                tqdm.write(f"Warning: {url} appears to have minimal content after {js_wait_time}s wait")

            final_url = driver.current_url if follow_redirects else url
            if full_page and hasattr(driver, "get_full_page_screenshot_as_png"):
                png_data = driver.get_full_page_screenshot_as_png()
            else:
                png_data = driver.get_screenshot_as_png()

            base64_data = base64.b64encode(png_data).decode('utf-8')

            return True, png_data, base64_data, final_url

        except WebDriverException as e:
            tqdm.write(f"WebDriver error for {url}: {e}")
            return False, None, None, url
        except Exception as e:
            tqdm.write(f"Failed to capture screenshot for {url}: {e}")
            return False, None, None, url


class DocumentGenerator:
    """Handles document generation in HTML and DOCX formats."""

    # HTML template as class constant for better performance
    HTML_TEMPLATE = """<html>
<head>
  <title>Web Server Screenshots</title>
  <meta charset='UTF-8'>
  <style>
    body {{ font-family: Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 20px; color: #333; }}
    h1 {{ text-align: center; margin-bottom: 30px; }}
    table {{ 
      margin: 0 auto; 
      border-collapse: collapse; 
      width: 90%; 
      max-width: 1200px; 
      box-shadow: 0 2px 5px rgba(0,0,0,0.15); 
      table-layout: fixed;
    }}
    th, td {{ 
      border: 1px solid #ccc; 
      padding: 12px; 
      text-align: center; 
      vertical-align: top;
    }}
    th {{ background-color: #e0e0e0; }}
    tr:nth-child(even) {{ background-color: #fafafa; }}
    th:first-child, td:first-child {{ 
      width: 25%; 
      min-width: 200px; 
      max-width: 300px;
    }}
    th:last-child, td:last-child {{ width: 75%; }}
    .url-text {{ 
      word-wrap: break-word; 
      word-break: break-all; 
      overflow-wrap: break-word; 
      hyphens: auto; 
      line-height: 1.4; 
      font-size: 12px; 
      text-align: left; 
      padding: 8px;
    }}
    img {{ 
      max-width: 100%; 
      height: auto; 
      border-radius: 5px; 
      display: block; 
      margin: 0 auto;
    }}
    @media (max-width: 768px) {{
      table {{ width: 100%; }}
      th:first-child, td:first-child {{ width: 30%; }}
      th:last-child, td:last-child {{ width: 70%; }}
      .url-text {{ font-size: 10px; }}
    }}
  </style>
</head>
<body>
  <h1>Web Server Screenshots</h1>
  <table>
    <tr><th>Web Request Info</th><th>Web Screenshot</th></tr>
{rows}
  </table>
</body>
</html>"""

    @staticmethod
    def build_url(host: str, port: int, scheme: str) -> str:
        """Build clean URL from components, wrapping IPv6 in [] as needed."""
        host_for_url = f"[{host}]" if is_ipv6(host) else host
        is_standard_port = (port == 80 and scheme == 'http') or (port == 443 and scheme == 'https')
        return f"{scheme}://{host_for_url}" if is_standard_port else f"{scheme}://{host_for_url}:{port}"

    @staticmethod
    def _process_screenshot_batch(
        driver: webdriver.Firefox,
        host_port_batches: List[Tuple[str, int, str]],
        progress_bar: tqdm,
        follow_redirects: bool,
        timeout: int,
        full_page: bool
    ) -> List[Tuple[str, str]]:
        """Process a batch of screenshots and return results."""
        items = []

        for host, port, scheme in host_port_batches:
            url = DocumentGenerator.build_url(host, port, scheme)

            success, _, b64_data, final_url = WebDriverManager.capture_screenshot(
                driver, url, follow_redirects, timeout, full_page
            )

            if success and b64_data:
                display_text = url if url == final_url else f"{url} → {final_url}"
                items.append((display_text, b64_data))
                whisper_winds(f"Successfully captured {url}" +
                              (f" (redirected to {final_url})" if url != final_url else ""))

            progress_bar.update(1)

        return items

    @classmethod
    def generate_html(
        cls,
        driver: webdriver.Firefox,
        output_file: str,
        hosts_to_capture: List[Tuple[str, List[Tuple[int, str]]]],
        progress_bar: tqdm,
        follow_redirects: bool = False,
        timeout: int = DEFAULT_TIMEOUT,
        full_page: bool = False
    ) -> None:
        """Generate HTML document with screenshots."""
        # Flatten host/port combinations for batch processing
        host_port_batches = [
            (host, port, scheme)
            for host, port_scheme_list in hosts_to_capture
            for port, scheme in port_scheme_list
        ]

        items = cls._process_screenshot_batch(
            driver, host_port_batches, progress_bar, follow_redirects, timeout, full_page
        )

        # Generate HTML content
        rows = [
            f"    <tr><td><span class='url-text'>{url}</span></td>"
            f"<td><img src='data:image/png;base64,{b64}' alt='Screenshot of {url}'></td></tr>"
            for url, b64 in items
        ]

        html_content = cls.HTML_TEMPLATE.format(rows='\n'.join(rows))

        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
        except IOError as e:
            logger.error(f"Failed to write HTML file {output_file}: {e}")
            sys.exit(1)

    @staticmethod
    def generate_docx(
        driver: webdriver.Firefox,
        output_file: str,
        hosts_to_capture: List[Tuple[str, List[Tuple[int, str]]]],
        progress_bar: tqdm,
        follow_redirects: bool = False,
        timeout: int = DEFAULT_TIMEOUT,
        full_page: bool = False
    ) -> None:
        """Generate DOCX document with screenshots."""
        try:
            doc = docx.Document()

            # Add title
            title_paragraph = doc.add_paragraph()
            title_paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
            title_run = title_paragraph.add_run("Web Server Screenshots")
            title_run.bold = True
            title_run.font.size = Pt(24)
            doc.add_paragraph("")

            # Create table
            table = doc.add_table(rows=1, cols=2)
            table.style = 'Light Grid Accent 1'
            table.autofit = False

            # Set column widths
            table.columns[0].width = Inches(2.0)  # URL column
            table.columns[1].width = Inches(4.0)  # Image column

            # Set header
            hdr_cells = table.rows[0].cells
            hdr_cells[0].text = 'Web Request Info'
            hdr_cells[1].text = 'Web Screenshot'

            for cell in hdr_cells:
                cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP
                cell.paragraphs[0].alignment = WD_PARAGRAPH_ALIGNMENT.LEFT

            # Add screenshots
            for host, port_scheme_list in hosts_to_capture:
                for port, scheme in port_scheme_list:
                    url = DocumentGenerator.build_url(host, port, scheme)

                    success, png_data, _, final_url = WebDriverManager.capture_screenshot(
                        driver, url, follow_redirects, timeout, full_page
                    )

                    if not success or not png_data:
                        progress_bar.update(1)
                        continue

                    # Add table row
                    row_cells = table.add_row().cells
                    url_cell = row_cells[0]

                    display_text = url if url == final_url else f"{url} → {final_url}"
                    url_cell.text = display_text
                    url_cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP
                    url_cell.paragraphs[0].alignment = WD_PARAGRAPH_ALIGNMENT.LEFT

                    # Add screenshot - optimize BytesIO usage
                    with BytesIO(png_data) as img_buf:
                        pic_run = row_cells[1].paragraphs[0].add_run()
                        pic_run.add_picture(img_buf, width=Inches(4.0))

                    whisper_winds(f"Successfully captured {url}" +
                                  (f" (redirected to {final_url})" if url != final_url else ""))
                    progress_bar.update(1)

            # Add footer
            section = doc.sections[0]
            footer = section.footer
            footer_paragraph = footer.paragraphs[0]
            footer_paragraph.text = "Generated by NetGazer"
            footer_paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

            doc.save(output_file)

        except Exception as e:
            logger.error(f"Failed to generate DOCX file {output_file}: {e}")
            sys.exit(1)


def comma_separated_ints(value: str) -> List[int]:
    """Parse comma-separated port list with validation."""
    try:
        ports = [int(p.strip()) for p in value.split(',') if p.strip()]
        if not ports:
            raise ValueError("No valid ports provided")

        invalid_ports = [p for p in ports if not 1 <= p <= 65535]
        if invalid_ports:
            raise ValueError(f"Ports out of valid range (1-65535): {invalid_ports}")

        return sorted(set(ports))  # Remove duplicates and sort
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid port specification: {e}")


def check_dependencies() -> None:
    """Check for required libraries with detailed error messages."""
    required_libs = {
        'selenium': 'selenium',
        'docx': 'python-docx',
        'webdriver_manager': 'webdriver-manager',
        'tqdm': 'tqdm'
    }
    missing = []

    for import_name, package_name in required_libs.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append(package_name)

    if missing:
        print(f"Missing required libraries: {', '.join(missing)}")
        print(f"Install with: pip install {' '.join(missing)}")
        sys.exit(1)


def initial_checks() -> None:
    """Perform comprehensive initial system checks."""
    # Check if running as root (Unix-like systems)
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        print("Run as a regular user, not root.")
        sys.exit(1)

    # Check write permissions in current directory
    test_file = Path.cwd() / "temp_test_file"
    try:
        test_file.write_text("test")
        test_file.unlink()
    except (IOError, OSError, PermissionError):
        print("No write permissions in current directory.")
        sys.exit(1)

    # Check dependencies
    check_dependencies()


def whisper_winds(text: str) -> None:
    """Print colored success message with ANSI codes."""
    tqdm.write(f"\033[92m{text}\033[0m")


def expand_hosts(hosts: List[str]) -> List[str]:
    """Expand network ranges in host list with deduplication (correct /31, /127)."""
    expanded_hosts = []
    seen = set()

    for host in hosts:
        # First, try exact IP; if so, just add it
        try:
            ipaddress.ip_address(host)
            if host not in seen:
                expanded_hosts.append(host)
                seen.add(host)
            continue
        except ValueError:
            pass

        # Next, try network
        try:
            network = ipaddress.ip_network(host, strict=False)
            if network.num_addresses == 1:
                ip_str = str(network.network_address)
                if ip_str not in seen:
                    expanded_hosts.append(ip_str)
                    seen.add(ip_str)
            else:
                for ip in network.hosts():
                    ip_str = str(ip)
                    if ip_str not in seen:
                        expanded_hosts.append(ip_str)
                        seen.add(ip_str)
            continue
        except ValueError:
            pass

        # Else treat as hostname
        if host not in seen:
            expanded_hosts.append(host)
            seen.add(host)

    return expanded_hosts


def perform_port_scan(hosts: List[str], ports: List[int]) -> List[Tuple[str, List[Tuple[int, str]]]]:
    """Perform optimized port scanning on all hosts."""
    hosts_to_capture = []

    print(f"Starting optimized port scan on {len(hosts)} host(s) with ports {ports}...")

    with tqdm(total=len(hosts), unit='host', desc="Port scanning", leave=False) as pbar:
        with ThreadPoolExecutor(max_workers=MAX_PORT_WORKERS) as executor:
            futures = {
                executor.submit(PortScanner.scan_host, host, ports, pbar): host
                for host in hosts
            }

            for future in as_completed(futures):
                host = futures[future]
                try:
                    result = future.result()
                    if result:
                        hosts_to_capture.append(result)
                except Exception as e:
                    logger.error(f"Error during port scan for {host}: {e}")

    print("Port scan finished.")
    return hosts_to_capture


def perform_screenshot_capture(
    hosts_to_capture: List[Tuple[str, List[Tuple[int, str]]]],
    output_file: str,
    follow_redirects: bool,
    timeout: int,
    full_page: bool
) -> None:
    """Perform screenshot capture phase with improved error handling."""
    # Calculate total screenshots
    total_screenshots = sum(len(port_list) for _, port_list in hosts_to_capture)

    js_wait_time = min(max(timeout // 4, 3), 15)
    redirect_text = " (following redirects)" if follow_redirects else ""
    full_page_text = " with full-page capture" if full_page else ""
    print(f"Beginning screen capture with {timeout}s page timeout, "
          f"{js_wait_time}s JavaScript wait{redirect_text}{full_page_text}...")

    # Screenshot capture phase
    driver = WebDriverManager.create_driver(timeout)
    try:
        output_path = Path(output_file)
        with tqdm(total=total_screenshots, unit='screenshot', desc="Screen capturing", leave=False) as pbar:
            if output_path.suffix.lower() == '.docx':
                DocumentGenerator.generate_docx(
                    driver, output_file, hosts_to_capture, pbar, follow_redirects, timeout, full_page
                )
            else:
                DocumentGenerator.generate_html(
                    driver, output_file, hosts_to_capture, pbar, follow_redirects, timeout, full_page
                )

        print("Screen capture finished.")

    finally:
        WebDriverManager.cleanup_driver()


def validate_args(args: argparse.Namespace) -> None:
    """Validate command line arguments."""
    # Validate output file extension
    output_path = Path(args.output_file)
    if output_path.suffix.lower() not in ['.html', '.docx']:
        print("Error: Output file must have .html or .docx extension")
        sys.exit(1)

    # Validate timeout
    if args.timeout <= 0:
        print("Error: Timeout must be positive")
        sys.exit(1)

    # Check if output directory is writable
    output_dir = output_path.parent
    if not output_dir.exists():
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError):
            print(f"Error: Cannot create output directory {output_dir}")
            sys.exit(1)

    if not os.access(output_dir, os.W_OK):
        print(f"Error: No write permission for output directory {output_dir}")
        sys.exit(1)


def main() -> None:
    """Main execution function with improved error handling."""
    parser = argparse.ArgumentParser(
        description='Scan and capture web server screenshots.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s hosts.txt results.html
  %(prog)s 192.168.1.0/24 scan.docx --timeout 45 --redirect
  %(prog)s targets.txt output.html --ports 8080,8443,9000
  %(prog)s example.com results.html --ports 80,443,8080,8443,9090
        """
    )

    parser.add_argument('input', help='Input hosts file, CIDR notation, or IP range / URL')
    parser.add_argument('output_file', help='Output file name (.docx or .html)')
    parser.add_argument('--timeout', '-t', type=int, default=DEFAULT_TIMEOUT,
                       help=f'Page load timeout in seconds (default: {DEFAULT_TIMEOUT})')
    parser.add_argument('--redirect', '-r', action='store_true',
                       help='Label final destination if page redirects (browser still follows redirects).')
    parser.add_argument('--ports', '-p', type=comma_separated_ints, default=DEFAULT_PORTS,
                       help='Comma-separated list of ports to scan (default: 80,443)')
    parser.add_argument('--full-page', action='store_true',
                       help='Capture full-page screenshots (Firefox-only feature).')

    args = parser.parse_args()

    # Perform initial checks
    initial_checks()

    # Validate arguments
    validate_args(args)

    # Parse and expand hosts
    hosts = NetworkScanner.parse_hosts(args.input)
    if not hosts:
        print("No valid hosts found to scan.")
        sys.exit(1)

    expanded_hosts = expand_hosts(hosts)
    if not expanded_hosts:
        print("No hosts to scan after expansion.")
        sys.exit(1)

    # Perform port scanning
    hosts_to_capture = perform_port_scan(expanded_hosts, args.ports)

    if not hosts_to_capture:
        print("No web servers found on scanned hosts.")
        return

    # Perform screenshot capture
    perform_screenshot_capture(
        hosts_to_capture, args.output_file, args.redirect, args.timeout, args.full_page
    )


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python netgazer.py <hosts_file | IP/CIDR/range/domain/URL> <output_file> [--timeout SECONDS] [--redirect] [--full-page] [--ports PORT1,PORT2,...]")
        print("Examples:")
        print("  python netgazer.py hosts.txt results.html")
        print("  python netgazer.py 192.168.1.0/24 scan.docx --timeout 45 --redirect --full-page")
        print("  python netgazer.py targets.txt output.html --ports 8080,8443,9000")
        print("  python netgazer.py example.com results.html --ports 80,443,8080,8443,9090")
    else:
        main()
