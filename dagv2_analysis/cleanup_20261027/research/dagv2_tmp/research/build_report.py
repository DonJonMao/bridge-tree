from pathlib import Path
import argparse
import re, json, html
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Flowable, KeepTogether
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT = Path('/Users/mao/projects/dagv2')
parser = argparse.ArgumentParser()
parser.add_argument('--source', default='docs/research/dagv2_rag_innovation_20261001.md')
parser.add_argument('--output', default='DAGv2_RAG_Research_and_Innovation_20261001.pdf')
parser.add_argument('--date', default='2026-10-01')
parser.add_argument('--qa-prefix', default='tmp/research')
args=parser.parse_args()
SOURCE = ROOT / args.source
OUTPUT = ROOT / args.output
pdfmetrics.registerFont(TTFont('CJK', '/Library/Fonts/Arial Unicode.ttf'))
pdfmetrics.registerFontFamily('CJK', normal='CJK', bold='CJK', italic='CJK', boldItalic='CJK')
NAVY = colors.HexColor('#16344b')
TEAL = colors.HexColor('#087f8c')
GRAY = colors.HexColor('#536675')
LIGHT = colors.HexColor('#edf4f7')
CONTENT_WIDTH = 595.28 - 52 * 2 - 12  # Platypus frame padding is 6 points on each side.
styles = {
 'title': ParagraphStyle('title', fontName='CJK', fontSize=25, leading=34, textColor=NAVY, spaceAfter=18, wordWrap='CJK'),
 'h1': ParagraphStyle('h1', fontName='CJK', fontSize=18, leading=25, textColor=NAVY, spaceAfter=14, wordWrap='CJK'),
 'h2': ParagraphStyle('h2', fontName='CJK', fontSize=12.2, leading=18, textColor=TEAL, spaceBefore=9, spaceAfter=7, wordWrap='CJK'),
 'body': ParagraphStyle('body', fontName='CJK', fontSize=10.2, leading=16.7, textColor=NAVY, spaceAfter=9, wordWrap='CJK'),
 'bullet': ParagraphStyle('bullet', fontName='CJK', fontSize=10.2, leading=16.7, textColor=NAVY, leftIndent=10, firstLineIndent=-10, spaceAfter=7, wordWrap='CJK'),
 'small': ParagraphStyle('small', fontName='CJK', fontSize=8.7, leading=13.6, textColor=GRAY, spaceAfter=7, wordWrap='CJK'),
 'cell': ParagraphStyle('cell', fontName='CJK', fontSize=9.1, leading=14.2, textColor=NAVY, wordWrap='CJK'),
 'thead': ParagraphStyle('thead', fontName='CJK', fontSize=9.1, leading=14.2, textColor=colors.white, wordWrap='CJK'),
 'code': ParagraphStyle('code', fontName='CJK', fontSize=8.5, leading=13, textColor=NAVY, backColor=LIGHT, borderPadding=10, spaceAfter=11, wordWrap='CJK'),
}

def markup(s):
 s=html.escape(s)
 s=re.sub(r'\*\*(.*?)\*\*',r'<font color="#087f8c">\1</font>',s)
 s=re.sub(r'`([^`]+)`',r'<font color="#425d6d">\1</font>',s)
 s=re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)',r'<link href="\2" color="#087f8c">\1</link>',s)
 # Reference URLs remain readable and clickable while avoiding long unbreakable lines.
 s=re.sub(r'(?<![="\w])(https?://[^\s<]+)',lambda m:'<link href="'+m[1]+'" color="#087f8c">'+m[1]+'</link>' if not m[1].endswith('&quot;') else m[1],s)
 return s

class FlowDiagram(Flowable):
 def __init__(self, labels):
  Flowable.__init__(self);self.labels=labels;self.width=CONTENT_WIDTH;self.height=len(labels)*42+9
 def draw(self):
  c=self.canv; x=12; w=self.width-24
  for i,label in enumerate(self.labels):
   y=self.height-(i+1)*42
   c.setFillColor(LIGHT if i%2==0 else colors.HexColor('#e1f0ef')); c.setStrokeColor(colors.HexColor('#bdd5de'))
   c.roundRect(x,y,w,31,5,fill=1,stroke=1)
   p=Paragraph(markup(label),styles['cell']);pw,ph=p.wrap(w-20,30);p.drawOn(c,x+10,y+(31-ph)/2)
   if i<len(self.labels)-1:
    c.setStrokeColor(TEAL);c.setFillColor(TEAL);c.line(x+w/2,y-2,x+w/2,y-9)
    path=c.beginPath();path.moveTo(x+w/2-3,y-6);path.lineTo(x+w/2,y-10);path.lineTo(x+w/2+3,y-6);c.drawPath(path,stroke=1)

