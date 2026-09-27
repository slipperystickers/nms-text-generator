"""Render the maintained Markdown guide as one offline HTML page; stdlib only."""
import base64
import html
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def slug(text):
    return re.sub(r'\s+','-',re.sub(r'[^a-z0-9 -]','',text.lower()).strip())


def inline(text):
    pattern=re.compile(r'`([^`]+)`|\*\*([^*]+)\*\*|\[([^\]]+)\]\(([^)]+)\)')
    out=[];pos=0
    for match in pattern.finditer(text):
        out.append(html.escape(text[pos:match.start()].replace('\\|','|')))
        code,bold,label,url=match.groups()
        if code is not None:out.append('<code>'+html.escape(code.replace('\\|','|'))+'</code>')
        elif bold is not None:out.append('<strong>'+html.escape(bold)+'</strong>')
        elif url.startswith(('#','https://')) or re.fullmatch(r'[\w.-]+(?:#[\w-]+)?',url):
            out.append('<a href="'+html.escape(url,quote=True)+'">'+html.escape(label)+'</a>')
        else:out.append(html.escape(label))
        pos=match.end()
    out.append(html.escape(text[pos:].replace('\\|','|')))
    return ''.join(out)


def cells(line):
    values=[];value='';code=False;escaped=False
    for char in line.strip().strip('|'):
        if char=='`' and not escaped:code=not code
        if char=='|' and not code and not escaped:values.append(value.strip());value=''
        else:value+=char
        escaped=(char=='\\' and not escaped)
    return values+[value.strip()]


def markdown(source):
    lines=source.splitlines();out=[];i=0
    while i<len(lines):
        line=lines[i]
        if not line.strip():i+=1;continue
        heading=re.match(r'^(#{1,6}) (.+)$',line)
        if heading:
            level=len(heading[1]);title=heading[2]
            out.append(f'<h{level} id="{slug(title)}">{inline(title)}</h{level}>');i+=1;continue
        if line.startswith('```'):
            block=[];i+=1
            while i<len(lines) and not lines[i].startswith('```'):block.append(lines[i]);i+=1
            out.append('<pre><code>'+html.escape('\n'.join(block))+'</code></pre>');i+=1;continue
        if line.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].startswith('|'):rows.append(cells(lines[i]));i+=1
            out.append('<div class="table-wrap"><table><thead><tr>'+''.join('<th scope="col">'+inline(c)+'</th>' for c in rows[0])+'</tr></thead><tbody>')
            for row in rows[2:]:out.append('<tr>'+''.join('<td>'+inline(c)+'</td>' for c in row)+'</tr>')
            out.append('</tbody></table></div>');continue
        match=re.match(r'^(?:([-*]) |(\d+)\. )(.+)$',line)
        if match:
            kind='ul' if match[1] else 'ol';out.append('<'+kind+'>')
            while i<len(lines):
                entry=re.match(r'^(?:[-*] |\d+\. )(.+)$',lines[i])
                if not entry:break
                text=[entry[1]];i+=1
                while i<len(lines) and lines[i].startswith('  '):text.append(lines[i].strip());i+=1
                out.append('<li>'+inline(' '.join(text))+'</li>')
            out.append('</'+kind+'>');continue
        paragraph=[line.strip()];i+=1
        while i<len(lines) and lines[i].strip() and not re.match(r'^(?:#|\||```|[-*] |\d+\. )',lines[i]):
            paragraph.append(lines[i].strip());i+=1
        out.append('<p>'+inline(' '.join(paragraph))+'</p>')
    return '\n'.join(out)


