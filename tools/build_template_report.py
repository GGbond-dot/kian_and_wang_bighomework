import csv
import hashlib
import re
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from docx.text.paragraph import Paragraph
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'docs/reference/课程报告模板.docx'
OUTPUT = ROOT / 'deliverables/课程报告_kian_wang.docx'
ASSETS = ROOT / 'results/report_template_assets'
SOURCE_HASH = 'a294fc3eee56ca4a9cf848ed4cca4fae07ed8536ffbe2ad0274ab6ebf393bc44'


def trajectory():
    ASSETS.mkdir(parents=True, exist_ok=True)
    picture = Image.new('RGB', (1200, 1050), 'white')
    draw = ImageDraw.Draw(picture)
    font = ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', 26)
    project = lambda x, y: (135 + x * 205, 925 - y * 205)
    for n in range(5):
        draw.line((*project(n, 0), *project(n, 4)), fill='#dddddd', width=1)
        draw.line((*project(0, n), *project(4, n)), fill='#dddddd', width=1)
        draw.text((project(n, 0)[0] - 7, 940), str(n), fill='black', font=font)
        draw.text((85, project(0, n)[1] - 15), str(n), fill='black', font=font)
    world = ET.parse(ROOT / 'src/maze_control/worlds/maze.world')
    for model in world.findall('world/model'):
        box = model.find('link/collision/geometry/box/size')
        if box is not None:
            x, y = map(float, model.findtext('pose').split()[:2])
            sx, sy = map(float, box.text.split()[:2])
            draw.rectangle((*project(x - sx / 2, y + sy / 2), *project(x + sx / 2, y - sy / 2)), fill='#475569')
    with (ROOT / 'results/course_alignment/adaptive.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    points = [project(float(row['x_m']), float(row['y_m'])) for row in rows]
    draw.line(points, fill='#2563eb', width=4)
    for point, label in ((points[0], '起点'), (points[-1], '终点')):
        x, y = point
        draw.ellipse((x - 7, y - 7, x + 7, y + 7), fill='#c2410c')
        draw.text((x + 13, y - 15), label, fill='#c2410c', font=font)
    draw.text((135, 20), '优化模式 Gazebo 实测轨迹   141.1 s   16.9291 m', fill='black', font=font)
    draw.text((1030, 940), 'x / m', fill='black', font=font)
    draw.text((60, 40), 'y / m', fill='black', font=font)
    picture.save(ASSETS / 'trajectory.png')


def replace_text(element, text):
    result = deepcopy(element)
    properties = deepcopy(result.find(qn('w:r') + '/' + qn('w:rPr')))
    for child in list(result):
        if child.tag != qn('w:pPr'):
            result.remove(child)
    run = OxmlElement('w:r')
    if properties is not None:
        for color in properties.findall(qn('w:color')):
            color.set(qn('w:val'), '000000')
        run.append(properties)
    value = OxmlElement('w:t')
    value.set(qn('xml:space'), 'preserve')
    value.text = text
    run.append(value)
    result.append(run)
    return result


def make_table(doc, lines):
    values = [[value.strip() for value in row.strip('|').split('|')] for row in lines]
    values = [row for row in values if not all(re.fullmatch(r'[:\- ]+', value) for value in row)]
    count = len(values[0])
    widths = {2: [1.9, 3.86], 3: [3.25, 0.7, 1.81], 4: [1.6, 0.65, 0.85, 2.66]}[count]
    table = doc.add_table(rows=0, cols=count)
    table.autofit = False
    for column, width in zip(table.columns, widths):
        column.width = Inches(width)
    borders = OxmlElement('w:tblBorders')
    for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        border = OxmlElement('w:' + side)
        for key, value in (('val', 'single'), ('sz', '5'), ('color', 'D9D9D9')):
            border.set(qn('w:' + key), value)
        borders.append(border)
    table._tbl.tblPr.append(borders)
    for row_index, row in enumerate(values):
        cells = table.add_row().cells
        properties = table.rows[-1]._tr.get_or_add_trPr()
        properties.append(OxmlElement('w:cantSplit'))
        if row_index == 0:
            properties.append(OxmlElement('w:tblHeader'))
        for cell, value, width in zip(cells, row, widths):
            cell.width = Inches(width)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            cell.text = value
            margins = OxmlElement('w:tcMar')
            for side in ('top', 'left', 'bottom', 'right'):
                item = OxmlElement('w:' + side)
                item.set(qn('w:w'), '90')
                item.set(qn('w:type'), 'dxa')
                margins.append(item)
            cell._tc.get_or_add_tcPr().append(margins)
            if row_index == 0:
                shading = OxmlElement('w:shd')
                shading.set(qn('w:fill'), 'EEEEEE')
                cell._tc.get_or_add_tcPr().append(shading)
            for paragraph in cell.paragraphs:
                snap = OxmlElement('w:snapToGrid')
                snap.set(qn('w:val'), '0')
                paragraph._p.get_or_add_pPr().append(snap)
                paragraph.paragraph_format.line_spacing = 1.15
                paragraph.paragraph_format.space_after = Pt(2)
                paragraph.paragraph_format.space_before = Pt(2)
                for run in paragraph.runs:
                    run.font.name = 'Times New Roman'
                    run._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'), '宋体')
                    run.font.size = Pt(11)
                    run.font.color.rgb = RGBColor(0, 0, 0)
                    run.bold = row_index == 0
    return table


def main():
    assert hashlib.sha256(REFERENCE.read_bytes()).hexdigest() == SOURCE_HASH
    trajectory()
    doc = Document(REFERENCE)
    body = doc._element.body
    source = list(body)
    heading = source[28]
    normal = source[29]
    titles = [line[3:] for line in (ROOT / 'docs/report.md').read_text().splitlines() if line.startswith('## ')]
    for child in list(body):
        if child.tag != qn('w:sectPr'):
            body.remove(child)
    metadata = {
        14: '第____组  作品名称：地老鼠走迷宫系统',
        15: '提交时间：2026年____月____日',
        16: '学生1  学号：____________  姓名：kian',
        17: '学生2  学号：____________  姓名：wang',
    }
    for index in range(19):
        if index in range(7, 13):
            continue
        element = replace_text(source[index], metadata[index]) if index in metadata else deepcopy(source[index])
        body.insert(len(body) - 1, element)
    body.insert(len(body) - 1, deepcopy(source[19]))
    for title in titles:
        body.insert(len(body) - 1, replace_text(source[20], title))
    body.insert(len(body) - 1, deepcopy(source[26]))
    body.insert(len(body) - 1, deepcopy(source[27]))

    def paragraph(text, kind='normal'):
        element = replace_text(heading if kind in ('heading', 'subheading') else normal, text)
        body.insert(len(body) - 1, element)
        item = Paragraph(element, doc._body)
        snap = OxmlElement('w:snapToGrid')
        snap.set(qn('w:val'), '0')
        item._p.get_or_add_pPr().append(snap)
        if text.startswith('['):
            item.alignment = WD_ALIGN_PARAGRAPH.LEFT
            item.paragraph_format.keep_together = True
        if kind in ('heading', 'subheading'):
            item.paragraph_format.keep_with_next = True
            if kind == 'subheading':
                for run in item.runs:
                    run.font.size = Pt(12)
        if kind in ('code', 'caption', 'image'):
            item.paragraph_format.first_line_indent = Inches(0)
            ppr = item._p.get_or_add_pPr()
            indent = ppr.find(qn('w:ind'))
            if indent is not None:
                indent.attrib.pop(qn('w:firstLineChars'), None)
            item.paragraph_format.line_spacing = 1.0 if kind == 'code' else 1.15
            item.paragraph_format.space_after = Pt(3)
            for run in item.runs:
                run.font.size = Pt(9 if kind == 'code' else 10.5)
                if kind == 'code':
                    run.font.name = 'DejaVu Sans Mono'
            if kind == 'image':
                item.alignment = WD_ALIGN_PARAGRAPH.CENTER
                item.paragraph_format.keep_with_next = True
        return item

    lines = (ROOT / 'docs/report.md').read_text().splitlines()
    i = 0
    code = False
    while i < len(lines):
        line = lines[i]
        if line.startswith('```'):
            code = not code
        elif code:
            paragraph(line, 'code')
        elif line.startswith('### '):
            paragraph(line[4:], 'subheading')
        elif line.startswith('## '):
            paragraph(line[3:], 'heading')
        elif line.startswith('# ') or not line.strip():
            pass
        elif line.startswith('|'):
            table_lines = []
            while i < len(lines) and lines[i].startswith('|'):
                table_lines.append(lines[i])
                i += 1
            make_table(doc, table_lines)
            paragraph('')
            continue
        elif line.startswith('!['):
            path = re.search(r'\]\((.*?)\)', line).group(1)
            item = paragraph('', 'image')
            item.add_run().add_picture(str(ROOT / path), width=Inches(5.3))
        else:
            paragraph(line, 'caption' if line.startswith('图 1') else 'normal')
        i += 1
    OUTPUT.parent.mkdir(exist_ok=True)
    interim = ASSETS / 'working.docx'
    doc.save(interim)
    mutable = {'word/document.xml', 'word/_rels/document.xml.rels', '[Content_Types].xml'}
    with ZipFile(REFERENCE) as original, ZipFile(interim) as generated, ZipFile(OUTPUT, 'w', ZIP_DEFLATED) as final:
        for name in original.namelist():
            final.writestr(name, generated.read(name) if name in mutable else original.read(name))
        for name in generated.namelist():
            if name not in original.namelist():
                final.writestr(name, generated.read(name))
    with ZipFile(REFERENCE) as original, ZipFile(OUTPUT) as final:
        preserved = [name for name in original.namelist() if name not in mutable]
        assert all(original.read(name) == final.read(name) for name in preserved)
    assert hashlib.sha256(REFERENCE.read_bytes()).hexdigest() == SOURCE_HASH
    print(f'{OUTPUT}: {len(preserved)} original package parts preserved')


if __name__ == '__main__':
    main()
