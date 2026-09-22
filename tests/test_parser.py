from pathlib import Path

from radparse.parser import parse_and_write


def test_read():
    path = Path("tests/10092026_FNA_ref_5mg.txt")
    parse_and_write(path, None)


if __name__ == "__main__":
    test_read()
