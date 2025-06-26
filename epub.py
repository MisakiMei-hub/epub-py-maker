#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TXT文件和图片一键生成EPUB小说工具
支持自动章节分割、封面添加、图片插入等功能
自动处理当前目录下所有txt文件
修改版：将图片文件夹里除了封面以外的图片添加到标题页之后
新增：在标题和第一章之间添加强制分页
"""

import os
import re
import zipfile
import uuid
from datetime import datetime
from pathlib import Path
import mimetypes

class EpubGenerator:
    def __init__(self):
        self.book_id = str(uuid.uuid4())
        self.chapters = []
        self.images = []
        self.cover_image = None
        self.book_title = "未命名小说"
        self.author = "未知作者"
        self.language = "zh"
        
    def _sanitize_content(self, content):
        """清理内容，只处理HTML标签中的div，不影响文本内容"""
        content = re.sub(r'<div(\s[^>]*)?>', r'<section\1>', content)
        content = re.sub(r'</div>', '</section>', content)
        return content
    
    def _sanitize_title(self, title):
        """清理标题，移除所有HTML标签，只保留纯文本并用<text>包裹"""
        clean_title = re.sub(r'<[^>]+>', '', title)
        clean_title = clean_title.strip()
        return f'{clean_title}'
    
    def read_txt_file(self, txt_path, encoding='utf-8'):
        """读取txt文件并自动分割章节，第一行作为书名"""
        try:
            with open(txt_path, 'r', encoding=encoding) as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(txt_path, 'r', encoding='gbk') as f:
                content = f.read()
        
        lines = content.split('\n')
        if lines:
            self.book_title = lines[0].strip()
            content = '\n'.join(lines[1:])
        
        if not self.book_title or self.book_title == "未命名小说":
            book_name = Path(txt_path).stem
            if book_name:
                self.book_title = book_name
        
        chapter_patterns = [
            r'^第[一二三四五六七八九十百千万\d]+章',
            r'^Chapter\s*\d+',
            r'^\d+\..*$',
            r'^【.*】$'
        ]
        
        lines = content.split('\n')
        current_chapter = ""
        chapter_title = "前言"
        chapter_count = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                current_chapter += "\n"
                continue
                
            is_chapter_title = False
            for pattern in chapter_patterns:
                if re.match(pattern, line):
                    is_chapter_title = True
                    break
            
            if is_chapter_title:
                if current_chapter.strip():
                    self.chapters.append({
                        'title': chapter_title,
                        'content': current_chapter.strip()
                    })
                
                chapter_title = line
                current_chapter = ""
                chapter_count += 1
            else:
                current_chapter += line + "\n"
        
        if current_chapter.strip():
            self.chapters.append({
                'title': chapter_title,
                'content': current_chapter.strip()
            })
        
        if not self.chapters:
            self.chapters.append({
                'title': self.book_title,
                'content': content.strip()
            })
        
        print(f"成功读取文本文件，共检测到 {len(self.chapters)} 个章节")
    
    def add_images(self, image_folder):
        """添加图片文件夹中的所有图片"""
        if not os.path.exists(image_folder):
            print(f"图片文件夹不存在: {image_folder}")
            return
        
        supported_formats = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
        image_files = []
        
        for file in os.listdir(image_folder):
            if Path(file).suffix.lower() in supported_formats:
                image_files.append(file)
        
        image_files.sort()
        
        for img_file in image_files:
            img_path = os.path.join(image_folder, img_file)
            img_id = f"img_{len(self.images) + 1}"
            
            if 'cover' in img_file.lower() or '封面' in img_file.lower():
                self.cover_image = {
                    'id': 'cover',
                    'path': img_path,
                    'filename': img_file
                }
            else:
                self.images.append({
                    'id': img_id,
                    'path': img_path,
                    'filename': img_file
                })
        
        print(f"成功添加 {len(self.images)} 张图片" + 
              (f"，封面图片: {self.cover_image['filename']}" if self.cover_image else ""))
    
    def set_metadata(self, title=None, author=None, language='zh'):
        """设置书籍元数据"""
        if title:
            self.book_title = title
        if author:
            self.author = author
        self.language = language
    
    def generate_epub(self, output_path):
        """生成EPUB文件"""
        temp_dir = "temp_epub"
        os.makedirs(temp_dir, exist_ok=True)
        os.makedirs(f"{temp_dir}/META-INF", exist_ok=True)
        os.makedirs(f"{temp_dir}/OEBPS", exist_ok=True)
        os.makedirs(f"{temp_dir}/OEBPS/images", exist_ok=True)
        
        try:
            self._create_mimetype(temp_dir)
            self._create_container_xml(temp_dir)
            self._create_content_opf(temp_dir)
            self._create_toc_ncx(temp_dir)
            self._create_nav_xhtml(temp_dir)
            self._create_chapters_html(temp_dir)
            self._create_image_pages(temp_dir)  # 新增：创建图片页面
            self._copy_images(temp_dir)
            self._create_epub_zip(temp_dir, output_path)
            print(f"EPUB文件生成成功: {output_path}")
        finally:
            self._cleanup_temp(temp_dir)
    
    def _create_mimetype(self, temp_dir):
        with open(f"{temp_dir}/mimetype", 'w') as f:
            f.write("application/epub+zip")
    
    def _create_container_xml(self, temp_dir):
        container_content = '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
    </rootfiles>
</container>'''
        with open(f"{temp_dir}/META-INF/container.xml", 'w', encoding='utf-8') as f:
            f.write(container_content)
    
    def _create_content_opf(self, temp_dir):
        manifest_items = []
        spine_items = []
        
        # 添加封面和导航文档
        manifest_items.append('    <item id="cover" href="cover.xhtml" media-type="application/xhtml+xml"/>')
        manifest_items.append('    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>')
        spine_items.append('    <itemref idref="cover"/>')

        # 添加图片页面到spine中（在标题页之后）
        for i, img in enumerate(self.images):
            img_page_id = f"image_page_{i+1}"
            manifest_items.append(f'    <item id="{img_page_id}" href="image_page_{i+1}.xhtml" media-type="application/xhtml+xml"/>')
            spine_items.append(f'    <itemref idref="{img_page_id}"/>')

        # 添加章节
        for i, chapter in enumerate(self.chapters):
            chapter_id = f"chapter_{i+1}"
            manifest_items.append(f'    <item id="{chapter_id}" href="chapter_{i+1}.xhtml" media-type="application/xhtml+xml"/>')
            spine_items.append(f'    <itemref idref="{chapter_id}"/>')
        
        # 添加封面图片
        if self.cover_image:
            mime_type = mimetypes.guess_type(self.cover_image['path'])[0] or 'image/jpeg'
            manifest_items.append(f'    <item id="cover_img" href="images/{self.cover_image["filename"]}" media-type="{mime_type}"/>')
        
        # 添加其他图片
        for img in self.images:
            mime_type = mimetypes.guess_type(img['path'])[0] or 'image/jpeg'
            manifest_items.append(f'    <item id="{img["id"]}" href="images/{img["filename"]}" media-type="{mime_type}"/>')
        
        manifest_items.append('    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>')
        
        sanitized_title = self._sanitize_title(self.book_title)
        
        content_opf = f'''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="bookid" version="3.0">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
        <dc:title>{sanitized_title}</dc:title>
        <dc:creator>{self.author}</dc:creator>
        <dc:identifier id="bookid">{self.book_id}</dc:identifier>
        <dc:language>{self.language}</dc:language>
        <dc:date>{datetime.now().strftime('%Y-%m-%d')}</dc:date>
        {"<meta name='cover' content='cover_img'/>" if self.cover_image else ""}
    </metadata>
    <manifest>
{chr(10).join(manifest_items)}
    </manifest>
    <spine>
{chr(10).join(spine_items)}
    </spine>
</package>'''
        
        with open(f"{temp_dir}/OEBPS/content.opf", 'w', encoding='utf-8') as f:
            f.write(content_opf)

        # 创建封面页面（简化版，不包含封面图片）
        cover_html = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>{self.book_title}</title>
    <style type="text/css">
        body {{
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            padding: 0;
            text-align: center;
            font-family: serif;
        }}
        h1 {{
            font-size: 3em;
            color: #0066cc;
            margin: 0.5em 0;
            text-align: center;
            font-weight: bold;
        }}
        .author {{
            font-size: 1.2em;
            color: #666;
            margin-top: 1em;
        }}
        .book-info {{
            text-align: center;
            padding: 2em;
        }}
    </style>
</head>
<body>
    <main class="book-info">
        <h1>{self.book_title}</h1>
        <p class="author">{self.author}</p>
    </main>
</body>
</html>'''
        
        cover_html = self._sanitize_content(cover_html)
        
        with open(f"{temp_dir}/OEBPS/cover.xhtml", 'w', encoding='utf-8') as f:
            f.write(cover_html)
    
    def _create_toc_ncx(self, temp_dir):
        nav_points = []
        play_order = 1
        
        # 只添加章节到目录，不添加图片页面
        for i, chapter in enumerate(self.chapters):
            nav_points.append(f'''    <navPoint id="navpoint-{i+1}" playOrder="{play_order}">
        <navLabel>
            <text>{chapter["title"]}</text>
        </navLabel>
        <content src="chapter_{i+1}.xhtml"/>
    </navPoint>''')
            play_order += 1
        
        toc_ncx = f'''<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
    <head>
        <meta name="dtb:uid" content="{self.book_id}"/>
        <meta name="dtb:depth" content="1"/>
        <meta name="dtb:totalPageCount" content="0"/>
        <meta name="dtb:maxPageNumber" content="0"/>
    </head>
    <docTitle>
        <text>{self.book_title}</text>
    </docTitle>
    <navMap>
{chr(10).join(nav_points)}
    </navMap>
</ncx>'''
        
        with open(f"{temp_dir}/OEBPS/toc.ncx", 'w', encoding='utf-8') as f:
            f.write(toc_ncx)
    
    def _create_nav_xhtml(self, temp_dir):
        """创建EPUB3导航文档"""
        nav_items = []
        
        # 只添加章节到导航，不添加图片页面
        for i, chapter in enumerate(self.chapters):
            nav_items.append(f'        <li><a href="chapter_{i+1}.xhtml">{chapter["title"]}</a></li>')
        
        nav_xhtml = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
    <title>{self.book_title}</title>
    <meta charset="utf-8"/>
</head>
<body>
    <nav epub:type="toc" id="toc">
        <h1>目录</h1>
        <ol>
{chr(10).join(nav_items)}
        </ol>
    </nav>
</body>
</html>'''
        
        with open(f"{temp_dir}/OEBPS/nav.xhtml", 'w', encoding='utf-8') as f:
            f.write(nav_xhtml)
    
    def _create_image_pages(self, temp_dir):
        """创建独立的图片页面"""
        for i, img in enumerate(self.images):
            image_html = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>Image {i+1}</title>
    <style type="text/css">
        body {{
            margin: 0;
            padding: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            background-color: #ffffff;
        }}
        .image-container {{
            text-align: center;
            max-width: 100%;
            max-height: 100vh;
        }}
        .image-container img {{
            max-width: 100%;
            max-height: 100vh;
            height: auto;
            width: auto;
        }}
    </style>
</head>
<body>
    <section class="image-container">
        <img src="images/{img['filename']}" alt="Image"/>
    </section>
</body>
</html>'''
            
            image_html = self._sanitize_content(image_html)
            
            with open(f"{temp_dir}/OEBPS/image_page_{i+1}.xhtml", 'w', encoding='utf-8') as f:
                f.write(image_html)
    
    def _create_chapters_html(self, temp_dir):
        """创建章节HTML文件"""
        for i, chapter in enumerate(self.chapters):
            content_paragraphs = []
            for line in chapter['content'].split('\n'):
                line = line.strip()
                if line:
                    # 移除原有的图片插入逻辑，因为图片现在有独立页面
                    if line.startswith('[图片') or line.startswith('!['):
                        continue
                    content_paragraphs.append(f'<p>{line}</p>')
            
            # 判断是否为第一章，决定是否在章节标题前添加分页符
            page_break_before = ""
            if i == 0:  # 第一章
                page_break_before = "page-break-before: always;"
            
            chapter_html = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>{chapter["title"]}</title>
    <style type="text/css">
        body {{
            font-family: serif;
            line-height: 1.6;
            margin: 1em 2em;
        }}
        .book-title {{
            font-size: 2.5em;
            color: #0066cc;
            text-align: center;
            border-bottom: 2px solid #0066cc;
            padding-bottom: 0.5em;
            margin: 1.5em 0 2em 0;
            font-weight: bold;
        }}
        .chapter-title {{
            font-size: 2em;
            color: #0066cc;
            text-align: center;
            margin: 2em 0 1.5em 0;
            font-weight: bold;
            {page_break_before}
        }}
        h1 {{
            font-size: 2.5em;
            color: #0066cc;
            text-align: center;
            border-bottom: 2px solid #0066cc;
            padding-bottom: 0.5em;
            margin: 1.5em 0 2em 0;
            font-weight: bold;
        }}
        h2 {{
            font-size: 2em;
            color: #0066cc;
            text-align: center;
            margin: 2em 0 1.5em 0;
            font-weight: bold;
        }}
        p {{
            text-indent: 2em;
            margin: 0.8em 0;
            line-height: 1.8;
        }}
        section {{
            display: block;
            margin: 1em 0;
        }}
    </style>
</head>
<body>
    {f'<h1 class="book-title">{self.book_title}</h1>' if i == 0 else ''}
    <h1 class="chapter-title">{chapter["title"]}</h1>
    {chr(10).join(content_paragraphs)}
</body>
</html>'''
            
            chapter_html = self._sanitize_content(chapter_html)
            
            with open(f"{temp_dir}/OEBPS/chapter_{i+1}.xhtml", 'w', encoding='utf-8') as f:
                f.write(chapter_html)
    
    def _copy_images(self, temp_dir):
        if self.cover_image:
            import shutil
            shutil.copy2(self.cover_image['path'], f"{temp_dir}/OEBPS/images/{self.cover_image['filename']}")
        
        for img in self.images:
            import shutil
            shutil.copy2(img['path'], f"{temp_dir}/OEBPS/images/{img['filename']}")
    
    def _create_epub_zip(self, temp_dir, output_path):
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as epub_zip:
            epub_zip.write(f"{temp_dir}/mimetype", "mimetype", compress_type=zipfile.ZIP_STORED)
            
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    if file == 'mimetype':
                        continue
                    file_path = os.path.join(root, file)
                    arc_path = os.path.relpath(file_path, temp_dir)
                    epub_zip.write(file_path, arc_path)
    
    def _cleanup_temp(self, temp_dir):
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def process_all_txt_files():
    """处理当前目录下所有txt文件"""
    txt_files = [f for f in os.listdir() if f.lower().endswith('.txt')]
    
    if not txt_files:
        print("当前目录下没有找到任何txt文件")
        return
    
    print(f"找到 {len(txt_files)} 个txt文件:")
    for i, txt_file in enumerate(txt_files, 1):
        print(f"{i}. {txt_file}")
    
    print("\n开始处理...")
    
    for txt_file in txt_files:
        try:
            print(f"\n正在处理文件: {txt_file}")
            
            generator = EpubGenerator()
            generator.read_txt_file(txt_file)
            
            image_folder = os.path.splitext(txt_file)[0] + "_images"
            if os.path.exists(image_folder):
                print(f"找到对应的图片文件夹: {image_folder}")
                generator.add_images(image_folder)
            
            generator.set_metadata(
                title=None,
                author="Author：沉默的星",
                language='zh'
            )
            
            epub_file = os.path.splitext(txt_file)[0] + ".epub"
            generator.generate_epub(epub_file)
            print(f"成功生成: {epub_file}")
            
        except Exception as e:
            print(f"处理文件 {txt_file} 时出错: {str(e)}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    process_all_txt_files()