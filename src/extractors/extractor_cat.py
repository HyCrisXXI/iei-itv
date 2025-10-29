import xml.etree.ElementTree as ET
import json


def xmltojson():
    tree = ET.parse("ITV-CAT.xml")
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

    # Write to JSON
    with open("estaciones_cat.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    print("xml a json creado")
xmltojson()
