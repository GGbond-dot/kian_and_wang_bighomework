import re
import csv
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from PIL import Image, ImageDraw, ImageFont

from offline_sim import read_walls

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'deliverables'
FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'


def diagram(path, labels):
    picture = Image.new('RGB', (1500, 360), 'white')
    draw = ImageDraw.Draw(picture)
    font = ImageFont.truetype(FONT, 30)
    for i, label in enumerate(labels):
        x = 25 + i * 375
        draw.rounded_rectangle((x, 85, x + 325, 245), radius=12, fill='#f3f4f6', outline='#555555', width=3)
        lines = label.split('\n')
        for j, line in enumerate(lines):
            box = draw.textbbox((0, 0), line, font=font)
            draw.text((x + (325 - box[2]) / 2, 125 + j * 44), line, fill='black', font=font)
        if i < len(labels) - 1:
            draw.line((x + 330, 165, x + 367, 165), fill='#555555', width=4)
            draw.polygon([(x + 367, 165), (x + 355, 157), (x + 355, 173)], fill='#555555')
    picture.save(path)


def trajectory(path):
    picture = Image.new('RGB', (1400, 1200), 'white')
    draw = ImageDraw.Draw(picture)
    font = ImageFont.truetype(FONT, 32)
    small = ImageFont.truetype(FONT, 26)
    project = lambda x, y: (120 + (x + 0.25) * 220, 1080 - (y + 0.25) * 220)
    for n in range(5):
        a = project(n, 0)
        b = project(n, 4)
        draw.line((*a, *b), fill='#e5e7eb', width=2)
        a = project(0, n)
        b = project(4, n)
        draw.line((*a, *b), fill='#e5e7eb', width=2)
        draw.text((project(n, 0)[0] - 8, 1065), str(n), font=small, fill='black')
    for x0, y0, x1, y1 in read_walls():
        a, b = project(x0, y1), project(x1, y0)
        draw.rectangle((*a, *b), fill='#475569')
    for index, (name, color) in enumerate((('fixed', '#ea580c'), ('adaptive', '#2563eb'))):
        source = ROOT / 'results/gazebo' / (name + '.csv')
        if source.exists():
            with source.open() as stream:
                rows = list(csv.DictReader(stream))
            points = [project(float(row['x_m']), float(row['y_m'])) for row in rows[::3]]
            if len(points) > 1:
                draw.line(points, fill=color, width=5)
            draw.text((1130, 210 + index * 70), '固定速度' if name == 'fixed' else '自适应速度', font=small, fill=color)
    draw.text((110, 20), '官方 Burger 的 Gazebo 实测里程计轨迹', font=font, fill='black')
    draw.text((110, 1140), '墙体取自 maze.world    轨迹取自原始 CSV    坐标单位 m', font=small, fill='black')
    picture.save(path)


def cell_format(cell, header=False):
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    properties = cell._tc.get_or_add_tcPr()
    margins = OxmlElement('w:tcMar')
    for side in ('top', 'left', 'bottom', 'right'):
        item = OxmlElement('w:' + side)
        item.set(qn('w:w'), '100')
        item.set(qn('w:type'), 'dxa')
        margins.append(item)
    properties.append(margins)
    if header:
        shading = OxmlElement('w:shd')
        shading.set(qn('w:fill'), 'E7EDF4')
        properties.append(shading)
    for paragraph in cell.paragraphs:
        paragraph.paragraph_format.space_after = Pt(2)
        for run in paragraph.runs:
            run.font.size = Pt(10)
            run.bold = header


def table(doc, rows):
    entries = [[part.strip() for part in line.strip().strip('|').split('|')] for line in rows]
    entries = [row for row in entries if not all(re.fullmatch(r'[:\- ]+', item) for item in row)]
    item = doc.add_table(rows=0, cols=len(entries[0]))
    item.alignment = WD_TABLE_ALIGNMENT.CENTER
    item.autofit = False
    widths = [6.85 / len(entries[0])] * len(entries[0])
    if len(entries[0]) == 2:
        widths = [1.35, 5.5]
    for column, width in zip(item.columns, widths):
        column.width = Inches(width)
    for row_index, row in enumerate(entries):
        cells = item.add_row().cells
        for index, (cell, value) in enumerate(zip(cells, row)):
            cell.width = Inches(widths[index])
            cell.text = value
            cell_format(cell, row_index == 0)
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.keep_with_next = row_index < len(entries) - 1 and (len(entries) <= 4 or row_index == 0 or row_index == len(entries) - 2)
        if row_index == 0:
            repeat = OxmlElement('w:tblHeader')
            item.rows[0]._tr.get_or_add_trPr().append(repeat)
    borders = OxmlElement('w:tblBorders')
    for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        edge = OxmlElement('w:' + side)
        edge.set(qn('w:val'), 'single')
        edge.set(qn('w:sz'), '5')
        edge.set(qn('w:color'), 'D9D9D9')
        borders.append(edge)
    item._tbl.tblPr.append(borders)
    doc.add_paragraph().paragraph_format.space_after = Pt(1)


