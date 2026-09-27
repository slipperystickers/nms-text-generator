import importlib.util
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('build_instructions',ROOT/'scripts/build_instructions.py')
guide=importlib.util.module_from_spec(spec);spec.loader.exec_module(guide)


class Document(HTMLParser):
    def __init__(self):
        super().__init__();self.ids=[];self.links=[];self.images=[];self.tags=[];self.stack=[]
    def handle_starttag(self,tag,attrs):
        values=dict(attrs);self.tags.append(tag)
        if tag not in ('meta','img','br','hr','input','link'):self.stack.append(tag)
        if 'id' in values:self.ids.append(values['id'])
        if tag=='a':self.links.append(values['href'])
        if tag=='img':self.images.append(values['src'])
    def handle_endtag(self,tag):
        assert self.stack and self.stack.pop()==tag,tag


class InstructionTests(unittest.TestCase):
    def test_offline_page_complete_and_linked(self):
        with tempfile.TemporaryDirectory() as folder:
            file=guide.build_page(Path(folder)/'guide.html','2.0.0')
            source=file.read_text(encoding='utf-8')
        doc=Document();doc.feed(source);doc.close()
        self.assertFalse(doc.stack)
        self.assertEqual(len(doc.ids),len(set(doc.ids)))
        self.assertEqual(doc.tags.count('h1'),1)
        self.assertNotIn('script',doc.tags);self.assertNotIn('iframe',doc.tags)
        self.assertTrue(all(src.startswith('data:image/png;base64,') for src in doc.images))
        for link in doc.links:
            if link.startswith('#'):self.assertIn(link[1:],doc.ids)
        self.assertIn('WELCOME&lt;br&gt;TRAVELLERS',source)
        self.assertIn('Storage Panels (back)',source)
        self.assertIn('Very old signs',source)
        self.assertIn('Install from Disk',source)
        self.assertNotIn('C:/Users/',source)
        self.assertNotIn('C:\\Users\\',source)
    def test_pipe_character_in_table_code(self):
        self.assertEqual(guide.cells('| A | `|` and `\\|` |'),['A','`|` and `\\|`'])


if __name__=='__main__':unittest.main()