def header(canvas, doc):
 canvas.saveState();w,h=doc.pagesize
 canvas.setStrokeColor(colors.HexColor('#d5e2e8'));canvas.line(51,h-42,w-51,h-42)
 canvas.setFont('CJK',8);canvas.setFillColor(GRAY)
 canvas.drawString(51,h-31,'DAG v2 | RAG 文献与创新路线')
 canvas.drawRightString(w-51,h-31,'2024-2026 / '+args.date)
 canvas.line(51,43,w-51,43);canvas.drawString(51,29,'代码事实、历史成绩与待验证假设分别标注')
 canvas.drawRightString(w-51,29,str(doc.page))
 canvas.restoreState()

def parse(md):
 story=[]; page_specs=[]
 for pi,chunk in enumerate(md.split('<!-- page -->')):
  if pi:story.append(PageBreak())
  lines=chunk.strip().splitlines();i=0;title=''
  while i<len(lines):
   s=lines[i].strip()
   if not s:i+=1;continue
   if s.startswith('# '):
    title=s[2:];story.append(Paragraph(markup(title),styles['title'] if pi==0 else styles['h1']));i+=1
   elif s.startswith('## '):story.append(Paragraph(markup(s[3:]),styles['h2']));i+=1
   elif s.startswith('> '):story.append(Paragraph(markup(s[2:]),styles['small']));i+=1
   elif s.startswith('- '):story.append(Paragraph('• '+markup(s[2:]),styles['bullet']));i+=1
   elif s.startswith(':::flow'):
    labels=[];i+=1
    while i<len(lines) and lines[i].strip()!=':::':labels.append(lines[i].strip());i+=1
    story.extend([FlowDiagram(labels),Spacer(1,8)]);i+=1
   elif s.startswith('```'):
    code=[];i+=1
    while i<len(lines) and not lines[i].startswith('```'):code.append(html.escape(lines[i]));i+=1
    story.append(Paragraph('<br/>'.join(code),styles['code']));i+=1
   elif s.startswith('|'):
    rows=[]
    while i<len(lines) and lines[i].strip().startswith('|'):
     cells=[x.strip() for x in lines[i].strip().strip('|').split('|')]
     if not all(re.match(r'^:?-+:?$',x) for x in cells):rows.append(cells)
     i+=1
    n=len(rows[0]); widths=([105,386] if n==2 else [90,175,226] if n==3 else [82,136,137,136] if n==4 else [99]*n)
    widths=[w * CONTENT_WIDTH / sum(widths) for w in widths]
    data=[[Paragraph(markup(x),styles['thead' if ri==0 else 'cell']) for x in row] for ri,row in enumerate(rows)]
    t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,LIGHT]),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,0),0.8,TEAL),('LINEBELOW',(0,1),(-1,-1),0.3,colors.HexColor('#d5e2e8'))]));story.extend([t,Spacer(1,10)])
   else:
    para=[s];i+=1
    while i<len(lines) and lines[i].strip() and not any(lines[i].strip().startswith(x) for x in ['#','|','- ','> ','```',':::']):para.append(lines[i].strip());i+=1
    story.append(Paragraph(markup(' '.join(para)),styles['body']))
  page_specs.append({'expected_page':pi+1,'title':title})
 return story,page_specs

md=SOURCE.read_text();story,specs=parse(md)
doc=SimpleDocTemplate(str(OUTPUT),pagesize=(595.28,841.89),leftMargin=52,rightMargin=52,topMargin=62,bottomMargin=59,title=specs[0]['title'],author='DAG v2 Research Review',subject='源码对照、2024-2026 文献、创新设计与实验方案')
doc.build(story,onFirstPage=header,onLaterPages=header)
qa_dir=ROOT/args.qa_prefix;qa_dir.mkdir(parents=True,exist_ok=True)
(qa_dir/'page_specs.json').write_text(json.dumps(specs,ensure_ascii=False,indent=2))
print(OUTPUT)
print('Expected pages:',len(specs))
