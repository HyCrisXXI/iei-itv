# src/wrappers/wrapper_cat.py
import xml.etree.ElementTree as ET
from pathlib import Path

def xmltojson() -> list:
    xml_path = (
        Path(__file__).resolve()
        .parent.parent.parent / "data" / "ITV-CAT.xml"
    )

    if not xml_path.exists():
        raise FileNotFoundError(f"ITV-CAT.xml not found at: {xml_path}")

    tree = ET.parse(xml_path)
    root = tree.getroot()

    if (
        len(root) == 1
        and root[0].tag == "row"
        and all(child.tag == "row" for child in root[0])
    ):
        rows = root[0].findall("row")
    else:
        rows = root.findall("row")

    data = []
    for row in rows:
        record = {}
        # añade elementos tipo (_id, _uuid, etc.)
        record.update(row.attrib)

        for child in row:
            if list(child.attrib.keys()) == ["url"] and (not child.text or not child.text.strip()):
                record[child.tag] = child.attrib["url"]
            elif child.attrib:
                entry = dict(child.attrib)
                if child.text and child.text.strip():
                    entry["text"] = child.text.strip()
                record[child.tag] = entry
            else:
                record[child.tag] = child.text.strip() if child.text else None
        if record:
            data.append(record)

    return data
