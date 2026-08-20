"""Synthetic pipeline test for render_note formatting paths (no Bear writes)."""
import re
import render_note as rn

md = """# Pipeline Test
- [ ] task one
- [x] task done
> a blockquote line

| Col A | Col B |
|-------|-------|
| x     | y     |

```python
def hello():
    return "hi"
```

**bold** and *italic* and `inline code` and ~~strike~~
https://example.com bare link
"""
body = rn.preprocess(md, {})
html = rn.markdown.markdown(
    body, extensions=["extra", "codehilite", "smarty"],
    extension_configs={"codehilite": {"guess_lang": False, "css_class": "highlight"}})
html = re.sub(r'<li><input type="checkbox"([^>]*)>',
              r'<li class="task"><input type="checkbox"\1>', html)

checks = {
    "task li": html.count('class="task"'),
    "checked box": html.count("checked"),
    "table": "<table>" in html,
    "code block hl": "highlight" in html,
    "blockquote": "<blockquote>" in html,
    "bold": "<strong>" in html,
    "italic": "<em>" in html,
    "inline code": html.count("<code>") >= 1,
    "strike": "<del>" in html,
    "bare url linkified": '<a href="https://example.com">' in html,
}
print(checks)
assert all(checks.values()), checks
print("ALL PASS")
