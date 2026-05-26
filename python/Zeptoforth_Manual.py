import os
import re

# Folder containing your .md files
folder = r"C:\Users\rober\OneDrive\AA-Roberts-Hobbies\Languages\Forth\zeptoforth-master\docs\words"

# Output manual (new file)
output_file = r"C:\Users\rober\zeptoforth_manual.md"


def make_anchor(title):
    """
    Convert a Markdown heading into a GitHub/VS Code compatible anchor.
    Rules:
    - lowercase
    - remove punctuation/symbols
    - spaces -> hyphens
    """
    anchor = title.lower()
    anchor = re.sub(r"[^a-z0-9 -]", "", anchor)  # remove punctuation
    anchor = anchor.replace(" ", "-")
    return anchor


sections = []

# First pass: read all files and extract titles + content
for filename in sorted(os.listdir(folder)):
    if filename.endswith(".md"):
        full_path = os.path.join(folder, filename)

        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Extract first Markdown heading as the section title
        title = None
        for line in content.splitlines():
            if line.startswith("#"):
                title = line.lstrip("# ").strip()
                break

        # Fallback: use filename if no heading found
        if not title:
            title = filename.replace(".md", "")

        sections.append((title, filename, content))


# Build the manual
with open(output_file, "w", encoding="utf-8") as out:

    # Title page
    out.write("# Zeptoforth Words Manual\n")
    out.write("Generated automatically from local Markdown sources.\n\n")
    out.write("---\n\n")

    # Table of contents
    out.write("## Table of Contents\n\n")
    for title, filename, _ in sections:
        anchor = make_anchor(title)
        out.write(f"- [{title}](#{anchor})\n")
    out.write("\n---\n\n")

    # Sections
    for title, filename, content in sections:
        anchor = make_anchor(title)
        out.write(f"\n\n## {title}\n")
        out.write(f"*Source file: `{filename}`*\n\n")
        out.write(content)
        out.write("\n\n---\n")

print("Manual created:", output_file)
