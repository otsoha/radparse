import logging
from collections.abc import Iterator
from dataclasses import dataclass
from itertools import zip_longest
from pathlib import Path

format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.DEBUG, format=format)
logger = logging.getLogger(__name__)


@dataclass
class Data:
    mdata: list[str]
    headers: list[str]
    data: list[list[str]]


def validate_count(data: Data, search_str: str) -> bool:
    # check that line count matches the expected number of data points
    mdata = data.mdata
    for line in mdata:
        if search_str in line:
            line = line.strip()
            line = line.split("\t")
            n_points = line[1]
            logger.debug(f"Expected number of data points: {n_points}")
            if len(data.data) != int(n_points):
                return False

    return True


def absparse(lstream: Iterator[str], metadata_lines: int) -> Data:
    """Parse a stream of lines and return the next header line."""
    metadata = []
    # read the metadata lines somewhere if we happen to need them
    for _ in range(metadata_lines):
        line = next(lstream, None)
        if line is None:
            raise ValueError("Not enough metadata lines in the stream")
        line = line.strip()
        metadata.append(str(line))
        logger.debug(f"Metadata line: {metadata[-1]}")

    # next line should be the header line
    headers_line = next(lstream, None)
    if headers_line is None or not headers_line.strip():
        raise ValueError("No header line found after metadata lines")
    headers = headers_line.strip().split("\t")
    logger.debug(f"Headers: {headers}")

    # Lets gooooo data time!!!
    data = []
    num_headers = len(headers)
    for line in lstream:
        line = line.strip()  # strip newline
        if not line:
            logger.debug("Section end reached (blank line)")
            break

        data_line = line.split("\t")
        if len(data_line) != num_headers:
            raise ValueError(
                f"Data line has {len(data_line)} columns, expected {num_headers}: {data_line}"
            )
        data.append(data_line)
    logger.debug(f"Parsed {len(data)} data lines")
    return Data(metadata, headers, data)


def line_is_header(line: str) -> bool:
    """Check if a line is a header."""
    return line.startswith("[") and line.endswith("]")


def parse_LCChromatogram(lstream: Iterator[str]) -> Data:
    logger.debug("Parsing LC Chromatogram")
    # pass to absparse
    data = absparse(lstream, metadata_lines=6)
    if not validate_count(data, "# of Points"):
        raise ValueError(
            "Data line count in AD1 does not match expected number of points"
        )

    return data


def parse_PDAMultiChromatogram(lstream: Iterator[str]) -> Data:
    logger.debug("Parsing PDA Multi Chromatogram")
    # pass to absparse
    data = absparse(lstream, metadata_lines=9)
    if not validate_count(data, "# of Points"):
        raise ValueError(
            "Data line count in LC1 does not match expected number of points"
        )

    return data


HANDLERS = {
    "[LC Chromatogram(AD1)]": parse_LCChromatogram,
    "[PDA Multi Chromatogram(Ch1)]": parse_PDAMultiChromatogram,
}


def main(data_path: Path) -> None:
    results: dict[str, Data] = {}

    # read csv data
    with open(data_path, "r") as f:
        lstream = iter(f)

        for line in lstream:
            line = line.strip()
            if not line:
                continue  # skip blank lines

            if line_is_header(line):
                logger.debug(f"Header found: {line}")
                handler = HANDLERS.get(line)
                if handler is None:
                    logger.debug(f"No handler for header: {line}")
                    continue
                # parse the header
                results[line] = handler(lstream)
            else:
                # we only care about headers.
                pass

    # for now, we want a hardcoded output: First, AD1 and then ch1. Write to a single output file in
    op_path = data_path.with_name(data_path.stem + "_parsed.txt")
    delim = "\t"
    with open(op_path, "w") as f:
        ad1_data = results.get("[LC Chromatogram(AD1)]")
        ch1_data = results.get("[PDA Multi Chromatogram(Ch1)]")
        if ad1_data is None:
            raise ValueError("No data found for header: [LC Chromatogram(AD1)]")
        if ch1_data is None:
            raise ValueError("No data found for header: [PDA Multi Chromatogram(Ch1)]")

        # create a single header line
        ad1_headers = ad1_data.headers
        ch1_headers = ch1_data.headers
        combined_headers = ad1_headers + ch1_headers

        # empty rows for padding if we run out
        ad1_empty = [""] * len(ad1_data.headers)
        ch1_empty = [""] * len(ch1_data.headers)

        with open(op_path, "w") as f:
            f.write(delim.join(combined_headers) + "\n")
            for row_ad1, row_ch1 in zip_longest(ad1_data.data, ch1_data.data):
                # Use padded empty list if one section ended earlier than the other
                if row_ad1 is None:
                    row_ad1 = ad1_empty
                if row_ch1 is None:
                    row_ch1 = ch1_empty
                r1 = [str(val) for val in row_ad1]
                r2 = [str(val) for val in row_ch1]

                combined_row = r1 + r2
                f.write(delim.join(combined_row) + "\n")
        logger.info(f"Parsed data written to {op_path}")