def main():
    OUTPUT.mkdir(exist_ok=True)
    qa = ROOT / 'results' / 'report_assets'
    qa.mkdir(parents=True, exist_ok=True)
    diagram(qa / 'architecture.png', ['Gazebo 仿真\n激光与里程计', '感知处理\n分区墙距', '闭环控制\n左墙状态机', '速度输出\n轨迹与记录'])
    diagram(qa / 'states.png', ['FOLLOW\n墙距与开口判断', 'ADVANCE\n越过墙角', 'TURN\n里程计闭环转向', 'CLEAR\n通过后回到跟随'])
    doc = Document()
    for border in doc.styles._element.xpath('.//w:pBdr'):
        border.getparent().remove(border)
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(0.75)
    section.bottom_margin = Inches(0.7)
    section.left_margin = section.right_margin = Inches(0.825)
    for name in ('Normal', 'Title', 'Heading 1', 'Heading 2', 'Heading 3'):
        style = doc.styles[name]
        style.font.name = 'Noto Sans CJK SC'
        style.font.color.rgb = RGBColor(0, 0, 0)
        style._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'), 'Noto Sans CJK SC')
    doc.styles['Normal'].font.size = Pt(11)
    doc.styles['Normal'].paragraph_format.line_spacing = 1.25
    doc.styles['Normal'].paragraph_format.space_after = Pt(7)
    doc.styles['Title'].font.size = Pt(22)
    doc.styles['Heading 1'].font.size = Pt(15)
    doc.styles['Heading 2'].font.size = Pt(12)
    lines = (ROOT / 'docs/report.md').read_text().splitlines()
    i = 0
    diagram_index = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('```'):
            language = line[3:]
            code = []
            i += 1
            while i < len(lines) and not lines[i].startswith('```'):
                code.append(lines[i])
                i += 1
            if language == 'mermaid':
                image = 'architecture.png' if diagram_index == 0 else 'states.png'
                doc.add_picture(str(qa / image), width=Inches(6.8))
                diagram_index += 1
            else:
                paragraph = doc.add_paragraph()
                paragraph.paragraph_format.line_spacing = 1.0
                for j, code_line in enumerate(code):
                    run = paragraph.add_run(code_line + ('\n' if j < len(code) - 1 else ''))
                    run.font.name = 'DejaVu Sans Mono'
                    run.font.size = Pt(8)
        elif line.startswith('|'):
            rows = []
            while i < len(lines) and lines[i].startswith('|'):
                rows.append(lines[i])
                i += 1
            table(doc, rows)
            continue
        elif line.startswith('# '):
            doc.add_paragraph(line[2:], style='Title')
        elif line.startswith('### '):
            doc.add_heading(line[4:], 2)
        elif line.startswith('## '):
            doc.add_heading(line[3:], 1)
        elif line.strip():
            text = re.sub(r'\*\*(.*?)\*\*', r'\1', line.strip())
            doc.add_paragraph(text)
        i += 1
    if (ROOT / 'results/gazebo/adaptive.json').exists():
        trajectory(qa / 'gazebo_trajectory.png')
        doc.add_heading('Gazebo 实测轨迹', 1)
        doc.add_picture(str(qa / 'gazebo_trajectory.png'), width=Inches(6.8))
        doc.add_paragraph('同一迷宫和起点下的固定速度与自适应速度轨迹，数据来源见 results/gazebo 原始 CSV。')
    for name in ('point', 'adaptive'):
        path = ROOT / 'results/gazebo_gui' / (name + '_screen.png')
        final = ROOT / 'results/gazebo_gui_final' / (name + '_screen.png')
        if name == 'adaptive' and final.exists():
            path = final
        if path.exists():
            doc.add_heading('实测画面 ' + ('点控制' if name == 'point' else '迷宫出口'), 1)
            doc.add_picture(str(path), width=Inches(6.2))
            doc.paragraphs[-1].alignment = 1
            doc.paragraphs[-1].paragraph_format.keep_with_next = True
            doc.add_paragraph('图为 Docker 内官方 Burger 在 Gazebo 和 RViz 中的实际运行截图。')
    footer = section.footer.paragraphs[0]
    footer.alignment = 1
    footer.add_run('S0610350  地老鼠走迷宫系统    ')
    field = OxmlElement('w:fldSimple')
    field.set(qn('w:instr'), 'PAGE')
    footer._p.append(field)
    doc.save(OUTPUT / '综合设计报告.docx')


if __name__ == '__main__':
    main()
