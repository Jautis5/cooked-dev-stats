"""Tie browser cache keys to the actual deployed JavaScript and CSS bytes."""
import hashlib, pathlib, re, sys


def version_assets(directory):
    directory=pathlib.Path(directory)
    index=directory/'index.html'
    html=index.read_text()
    for name in ['app.js','styles.css']:
        digest=hashlib.sha256((directory/name).read_bytes()).hexdigest()[:12]
        html=re.sub(r'(["\'])'+re.escape(name)+r'(?:\?[^"\']*)?(["\'])',
                    lambda match:match[1]+name+'?v='+digest+match[2],html)
    index.write_text(html)


if __name__=='__main__':version_assets(sys.argv[1])
