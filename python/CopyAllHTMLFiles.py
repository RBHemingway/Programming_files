import os
import re
import markdown

# Folder containing your .md files
folder = r"C:\Users\rober\OneDrive\AA-Roberts-Hobbies\Languages\Forth\zeptoforth-master\docs\words"

# Output HTML manual
output_file = r"C:\Users\rober\zeptoforth_manual.html"


def make_anchor(title):
    anchor = title.lower()
    anchor = re.sub(r"[^a-z0-9 -]", "", anchor)  # remove punctuation
    anchor = anchor.replace(" ", "-")
    return anchor


sections = []

# Collect sections: title, filename, HTML content
for filename in sorted(os.listdir(folder)):
    if filename.endswith(".md"):
        full_path = os.path.join(folder, filename)

        with open(full_path, "r", encoding="utf-8") as f:
            md_content = f.read()

        # Extract first heading as title
        title = None
        for line in md_content.splitlines():
            if line.startswith("#"):
                title = line.lstrip("# ").strip()
                break
        if not title:
            title = filename.replace(".md", "")

        html_content = markdown.markdown(md_content, extensions=["fenced_code", "tables"])
        sections.append((title, filename, html_content))


# Build HTML manual
with open(output_file, "w", encoding="utf-8") as out:
    out.write("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Zeptoforth Words Manual</title>
<style>
body { font-family: sans-serif; max-width: 900px; margin: 2rem auto; line-height: 1.5; }
code, pre { font-family: Consolas, monospace; }
pre { background: #f5f5f5; padding: 0.75rem; overflow-x: auto; }
h1, h2, h3 { margin-top: 2rem; }
hr { margin: 2rem 0; }
.toc ul { list-style: none; padding-left: 0; }
.toc li { margin: 0.25rem 0; }
.small { color: #666; font-size: 0.9em; }
</style>
</head>
<body>
<h1>Zeptoforth Words Manual</h1>
<p class="small">Generated automatically from local Markdown sources.</p>
<hr>
<h2>Table of Contents</h2>
<div class="toc">
<ul>
""")

    # TOC
    for title, filename, _ in sections:
        anchor = make_anchor(title)
        out.write(f'<li><a href="#{anchor}">{title}</a> <span class="small">({filename})</span></li>\n')

    out.write("</ul>\n</div>\n<hr>\n")

    # Sections
    for title, filename, html_content in sections:
        anchor = make_anchor(title)
        out.write(f'<h2 id="{anchor}">{title}</h2>\n')
        out.write(f'<p class="small">Source file: <code>{filename}</code></p>\n')
        out.write(html_content)
        out.write("<hr>\n")

    out.write("</body>\n</html>\n")

print("HTML manual created:", output_file)
