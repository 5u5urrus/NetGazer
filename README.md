NetGazer is designed to efficiently capture screenshots of websites and web servers based on a predefined list of IP addresses and URLs. It then meticulously organizes and presents these results in a Word document table.

<p align="center">
  <img src="netgazer.jpg" width="100%" alt="fuzz Banner">
</p>

Finally you will have EyeWitness that works normally. :) Welcome NetGazer.

<h2>NetGazer: Web Server Screenshot Capturer</h2>

**Overview**

NetGazer is a Python tool designed for pentesters, security researchers, and anyone interested in cyber security field. It accepts hosts in a whole variety of formats - IP ranges, CIDR notations, URLs, fils and captures screenshots of their landing pages. These screenshots are then neatly organized into a Microsoft Word document or an HTML file, providing a visual inventory of web servers within the scanned range. 

**EyeWtiness vs NetGazer**

While EyeWitness is an amazing tool with multitudes of features, NetGazer in some areas is better.
<ul style="list-style-type: '*';">
    <li>NetGazer works faster and more effective. If you submit the same IP range to EyeWitness and NetGazer, you will see NetGazer on average doing the job about 7-10 times faster.</li>
    <li>NetGazer automates the management of browser drivers, which is a significant advantage over EyeWitness that often breaks for those reasons. NetGazer feature ensures that: You always use the latest compatible version of the web driver for your browser, enhancing the reliability of screenshot captures. The tool abstracts away the complexity of manually downloading, setting up, and updating web drivers. </li>
    <li>NetGazer accepts targets in multiple and mixed formats that EyeWitness does not support. Although EyeWitness has its strengths too in supporting nmap xml formats, which my tool does not (yet).</li>
    <li>NetGazer supports output in both html and word documents. EyeWitness does not support word document formats.</li>
    <li>NetGazer does not accumulate screenshots during capture, incorporating data directly into a single final docx or html files, hence presenting a cleaner job. EyeWitness creates a separate folder for all the images.</li>
</ul>

**Usage Examples**
<ul>
    <li><code>python netgazer.py hosts.txt output.docx</code></li>
    <li><code>python netgazer.py 192.168.1.0/24 network_scan.html</code></li>
    <li><code>python netgazer.py 10.10.10.1-10.10.10.255 server_screenshots.docx</code></li>
    <li><code>python netgazer.py 10.10.9-10.1-255 server_screenshots.docx</code></li>
    <li><code>python netgazer.py 8.8.8.8 output.html</code></li>
    <li><code>python netgazer.py hacking.cool output.html</code></li>
</ul>


As seen above, we can submit targets to scan in a variety of ways. As IPs, URLs, CIDR notations, directly specified ranges, etc. or as files (which can contain data also in mixed formats). This is one benefit over EyeWitness, which has a very limited way of processing targets.

**Example 1: python netgazer.py hosts.txt screens.html** <br><br>
hosts.txt:<br>
<img style="width: 30%;" alt="hosts1" src="https://github.com/5u5urrus/NetGazer/assets/165041037/31da8146-3f31-4f6f-89b0-c3b5fdbcf0e7"><br>
Running the command:<br>
<img style="width: 30%;" alt="netgazer2_html3" src="https://github.com/5u5urrus/NetGazer/assets/165041037/870a9446-ebfb-4dc0-81f6-2f06694f89d3"><br>
Resulting HTML page:<br>
<table>
  <tr>
    <td align="center"><img src="https://github.com/5u5urrus/NetGazer/assets/165041037/03c61b71-ec6d-4623-8a04-4d193a201f69" alt="html1" style="width: 70%;"></td>
    <td align="center"><img src="https://github.com/5u5urrus/NetGazer/assets/165041037/ddddc1fd-0938-4b5f-b833-a97f1acf59cd" alt="html2" style="width: 70%;"></td>
  </tr>
</table>

**Example 2: python3 netgazer.py 23.96.35.0/26 screens2.docx** <br><br>
Command running:<br>
<img width="251" alt="docx2" src="https://github.com/5u5urrus/NetGazer/assets/165041037/7e186ccf-3451-451d-b4d9-e2fb7dce0a1a"><br>
Resulting word document:<br> 
<img width="694" alt="docx" src="https://github.com/5u5urrus/NetGazer/assets/165041037/072e5fa0-83eb-47b3-8759-de3abb47c856">

**Example 3: python netgazer.py 1.1.1.1-255 output.docx** <br>
Command running:<br>
<img width="542" alt="Screenshot 2024-06-23 030350" src="https://github.com/5u5urrus/NetGazer/assets/165041037/e89b402a-6106-49d7-b260-b0255eb433ed">



