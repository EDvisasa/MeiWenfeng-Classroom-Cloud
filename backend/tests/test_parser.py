import re
import xml.etree.ElementTree as ET

full_content = """
<thought>
I will read two files.
</thought>
<call_tool name="read_file">
<path>file1.txt</path>
</call_tool>
<call_tool name="read_file">
<path>file2.txt</path>
</call_tool>
"""

matches = re.finditer(r'<call_tool[^>]*>.*?(?:</call_tool>|$)', full_content, re.DOTALL)
tools_to_run = []

for match in matches:
    tool_xml = match.group(0)
    print("MATCH:", tool_xml)
    if not tool_xml.endswith("</call_tool>"):
        tool_xml += "</call_tool>"
    try:
        root = ET.fromstring(tool_xml)
        t_name = root.attrib.get("name")
        print("T_NAME:", t_name)
    except Exception as e:
        print("XML Error:", e)

print("Matches count:", len(list(re.finditer(r'<call_tool[^>]*>.*?(?:</call_tool>|$)', full_content, re.DOTALL))))
