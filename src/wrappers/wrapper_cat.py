# src/wrappers/wrapper_cat.py
import xml.etree.ElementTree as ET
import json
from pathlib import Path


def xmltojson():
    base_dir = Path(__file__).resolve().parent
    xml_path = base_dir / "ITV-CAT.xml"

    if not xml_path.exists():
        # Helpful error with absolute path for easier debugging
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

    # Write to JSON next to this script
    out_path = base_dir / "CAT.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    print("xml a json creado")
xmltojson()
