"""Build the four-slide submission PDF. Requires Pillow; no app runtime dependency."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/pdf/canopy-night-shift-demo.pdf'
OUT.parent.mkdir(parents=True, exist_ok=True)
W, H = 1920, 1080
BG = '#111315'; PANEL = '#1d2022'; LINE = '#383b3d'; TEXT = '#f5f1ed'
MUTED = '#b4b0aa'; ACCENT = '#e8a386'; GREEN = '#a9d6a2'
def available(*candidates):
    return next((p for p in candidates if Path(p).is_file()), None)

REG = available('/System/Library/Fonts/Supplemental/Arial.ttf',
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                'C:/Windows/Fonts/arial.ttf')
BOLD = available('/System/Library/Fonts/Supplemental/Arial Bold.ttf',
                 '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
                 'C:/Windows/Fonts/arialbd.ttf')
MONO = available('/System/Library/Fonts/Menlo.ttc',
                 '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',
                 'C:/Windows/Fonts/consola.ttf')

def font(size, bold=False, mono=False):
    path = MONO if mono else BOLD if bold else REG
    return ImageFont.truetype(path, size) if path else ImageFont.load_default(size=size)

def base(num, eyebrow, title, subtitle):
    im = Image.new('RGB', (W,H), BG); d = ImageDraw.Draw(im)
    d.text((90,55), 'canopy.', font=font(48,True), fill=TEXT)
    d.text((1650,67), 'NIGHT SHIFT / 2026', font=font(25,mono=True), fill=MUTED)
    d.line((90,125,1830,125), fill=LINE, width=2)
    d.text((90,166), eyebrow.upper(), font=font(24,mono=True), fill=ACCENT)
    d.text((90,210), title, font=font(66,True), fill=TEXT)
    d.text((90,305), subtitle, font=font(31), fill=MUTED)
    d.line((90,1000,1830,1000), fill=LINE, width=2)
    d.text((90,1022), 'canopy-sbs0.onrender.com', font=font(23,mono=True), fill=MUTED)
    d.text((1590,1022), f'{num:02d} / 04', font=font(23,mono=True), fill=ACCENT)
    return im,d

def card(d, box, heading, lines, color=ACCENT):
    d.rounded_rectangle(box, radius=22, fill=PANEL, outline=LINE, width=2)
    x,y,x2,y2=box
    d.text((x+34,y+35), heading, font=font(34,True), fill=color)
    yy=y+98
    for s in lines:
        d.text((x+34,yy), s, font=font(27), fill=TEXT); yy+=43

pages=[]
im,d=base(1,'Recurring policy decisions','Canopy makes a verdict inspectable','A reviewer can see the rule, the supplied facts, and the Mubit trace.')
d.rounded_rectangle((90,395,930,895),radius=24,fill=PANEL,outline=LINE,width=2)
d.text((140,452),'THE JOB',font=font(27,mono=True),fill=ACCENT)
d.text((140,517),'Policy + evidence + claim',font=font(43,True),fill=TEXT)
d.text((140,595),'A clear verdict, its reason, and',font=font(34),fill=TEXT)
d.text((140,646),'an exact supplied policy quote.',font=font(34),fill=TEXT)
d.text((140,748),'SUPPORTED   VIOLATES',font=font(30,mono=True),fill=GREEN)
d.text((140,798),'INSUFFICIENT',font=font(30,mono=True),fill=GREEN)
shot=Image.open(ROOT/'docs/demo/terminal.jpg').convert('RGB')
shot.thumbnail((810,500))
d.rounded_rectangle((990,395,1830,895),radius=24,fill=PANEL,outline=LINE,width=2)
im.paste(shot,(1005,445))
d.text((1020,855),'Earlier live fictional-case capture',font=font(23),fill=MUTED)
pages.append(im)

im,d=base(2,'Live example','The damaged-item exception wins','The built-in refund case is fictional and safe to show in public.')
card(d,(90,405,910,825),'SUPPLIED POLICY',['Damaged items: refund within 30 days,','even after use. Normal window: 14 days.','Evidence: 21 days, used, arrived damaged,','photos supplied.'])
card(d,(1010,405,1830,825),'CLAIM AND VERDICT',['Claim: refuse because used and late.','Canopy verdict: VIOLATES.','Reason: the damaged-item exception','covers the supplied facts.'],GREEN)
d.text((95,881),'A reviewer confirmed this correct verdict; the review is saved locally.',font=font(29),fill=ACCENT)
pages.append(im)

im,d=base(3,'Mubit integration','One traceable inference path','Extraction, verification, and chat use the Mubit OpenAI gateway.')
card(d,(90,420,490,760),'Browser',['Chat or verify','case'])
card(d,(560,420,960,760),'Canopy server',['Stable verify task','Session storage'])
card(d,(1030,420,1430,760),'Mubit gateway',['Recorded calls','mreq_ IDs'])
card(d,(1500,420,1830,760),'Provider',['Model reply'])
for x in (500,970,1440):
    d.line((x,585,x+50,585),fill=ACCENT,width=6)
    d.polygon([(x+50,585),(x+34,574),(x+34,596)],fill=ACCENT)
d.text((90,827),'Live verification response ID:',font=font(28),fill=MUTED)
d.text((90,871),'mreq_01a16ee996087620822b6764c56cf1dd',font=font(29,mono=True),fill=GREEN)
d.text((90,926),'A reviewer confirmation remained visible after browser reload.',font=font(27),fill=TEXT)
pages.append(im)

im,d=base(4,'Judging evidence','Learning status without invention','Mubit support accepts app routing plus a labelled Try models comparison.')
card(d,(90,400,910,855),'PROVEN NOW',['Live Mubit-routed verification','Request IDs and policy evidence','Review persists after browser reload','35 local tests; hosted CI passed'],GREEN)
card(d,(1010,400,1830,855),'OPEN LEARNING GATE',['Review remains local_only','Kept examples need console proof','Try models calls do not train','Compare only a Passed adapter'],ACCENT)
d.text((95,908),'If no adapter passes in time, show the current task status and say so.',font=font(26),fill=MUTED)
d.text((95,949),'Code: github.com/ShieldTech-Ltd/canopy',font=font(25,mono=True),fill=MUTED)
pages.append(im)

pages[0].save(OUT, 'PDF', resolution=144.0, save_all=True, append_images=pages[1:])
print(OUT)
