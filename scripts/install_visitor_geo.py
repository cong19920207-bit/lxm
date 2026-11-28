"""Install the pinned public ip2region release, for offline lookup at request time."""
import argparse
from hashlib import sha256
from pathlib import Path
import shutil
import tempfile
from urllib.request import urlopen

RELEASE = "v3.19.0"
FILES = {
    "ip2region_v4.xdb": "a12ad5aca1277d67e525efcda531a20cc0d654ff4f087150d45bc17fca4bc260",
    "ip2region_v6.xdb": "939f6b46bd2b8bec3cf7c5ceb8ba782266ae9b1f35b5ba7916700dec0b7506ed",
}


def install(destination):
    base = f"https://raw.githubusercontent.com/lionsoul2014/ip2region/{RELEASE}"
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination) as temp:
        stage = Path(temp)
        for name, expected in FILES.items():
            with urlopen(f"{base}/data/{name}", timeout=90) as response, (stage / name).open("wb") as out:
                shutil.copyfileobj(response, out)
            if sha256((stage / name).read_bytes()).hexdigest() != expected:
                raise ValueError(f"Unexpected {RELEASE} checksum for {name}")
        with urlopen(f"{base}/LICENSE.md", timeout=30) as response:
            (stage / "LICENSE.md").write_bytes(response.read())
        for file in stage.iterdir():
            file.replace(destination / file.name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path, nargs="?", default=Path("var/visitor-geo"))
    install(parser.parse_args().destination)