def build_page(destination,version):
    logo=base64.b64encode((ROOT/'nms_text_generator/previews/nmscribe_credit.png').read_bytes()).decode('ascii')
    body=markdown((ROOT/'USER_GUIDE.md').read_text(encoding='utf-8'))
    page='''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; base-uri 'none'">
<title>NMScribe __VERSION__ — Instructions</title>
<style>
:root{color-scheme:dark;--bg:#141820;--surface:#1d242d;--ink:#edf0f3;--muted:#bbc5d0;--line:#374351;--accent:#ffb054}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:24px}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.7 system-ui,-apple-system,"Segoe UI",sans-serif}
header,main,footer{max-width:1000px;margin:auto;padding:32px 44px}
header{padding-top:48px;border-bottom:1px solid var(--line)}.brand{max-width:420px;width:100%;height:auto;display:block;margin-bottom:24px}
.eyebrow{color:var(--accent);font-size:13px;letter-spacing:.14em;text-transform:uppercase;font-weight:700}
.quick{display:flex;flex-wrap:wrap;gap:12px;margin-top:22px}.quick a{background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:8px 16px;text-decoration:none}
h1,h2,h3{line-height:1.25;letter-spacing:-.02em}h1{font-size:30px;margin:10px 0 24px}h2{font-size:25px;border-top:1px solid var(--line);padding-top:30px;margin:44px 0 20px}h3{font-size:19px;color:var(--accent);margin:28px 0 14px}
p,li{color:var(--muted)}strong{color:var(--ink)}a{color:var(--accent);text-underline-offset:3px}a:hover{text-decoration:none;color:#ffd09a}a:focus-visible{outline:2px solid var(--accent);outline-offset:4px}
li{padding-left:4px;margin:9px 0}ul,ol{padding-left:26px}code{font: .92em/1.5 Consolas,monospace;color:#ffcf99;background:#252e38;border:1px solid var(--line);border-radius:4px;padding:1px 5px;overflow-wrap:anywhere}
pre{padding:18px;background:var(--surface);overflow:auto;border-radius:8px}pre code{border:0;padding:0}
#contents+ul{columns:2;column-gap:28px;font-size:15px}#contents+ul li{break-inside:avoid;margin:5px 0}
.table-wrap{overflow-x:auto;margin:22px 0;border:1px solid var(--line);border-radius:8px}table{width:100%;border-collapse:collapse;min-width:500px;font-size:15px}th{text-align:left;background:var(--surface);color:var(--accent)}th,td{padding:13px 16px;border-bottom:1px solid var(--line);vertical-align:top}td{color:var(--muted)}tr:last-child td{border-bottom:0}
footer{border-top:1px solid var(--line);font-size:14px;color:var(--muted);padding-bottom:48px}
@media(max-width:640px){header,main,footer{padding:24px 20px}h1{font-size:25px}h2{font-size:22px}#contents+ul{columns:1}.brand{max-width:360px}}
@media print{:root{color-scheme:light;--bg:white;--surface:#eee;--ink:#111;--muted:#222;--line:#ccc;--accent:#7b4200}body{font-size:11pt}header,main,footer{max-width:none;padding:12pt 0}.brand,.quick{display:none}h2,h3{break-after:avoid}table{min-width:0}tr{break-inside:avoid}a{color:#111}code{color:#111;background:#eee}h2{margin-top:24pt}.table-wrap{overflow:visible}}
</style></head><body>
<header id="top"><img class="brand" src="data:image/png;base64,__LOGO__" alt="NMScribe, by FuriousFurby(FF), 2026">
<div class="eyebrow">Launch guide · Version __VERSION__ · Blender Base Builder</div>
<nav class="quick" aria-label="Quick navigation"><a href="#install-and-find-the-panel">Install</a><a href="#your-first-sign">Make text</a><a href="#svg-icons-and-stickers">Make an SVG icon</a><a href="#troubleshooting">Troubleshooting</a></nav>
</header><main>__BODY__</main>
<footer>Offline instructions · No scripts, analytics, remote images or login required.<br>
<a href="#top">Back to top</a> · <a href="https://discord.gg/arbW3DvM5y">CCB / Traveller Toolkit</a></footer>
</body></html>'''
    destination.write_text(page.replace('__VERSION__',version).replace('__LOGO__',logo).replace('__BODY__',body),encoding='utf-8')
    return destination
